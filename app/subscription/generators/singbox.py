import json
from copy import deepcopy

from app.models.subscription_template import SubscriptionFormat
from app.subscription.generators.composition import assemble_singbox, required_sources
from app.subscription.generators.base import apply_resolved_options, builder_arguments, finish, map_node
from app.subscription.singbox import SingBoxConfiguration
from app.subscription.validation import OutputValidator, TagAllocator, validate_identities
from app.utils.subscription_templates import parse_subscription_document, render_subscription_template


class SingBoxSubscriptionGenerator:
    def generate(self, data):
        if not data.profiles:
            return finish("", data, "application/json")
        profile = data.profiles[0]
        context = {**profile.connections[0].context, "host_ids": [item.host_id for item in profile.sources]}
        template = parse_subscription_document(
            SubscriptionFormat.sing_box, render_subscription_template(profile.template.content, context))
        builder = SingBoxConfiguration(document=template, defaults=data.defaults)
        allocator = TagAllocator()
        allocator.used.update(validate_identities(template["outbounds"], "tag"))
        names = {}
        connections = {connection.host_id: connection
                       for connection in required_sources(template, data.profiles[0], "sing-box")}
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
        diagnostics = []
        nodes_by_tag = {node["tag"]: node for node in builder.config["outbounds"]}
        nodes = {host_id: nodes_by_tag[tag] for host_id, tag in names.items()}
        builder.default_proxy_remarks = [names[host_id] for host_id in profile.visible_ids if host_id in names]
        document = assemble_singbox(json.loads(builder.render(reverse=data.reverse)), profile, nodes, diagnostics)
        if document is None:
            return finish("", data, "application/json", diagnostics)
        OutputValidator().validate(document, "sing-box")
        return finish(json.dumps(document, ensure_ascii=False, indent=2), data, "application/json", diagnostics)
