# Import all SQLAlchemy models so Base.metadata is complete for runtime and Alembic.
from app.db.models.associations import (  # noqa: F401
    excluded_inbounds_association,
    host_group_hosts_association,
    node_certificate_inbounds_association,
    node_inbounds_association,
    node_outbounds_association,
    node_routing_rules_association,
    template_inbounds_association,
)
from app.db.models.admins import Admin, AdminUsageLogs  # noqa: F401
from app.db.models.users import NextPlan, User, UserTemplate, UserUsageResetLogs  # noqa: F401
from app.db.models.proxies import HostGroup, HostLink, Proxy, ProxyHost, ProxyInbound, ProxyOutbound  # noqa: F401
from app.db.models.routing import RoutingRule  # noqa: F401
from app.db.models.settings import JWT, RuntimeSettings, System, TLS  # noqa: F401
from app.db.models.nodes import Node  # noqa: F401
from app.db.models.node_certificates import NodeCertificate  # noqa: F401
from app.db.models.node_geo_resources import NodeGeoResourceUpdate  # noqa: F401
from app.db.models.usages import NodeUsage, NodeUserUsage  # noqa: F401
from app.db.models.notifications import NotificationReminder  # noqa: F401

from app.db.models.subscription_templates import HostSubscriptionTemplate, SubscriptionTemplate  # noqa: F401
