from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.models.associations import (
    excluded_inbounds_association,
    host_group_hosts_association,
    node_certificate_inbounds_association,
    node_inbounds_association,
    node_outbounds_association,
)
from app.models.proxy import ProxyTypes


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

    id = Column(Integer, primary_key=True)
    remark = Column(String(256), nullable=False)
    address = Column(String(256), nullable=False)
    port = Column(Integer, nullable=True)
    inbound_id = Column(Integer, ForeignKey("inbounds.id"), nullable=False)
    inbound = relationship("ProxyInbound", back_populates="hosts")
    enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    position = Column(Integer, nullable=False, default=0, server_default="0", index=True)
    show_when_composed = Column(Boolean, nullable=False, default=True, server_default="1")
    overrides = Column(JSON, nullable=False, default=dict)
    balancer_settings = Column(JSON(none_as_null=True), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    groups = relationship("HostGroup", secondary=host_group_hosts_association, back_populates="hosts",
                          order_by="HostGroup.id")
    subscription_templates = relationship(
        "HostSubscriptionTemplate", back_populates="host", cascade="all, delete-orphan"
    )
    outgoing_links = relationship(
        "HostLink", foreign_keys="HostLink.owner_host_id", back_populates="owner",
        cascade="all, delete-orphan", order_by="HostLink.position",
    )
    incoming_links = relationship(
        "HostLink", foreign_keys="HostLink.member_host_id", back_populates="member",
        cascade="all, delete-orphan",
    )

    @property
    def subscription_template_ids(self) -> dict[str, int]:
        return {binding.format: binding.template_id for binding in self.subscription_templates}

    @property
    def inbound_tag(self):
        return self.inbound.tag

    @property
    def linked_host_ids(self) -> list[int]:
        return [link.member_host_id for link in self.outgoing_links]

    @property
    def member_of(self) -> list[dict]:
        return [{"id": link.owner_host_id, "remark": link.owner.remark} for link in self.incoming_links]


class HostLink(Base):
    __tablename__ = "host_links"
    __table_args__ = (
        CheckConstraint("owner_host_id != member_host_id", name="ck_host_link_no_self"),
        UniqueConstraint("owner_host_id", "position", name="uq_host_link_position"),
    )
    owner_host_id = Column(Integer, ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True)
    member_host_id = Column(Integer, ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True, index=True)
    position = Column(Integer, nullable=False)
    owner = relationship("ProxyHost", foreign_keys=[owner_host_id], back_populates="outgoing_links")
    member = relationship("ProxyHost", foreign_keys=[member_host_id], back_populates="incoming_links")


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
