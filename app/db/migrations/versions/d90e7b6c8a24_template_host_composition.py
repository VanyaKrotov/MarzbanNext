"""Move composition from hosts to templates, retaining a checked rollback archive."""

from datetime import datetime

from alembic import op
import sqlalchemy as sa

from app.db.migrations.template_composition_v1 import convert, encode_snapshot, read_snapshot

revision = "d90e7b6c8a24"
down_revision = "c82a6f0159bd"
branch_labels = None
depends_on = None

ARCHIVE = "host_composition_archive"


def _table(name):
    return sa.Table(name, sa.MetaData(), autoload_with=op.get_bind())


def upgrade():
    connection = op.get_bind()
    original = read_snapshot(connection)
    converted = convert(original)
    # Render every transformed template before destructive DDL or writing a single row.
    from app.models.subscription_template import SubscriptionFormat
    from app.utils.subscription_templates import validate_subscription_template

    before = {row["id"]: row["content"] for row in original["subscription_templates"]}
    for row in converted["subscription_templates"]:
        if before.get(row["id"]) != row["content"]:
            try:
                validate_subscription_template(SubscriptionFormat(row["format"]), row["content"],
                                               {"host_ids": [host["id"] for host in original["hosts"]]})
            except ValueError as exc:
                raise RuntimeError(f"Template {row['id']} cannot be migrated safely: {exc}") from exc
    op.create_table(ARCHIVE, sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("original", sa.JSON(), nullable=False), sa.Column("converted", sa.JSON(), nullable=False))
    archive = _table(ARCHIVE)
    connection.execute(archive.insert().values(id=1, original=encode_snapshot(original),
                                               converted=encode_snapshot(converted)))
    op.add_column("hosts", sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="0"))
    hosts = _table("hosts")
    existing = {row["id"] for row in original["hosts"]}
    for row in converted["subscription_templates"]:
        table = _table("subscription_templates")
        if row["id"] in before:
            connection.execute(table.update().where(table.c.id == row["id"]).values(content=row["content"]))
        else:
            connection.execute(table.insert().values(**row))
    for row in converted["hosts"]:
        if row["id"] in existing:
            connection.execute(hosts.update().where(hosts.c.id == row["id"]).values(is_hidden=row["is_hidden"]))
        else:
            connection.execute(hosts.insert().values(**row, show_when_composed=True))
    for name in ("host_subscription_templates", "host_group_hosts"):
        old = original[name]
        table = _table(name)
        for row in converted[name]:
            if row not in old:
                connection.execute(table.insert().values(**row))
    op.drop_table("host_links")
    op.drop_column("hosts", "show_when_composed")
    op.drop_column("hosts", "balancer_settings")


def downgrade():
    connection = op.get_bind()
    archive = connection.execute(_table(ARCHIVE).select()).mappings().one()
    original, expected = archive["original"], archive["converted"]
    current = encode_snapshot(read_snapshot(connection, tuple(expected)))
    # Restoring an archive must never overwrite edits made after upgrading.

    def normalized(snapshot):
        return {name: sorted(rows, key=lambda row: str(sorted(row.items()))) for name, rows in snapshot.items()}

    if normalized(current) != normalized(expected):
        raise RuntimeError("Composition data changed after upgrading; export it before restoring the migration archive")
    op.add_column("hosts", sa.Column("show_when_composed", sa.Boolean(), nullable=False, server_default="1"))
    op.add_column("hosts", sa.Column("balancer_settings", sa.JSON(), nullable=True))
    op.create_table("host_links",
                    sa.Column("owner_host_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"),
                              primary_key=True),
                    sa.Column("member_host_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"),
                              primary_key=True),
                    sa.Column("position", sa.Integer(), nullable=False),
                    sa.CheckConstraint("owner_host_id != member_host_id", name="ck_host_link_no_self"),
                    sa.UniqueConstraint("owner_host_id", "position", name="uq_host_link_position"))
    op.create_index("ix_host_links_member_host_id", "host_links", ["member_host_id"])
    for name in ("host_group_hosts", "host_subscription_templates", "host_links"):
        connection.execute(_table(name).delete())
    hosts = _table("hosts")
    original_ids = [row["id"] for row in original["hosts"]]
    connection.execute(hosts.delete().where(hosts.c.id.not_in(original_ids)))
    templates = _table("subscription_templates")
    connection.execute(templates.delete().where(templates.c.id.not_in(
        [row["id"] for row in original["subscription_templates"]])))
    for name in ("hosts", "subscription_templates"):
        table = _table(name)
        for row in original[name]:
            restored = dict(row)
            for key in ("created_at", "updated_at"):
                if key in restored:
                    restored[key] = datetime.fromisoformat(restored[key])
            connection.execute(table.update().where(table.c.id == row["id"]).values(**restored))
    for name in ("host_group_hosts", "host_subscription_templates", "host_links"):
        if original[name]:
            connection.execute(_table(name).insert(), original[name])
    op.drop_column("hosts", "is_hidden")
    op.drop_table(ARCHIVE)
