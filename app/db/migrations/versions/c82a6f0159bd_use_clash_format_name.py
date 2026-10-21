"""Use clash as the single YAML format name.

Only stored data is renamed; runtime aliases are not introduced.
"""

from copy import deepcopy

from alembic import op
import sqlalchemy as sa

revision = "c82a6f0159bd"
down_revision = "b57c20e91a46"
branch_labels = None
depends_on = None

CHECK_NAME = "ck_subscription_template_format"
FORMATS = "'v2ray', 'v2ray-json', 'sing-box', 'outline'"


def _rename_key(document, source, target, host_id):
    result = deepcopy(document)
    if source in result:
        value = result.pop(source)
        if target in result and result[target] != value:
            raise RuntimeError(f"Host {host_id}: conflicting {source}/{target} settings; resolve before upgrading")
        result[target] = value
    return result


def _migrate(source, target):
    connection = op.get_bind()
    hosts = sa.Table("hosts", sa.MetaData(), autoload_with=connection)
    prepared = []
    for row in connection.execute(hosts.select()).mappings():
        overrides = deepcopy(row["overrides"] or {})
        for key in ("clients", "mapper"):
            if key in overrides:
                overrides[key] = _rename_key(overrides[key], source, target, row["id"])
        settings = deepcopy(row["balancer_settings"])
        if settings is not None:
            settings["clients"] = _rename_key(settings.get("clients", {}), source, target, row["id"])
        prepared.append((row["id"], overrides, settings))

    sqlite = connection.dialect.name == "sqlite"
    foreign_keys = sqlite and connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
    if foreign_keys:
        # SQLite rebuilds the referenced template table when replacing its CHECK constraint.
        if not op.get_context().impl.transactional_ddl:
            connection.commit()
        with op.get_context().autocommit_block():
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("subscription_templates") as batch:
            batch.drop_constraint(CHECK_NAME, type_="check")
            batch.create_check_constraint(CHECK_NAME, f"format IN ({FORMATS}, '{source}', '{target}')")

        for name in ("subscription_templates", "host_subscription_templates"):
            table = sa.table(name, sa.column("format", sa.String()))
            connection.execute(table.update().where(table.c.format == source).values(format=target))
        for host_id, overrides, settings in prepared:
            connection.execute(hosts.update().where(hosts.c.id == host_id).values(
                overrides=overrides, balancer_settings=sa.null() if settings is None else settings))

        with op.batch_alter_table("subscription_templates") as batch:
            batch.drop_constraint(CHECK_NAME, type_="check")
            batch.create_check_constraint(CHECK_NAME, f"format IN ({FORMATS}, '{target}')")
        if sqlite and connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone():
            raise RuntimeError("Clash format migration found broken foreign-key references")
    finally:
        if foreign_keys:
            if not op.get_context().impl.transactional_ddl:
                connection.commit()
            with op.get_context().autocommit_block():
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade():
    _migrate("clash-meta", "clash")


def downgrade():
    _migrate("clash", "clash-meta")
