"""Shared capability policy for administrative validation and subscription planning."""

STRATEGIES = {
    "v2ray-json": ("least_ping", "least_load", "random", "round_robin"),
    "clash": ("least_ping", "round_robin"),
    "sing-box": ("least_ping",),
}
TARGET_FAMILIES = {
    "v2ray": "v2ray", "v2ray-json": "v2ray-json", "clash": "clash", "sing-box": "sing-box", "outline": "outline",
}
CLIENT_FIELDS = {
    "v2ray-json": {"strategy", "probe_url", "probe_interval", "enable_concurrency", "strategy_settings"},
    "clash": {"strategy", "probe_url", "probe_interval", "tolerance", "lazy"},
    "sing-box": {"strategy", "probe_url", "probe_interval", "tolerance", "idle_timeout",
                 "interrupt_existing_connections"},
}


def validate_balancer(settings: dict, bindings: dict, member_ids: set[int]) -> None:
    for target, options in settings.get("clients", {}).items():
        invalid = options.keys() - CLIENT_FIELDS[target]
        if invalid:
            raise ValueError(f"balancer_settings.clients.{target}: unsupported fields {', '.join(sorted(invalid))}")
        strategy = options.get("strategy", settings["strategy"])
        if options.get("strategy_settings"):
            if target != "v2ray-json" or strategy != "least_load":
                raise ValueError("Xray strategy_settings require least_load")
            costs = options["strategy_settings"].get("costs", [])
            if any(cost["host_id"] not in member_ids for cost in costs):
                raise ValueError("Balancer costs can reference only the owner and direct members")
    for target, strategies in STRATEGIES.items():
        if TARGET_FAMILIES[target] not in bindings:
            continue
        selected = settings.get("clients", {}).get(target, {}).get("strategy", settings["strategy"])
        if selected not in strategies:
            raise ValueError(f"balancer_settings.clients.{target}.strategy: choose a supported strategy")


def supports_connection(target: str, inbound: dict) -> bool:
    protocol, network = inbound["protocol"], inbound["network"]
    if target == "outline":
        return protocol == "shadowsocks"
    if target in {"clash", "sing-box"} and network in {"kcp", "quic"}:
        return False
    if target == "sing-box" and network in {"splithttp", "xhttp"}:
        return False
    return protocol in {"vmess", "vless", "trojan", "shadowsocks", "hysteria"}


def host_capabilities() -> dict:
    from app.models.host import HostOverrides, BalancerSettings

    return {
        "schema_version": 3,
        "overrides_schema": HostOverrides.model_json_schema(),
        "balancer_schema": BalancerSettings.model_json_schema(),
        "strategies": STRATEGIES,
        "target_families": TARGET_FAMILIES,
    }
