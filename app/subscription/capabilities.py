"""Shared capability policy for administrative validation and subscription planning."""

TARGET_FAMILIES = {
    "v2ray": "v2ray", "v2ray-json": "v2ray-json", "clash": "clash", "sing-box": "sing-box", "outline": "outline",
}


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
    from app.models.host import HostOverrides

    return {
        "schema_version": 4,
        "overrides_schema": HostOverrides.model_json_schema(),
        "target_families": TARGET_FAMILIES,
    }
