"""Validate identity and references after node mapping and complete template assembly."""

from app.subscription.contracts import SubscriptionError

CLASH_BUILTINS = {"DIRECT", "REJECT", "REJECT-DROP", "GLOBAL", "PASS", "COMPATIBLE"}
GROUP_TYPES = {"selector", "select", "urltest", "url-test", "load-balance", "fallback"}


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
        nodes = document.get("outbounds", [])
        if target == "clash":
            nodes = document.get("proxies", []) + document.get("proxy-groups", [])
        key = "name" if target == "clash" else "tag"
        available = set(validate_identities(nodes, key))
        if target == "clash":
            available.update(CLASH_BUILTINS)
        graph = self._reference_graph(nodes, key, available)
        validate_reference_graph(graph)
        if target in {"clash", "sing-box"}:
            for node in nodes:
                if node.get("type") in GROUP_TYPES and not graph[node[key]] and not node.get("use"):
                    raise SubscriptionError("Generated configuration contains an empty proxy group")
        if target == "sing-box":
            self._validate_singbox(document, nodes, available)
        elif target == "clash":
            self._validate_clash(document, nodes, available)
        elif target == "v2ray-json":
            self._validate_xray(document, available)

    @staticmethod
    def _require_reference(reference, available, message):
        if not isinstance(reference, str) or reference not in available:
            raise SubscriptionError(message)

    def _reference_graph(self, nodes, key, available):
        graph = {}
        for node in nodes:
            references = node.get("proxies") or node.get("outbounds") or []
            if not isinstance(references, list):
                raise SubscriptionError("Proxy group references must be an array of strings")
            references = list(references)
            references.extend(value for value in (
                node.get("detour"), node.get("proxySettings", {}).get("tag"),
                node.get("streamSettings", {}).get("sockopt", {}).get("dialerProxy"),
            ) if value)
            graph[node[key]] = references
            for reference in references:
                self._require_reference(reference, available,
                                        "Generated configuration contains an unknown outbound reference")
        return graph

    def _validate_singbox(self, document, nodes, available):
        route = document.get("route", {})
        if route.get("final"):
            self._require_reference(route["final"], available, "sing-box route.final references an unknown outbound")
        for node in nodes:
            for field in ("default", "detour"):
                if node.get(field):
                    self._require_reference(node[field], available, f"sing-box {field} references an unknown outbound")
            if node.get("default") and node["default"] not in (node.get("outbounds") or []):
                raise SubscriptionError("sing-box selector default is outside its outbound list")
        for rule in route.get("rules", []):
            if rule.get("outbound"):
                self._require_reference(rule["outbound"], available, "sing-box route references an unknown outbound")

    def _validate_clash(self, document, nodes, available):
        providers = document.get("proxy-providers", {})
        for node in nodes:
            references = node.get("use", [])
            if not isinstance(references, list):
                raise SubscriptionError("Clash provider references must be an array of strings")
            for reference in references:
                self._require_reference(reference, providers, "Clash group references an unknown provider")
        for rule in document.get("rules", []):
            if isinstance(rule, str):
                fields = rule.rsplit(",", 2)
                reference = fields[-2] if fields[-1] == "no-resolve" and len(fields) > 1 else fields[-1]
                self._require_reference(reference, available, "Clash rule references an unknown proxy")

    def _validate_xray(self, document, available):
        routing = document.get("routing", {})
        balancer_nodes = routing.get("balancers", [])
        balancer_names = [item.get("tag") for item in balancer_nodes]
        if any(not isinstance(tag, str) or not tag for tag in balancer_names):
            raise SubscriptionError("Xray balancer is missing its tag")
        balancers = set(balancer_names)
        if len(balancers) != len(balancer_names) or balancers.intersection(available):
            raise SubscriptionError("Xray contains duplicate routing identities")
        for balancer in balancer_nodes:
            prefixes = balancer.get("selector")
            if not isinstance(prefixes, list) or any(not isinstance(prefix, str) or not prefix for prefix in prefixes):
                raise SubscriptionError("Xray balancer requires outbound tag prefixes")
            if not any(name.startswith(prefix) for prefix in prefixes for name in available):
                raise SubscriptionError("Xray balancer does not select any outbound")
            if balancer.get("fallbackTag"):
                self._require_reference(balancer["fallbackTag"], available,
                                        "Xray balancer fallback references an unknown outbound")
        for rule in routing.get("rules", []):
            if rule.get("outboundTag"):
                self._require_reference(rule["outboundTag"], available, "Xray routing references an unknown outbound")
            if rule.get("balancerTag"):
                self._require_reference(rule["balancerTag"], balancers, "Xray routing references an unknown balancer")
