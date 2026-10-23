"""Frozen migration helpers shared with the read-only preflight command. Do not evolve this schema."""

import json
import re

LEGACY_HOST_COLUMNS = (
    "path", "sni", "host", "security", "alpn", "fingerprint", "allowinsecure", "is_disabled",
    "mux_enable", "fragment_setting", "noise_setting", "random_user_agent", "use_sni_as_host",
    "sc_max_buffered_posts", "x_padding_obfs_mode", "uplink_http_method",
)
COMPOSITE_FORMATS = ("v2ray-json", "clash", "sing-box")
EXTRA_FIELDS = ("xPaddingKey", "xPaddingHeader", "xPaddingMethod", "xPaddingPlacement",
                "scMaxBufferedPosts", "xPaddingObfsMode", "uplinkHTTPMethod")
HTTP_TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
FRAGMENT = re.compile(r'^((\d{1,4}-\d{1,4})|(\d{1,4})),((\d{1,3}-\d{1,3})|(\d{1,3})),(tlshello|\d|\d\-\d)$')
NOISE = re.compile(r'^(rand:(\d{1,4}-\d{1,4}|\d{1,4})|str:.+|hex:.+|base64:.+)(,(\d{1,4}-\d{1,4}|\d{1,4}))?'
                   r'(&(rand:(\d{1,4}-\d{1,4}|\d{1,4})|str:.+|hex:.+|base64:.+)(,(\d{1,4}-\d{1,4}|\d{1,4}))?)*$')


def _object(value):
    document = json.loads(value) if isinstance(value, str) else value
    if document is None:
        return {}
    if not isinstance(document, dict):
        raise ValueError("Inbound content must be an object")
    return document


def legacy_overrides(host, inbound):
    result, security, transport = {}, {}, {}
    for source, target in (("sni", "sni"), ("fingerprint", "fingerprint")):
        if host.get(source) and host[source] != "none":
            security[target] = host[source]
    if host.get("security") in {"tls", "none"}:
        security["mode"] = host["security"]
    if host.get("alpn") and host["alpn"] != "none":
        security["alpn"] = host["alpn"].split(",")
    if host.get("allowinsecure"):
        security["allow_insecure"] = True
    for source, target in (("path", "path"), ("host", "host"),
                           ("use_sni_as_host", "use_sni_as_host"), ("random_user_agent", "random_user_agent")):
        if host.get(source):
            transport[target] = host[source]
    fields = {"sc_max_buffered_posts": "scMaxBufferedPosts", "x_padding_obfs_mode": "xPaddingObfsMode",
              "uplink_http_method": "uplinkHTTPMethod"}
    supplied = {target: host[source] for source, target in fields.items()
                if host.get(source) is not None and host[source] != ""}
    if supplied:
        stream = _object(inbound.get("content")).get("streamSettings", {})
        settings = stream.get("xhttpSettings") or stream.get("splithttpSettings") or {}
        # The old registry gave top-level settings priority over its supported extra keys.
        extra = {key: settings.get(key, settings.get("extra", {}).get(key)) for key in EXTRA_FIELDS
                 if settings.get(key, settings.get("extra", {}).get(key)) is not None}
        extra.update(supplied)
        if isinstance(extra.get("uplinkHTTPMethod"), str):
            extra["uplinkHTTPMethod"] = extra["uplinkHTTPMethod"].strip().upper()
        transport["xhttp"] = {"extra": extra}
    if security:
        result["security"] = security
    if transport:
        result["transport"] = transport
    if host.get("mux_enable"):
        result["mux"] = {"enabled": True}
    for source, target in (("fragment_setting", "fragment"), ("noise_setting", "noise")):
        if host.get(source):
            result[target] = host[source]
    return result


def _validate_legacy_overrides(overrides, inbound):
    # Keep migration validation frozen; future request schemas must not change old upgrades.
    for key, pattern in (("fragment", FRAGMENT), ("noise", NOISE)):
        if overrides.get(key) and not pattern.fullmatch(overrides[key]):
            raise ValueError(f"Invalid {key} settings")
    xhttp = overrides.get("transport", {}).get("xhttp", {})
    if not xhttp:
        return
    stream = _object(inbound["content"]).get("streamSettings", {})
    if stream.get("network", "tcp") not in {"xhttp", "splithttp"}:
        raise ValueError("XHTTP extra requires an XHTTP inbound")
    extra = xhttp["extra"]
    posts = extra.get("scMaxBufferedPosts")
    if posts is not None and (type(posts) is not int or posts < 0):
        raise ValueError("scMaxBufferedPosts must be a nonnegative integer")
    padding = extra.get("xPaddingObfsMode")
    if padding is not None and type(padding) is not bool:
        raise ValueError("xPaddingObfsMode must be boolean")
    method = extra.get("uplinkHTTPMethod")
    if method is not None:
        if not isinstance(method, str) or len(method) > 32 or not HTTP_TOKEN.fullmatch(method):
            raise ValueError("Uplink HTTP method must be a nonempty HTTP token")
        settings = stream.get("xhttpSettings") or stream.get("splithttpSettings") or {}
        if method == "GET" and settings.get("mode", "auto") != "packet-up":
            raise ValueError("GET requires packet-up mode")


