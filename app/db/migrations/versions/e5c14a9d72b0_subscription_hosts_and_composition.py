"""Convert master hosts and balancers directly to template composition.

SQLite 3.35+ is required to remove columns without rebuilding referenced hosts.
Downgrade restores the master snapshot only if migrated data has not been edited.
"""

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

from app.db.migrations.host_redesign_v1 import LEGACY_HOST_COLUMNS
from app.db.migrations.template_composition_v1 import (
    encode_snapshot, prepare, read_snapshot,
)

revision = "e5c14a9d72b0"
down_revision = "f6a82c1d5e90"
branch_labels = None
depends_on = None

ARCHIVE = "host_composition_archive"
NEW_COLUMNS = ("enabled", "is_hidden", "overrides", "created_at", "updated_at")


def _table(name):
    return sa.Table(name, sa.MetaData(), autoload_with=op.get_bind())


def _write_rows(connection, table_name, original_rows, converted_rows):
    table = _table(table_name)
    existing_ids = {row["id"] for row in original_rows}
    for row in converted_rows:
        statement = table.update().where(table.c.id == row["id"]) if row["id"] in existing_ids else table.insert()
        connection.execute(statement.values(**row))


def _insert_new_links(connection, table_name, original_rows, converted_rows):
    table = _table(table_name)
    keys = tuple(table.primary_key.columns.keys())
    existing = {tuple(row[key] for key in keys) for row in original_rows}
    additions = [row for row in converted_rows if tuple(row[key] for key in keys) not in existing]
    if additions:
        connection.execute(table.insert(), additions)


