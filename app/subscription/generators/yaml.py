from copy import deepcopy
import re

import yaml

from app.subscription.clash import ClashMetaConfiguration
from app.subscription.generators.composition import assemble_clash, required_sources
from app.subscription.generators.base import apply_resolved_options, builder_arguments, finish, map_node
from app.subscription.validation import OutputValidator, TagAllocator, validate_identities


def clash_xhttp(connection):
    inbound = connection.inbound
    options = {key: inbound[key] for key in ("path", "host", "mode") if inbound.get(key)}
    extra = inbound.get("_xhttp_extra", {})
    for key, value in extra.items():
        if key == "xmux":
            options["reuse-settings"] = {
                re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower(): item if name == "hKeepAlivePeriod" else str(item)
                for name, item in value.items()
            }
        elif key == "headers":
            options[key] = deepcopy(value)
        else:
            target = {"noGRPCHeader": "no-grpc-header", "uplinkHTTPMethod": "uplink-http-method"}.get(key)
            if target is None:
                target = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", key).lower()
            options[target] = deepcopy(value)
    return options


class ClashSubscriptionGenerator:
    builder_class = ClashMetaConfiguration
    target = "clash"

    def generate(self, data):
        if not data.profiles:
            return finish("", data, "text/yaml")
        builder = self.builder_class(template=data.profiles[0].template.content, defaults=data.defaults)
        builder.template_context = {**data.profiles[0].connections[0].context,
                                    "host_ids": [item.host_id for item in data.profiles[0].sources]}
        allocator = TagAllocator()
        baseline = yaml.safe_load(builder.render())
        allocator.used.update(validate_identities(baseline.get(
            "proxies", []) + baseline.get("proxy-groups", []), "name"))
        connections = {connection.host_id: connection
                       for connection in required_sources(baseline, data.profiles[0], self.target)}
        names = {}
        for connection in connections.values():
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
            if "server_description" in connection.client_options:
                node["serverDescription"] = connection.client_options["server_description"]
            node = map_node(node, connection, "clash")
            builder.data["proxies"][-1] = node
            names[connection.host_id] = node["name"]
        diagnostics = []
        profile = data.profiles[0]
        nodes = {host_id: node for host_id, node in zip(names, builder.data["proxies"])}
        builder.data["proxies"] = [nodes[host_id] for host_id in profile.visible_ids if host_id in nodes]
        builder.default_proxy_remarks = [names[host_id] for host_id in profile.visible_ids if host_id in names]
        document = assemble_clash(yaml.safe_load(builder.render(reverse=data.reverse)), profile, nodes, diagnostics)
        if document is None:
            return finish("", data, "text/yaml", diagnostics)
        OutputValidator().validate(document, self.target)
        return finish(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), data, "text/yaml", diagnostics)
