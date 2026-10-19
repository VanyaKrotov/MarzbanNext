import os
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.models.associations import subscription_balancer_hosts_association
from app.models.settings import default_node_config


class System(Base):
    __tablename__ = "system"

    id = Column(Integer, primary_key=True)
    uplink = Column(BigInteger, default=0)
    downlink = Column(BigInteger, default=0)


class JWT(Base):
    __tablename__ = "jwt"

    id = Column(Integer, primary_key=True)
    secret_key = Column(
        String(64), nullable=False, default=lambda: os.urandom(32).hex()
    )


class TLS(Base):
    __tablename__ = "tls"

    id = Column(Integer, primary_key=True)
    key = Column(String(4096), nullable=False)
    certificate = Column(String(2048), nullable=False)


class RuntimeSettings(Base):
    __tablename__ = "runtime_settings"

    id = Column(Integer, primary_key=True)

    sub_profile_title = Column(String(256), nullable=False, default="Subscription", server_default="Subscription")
    sub_support_url = Column(String(2048), nullable=False, default="https://t.me/", server_default="https://t.me/")
    sub_update_interval = Column(String(32), nullable=False, default="12", server_default="12")
    external_config = Column(Text, nullable=False, default="")
    use_custom_json_default = Column(Boolean, nullable=False, default=False, server_default="0")
    use_custom_json_for_v2rayn = Column(Boolean, nullable=False, default=False, server_default="0")
    use_custom_json_for_v2rayng = Column(Boolean, nullable=False, default=False, server_default="0")
    use_custom_json_for_streisand = Column(Boolean, nullable=False, default=False, server_default="0")
    use_custom_json_for_happ = Column(Boolean, nullable=False, default=False, server_default="0")

    active_status_text = Column(String(128), nullable=False, default="Active", server_default="Active")
    expired_status_text = Column(String(128), nullable=False, default="Expired", server_default="Expired")
    limited_status_text = Column(String(128), nullable=False, default="Limited", server_default="Limited")
    disabled_status_text = Column(String(128), nullable=False, default="Disabled", server_default="Disabled")
    onhold_status_text = Column(String(128), nullable=False, default="On-Hold", server_default="On-Hold")

    notify_status_change = Column(Boolean, nullable=False, default=True, server_default="1")
    notify_user_created = Column(Boolean, nullable=False, default=True, server_default="1")
    notify_user_updated = Column(Boolean, nullable=False, default=True, server_default="1")
    notify_user_deleted = Column(Boolean, nullable=False, default=True, server_default="1")
    notify_user_data_used_reset = Column(Boolean, nullable=False, default=True, server_default="1")
    notify_user_sub_revoked = Column(Boolean, nullable=False, default=True, server_default="1")
    notify_if_data_usage_percent_reached = Column(Boolean, nullable=False, default=True, server_default="1")
    notify_if_days_left_reached = Column(Boolean, nullable=False, default=True, server_default="1")
    notify_login = Column(Boolean, nullable=False, default=True, server_default="1")
    notify_days_left = Column(JSON, nullable=False, default=lambda: [3])
    notify_reached_usage_percent = Column(JSON, nullable=False, default=lambda: [80])
    login_notify_white_list = Column(JSON, nullable=False, default=list)

    webhook_addresses = Column(JSON, nullable=False, default=list)
    webhook_secret = Column(String(2048), nullable=True, default=None)
    recurrent_notifications_timeout = Column(Integer, nullable=False, default=180, server_default="180")
    number_of_recurrent_notifications = Column(Integer, nullable=False, default=3, server_default="3")
    default_node_config = Column(JSON, nullable=False, default=default_node_config)

    clash_settings = Column(Text, nullable=False, default="")
    singbox_settings = Column(Text, nullable=False, default="")
    v2ray_settings = Column(Text, nullable=False, default="")
    mux = Column(Text, nullable=False, default="")
    user_agent = Column(Text, nullable=False, default="")
    grpc_user_agent = Column(Text, nullable=False, default="")

    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class SubscriptionBalancer(Base):
    __tablename__ = "subscription_balancers"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), unique=True, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    strategy = Column(String(32), nullable=False, default="least_ping", server_default="least_ping")
    probe_url = Column(String(2048), nullable=False)
    probe_interval = Column(Integer, nullable=False, default=300, server_default="300")
    position = Column(Integer, nullable=False, default=0, server_default="0", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    hosts = relationship(
        "ProxyHost",
        secondary=subscription_balancer_hosts_association,
        backref="subscription_balancers",
    )

    @property
    def host_ids(self) -> list[int]:
        return [host.id for host in self.hosts]
