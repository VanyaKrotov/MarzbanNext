"""Validate identity and references after node mapping and complete template assembly."""

from app.subscription.contracts import SubscriptionError


class TagAllocator:
    def __init__(self):
        self.used = set()

    def allocate(self, preferred, suffix):
        value = preferred
        if value in self.used:
            value = f"{preferred} [{suffix}]"
        while value in self.used:
            value += "_"
        self.used.add(value)
        return value


def validate_reference_graph(graph):
    visiting, visited = set(), set()
    for root in graph:
        stack = [(root, False)]
        while stack:
            name, leaving = stack.pop()
            if leaving:
                visiting.remove(name)
                visited.add(name)
            elif name in visiting:
                raise SubscriptionError("Generated configuration contains an outbound cycle")
            elif name not in visited and name in graph:
                visiting.add(name)
                stack.append((name, True))
                stack.extend((reference, False) for reference in graph[name])


def validate_identities(nodes, key):
    names = [node.get(key) for node in nodes]
    if any(not isinstance(name, str) or not name for name in names) or len(names) != len(set(names)):
        raise SubscriptionError("Generated configuration contains missing or duplicate tags")
    return names


class OutputValidator:
    def validate(self, document, target):
        nodes = document.get("proxies", []) + document.get("proxy-groups", []
                                                           ) if target == "clash" else document.get("outbounds", [])
        key = "name" if target == "clash" else "tag"
        names = validate_identities(nodes, key)
        available = set(names) | ({"DIRECT", "REJECT", "REJECT-DROP", "GLOBAL", "PASS", "COMPATIBLE"}
                                  if target == "clash" else set())
        graph = {}
        for node in nodes:
            references = list(node.get("proxies", []) or node.get("outbounds", []) or [])
            references.extend(value for value in (
                node.get("detour"), node.get("proxySettings", {}).get("tag"),
                node.get("streamSettings", {}).get("sockopt", {}).get("dialerProxy"),
            ) if value)
            graph[node[key]] = references
            for reference in references:
                if not isinstance(reference, str) or reference not in available:
                    raise SubscriptionError("Generated configuration contains an unknown outbound reference")
        validate_reference_graph(graph)
        if target in {"clash", "sing-box"}:
            for node in nodes:
                if node.get("type") in {"selector", "select", "urltest", "url-test", "load-balance", "fallback"}:
                    if not graph[node[key]] and not node.get("use"):
                        raise SubscriptionError("Generated configuration contains an empty proxy group")
        if target == "sing-box":
            final = document.get("route", {}).get("final")
            if final and (not isinstance(final, str) or final not in available):
                raise SubscriptionError("sing-box route.final references an unknown outbound")
            for node in nodes:
                for field in ("default", "detour"):
                    if node.get(field) and (not isinstance(node[field], str) or node[field] not in available):
                        raise SubscriptionError(f"sing-box {field} references an unknown outbound")
                if node.get("default") and node["default"] not in (node.get("outbounds") or []):
                    raise SubscriptionError("sing-box selector default is outside its outbound list")
            for rule in document.get("route", {}).get("rules", []):
                if rule.get("outbound") and (
                    not isinstance(rule["outbound"], str) or rule["outbound"] not in available
                ):
                    raise SubscriptionError("sing-box route references an unknown outbound")
        if target == "clash":
            providers = document.get("proxy-providers", {})
            for node in nodes:
                if any(name not in providers for name in node.get("use", [])):
                    raise SubscriptionError("Clash group references an unknown provider")
            for rule in document.get("rules", []):
                if isinstance(rule, str):
                    fields = rule.rsplit(",", 2)
                    reference = fields[-2] if fields[-1] == "no-resolve" else fields[-1]
                    if reference not in available:
                        raise SubscriptionError("Clash rule references an unknown proxy")
        if target == "v2ray-json":
            for outbound in nodes:
                dialer = outbound.get("streamSettings", {}).get("sockopt", {}).get("dialerProxy")
                if dialer and dialer not in available:
                    raise SubscriptionError("Xray socket options reference an unknown dialer")
            routing = document.get("routing", {})
            balancer_names = [item.get("tag") for item in routing.get("balancers", [])]
            if any(not isinstance(tag, str) or not tag for tag in balancer_names):
                raise SubscriptionError("Xray balancer is missing its tag")
            balancers = set(balancer_names)
            if len(balancers) != len(routing.get("balancers", [])) or balancers.intersection(available):
                raise SubscriptionError("Xray contains duplicate routing identities")
            for balancer in routing.get("balancers", []):
                if not isinstance(balancer.get("selector"), list) or any(
                    not isinstance(prefix, str) or not prefix for prefix in balancer["selector"]
                ):
                    raise SubscriptionError("Xray balancer requires outbound tag prefixes")
                if not any(name.startswith(prefix) for prefix in balancer.get("selector", []) for name in available):
                    raise SubscriptionError("Xray balancer does not select any outbound")
                if balancer.get("fallbackTag") and (
                    not isinstance(balancer["fallbackTag"], str) or balancer["fallbackTag"] not in available
                ):
                    raise SubscriptionError("Xray balancer fallback references an unknown outbound")
            for rule in routing.get("rules", []):
                if rule.get("outboundTag") and (
                    not isinstance(rule["outboundTag"], str) or rule["outboundTag"] not in available
                ):
                    raise SubscriptionError("Xray routing references an unknown outbound")
                if rule.get("balancerTag") and (
                    not isinstance(rule["balancerTag"], str) or rule["balancerTag"] not in balancers
                ):
                    raise SubscriptionError("Xray routing references an unknown balancer")
