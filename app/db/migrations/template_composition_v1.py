"""Frozen conversion of host composition into native template configuration."""

from copy import deepcopy
from datetime import UTC, datetime
import json

import sqlalchemy as sa


TABLES = ("hosts", "subscription_templates", "host_subscription_templates", "host_group_hosts")
LEGACY_TABLES = (*TABLES, "inbounds", "subscription_balancers", "subscription_balancer_hosts")


def read_snapshot(connection, names=TABLES):
    result = {}
    for name in names:
        table = sa.Table(name, sa.MetaData(), autoload_with=connection)
        result[name] = [dict(row) for row in connection.execute(table.select()).mappings()]
    return result


def encode_snapshot(snapshot):
    return json.loads(json.dumps(snapshot, default=lambda value: value.isoformat()))


def wrap_template(source, overlay, target):
    # Capture the original source, retaining Jinja expressions and user-defined sections verbatim.
    return ("{% set original_config %}" + source + "{% endset %}\n"
            "{% set composition_config %}" + json.dumps(overlay, ensure_ascii=False) + "{% endset %}\n"
            "{{ original_config | merge_config(composition_config, " + json.dumps(target) + ") | tojson }}")


def wrap_aggregate(source, entries, target):
    # Disabled balancers retain their native configuration but never enter the response.
    parts = ["{% set composition_nodes = [] %}"]
    for member_ids, node in entries:
        parts.append("{% if " + repr(member_ids) + " | select('in', host_ids) | list %}"
                     "{% set composition_nodes = composition_nodes + ["
                     + repr(node) + "] %}{% endif %}")
    if target == "clash":
        parts.append("{% set proxy_remarks = proxy_remarks + (composition_nodes | map(attribute='name')"
                     " | map('format_variables') | list) %}")
    parts.extend(["{% set original_config %}", source, "{% endset %}\n{% set composition_config %}{\"",
                  "proxy-groups" if target == "clash" else "outbounds",
                  "\": {{ composition_nodes | tojson }}}{% endset %}\n",
                  "{{ original_config | merge_config(composition_config, " + json.dumps(target) + ") | tojson }}"])
    return "".join(parts)


def xray_overlay(balancer, members):
    prefix = f"mb-auto-{balancer['id']}-"
    strategy = {"type": {"least_ping": "leastPing", "least_load": "leastLoad", "random": "random",
                         "round_robin": "roundRobin"}[balancer["strategy"]]}
    overlay = {
        "marzban": {"addVirtualHostAsOutbound": False, "injectHosts": [
            {"selector": {"type": "ids", "values": [host_id]}, "selectFrom": "ALL",
             "tagPrefix": f"{prefix}host-{host_id}"} for host_id in members]},
        "routing": {"balancers": [{"tag": prefix + "balancer", "selector": [prefix + "host-"],
                                   "strategy": strategy}]},
    }
    if balancer["strategy"] in {"least_ping", "least_load"}:
        overlay["observatory"] = {"subjectSelector": [prefix + "host-"], "probeUrl": balancer["probe_url"],
                                  "probeInterval": f"{balancer['probe_interval']}s",
                                  "enableConcurrency": True}
    return overlay


def aggregate_node(balancer, members, target):
    selection = {"selector": {"type": "ids", "values": members}, "selectFrom": "ALL"}
    node = {"name" if target == "clash" else "tag": balancer["name"]}
    if target == "clash":
        round_robin = balancer["strategy"] == "round_robin"
        node.update(type="load-balance" if round_robin else "url-test", url=balancer["probe_url"],
                    interval=balancer["probe_interval"], proxies=[],
                    marzban=dict(selection, **{"include-proxies": True}))
        if round_robin:
            node["strategy"] = "round-robin"
    else:
        node.update(type="urltest", url=balancer["probe_url"], interval=f"{balancer['probe_interval']}s",
                    outbounds=[], marzban=dict(selection, includeProxies=True))
    return node


