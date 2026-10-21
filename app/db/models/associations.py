from sqlalchemy import Column, ForeignKey, Integer, String, Table

from app.db.base import Base


excluded_inbounds_association = Table(
    "exclude_inbounds_association",
    Base.metadata,
    Column("proxy_id", ForeignKey("proxies.id")),
    Column("inbound_tag", ForeignKey("inbounds.tag")),
)

template_inbounds_association = Table(
    "template_inbounds_association",
    Base.metadata,
    Column("user_template_id", ForeignKey("user_templates.id")),
    Column("inbound_tag", ForeignKey("inbounds.tag")),
)

node_inbounds_association = Table(
    "node_inbounds_association",
    Base.metadata,
    Column("node_id", ForeignKey("nodes.id"), primary_key=True),
    Column("inbound_tag", ForeignKey("inbounds.tag"), primary_key=True),
)

node_outbounds_association = Table(
    "node_outbounds_association",
    Base.metadata,
    Column("node_id", ForeignKey("nodes.id"), primary_key=True),
    Column("outbound_tag", ForeignKey("outbounds.tag"), primary_key=True),
)

node_routing_rules_association = Table(
    "node_routing_rules_association",
    Base.metadata,
    Column("node_id", ForeignKey("nodes.id"), primary_key=True),
    Column("routing_rule_id", ForeignKey("routing_rules.id"), primary_key=True),
)

node_certificate_inbounds_association = Table(
    "node_certificate_inbounds_association",
    Base.metadata,
    Column("certificate_id", ForeignKey("node_certificates.id"), primary_key=True),
    Column("inbound_tag", ForeignKey("inbounds.tag"), primary_key=True),
)

host_group_hosts_association = Table(
    "host_group_hosts",
    Base.metadata,
    Column("host_id", Integer, ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", String(64), ForeignKey("host_groups.id", ondelete="CASCADE"), primary_key=True),
)
