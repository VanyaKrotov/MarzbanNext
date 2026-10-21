import json
from copy import deepcopy

from app.models.subscription_template import SubscriptionFormat
from app.subscription.generators.base import apply_resolved_options, builder_arguments, finish, map_node
from app.subscription.singbox import SingBoxConfiguration
from app.subscription.validation import OutputValidator, TagAllocator
from app.utils.subscription_templates import parse_subscription_document, render_subscription_template


class SingBoxSubscriptionGenerator:
    def generate(self, data):
        if not data.profiles:
            return finish("", data, "application/json")
        template = parse_subscription_document(SubscriptionFormat.sing_box,
                                               render_subscription_template(data.profiles[0].template.content))
        builder = SingBoxConfiguration(template=json.dumps(template), defaults=data.defaults)
        allocator = TagAllocator()
        allocator.used.update(item.get("tag") for item in template["outbounds"])
        names = {}
        connections = {connection.host_id: connection for profile in data.profiles for connection in profile.connections}
        for connection in connections.values():
            name = allocator.allocate(connection.remark, f"h{connection.host_id}")
            result = builder.add(**builder_arguments(connection, name), include_in_default=False)
            if not result:
                continue
            node = builder.config["outbounds"][-1]
            apply_resolved_options(node, connection, "sing-box")
            smux = connection.mux.get("smux", {})
            if smux.get("enabled") and not node.get("udp_over_tcp", {}).get("enabled"):
                node["multiplex"] = deepcopy(smux)
            node = map_node(node, connection, "singbox")
            builder.config["outbounds"][-1] = node
            names[connection.host_id] = node["tag"]
        for profile in data.profiles:
            if not profile.automatic:
                if profile.owner.id in names:
                    builder.default_proxy_remarks.append(names[profile.owner.id])
                continue
            options = profile.balancer
            name = allocator.allocate(profile.remark, f"auto{profile.owner.id}")
            builder.add_balancer(name, [names[item.host_id] for item in profile.connections if item.host_id in names],
                                 options["probe_url"], options["probe_interval"])
            node = builder.config["outbounds"][-1]
            if "tolerance" in options:
                node["tolerance"] = options["tolerance"]
            if "idle_timeout" in options:
                node["idle_timeout"] = f"{options['idle_timeout']}s"
            if "interrupt_existing_connections" in options:
                node["interrupt_exist_connections"] = options["interrupt_existing_connections"]
        rendered = builder.render(reverse=data.reverse)
        OutputValidator().validate(json.loads(rendered), "sing-box")
        return finish(rendered, data, "application/json")