def inspect_legacy(rows):
    hosts = {row["id"]: row for row in rows["hosts"]}
    inbounds = {row["id"]: row for row in rows["inbounds"]}
    templates = {row["id"]: row for row in rows["subscription_templates"]}
    errors, warnings = [], []
    for binding in rows["host_subscription_templates"]:
        template = templates.get(binding["template_id"])
        if binding["host_id"] not in hosts or template is None or template["format"] != binding["format"]:
            errors.append({"host_id": binding["host_id"], "template_id": binding["template_id"],
                           "reason": "invalid_template_binding"})
    balancer_ids = {row["id"] for row in rows["subscription_balancers"]}
    for link in rows["subscription_balancer_hosts"]:
        if link["host_id"] not in hosts or link["balancer_id"] not in balancer_ids:
            errors.append({"balancer_id": link["balancer_id"], "host_id": link["host_id"],
                           "reason": "dangling_balancer_member"})
    for host in hosts.values():
        if host["inbound_id"] not in inbounds:
            errors.append({"host_id": host["id"], "reason": "missing_inbound"})
            continue
        try:
            overrides = legacy_overrides(host, inbounds[host["inbound_id"]])
            _validate_legacy_overrides(overrides, inbounds[host["inbound_id"]])
            for family in COMPOSITE_FORMATS:
                supports_family(family, inbounds[host["inbound_id"]])
        except (ValueError, TypeError, AttributeError) as exc:
            errors.append({"host_id": host["id"], "reason": str(exc)})
            continue
        if overrides.get("transport", {}).get("xhttp"):
            warnings.append({"host_id": host["id"], "reason": "xhttp_extra_becomes_explicit_snapshot"})
    mapping = []
    invalid_hosts = {error["host_id"] for error in errors if "host_id" in error}
    bindings = {host_id: set() for host_id in hosts}
    for binding in rows["host_subscription_templates"]:
        if binding["host_id"] in bindings:
            bindings[binding["host_id"]].add(binding["format"])
    for balancer in rows["subscription_balancers"]:
        members = [link["host_id"] for link in rows["subscription_balancer_hosts"]
                   if link["balancer_id"] == balancer["id"]]
        if not members:
            errors.append({"balancer_id": balancer["id"], "reason": "empty_balancer_requires_source_host"})
        else:
            for family in COMPOSITE_FORMATS:
                eligible = []
                for host_id in members:
                    host = hosts.get(host_id)
                    if host is None or host_id in invalid_hosts or family not in bindings[host_id]:
                        continue
                    inbound = inbounds.get(host["inbound_id"])
                    if inbound is not None and supports_family(family, inbound):
                        eligible.append(host)
                eligible.sort(key=lambda host: (bool(host["is_disabled"]), host["position"], host["id"]))
                mapping.append({"balancer_id": balancer["id"], "format": family,
                                "source_host_id": eligible[0]["id"] if eligible else None,
                                "member_host_ids": [row["id"] for row in eligible],
                                "enabled": bool(balancer["enabled"] and eligible and not eligible[0]["is_disabled"])})
        if not balancer["enabled"]:
            warnings.append({"balancer_id": balancer["id"], "reason": "disabled_balancer_preserved"})
        if len(members) == 1:
            warnings.append({"balancer_id": balancer["id"], "reason": "single_member_composition"})
    return {"schema_version": 2, "host_count": len(hosts), "balancer_count": len(rows["subscription_balancers"]),
            "mapping": mapping, "errors": errors, "warnings": warnings}


def supports_family(family, inbound):
    content = _object(inbound["content"])
    protocol = content.get("protocol")
    network = content.get("streamSettings", {}).get("network", "tcp")
    if family == "clash":
        return protocol in {"vmess", "vless", "trojan", "shadowsocks", "hysteria"} and network not in {
            "kcp", "xhttp", "splithttp", "quic"}
    if family == "sing-box":
        return network not in {"kcp", "xhttp", "splithttp", "quic"}
    return True


def preflight(connection):
    from app.db.migrations.template_composition_v1 import prepare

    return prepare(connection)[2]
