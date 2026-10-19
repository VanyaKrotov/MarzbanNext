from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship

from app.db.base import Base


class SubscriptionTemplate(Base):
    __tablename__ = "subscription_templates"
    __table_args__ = (
        UniqueConstraint("format", "name", name="uq_subscription_template_name"),
        UniqueConstraint("format", "default_marker", name="uq_subscription_template_default"),
        CheckConstraint("default_marker IS NULL OR default_marker = 1", name="ck_subscription_template_default"),
        CheckConstraint(
            "format IN ('v2ray', 'v2ray-json', 'clash', 'sing-box', 'outline')",
            name="ck_subscription_template_format",
        ),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    format = Column(String(32), nullable=False)
    content = Column(Text().with_variant(LONGTEXT(), "mysql", "mariadb"), nullable=False)
    # NULL permits many non-default rows under the portable unique constraint above.
    default_marker = Column(SmallInteger, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_default(self) -> bool:
        return self.default_marker == 1


class HostSubscriptionTemplate(Base):
    __tablename__ = "host_subscription_templates"

    host_id = Column(Integer, ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True)
    format = Column(String(32), primary_key=True)
    template_id = Column(Integer, ForeignKey("subscription_templates.id",
                         ondelete="RESTRICT"), nullable=False, index=True)
    host = relationship("ProxyHost", back_populates="subscription_templates")
    template = relationship("SubscriptionTemplate")
