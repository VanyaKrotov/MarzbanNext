from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.models.associations import (
    excluded_inbounds_association,
    host_group_hosts_association,
    node_certificate_inbounds_association,
    node_inbounds_association,
    node_outbounds_association,
)
from app.models.proxy import ProxyHostALPN, ProxyHostFingerprint, ProxyHostSecurity, ProxyTypes


class Proxy(Base):
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="proxies")
    type = Column(Enum(ProxyTypes), nullable=False)
    settings = Column(JSON, nullable=False)
    excluded_inbounds = relationship(
        "ProxyInbound", secondary=excluded_inbounds_association
    )


class ProxyInbound(Base):
    __tablename__ = "inbounds"

    id = Column(Integer, primary_key=True)
    tag = Column(String(256), unique=True, nullable=False, index=True)
    content = Column(JSON, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    readonly = Column(Boolean, nullable=False, default=False, server_default="0")
    hosts = relationship(
        "ProxyHost", back_populates="inbound", cascade="all, delete-orphan"
    )
    nodes = relationship(
        "Node", secondary=node_inbounds_association, back_populates="inbounds"
    )
    node_certificates = relationship(
        "NodeCertificate",
        secondary=node_certificate_inbounds_association,
        back_populates="inbounds",
    )


class ProxyOutbound(Base):
    __tablename__ = "outbounds"

    id = Column(Integer, primary_key=True)
    tag = Column(String(256), unique=True, nullable=False, index=True)
    content = Column(JSON, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    readonly = Column(Boolean, nullable=False, default=False, server_default="0")
    nodes = relationship(
        "Node", secondary=node_outbounds_association, back_populates="outbounds"
    )


class ProxyHost(Base):
    __tablename__ = "hosts"
    # __table_args__ = (
    #     UniqueConstraint('inbound_tag', 'remark'),
    # )

    id = Column(Integer, primary_key=True)
    remark = Column(String(256), unique=False, nullable=False)
    address = Column(String(256), unique=False, nullable=False)
    port = Column(Integer, nullable=True)
    path = Column(String(256), unique=False, nullable=True)
    sni = Column(String(1000), unique=False, nullable=True)
    host = Column(String(1000), unique=False, nullable=True)
    security = Column(
        Enum(ProxyHostSecurity),
        unique=False,
        nullable=False,
        default=ProxyHostSecurity.inbound_default,
    )
    alpn = Column(
        Enum(ProxyHostALPN),
        unique=False,
        nullable=False,
        default=ProxyHostSecurity.none,
        server_default=ProxyHostSecurity.none.name
    )
    fingerprint = Column(
        Enum(ProxyHostFingerprint),
        unique=False,
        nullable=False,
        default=ProxyHostSecurity.none,
        server_default=ProxyHostSecurity.none.name
    )

    inbound_id = Column(Integer, ForeignKey("inbounds.id"), nullable=False)
    inbound = relationship("ProxyInbound", back_populates="hosts")
    groups = relationship(
        "HostGroup",
        secondary=host_group_hosts_association,
        back_populates="hosts",
    )
    position = Column(Integer, nullable=False, default=0, server_default="0", index=True)
    allowinsecure = Column(Boolean, nullable=True)
    is_disabled = Column(Boolean, nullable=True, default=False)
    mux_enable = Column(Boolean, nullable=False, default=False, server_default='0')
    fragment_setting = Column(String(100), nullable=True)
    noise_setting = Column(String(2000), nullable=True)
    random_user_agent = Column(Boolean, nullable=False, default=False, server_default='0')
    use_sni_as_host = Column(Boolean, nullable=False, default=False, server_default="0")
    sc_max_buffered_posts = Column(Integer, nullable=True)
    x_padding_obfs_mode = Column(Boolean, nullable=True)
    uplink_http_method = Column(String(32), nullable=True)

    subscription_templates = relationship(
        "HostSubscriptionTemplate", back_populates="host", cascade="all, delete-orphan"
    )

    @property
    def subscription_template_ids(self) -> dict[str, int]:
        return {binding.format: binding.template_id for binding in self.subscription_templates}

    @property
    def inbound_tag(self):
        return self.inbound.tag if self.inbound else None


class HostGroup(Base):
    __tablename__ = "host_groups"

    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    tags = Column(JSON, nullable=False, default=list)
    hosts = relationship(
        "ProxyHost",
        secondary=host_group_hosts_association,
        back_populates="groups",
    )
