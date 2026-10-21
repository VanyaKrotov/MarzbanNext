from copy import deepcopy
import re

import yaml

from app.subscription.clash import ClashConfiguration, ClashMetaConfiguration
from app.subscription.generators.base import apply_resolved_options, builder_arguments, finish, map_node
from app.subscription.validation import OutputValidator, TagAllocator


def mihomo_xhttp(connection):
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
    builder_class = ClashConfiguration
    target = "clash"

    def generate(self, data):
        if not data.profiles:
            return finish("", data, "text/yaml")
        builder = self.builder_class(template=data.profiles[0].template.content, defaults=data.defaults)
        allocator = TagAllocator()
        baseline = yaml.safe_load(builder.render())
        allocator.used.update(node["name"] for node in baseline.get("proxies", [])
                              + baseline.get("proxy-groups", []) if "name" in node)
        connections = {connection.host_id: connection for profile in data.profiles for connection in profile.connections}
        names = {}
        for connection in connections.values():
            name = allocator.allocate(connection.remark, f"h{connection.host_id}")
            arguments = builder_arguments(connection, name)
            xhttp = self.target == "mihomo" and connection.inbound["network"] in {"xhttp", "splithttp"}
            if xhttp:
                arguments["inbound"]["network"] = "tcp"
            result = builder.add(**arguments, include_in_default=False)
            if not result:
                continue
            node = builder.data["proxies"][-1]
            if xhttp:
                node.update({"network": "xhttp", "xhttp-opts": mihomo_xhttp(connection)})
            apply_resolved_options(node, connection, self.target)
            if self.target == "mihomo":
                options = connection.client_options.get("mihomo", {})
                if "ip_version" in options:
                    node["ip-version"] = options["ip_version"]
                if "x25519" in options and "reality-opts" in node:
                    node["reality-opts"]["support-x25519mlkem768"] = options["x25519"]
                if connection.mux.get("smux", {}).get("enabled"):
                    node["smux"] = {key.replace("_", "-"): deepcopy(value)
                                    for key, value in connection.mux["smux"].items()}
                if "server_description" in connection.client_options:
                    node["serverDescription"] = connection.client_options["server_description"]
                node = map_node(node, connection, "mihomo")
            builder.data["proxies"][-1] = node
            names[connection.host_id] = node["name"]
        for profile in data.profiles:
            if not profile.automatic:
                if profile.owner.id in names:
                    builder.default_proxy_remarks.append(names[profile.owner.id])
                continue
            options = profile.balancer
            name = allocator.allocate(profile.remark, f"auto{profile.owner.id}")
            builder.add_balancer(name, [names[item.host_id] for item in profile.connections if item.host_id in names],
                                 options["probe_url"], options["probe_interval"], options["strategy"])
            group = builder.data["proxy-groups"][-1]
            for key in ("tolerance", "lazy"):
                if key in options:
                    group[key] = options[key]
            builder.default_proxy_remarks.append(name)
        rendered = builder.render(reverse=data.reverse)
        OutputValidator().validate(yaml.safe_load(rendered), self.target)
        return finish(rendered, data, "text/yaml")


class MihomoSubscriptionGenerator(ClashSubscriptionGenerator):
    builder_class = ClashMetaConfiguration
    target = "mihomo"
