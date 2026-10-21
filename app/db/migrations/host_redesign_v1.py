"""Frozen migration helpers shared with the read-only preflight command. Do not evolve this schema."""

from copy import deepcopy
from datetime import UTC, datetime
import json
import re

import sqlalchemy as sa

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
    return json.loads(value) if isinstance(value, str) else (value or {})


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
        if "uplinkHTTPMethod" in extra:
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


def read_legacy(connection):
    metadata = sa.MetaData()
    metadata.reflect(connection, only=["hosts", "inbounds", "subscription_balancers", "subscription_balancer_hosts",
                                       "host_subscription_templates", "host_group_hosts"])
    rows = {name: [dict(row) for row in connection.execute(table.select()).mappings()]
            for name, table in metadata.tables.items()}
    return metadata, rows


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


def preflight(connection):
    _, rows = read_legacy(connection)
    hosts = {row["id"]: row for row in rows["hosts"]}
    inbounds = {row["id"]: row for row in rows["inbounds"]}
    errors, warnings = [], []
    balancer_ids = {row["id"] for row in rows["subscription_balancers"]}
    for link in rows["subscription_balancer_hosts"]:
        if link["host_id"] not in hosts or link["balancer_id"] not in balancer_ids:
            errors.append({"balancer_id": link["balancer_id"], "host_id": link["host_id"],
                           "reason": "dangling_balancer_member"})
    for host in hosts.values():
        if host["inbound_id"] not in inbounds:
            errors.append({"host_id": host["id"], "reason": "missing_inbound"})
            continue
        overrides = legacy_overrides(host, inbounds[host["inbound_id"]])
        try:
            _validate_legacy_overrides(overrides, inbounds[host["inbound_id"]])
        except ValueError as exc:
            errors.append({"host_id": host["id"], "reason": str(exc)})
        if overrides.get("transport", {}).get("xhttp"):
            warnings.append({"host_id": host["id"], "reason": "xhttp_extra_becomes_explicit_snapshot"})
    mapping = []
    bindings = {host_id: {row["format"] for row in rows["host_subscription_templates"]
                          if row["host_id"] == host_id} for host_id in hosts}
    for balancer in rows["subscription_balancers"]:
        members = [link["host_id"] for link in rows["subscription_balancer_hosts"]
                   if link["balancer_id"] == balancer["id"]]
        if not members:
            errors.append({"balancer_id": balancer["id"], "reason": "empty_balancer_requires_source_host"})
        else:
            for family in COMPOSITE_FORMATS:
                eligible = sorted((hosts[host_id] for host_id in members if host_id in hosts
                                   and family in bindings[host_id] and hosts[host_id]["inbound_id"] in inbounds
                                   and _supports_family(family, inbounds[hosts[host_id]["inbound_id"]])),
                                  key=lambda row: (bool(row["is_disabled"]), row["position"], row["id"]))
                if family == "clash":
                    eligible.sort(key=lambda row: (bool(row["is_disabled"]),
                                  _object(inbounds[row["inbound_id"]]["content"]).get("protocol")
                                  not in {"vmess", "trojan", "shadowsocks"}, row["position"], row["id"]))
                mapping.append({"balancer_id": balancer["id"], "format": family,
                                "source_host_id": eligible[0]["id"] if eligible else None,
                                "member_host_ids": [row["id"] for row in eligible],
                                "enabled": bool(balancer["enabled"] and eligible and not eligible[0]["is_disabled"])})
        if not balancer["enabled"]:
            warnings.append({"balancer_id": balancer["id"], "reason": "disabled_balancer_preserved"})
        if len(members) == 1:
            warnings.append({"balancer_id": balancer["id"], "reason": "single_member_composition"})
    return {"schema_version": 1, "host_count": len(hosts), "balancer_count": len(rows["subscription_balancers"]),
            "mapping": mapping, "errors": errors, "warnings": warnings}


