import base64
from copy import deepcopy
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.subscription.contracts import GenerationResult
from app.subscription.contracts import SubscriptionError
from app.subscription.mapper import HostMapper


def builder_arguments(connection, remark=None):
    return {"remark": remark or connection.remark, "address": connection.address,
            "inbound": deepcopy(connection.inbound), "settings": deepcopy(connection.credentials)}


def finish(body, data, media_type):
    if data.as_base64 and body:
        body = base64.b64encode(body.encode()).decode()
    return GenerationResult(body, media_type, len(data.profiles))


def map_node(node, connection, target):
    mapped = HostMapper().apply(node, connection.mapper.get(target, []), connection)
    identity = "name" if target == "mihomo" else "tag"
    if not isinstance(mapped.get(identity), str) or not mapped[identity]:
        raise SubscriptionError("Host mapper removed the connection identity")
    if target == "xrayJson" and mapped[identity] != node[identity]:
        raise SubscriptionError("Host mapper cannot change an Xray managed outbound tag")
    return mapped


def apply_resolved_options(node, connection, target):
    """Apply resolved transport/security values after legacy encoding defaults."""
    network = connection.inbound["network"]
    options = connection.transport
    if target == "v2ray-json":
        stream = node.setdefault("streamSettings", {})
        key = {"ws": "wsSettings", "httpupgrade": "httpupgradeSettings", "grpc": "grpcSettings",
               "xhttp": "xhttpSettings", "splithttp": "splithttpSettings"}.get(network)
        section = stream.setdefault(key, {}) if key else None
    elif target in {"clash", "mihomo"}:
        key = {"ws": "ws-opts", "httpupgrade": "ws-opts", "grpc": "grpc-opts"}.get(network)
        section = node.setdefault(key, {}) if key else None
    else:
        section = node.get("transport")
    if section is not None:
        if "headers" in options:
            headers = {**section.get("headers", {}), **deepcopy(options["headers"])}
            if connection.inbound.get("random_user_agent") and "User-Agent" in section.get("headers", {}):
                headers["User-Agent"] = section["headers"]["User-Agent"]
            section["headers"] = headers
        if "path" in options:
            key = "path"
            if network == "grpc":
                key = {"v2ray-json": "serviceName", "clash": "grpc-service-name",
                       "mihomo": "grpc-service-name", "sing-box": "service_name"}[target]
            section[key] = options["path"]
        if "host" in options:
            if network in {"ws", "httpupgrade"} and target != "v2ray-json":
                section.setdefault("headers", {})["Host"] = options["host"]
            elif network == "grpc":
                if target == "v2ray-json":
                    section["authority"] = options["host"]
            else:
                section["host"] = options["host"]
        if target == "v2ray-json" and network == "ws" and "heartbeatPeriod" in options:
            section["heartbeatPeriod"] = options["heartbeatPeriod"]
    security = connection.security
    if connection.inbound["tls"] not in {"tls", "reality"}:
        return
    if target == "v2ray-json":
        tls = node["streamSettings"].setdefault(connection.inbound["tls"] + "Settings", {})
        insecure_key = "allowInsecure"
    elif target in {"clash", "mihomo"}:
        tls, insecure_key = node, "skip-cert-verify"
    else:
        tls, insecure_key = node.setdefault("tls", {}), "insecure"
    if "alpn" in security:
        tls["alpn"] = deepcopy(security["alpn"])
    if "allow_insecure" in security:
        tls[insecure_key] = security["allow_insecure"]


def apply_xray_options(outbound, connection):
    stream = outbound.setdefault("streamSettings", {})
    if "sockopt" in connection.stream:
        # Fragment/noise may have installed a dialer; user socket options must retain it.
        previous = stream.get("sockopt", {})
        stream["sockopt"] = {**previous, **deepcopy(connection.stream["sockopt"])}
        if "dialerProxy" in previous:
            stream["sockopt"]["dialerProxy"] = previous["dialerProxy"]
    if "final_mask" in connection.stream:
        stream["finalmask"] = deepcopy(connection.stream["final_mask"])
    if connection.mux.get("enabled") and "xray" in connection.mux:
        outbound["mux"] = {"enabled": True, **deepcopy(connection.mux["xray"])}


def map_uri(link, connection):
    operations = connection.mapper.get("base64", [])
    if not operations:
        return link
    parsed = urlsplit(link)
    if parsed.scheme == "vmess":
        payload = json.loads(base64.b64decode(link.removeprefix("vmess://")))
        payload = HostMapper().apply(payload, operations, connection, flat=True)
        return "vmess://" + base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    query = HostMapper().apply(dict(parse_qsl(parsed.query, keep_blank_values=True)), operations, connection, flat=True)
    query = {key: json.dumps(value, separators=(",", ":")) if isinstance(value, (dict, list, bool)) else str(value)
             for key, value in query.items()}
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