def convert(snapshot):
    """Convert master rows straight to the final schema, without synthetic composition owners."""
    from app.db.migrations.host_redesign_v1 import COMPOSITE_FORMATS, legacy_overrides, supports_family

    result = {name: deepcopy(snapshot[name]) for name in TABLES}
    hosts = {host["id"]: host for host in result["hosts"]}
    inbounds = {row["id"]: row for row in snapshot["inbounds"]}
    templates = {row["id"]: row for row in result["subscription_templates"]}
    bindings = {(row["host_id"], row["format"]): row["template_id"]
                for row in result["host_subscription_templates"]}
    now = datetime.now(UTC).replace(tzinfo=None)
    for host in hosts.values():
        overrides = legacy_overrides(host, inbounds[host["inbound_id"]])
        normalized = {key: host[key] for key in ("id", "remark", "address", "inbound_id", "position")}
        normalized.update(port=host["port"] or None, enabled=not bool(host["is_disabled"]), is_hidden=False,
                          overrides=overrides, created_at=now, updated_at=now)
        host.clear()
        host.update(normalized)
    next_host = max(hosts, default=0) + 1
    next_template = max(templates, default=0) + 1
    position = max((host["position"] for host in hosts.values()), default=-1) + 1
    overlays = {}
    for balancer in sorted(snapshot["subscription_balancers"], key=lambda row: (row["position"], row["id"])):
        if balancer["strategy"] not in {"least_ping", "least_load", "random", "round_robin"}:
            raise RuntimeError(f"Balancer {balancer['id']}: unsupported strategy {balancer['strategy']}")
        member_ids = {row["host_id"] for row in snapshot["subscription_balancer_hosts"]
                      if row["balancer_id"] == balancer["id"]}
        for target in COMPOSITE_FORMATS:
            members = sorted((hosts[host_id] for host_id in member_ids
                              if (host_id, target) in bindings
                              and supports_family(target, inbounds[hosts[host_id]["inbound_id"]])),
                             key=lambda host: (not host["enabled"], host["position"], host["id"]))
            if not members:
                continue
            source = members[0]
            selected_ids = [host["id"] for host in members]
            template_id = bindings[source["id"], target]
            if target != "v2ray-json":
                node = aggregate_node(balancer, selected_ids, target)
                overlays.setdefault((target, template_id), []).append(
                    (selected_ids if balancer["enabled"] else [], node))
                continue
            template = deepcopy(templates[template_id])
            template.update(id=next_template, default_marker=None,
                            name=f"Migrated Xray balancer {balancer['id']} ({next_template})")
            used_names = {row["name"] for row in result["subscription_templates"] if row["format"] == target}
            while template["name"] in used_names:
                template["name"] += "_"
            # Balancer IDs form their own namespace; no temporary host IDs enter selectors.
            overlay = xray_overlay(balancer, selected_ids)
            template["content"] = wrap_template(template["content"], overlay, target)
            template["content"] = "{% set migrated %}" + template["content"] + (
                "{% endset %}{{ migrated | migrate_xray_routing(" + json.dumps(
                    f"mb-auto-{balancer['id']}-balancer") + ", none, host_ids) | tojson }}")
            result["subscription_templates"].append(template)
            recipient = deepcopy(source)
            recipient.update(id=next_host, remark=balancer["name"], enabled=bool(balancer["enabled"]),
                             position=position, created_at=balancer["created_at"], updated_at=balancer["updated_at"])
            result["hosts"].append(recipient)
            result["host_subscription_templates"].append({"host_id": next_host, "format": target,
                                                          "template_id": next_template})
            groups = {row["group_id"] for row in snapshot["host_group_hosts"] if row["host_id"] in member_ids}
            result["host_group_hosts"].extend({"host_id": next_host, "group_id": group_id}
                                              for group_id in sorted(groups))
            next_host += 1
            next_template += 1
            position += 1
    for (target, template_id), entries in overlays.items():
        used = {row["template_id"] for row in result["host_subscription_templates"] if row["format"] == target
                and hosts.get(row["host_id"], {}).get("enabled", False)}
        if used - {template_id}:
            raise RuntimeError(f"{target}: incompatible aggregate templates {sorted(used | {template_id})}; "
                               "assign one shared template before upgrading")
        template = templates[template_id]
        template["content"] = wrap_aggregate(template["content"], entries, target)
    for template in result["subscription_templates"]:
        if template["format"] == "clash":
            template["content"] = ("{% set legacy_clash %}" + template["content"]
                                   + "{% endset %}{{ legacy_clash | preserve_clash_groups | tojson }}")
    return result


def validate_conversion(original, converted):
    from app.models.subscription_template import SubscriptionFormat
    from app.utils.subscription_templates import validate_subscription_template

    before = {row["id"]: row["content"] for row in original["subscription_templates"]}
    context = {"host_ids": [row["id"] for row in original["hosts"]]}
    for template in converted["subscription_templates"]:
        if before.get(template["id"]) != template["content"]:
            try:
                validate_subscription_template(SubscriptionFormat(template["format"]), template["content"], context)
            except ValueError as exc:
                raise RuntimeError(f"Template {template['id']} cannot be migrated safely: {exc}") from exc


def prepare(connection):
    """Build and validate one complete transfer plan for both CLI and Alembic."""
    from app.db.migrations.host_redesign_v1 import inspect_legacy

    original = read_snapshot(connection, LEGACY_TABLES)
    report = inspect_legacy(original)
    converted = None
    if not report["errors"]:
        try:
            converted = convert(original)
            validate_conversion(original, converted)
        except (ValueError, RuntimeError) as exc:
            report["errors"].append({"reason": str(exc)})
    return original, converted, report