def upgrade():
    connection = op.get_bind()
    original, converted, report = prepare(connection)
    if report["errors"]:
        raise RuntimeError(f"Host migration preflight failed: {report['errors']}")
    sqlite = connection.dialect.name == "sqlite"
    if sqlite:
        version = connection.exec_driver_sql("select sqlite_version()").scalar()
        if tuple(map(int, version.split("."))) < (3, 35):
            raise RuntimeError("Host migration requires SQLite 3.35 or newer")

    # No destructive DDL runs until every source row and transformed template is checked.
    op.create_table(ARCHIVE, sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("original", sa.JSON(), nullable=False), sa.Column("converted", sa.JSON(), nullable=False))
    connection.execute(_table(ARCHIVE).insert().values(
        id=1, original=encode_snapshot(original), converted=encode_snapshot(converted)))
    op.add_column("hosts", sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"))
    op.add_column("hosts", sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("hosts", sa.Column("overrides", sa.JSON(), nullable=not sqlite,
                                     server_default=sa.text("'{}'") if sqlite else None))
    date_default = sa.text("'" + datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S") + "'") if sqlite else None
    for name in ("created_at", "updated_at"):
        op.add_column("hosts", sa.Column(name, sa.DateTime(), nullable=not sqlite, server_default=date_default))
    for name in LEGACY_HOST_COLUMNS:
        op.drop_column("hosts", name)

    op.add_column("subscription_templates", sa.Column("migration_settings", sa.JSON(), nullable=True))
    for name in ("hosts", "subscription_templates"):
        _write_rows(connection, name, original[name], converted[name])
    for name in ("host_subscription_templates", "host_group_hosts"):
        _insert_new_links(connection, name, original[name], converted[name])
    if not sqlite:
        required_columns = (("overrides", sa.JSON()), ("created_at", sa.DateTime()), ("updated_at", sa.DateTime()))
        for name, column_type in required_columns:
            op.alter_column("hosts", name, existing_type=column_type, nullable=False)
    op.drop_table("subscription_balancer_hosts")
    op.drop_table("subscription_balancers")


def _restore_legacy_schema():
    columns = {
        "path": sa.String(256), "sni": sa.String(1000), "host": sa.String(1000),
        "allowinsecure": sa.Boolean(), "is_disabled": sa.Boolean(),
        "fragment_setting": sa.String(100), "noise_setting": sa.String(2000),
        "sc_max_buffered_posts": sa.Integer(), "x_padding_obfs_mode": sa.Boolean(),
        "uplink_http_method": sa.String(32),
    }
    for name, column_type in columns.items():
        op.add_column("hosts", sa.Column(name, column_type, nullable=True))
    for name in ("mux_enable", "random_user_agent", "use_sni_as_host"):
        op.add_column("hosts", sa.Column(name, sa.Boolean(), nullable=False, server_default="0"))
    enums = {
        "security": ("proxyhostsecurity", ("inbound_default", "none", "tls"), "inbound_default"),
        "alpn": ("alpn", ("h3", "h3,h2", "h3,h2,http/1.1", "none", "h2", "http/1.1", "h2,http/1.1"), "none"),
        "fingerprint": ("proxyhostfingerprint", ("none", "chrome", "firefox", "safari", "ios", "android", "edge",
                                                 "360", "qq", "random", "randomized"), "none"),
    }
    for name, (enum_name, values, default) in enums.items():
        column_type = sa.Enum(*values, name=enum_name)
        column_type.create(op.get_bind(), checkfirst=True)
        op.add_column("hosts", sa.Column(name, column_type, nullable=False, server_default=default))
    op.create_table("subscription_balancers",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(256), nullable=False, unique=True),
                    sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
                    sa.Column("strategy", sa.String(32), nullable=False, server_default="least_ping"),
                    sa.Column("probe_url", sa.String(2048), nullable=False),
                    sa.Column("probe_interval", sa.Integer(), nullable=False, server_default="300"),
                    sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
                    sa.Column("created_at", sa.DateTime(), nullable=False),
                    sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_subscription_balancers_position", "subscription_balancers", ["position"])
    op.create_table("subscription_balancer_hosts",
                    sa.Column("balancer_id", sa.Integer(), sa.ForeignKey(
                        "subscription_balancers.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("host_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True))


def downgrade():
    connection = op.get_bind()
    archive = connection.execute(_table(ARCHIVE).select()).mappings().one()
    original, expected = archive["original"], archive["converted"]
    current = encode_snapshot(read_snapshot(connection, (*expected, "inbounds")))
    expected = dict(expected, inbounds=original["inbounds"])

    def normalized(snapshot):
        return {name: sorted(rows, key=lambda row: str(sorted(row.items()))) for name, rows in snapshot.items()}

    # Include inbound edits: restoring old XHTTP overrides against changed defaults is unsafe.
    if normalized(current) != normalized(expected):
        raise RuntimeError("Composition data changed after upgrading; export it before restoring the migration archive")
    _restore_legacy_schema()
    for name in ("host_group_hosts", "host_subscription_templates"):
        connection.execute(_table(name).delete())
    hosts, templates = _table("hosts"), _table("subscription_templates")
    connection.execute(hosts.delete().where(hosts.c.id.not_in([row["id"] for row in original["hosts"]])))
    connection.execute(templates.delete().where(templates.c.id.not_in(
        [row["id"] for row in original["subscription_templates"]])))
    for name in ("hosts", "subscription_templates", "subscription_balancers"):
        table = _table(name)
        for row in original[name]:
            restored = dict(row)
            for key in ("created_at", "updated_at"):
                if key in restored:
                    restored[key] = datetime.fromisoformat(restored[key])
            statement = table.insert() if name == "subscription_balancers" else table.update().where(
                table.c.id == row["id"])
            connection.execute(statement.values(**restored))
    for name in ("host_group_hosts", "host_subscription_templates", "subscription_balancer_hosts"):
        if original[name]:
            connection.execute(_table(name).insert(), original[name])
    for name in NEW_COLUMNS:
        op.drop_column("hosts", name)
    op.drop_column("subscription_templates", "migration_settings")
    op.drop_table(ARCHIVE)
