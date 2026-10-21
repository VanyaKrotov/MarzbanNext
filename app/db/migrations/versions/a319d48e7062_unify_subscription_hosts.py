"""Unify host overrides and direct composition links.

Downgrade cannot represent arbitrary mapper, stream, client-specific or visibility
settings. Export a full backup before downgrading; the downgrade refuses such data.
SQLite 3.35+ is required for native column removal without rebuilding referenced hosts.
"""

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

from app.db.migrations.host_redesign_v1 import LEGACY_HOST_COLUMNS, preflight, read_legacy, transfer

revision = "a319d48e7062"
down_revision = "f6a82c1d5e90"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    report = preflight(connection)
    if report["errors"]:
        raise RuntimeError(f"Host migration preflight failed: {report['errors']}")
    _, rows = read_legacy(connection)
    sqlite = connection.dialect.name == "sqlite"
    if sqlite:
        version = connection.exec_driver_sql("select sqlite_version()").scalar()
        if tuple(map(int, version.split("."))) < (3, 35):
            raise RuntimeError("Host migration requires SQLite 3.35 or newer")
    op.add_column("hosts", sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"))
    op.add_column("hosts", sa.Column("show_when_composed", sa.Boolean(), nullable=False, server_default="1"))
    op.add_column("hosts", sa.Column("overrides", sa.JSON(), nullable=not sqlite,
                                     server_default=sa.text("'{}'") if sqlite else None))
    op.add_column("hosts", sa.Column("balancer_settings", sa.JSON(), nullable=True))
    date_default = sa.text(
        "'" + datetime.now(UTC).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S") + "'") if sqlite else None
    for name in ("created_at", "updated_at"):
        op.add_column("hosts", sa.Column(name, sa.DateTime(), nullable=not sqlite, server_default=date_default))
    # Snapshot old columns in memory before removing their NOT NULL constraints/default dependencies.
    for name in LEGACY_HOST_COLUMNS:
        op.drop_column("hosts", name)
    op.create_table(
        "host_links",
        sa.Column("owner_host_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("member_host_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("owner_host_id != member_host_id", name="ck_host_link_no_self"),
        sa.UniqueConstraint("owner_host_id", "position", name="uq_host_link_position"),
    )
    op.create_index("ix_host_links_member_host_id", "host_links", ["member_host_id"])
    transfer(connection, rows)
    if not sqlite:
        op.alter_column("hosts", "overrides", existing_type=sa.JSON(), nullable=False)
        for name in ("created_at", "updated_at"):
            op.alter_column("hosts", name, existing_type=sa.DateTime(), nullable=False)
    op.drop_table("subscription_balancer_hosts")
    op.drop_table("subscription_balancers")


def downgrade():
    connection = op.get_bind()
    metadata = sa.MetaData()
    hosts = sa.Table("hosts", metadata, autoload_with=connection)
    rows = [dict(row) for row in connection.execute(hosts.select()).mappings()]
    for row in rows:
        overrides = row["overrides"] or {}
        security = overrides.get("security", {})
        transport = overrides.get("transport", {})
        extra = transport.get("xhttp", {}).get("extra", {})
        unsupported = (
            set(overrides) - {"security", "transport", "mux", "fragment", "noise"}
            or set(security) - {"mode", "sni", "alpn", "fingerprint", "allow_insecure"}
            or set(transport) - {"path", "host", "random_user_agent", "use_sni_as_host", "xhttp"}
            or set(transport.get("xhttp", {})) - {"extra"}
            or set(extra) - {"scMaxBufferedPosts", "xPaddingObfsMode", "uplinkHTTPMethod"}
            or set(overrides.get("mux", {})) - {"enabled"}
            or ("path" in transport and transport["path"] == "")
            or ("alpn" in security and security["alpn"] == [])
            or security.get("allow_insecure") is False
            or row["balancer_settings"] is not None
            or not row["show_when_composed"]
        )
        if unsupported:
            raise RuntimeError("This host configuration requires backup restoration to downgrade without data loss")
    columns = {
        "path": sa.String(256), "sni": sa.String(1000), "host": sa.String(1000),
        "security": sa.String(32), "alpn": sa.String(64), "fingerprint": sa.String(32),
        "allowinsecure": sa.Boolean(), "is_disabled": sa.Boolean(), "mux_enable": sa.Boolean(),
        "fragment_setting": sa.String(100), "noise_setting": sa.String(2000),
        "random_user_agent": sa.Boolean(), "use_sni_as_host": sa.Boolean(),
        "sc_max_buffered_posts": sa.Integer(), "x_padding_obfs_mode": sa.Boolean(), "uplink_http_method": sa.String(32),
    }
    for name, column_type in columns.items():
        op.add_column("hosts", sa.Column(name, column_type, nullable=True))
    op.create_table("subscription_balancers", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(256), nullable=False, unique=True),
                    sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("strategy", sa.String(32)),
                    sa.Column("probe_url", sa.String(2048)), sa.Column("probe_interval", sa.Integer()),
                    sa.Column("position", sa.Integer()), sa.Column("created_at", sa.DateTime()),
                    sa.Column("updated_at", sa.DateTime()))
    op.create_index("ix_subscription_balancers_position", "subscription_balancers", ["position"])
    op.create_table("subscription_balancer_hosts",
                    sa.Column("balancer_id", sa.Integer(), sa.ForeignKey(
                        "subscription_balancers.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("host_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True))
    metadata = sa.MetaData()
    metadata.reflect(connection, only=["hosts", "host_links", "subscription_balancers", "subscription_balancer_hosts"])
    for row in rows:
        overrides = row["overrides"] or {}
        security, transport = overrides.get("security", {}), overrides.get("transport", {})
        extra = transport.get("xhttp", {}).get("extra", {})
        values = {"security": security.get("mode", "inbound_default"), "alpn": ",".join(security.get("alpn", [])) or "none",
                  "fingerprint": security.get("fingerprint", "none"), "allowinsecure": security.get("allow_insecure"),
                  "is_disabled": not row["enabled"], "mux_enable": overrides.get("mux", {}).get("enabled", False),
                  "fragment_setting": overrides.get("fragment"), "noise_setting": overrides.get("noise"),
                  "sc_max_buffered_posts": extra.get("scMaxBufferedPosts"), "x_padding_obfs_mode": extra.get("xPaddingObfsMode"),
                  "uplink_http_method": extra.get("uplinkHTTPMethod"), "sni": security.get("sni"),
                  "path": transport.get("path"), "host": transport.get("host"),
                  "random_user_agent": transport.get("random_user_agent", False),
                  "use_sni_as_host": transport.get("use_sni_as_host", False)}
        connection.execute(metadata.tables["hosts"].update().where(
            metadata.tables["hosts"].c.id == row["id"]).values(**values))
    op.drop_table("host_links")
    for name in ("overrides", "balancer_settings", "enabled", "show_when_composed", "created_at", "updated_at"):
        op.drop_column("hosts", name)