def _supports_family(family, inbound):
    content = _object(inbound["content"])
    protocol = content.get("protocol")
    network = content.get("streamSettings", {}).get("network", "tcp")
    if family == "clash":
        return protocol in {"vmess", "vless", "trojan", "shadowsocks", "hysteria"} and network not in {
            "kcp", "xhttp", "splithttp", "quic"}
    if family == "sing-box":
        return network not in {"kcp", "xhttp", "splithttp", "quic"}
    return True


def transfer(connection, rows):
    metadata = sa.MetaData()
    metadata.reflect(connection, only=["hosts", "host_links", "host_subscription_templates", "host_group_hosts"])
    hosts_table = metadata.tables["hosts"]
    hosts = {row["id"]: row for row in rows["hosts"]}
    inbounds = {row["id"]: row for row in rows["inbounds"]}
    bindings = {host_id: {row["format"]: row["template_id"] for row in rows["host_subscription_templates"]
                          if row["host_id"] == host_id} for host_id in hosts}
    normalized = {}
    now = datetime.now(UTC).replace(tzinfo=None)
    for host_id, host in hosts.items():
        values = {"enabled": not bool(host["is_disabled"]), "show_when_composed": True,
                  "overrides": legacy_overrides(host, inbounds[host["inbound_id"]]),
                  "created_at": now, "updated_at": now, "port": host["port"] or None}
        connection.execute(hosts_table.update().where(hosts_table.c.id == host_id).values(**values))
        normalized[host_id] = {**host, **values}
    position = max([row["position"] for row in hosts.values()] + [-1]) + 1
    for balancer in sorted(rows["subscription_balancers"], key=lambda row: (row["position"], row["id"])):
        member_ids = [link["host_id"] for link in rows["subscription_balancer_hosts"]
                      if link["balancer_id"] == balancer["id"]]
        members = sorted((normalized[host_id] for host_id in member_ids),
                         key=lambda row: (not row["enabled"], row["position"], row["id"]))
        # Partition only when format gating changes the eligible members. No excluded format is enabled.
        partitions = {}
        for family in COMPOSITE_FORMATS:
            eligible = [row for row in members if family in bindings[row["id"]]
                        and _supports_family(family, inbounds[row["inbound_id"]])]
            candidates = eligible
            if family == "clash":
                candidates.sort(key=lambda row: (not row["enabled"],
                                _object(inbounds[row["inbound_id"]]["content"]).get("protocol")
                                not in {"vmess", "trojan", "shadowsocks"}, row["position"], row["id"]))
            if candidates:
                partitions.setdefault(tuple(row["id"] for row in candidates), []).append(family)
        if not partitions:
            partitions[tuple(row["id"] for row in members)] = []
        for selected_ids, families in partitions.items():
            source = normalized[selected_ids[0]]
            settings = {"remark": balancer["name"], "strategy": balancer["strategy"],
                        "probe_url": balancer["probe_url"], "probe_interval": balancer["probe_interval"],
                        "clients": {"sing-box": {"strategy": "least_ping"}}}
            if balancer["strategy"] not in {"least_ping", "round_robin"}:
                settings["clients"].update({"clash": {"strategy": "least_ping"},
                                            "mihomo": {"strategy": "least_ping"}})
            values = {key: deepcopy(source[key]) for key in ("inbound_id", "address", "port", "overrides")}
            values.update(remark=balancer["name"], enabled=bool(balancer["enabled"] and source["enabled"]),
                          position=position, show_when_composed=False, balancer_settings=settings,
                          created_at=balancer["created_at"], updated_at=balancer["updated_at"])
            owner_id = connection.execute(hosts_table.insert().values(**values)).inserted_primary_key[0]
            position += 1
            for index, member_id in enumerate(selected_ids[1:]):
                connection.execute(metadata.tables["host_links"].insert().values(
                    owner_host_id=owner_id, member_host_id=member_id, position=index))
            for family in families:
                connection.execute(metadata.tables["host_subscription_templates"].insert().values(
                    host_id=owner_id, format=family, template_id=bindings[source["id"]][family]))
            groups = {row["group_id"] for row in rows["host_group_hosts"] if row["host_id"] in member_ids}
            for group_id in groups:
                connection.execute(metadata.tables["host_group_hosts"].insert().values(
                    host_id=owner_id, group_id=group_id))
