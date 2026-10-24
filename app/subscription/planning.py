"""Permission-aware endpoint catalog and template recipients for each output format."""

from app.subscription.capabilities import COMMON_TEMPLATE_FORMATS, TARGET_FAMILIES, supports_connection
from app.subscription.contracts import ConnectionInput, ProfilePlan, SubscriptionError
from app.subscription.resolver import ConnectionResolver, ResolveContext


class TemplateSelector:
    def select(self, snapshot, host, family, template_id=None):
        if template_id is not None:
            selected = template_id
        elif family in COMMON_TEMPLATE_FORMATS:
            selected = snapshot.default_template_ids.get(family)
            if selected is None:
                raise SubscriptionError(f"Default subscription template is missing for {family}")
        else:
            selected = host.subscription_template_ids[family]
        template = snapshot.templates.get(selected)
        if template is None or template.format != family:
            raise SubscriptionError("Subscription template does not match the requested format")
        return template


class ConnectionCatalog:
    def resolve(self, snapshot, hosts, target, proxies, allowed_inbounds, context):
        resolved, diagnostics = {}, []
        for host in hosts:
            reason = self.exclusion_reason(snapshot, host, target, proxies, allowed_inbounds)
            if reason:
                diagnostics.append({"host_id": host.id, "reason": reason})
                continue
            inbound = snapshot.inbounds[host.inbound_id]
            credentials = proxies[inbound["protocol"]]
            if hasattr(credentials, "model_dump"):
                credentials = credentials.model_dump()
            resolved[host.id] = ConnectionResolver().resolve(
                ConnectionInput(host, inbound, snapshot.raw_inbounds[host.inbound_id], credentials), context,
            )
        return resolved, tuple(diagnostics)

    def exclusion_reason(self, snapshot, host, target, proxies, allowed_inbounds):
        if not host.enabled or host.inbound_id not in snapshot.inbounds:
            return "disabled_or_missing"
        if TARGET_FAMILIES[target] not in host.subscription_template_ids:
            return "format_disabled"
        inbound = snapshot.inbounds[host.inbound_id]
        protocol = inbound["protocol"]
        if not proxies.get(protocol) or host.inbound_tag not in allowed_inbounds.get(protocol, []):
            return "inbound_not_allowed"
        if not supports_connection(target, inbound):
            return "unsupported_connection"
        return None


class ProfilePlanner:
    def plan(self, snapshot, target, proxies, allowed_inbounds, context: ResolveContext,
             root_ids=None, groups=(), template_id=None):
        family = TARGET_FAMILIES[target]
        roots = [host for host in snapshot.hosts
                 if (root_ids is None or host.id in root_ids)
                 and (not groups or set(groups).intersection(host.group_ids))]
        # URI/Outline have no dependencies, so unrelated hosts must not affect their rendering.
        source_hosts = roots if target in {"v2ray", "outline"} else snapshot.hosts
        resolved, diagnostics = ConnectionCatalog().resolve(
            snapshot, source_hosts, target, proxies, allowed_inbounds, context)
        visible = [host for host in roots if host.id in resolved and not host.is_hidden]
        recipients = visible
        # Common templates can inject hidden sources without a visible recipient.
        if not recipients and target in {"clash", "sing-box"}:
            recipients = [host for host in roots if host.id in resolved][:1]
        sources, visible_ids = tuple(resolved.values()), tuple(host.id for host in visible)
        profiles = tuple(ProfilePlan(
            owner, (resolved[owner.id],), TemplateSelector().select(snapshot, owner, family, template_id),
            resolved[owner.id].remark, sources, snapshot.hosts, visible_ids,
        ) for owner in recipients)
        return profiles, diagnostics
