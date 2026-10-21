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
    is_hidden = Column(Boolean, nullable=False, default=False, server_default="0")
    overrides = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    groups = relationship("HostGroup", secondary=host_group_hosts_association, back_populates="hosts",
                          order_by="HostGroup.id")
    subscription_templates = relationship(
        "HostSubscriptionTemplate", back_populates="host", cascade="all, delete-orphan"
    )

    @property
    def subscription_template_ids(self) -> dict[str, int]:
        return {binding.format: binding.template_id for binding in self.subscription_templates}

    @property
    def inbound_tag(self):
        return self.inbound.tag


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
