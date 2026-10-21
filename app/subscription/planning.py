"""Flat profile planning, permission checks, template selection and conditional visibility."""

from copy import deepcopy

from app.subscription.capabilities import STRATEGIES, TARGET_FAMILIES, supports_connection
from app.subscription.contracts import ConnectionInput, ProfilePlan, SubscriptionError, TemplateConflict
from app.subscription.resolver import ConnectionResolver, ResolveContext


class BalancerOptionsResolver:
    def resolve(self, settings: dict, target: str) -> dict:
        result = deepcopy(settings)
        result.update(result.pop("clients", {}).get(target, {}))
        if result["strategy"] not in STRATEGIES[target]:
            raise SubscriptionError(f"Unsupported balancer strategy for {target}")
        return result


class TemplateSelector:
    def select(self, snapshot, host, family, template_id=None):
        selected = template_id if template_id is not None else host.subscription_template_ids[family]
        template = snapshot.templates.get(selected)
        if template is None or template.format != family:
            raise SubscriptionError("Subscription template does not match the requested format")
        return template

    def validate_aggregate(self, profiles, family):
        if family not in {"v2ray", "v2ray-json"} and len({plan.template.id for plan in profiles}) > 1:
            raise TemplateConflict()


class ProfilePlanner:
    def plan(self, snapshot, target, proxies, allowed_inbounds, context: ResolveContext,
             root_ids=None, groups=(), template_id=None):
        family = TARGET_FAMILIES[target]
        by_id = {host.id: host for host in snapshot.hosts}
        diagnostics = []
        cache = {}

        def connection(host_id):
            if host_id in cache:
                return cache[host_id]
            cache[host_id] = None
            host = by_id.get(host_id)
            reason = None
            if host is None or not host.enabled or host.inbound_id not in snapshot.inbounds:
                reason = "disabled_or_missing"
            elif family not in host.subscription_template_ids:
                reason = "format_disabled"
            else:
                inbound = snapshot.inbounds[host.inbound_id]
                protocol = inbound["protocol"]
                credentials = proxies.get(protocol)
                if not credentials or host.inbound_tag not in allowed_inbounds.get(protocol, []):
                    reason = "inbound_not_allowed"
                elif not supports_connection(target, inbound):
                    reason = "unsupported_connection"
                else:
                    if hasattr(credentials, "model_dump"):
                        credentials = credentials.model_dump()
                    cache[host_id] = ConnectionResolver().resolve(
                        ConnectionInput(host, inbound, snapshot.raw_inbounds[host.inbound_id], credentials), context,
                    )
            if reason:
                diagnostics.append({"host_id": host_id, "reason": reason})
            return cache[host_id]

        roots = [host for host in snapshot.hosts
                 if (root_ids is None or host.id in root_ids)
                 and (not groups or set(groups).intersection(host.group_ids))]
        automatic = {}
        participants = set()
        if target in STRATEGIES:
            for owner in roots:
                if owner.balancer_settings is None and not owner.linked_host_ids:
                    continue
                own_connection = connection(owner.id)
                if own_connection is None:
                    continue
                # Only each direct member's own endpoint is read; never walk the member's links.
                connections = [own_connection]
                connections.extend(item for member_id in owner.linked_host_ids
                                   if (item := connection(member_id)) is not None)
                from app.models.host import BalancerSettings

                settings = owner.balancer_settings or BalancerSettings().model_dump(exclude_none=True)
                options = BalancerOptionsResolver().resolve(settings, target)
                name = options.get("remark") or f"{own_connection.remark} · Auto"
                automatic[owner.id] = ProfilePlan(
                    owner, tuple(connections), TemplateSelector().select(snapshot, owner, family, template_id),
                    name.format_map(context.variables), options,
                )
                participants.update(item.host_id for item in connections)
                if len(connections) == 1:
                    diagnostics.append({"host_id": owner.id, "reason": "single_member_composition"})
        profiles = []
        for owner in roots:
            own_connection = connection(owner.id)
            if own_connection is None:
                continue
            if owner.show_when_composed or owner.id not in participants:
                profiles.append(ProfilePlan(
                    owner, (own_connection,), TemplateSelector().select(snapshot, owner, family, template_id),
                    own_connection.remark,
                ))
            if owner.id in automatic:
                profiles.append(automatic[owner.id])
        TemplateSelector().validate_aggregate(profiles, family)
        return tuple(profiles), tuple(diagnostics)
