"""Use clash-meta for templates, host options and balancer settings.

Conflicting legacy client settings are rejected before any schema changes.
"""

from copy import deepcopy

from alembic import op
import sqlalchemy as sa

revision = "b57c20e91a46"
down_revision = "a319d48e7062"
branch_labels = None
depends_on = None

CHECK_NAME = "ck_subscription_template_format"
FORMATS = "'v2ray', 'v2ray-json', 'sing-box', 'outline'"


def _merge_options(values, host_id):
    result = {}
    for value in values:
        for key, item in value.items():
            if key in result and result[key] != item:
                raise RuntimeError(
                    f"Host {host_id}: conflicting Clash/Mihomo option {key}; resolve it before upgrading")
            result[key] = deepcopy(item)
    return result


def _rename_options(document, host_id, downgrade=False, duplicate=False):
    result = deepcopy(document or {})
    if downgrade:
        value = result.pop("clash-meta", None)
        if value is not None:
            result["mihomo"] = value
            if duplicate:
                result["clash"] = deepcopy(value)
        return result
    values = [result.pop(key) for key in ("clash", "mihomo", "clash-meta") if key in result]
    if values:
        # Mapper operations are ordered lists; they must agree if multiple aliases exist.
        if isinstance(values[0], list):
            if any(value != values[0] for value in values[1:]):
                raise RuntimeError(f"Host {host_id}: conflicting Clash/Mihomo mapper operations")
            result["clash-meta"] = values[0]
        else:
            result["clash-meta"] = _merge_options(values, host_id)
    return result


def _migrate(downgrade=False):
    connection = op.get_bind()
    hosts = sa.Table("hosts", sa.MetaData(), autoload_with=connection)
    prepared = []
    for row in connection.execute(hosts.select()).mappings():
        overrides = deepcopy(row["overrides"] or {})
        for key in ("clients", "mapper"):
            if key in overrides:
                overrides[key] = _rename_options(overrides[key], row["id"], downgrade)
        settings = deepcopy(row["balancer_settings"])
        if settings is not None:
            settings["clients"] = _rename_options(settings.get("clients", {}), row["id"], downgrade, duplicate=True)
        prepared.append((row["id"], overrides, settings))

    sqlite = connection.dialect.name == "sqlite"
    foreign_keys = sqlite and connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
    if foreign_keys:
        # SQLite must rebuild a referenced parent table when replacing its CHECK constraint.
        if not op.get_context().impl.transactional_ddl:
            connection.commit()
        with op.get_context().autocommit_block():
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        with op.batch_alter_table("subscription_templates") as batch:
            batch.drop_constraint(CHECK_NAME, type_="check")
            batch.create_check_constraint(CHECK_NAME, f"format IN ({FORMATS}, 'clash', 'clash-meta')")

        source, target = ("clash-meta", "clash") if downgrade else ("clash", "clash-meta")
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
            raise RuntimeError("Clash Meta migration found broken foreign-key references")
    finally:
        if foreign_keys:
            if not op.get_context().impl.transactional_ddl:
                connection.commit()
            with op.get_context().autocommit_block():
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade():
    _migrate()


def downgrade():
    _migrate(downgrade=True)
