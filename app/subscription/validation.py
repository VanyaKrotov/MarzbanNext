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


class OutputValidator:
    def validate(self, document, target):
        nodes = document.get("proxies", []) + document.get("proxy-groups", []) if target in {
            "clash", "mihomo"} else document.get("outbounds", [])
        key = "name" if target in {"clash", "mihomo"} else "tag"
        names = [node.get(key) for node in nodes]
        if any(not isinstance(name, str) or not name for name in names) or len(names) != len(set(names)):
            raise SubscriptionError("Generated configuration contains missing or duplicate tags")
        available = set(names) | ({"DIRECT", "REJECT", "GLOBAL", "PASS", "COMPATIBLE"}
                                  if target in {"clash", "mihomo"} else set())
        for node in nodes:
            for reference in node.get("proxies", []) or node.get("outbounds", []) or []:
                if reference not in available:
                    raise SubscriptionError("Generated configuration contains an unknown outbound reference")
        if target == "v2ray-json":
            for outbound in nodes:
                dialer = outbound.get("streamSettings", {}).get("sockopt", {}).get("dialerProxy")
                if dialer and dialer not in available:
                    raise SubscriptionError("Xray socket options reference an unknown dialer")
            routing = document.get("routing", {})
            balancers = {item["tag"] for item in routing.get("balancers", [])}
            for rule in routing.get("rules", []):
                if rule.get("outboundTag") and rule["outboundTag"] not in available:
                    raise SubscriptionError("Xray routing references an unknown outbound")
                if rule.get("balancerTag") and rule["balancerTag"] not in balancers:
                    raise SubscriptionError("Xray routing references an unknown balancer")
