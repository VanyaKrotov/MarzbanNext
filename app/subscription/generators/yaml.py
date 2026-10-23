from copy import deepcopy

import yaml

from app.subscription.clash import ClashMetaConfiguration
from app.subscription.client_metadata import get_server_description
from app.subscription.generators.composition import assemble_clash, required_sources
from app.subscription.generators.base import apply_resolved_options, builder_arguments, finish, map_node
from app.subscription.validation import OutputValidator, TagAllocator, validate_identities
from app.subscription.generators.xhttp import clash_xhttp


class ClashSubscriptionGenerator:
    builder_class = ClashMetaConfiguration
    target = "clash"

    def generate(self, data):
        if not data.profiles:
            return finish("", data, "text/yaml")
        builder = self.builder_class(template=data.profiles[0].template.content, defaults=data.defaults,
                                     migration_settings=data.profiles[0].template.migration_settings)
        builder.template_context = {**data.profiles[0].connections[0].context,
                                    "host_ids": [item.host_id for item in data.profiles[0].sources]}
        allocator = TagAllocator()
        baseline = yaml.safe_load(builder.render())
        allocator.used.update(validate_identities(baseline.get(
            "proxies", []) + baseline.get("proxy-groups", []), "name"))
        connections = required_sources(baseline, data.profiles[0], self.target)
        nodes = {}
        for connection in connections:
            name = allocator.allocate(connection.remark, f"h{connection.host_id}")
            arguments = builder_arguments(connection, name)
            xhttp = connection.inbound["network"] in {"xhttp", "splithttp"}
            if xhttp:
                arguments["inbound"]["network"] = "tcp"
            result = builder.add(**arguments, include_in_default=False)
            if not result:
                continue
            node = builder.data["proxies"][-1]
            if xhttp:
                node.update({"network": "xhttp", "xhttp-opts": clash_xhttp(connection)})
            apply_resolved_options(node, connection, self.target)
            options = connection.client_options.get("clash", {})
            if "ip_version" in options:
                node["ip-version"] = options["ip_version"]
            if "x25519" in options and "reality-opts" in node:
                node["reality-opts"]["support-x25519mlkem768"] = options["x25519"]
            if connection.mux.get("smux", {}).get("enabled"):
                node["smux"] = {key.replace("_", "-"): deepcopy(value)
                                for key, value in connection.mux["smux"].items()}
            description = get_server_description(connection, data.include_server_description)
            if description:
                node["serverDescription"] = description
            node = map_node(node, connection, "clash")
            builder.data["proxies"][-1] = node
            nodes[connection.host_id] = node
        diagnostics = []
        profile = data.profiles[0]
        builder.data["proxies"] = [nodes[host_id] for host_id in profile.visible_ids if host_id in nodes]
        builder.default_proxy_remarks = [nodes[host_id]["name"] for host_id in profile.visible_ids if host_id in nodes]
        document = assemble_clash(yaml.safe_load(builder.render(reverse=data.reverse)), profile, nodes, diagnostics)
        if document is None:
            return finish("", data, "text/yaml", diagnostics)
        OutputValidator().validate(document, self.target)
        return finish(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), data, "text/yaml", diagnostics)
