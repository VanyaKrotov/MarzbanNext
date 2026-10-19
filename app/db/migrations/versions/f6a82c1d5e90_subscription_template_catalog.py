"""Promote full subscription templates and snapshot per-format host assignments.

Downgrade retains the active defaults and generator settings. Additional catalog
entries and per-host assignments cannot be represented by the legacy schema;
export a database backup before downgrading if they need to be retained.
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

from app.utils.subscription_template_defaults import read_template_source
from config import (
    CLASH_SETTINGS_TEMPLATE,
    CLASH_SUBSCRIPTION_TEMPLATE,
    GRPC_USER_AGENT_TEMPLATE,
    MUX_TEMPLATE,
    SINGBOX_SETTINGS_TEMPLATE,
    SINGBOX_SUBSCRIPTION_TEMPLATE,
    USER_AGENT_TEMPLATE,
    V2RAY_SETTINGS_TEMPLATE,
    V2RAY_SUBSCRIPTION_TEMPLATE,
)

# Keep the imported catalog fixed even when later releases add formats.
FULL_TEMPLATE_SOURCES = {
    "clash": ("clash_subscription", CLASH_SUBSCRIPTION_TEMPLATE),
    "sing-box": ("singbox_subscription", SINGBOX_SUBSCRIPTION_TEMPLATE),
    "v2ray-json": ("v2ray_subscription", V2RAY_SUBSCRIPTION_TEMPLATE),
}
GENERATOR_TEMPLATE_SOURCES = {
    "clash_settings": CLASH_SETTINGS_TEMPLATE,
    "singbox_settings": SINGBOX_SETTINGS_TEMPLATE,
    "v2ray_settings": V2RAY_SETTINGS_TEMPLATE,
    "mux": MUX_TEMPLATE,
    "user_agent": USER_AGENT_TEMPLATE,
    "grpc_user_agent": GRPC_USER_AGENT_TEMPLATE,
}
WRAPPER_TEMPLATES = {
    "v2ray": "{{ links | join('\\n') }}",
    "outline": "{{ config | tojson }}",
}


revision = "f6a82c1d5e90"
down_revision = "e2f7a3c9b4d1"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    metadata = sa.MetaData()
    legacy = sa.Table("subscription_templates", metadata, autoload_with=connection)
    old = {row["key"]: dict(row) for row in connection.execute(sa.select(legacy)).mappings()}
    contents = {
        format: old[key]["content"] if key in old else read_template_source(path)
        for format, (key, path) in FULL_TEMPLATE_SOURCES.items()
    }
    fragments = {
        key: old[key]["content"] if key in old else read_template_source(path)
        for key, path in GENERATOR_TEMPLATE_SOURCES.items()
    }
    with op.batch_alter_table("runtime_settings") as batch:
        for key in fragments:
            batch.add_column(sa.Column(key, sa.Text(), nullable=True))
    settings = sa.Table("runtime_settings", sa.MetaData(), autoload_with=connection)
    connection.execute(settings.update().values(**fragments))
    # Stage TEXT backfills without server defaults, which older MySQL versions reject.
    with op.batch_alter_table("runtime_settings") as batch:
        for key in fragments:
            batch.alter_column(key, existing_type=sa.Text(), nullable=False)

    op.drop_table("subscription_templates")
    op.create_table(
        "subscription_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("format", sa.String(32), nullable=False),
        sa.Column("content", sa.Text().with_variant(LONGTEXT(), "mysql", "mariadb"), nullable=False),
        sa.Column("default_marker", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("format", "name", name="uq_subscription_template_name"),
        sa.UniqueConstraint("format", "default_marker", name="uq_subscription_template_default"),
        sa.CheckConstraint("default_marker IS NULL OR default_marker = 1", name="ck_subscription_template_default"),
        sa.CheckConstraint(
            "format IN ('v2ray', 'v2ray-json', 'clash', 'sing-box', 'outline')",
            name="ck_subscription_template_format",
        ),
    )
    templates = sa.Table("subscription_templates", sa.MetaData(), autoload_with=connection)
    now = datetime.utcnow()
    for format, content in {**contents, **WRAPPER_TEMPLATES}.items():
        legacy_key = FULL_TEMPLATE_SOURCES.get(format, (None,))[0]
        connection.execute(templates.insert().values(
            name="default", format=format, content=content, default_marker=1,
            created_at=now, updated_at=old.get(legacy_key, {}).get("updated_at") or now,
        ))
    op.create_table(
        "host_subscription_templates",
        sa.Column("host_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("format", sa.String(32), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("subscription_templates.id", ondelete="RESTRICT"),
                  nullable=False),
    )
    op.create_index("ix_host_subscription_templates_template_id", "host_subscription_templates", ["template_id"])
    bindings = sa.Table("host_subscription_templates", sa.MetaData(), autoload_with=connection)
    hosts = sa.Table("hosts", sa.MetaData(), autoload_with=connection)
    connection.execute(bindings.insert().from_select(
        ["host_id", "format", "template_id"],
        sa.select(hosts.c.id, templates.c.format, templates.c.id).select_from(hosts.join(templates, sa.true())),
    ))


def downgrade():
    connection = op.get_bind()
    templates = sa.Table("subscription_templates", sa.MetaData(), autoload_with=connection)
    defaults = {
        row["format"]: dict(row)
        for row in connection.execute(sa.select(templates).where(templates.c.default_marker == 1)).mappings()
    }
    settings = sa.Table("runtime_settings", sa.MetaData(), autoload_with=connection)
    runtime = connection.execute(sa.select(settings)).mappings().first()
    op.drop_table("host_subscription_templates")
    op.drop_table("subscription_templates")
    op.create_table(
        "subscription_templates",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("content", sa.Text().with_variant(LONGTEXT(), "mysql", "mariadb"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    legacy = sa.Table("subscription_templates", sa.MetaData(), autoload_with=connection)
    now = datetime.utcnow()
    for format, (key, path) in FULL_TEMPLATE_SOURCES.items():
        record = defaults.get(format)
        connection.execute(legacy.insert().values(
            key=key, format="yaml" if format == "clash" else "json",
            content=record["content"] if record else read_template_source(path),
            updated_at=record["updated_at"] if record else now,
        ))
    for key, path in GENERATOR_TEMPLATE_SOURCES.items():
        connection.execute(legacy.insert().values(
            key=key, format="yaml" if key == "clash_settings" else "json",
            content=runtime[key] if runtime else read_template_source(path), updated_at=now,
        ))
    with op.batch_alter_table("runtime_settings") as batch:
        for key in GENERATOR_TEMPLATE_SOURCES:
            batch.drop_column(key)
