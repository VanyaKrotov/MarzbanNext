"""Frozen conversion of host composition into native template configuration."""

from copy import deepcopy
import json

import sqlalchemy as sa


TABLES = ("hosts", "host_links", "subscription_templates", "host_subscription_templates", "host_group_hosts")


def read_snapshot(connection, names=TABLES):
    result = {}
    for name in names:
        table = sa.Table(name, sa.MetaData(), autoload_with=connection)
        result[name] = [dict(row) for row in connection.execute(table.select()).mappings()]
    return result


def encode_snapshot(snapshot):
    return json.loads(json.dumps(snapshot, default=lambda value: value.isoformat()))


def options_for(settings, target):
    result = {"strategy": "least_ping", "probe_url": "https://www.gstatic.com/generate_204", "probe_interval": 300}
    result.update(deepcopy(settings or {}))
    result.update(result.pop("clients", {}).get(target, {}))
    return result


def wrap_template(source, overlay, target):
    # Capture the original source, retaining Jinja expressions and user-defined sections verbatim.
    return ("{% set original_config %}" + source + "{% endset %}\n"
            "{% set composition_config %}" + json.dumps(overlay, ensure_ascii=False) + "{% endset %}\n"
            "{{ original_config | merge_config(composition_config, " + json.dumps(target) + ") | tojson }}")


def wrap_aggregate(source, entries, target):
    # Keep an old disabled/forbidden owner's group dormant; members cannot grant owner access.
    parts = ["{% set composition_nodes = [] %}"]
    for owner_id, node in entries:
        parts.append("{% if " + str(owner_id) + " in host_ids %}{% set composition_nodes = composition_nodes + ["
                     + repr(node) + "] %}{% endif %}")
    if target == "clash":
        parts.append("{% set proxy_remarks = proxy_remarks + (composition_nodes | map(attribute='name')"
                     " | map('format_variables') | list) %}")
    parts.extend(["{% set original_config %}", source, "{% endset %}\n{% set composition_config %}{\"",
                  "proxy-groups" if target == "clash" else "outbounds",
                  "\": {{ composition_nodes | tojson }}}{% endset %}\n",
                  "{{ original_config | merge_config(composition_config, " + json.dumps(target) + ") | tojson }}"])
    return "".join(parts)


def xray_overlay(owner, members, options):
    prefix = f"mb-auto-{owner['id']}-"
    strategy = {"type": {"least_ping": "leastPing", "least_load": "leastLoad", "random": "random",
                         "round_robin": "roundRobin"}[options["strategy"]]}
    settings = {}
    for key, value in options.get("strategy_settings", {}).items():
        if key == "max_rtt_ms":
            settings["maxRTT"] = f"{value}ms"
        elif key == "failure_tolerance":
            settings["tolerance"] = value
        elif key == "baselines_ms":
            settings["baselines"] = [f"{item}ms" for item in value]
        elif key == "costs":
            settings[key] = [{"regexp": False, "match": f"{prefix}host-{item['host_id']}", "value": item["value"]}
                             for item in value]
        else:
            settings[key] = value
    if settings:
        strategy["settings"] = settings
    overlay = {
        "marzban": {"addVirtualHostAsOutbound": False, "injectHosts": [
            {"selector": {"type": "ids", "values": [host_id]}, "selectFrom": "ALL",
             "tagPrefix": f"{prefix}host-{host_id}"} for host_id in members]},
        "routing": {"balancers": [{"tag": prefix + "balancer", "selector": [prefix + "host-"],
                                   "strategy": strategy}]},
    }
    if options["strategy"] in {"least_ping", "least_load"}:
        overlay["observatory"] = {"subjectSelector": [prefix + "host-"], "probeUrl": options["probe_url"],
                                  "probeInterval": f"{options['probe_interval']}s",
                                  "enableConcurrency": options.get("enable_concurrency", True)}
    return overlay


def convert(snapshot):
    """Prepare every transformation before the migration performs its first DDL statement."""
    result = deepcopy(snapshot)
    hosts = {host["id"]: host for host in result["hosts"]}
    templates = {template["id"]: template for template in result["subscription_templates"]}
    bindings = {(row["host_id"], row["format"]): row["template_id"]
                for row in result["host_subscription_templates"]}
    links = {}
    for link in sorted(result["host_links"], key=lambda row: row["position"]):
        links.setdefault(link["owner_host_id"], []).append(link["member_host_id"])
    owners = [host for host in hosts.values() if host["balancer_settings"] is not None or host["id"] in links]
    next_host = max(hosts, default=0) + 1
    next_template = max(templates, default=0) + 1
    overlays = {}
    for owner in owners:
        members = [owner["id"], *links.get(owner["id"], [])]
        for target in ("v2ray-json", "clash", "sing-box"):
            template_id = bindings.get((owner["id"], target))
            if template_id is None:
                continue
            options = options_for(owner["balancer_settings"], target)
            strategies = {"v2ray-json": {"least_ping", "least_load", "random", "round_robin"},
                          "clash": {"least_ping", "round_robin"}, "sing-box": {"least_ping"}}
            if options["strategy"] not in strategies[target]:
                raise RuntimeError(f"Host {owner['id']}: unsupported legacy strategy for {target}")
            if target == "v2ray-json":
                template = deepcopy(templates[template_id])
                overlay = xray_overlay(owner, members, options)
                # Rewriting proxy routing is explicit and checked; native user rules retain their order.
                template["id"] = next_template
                template["name"] = f"Migrated Xray host {owner['id']} ({next_template})"
                used_names = {row["name"] for row in result["subscription_templates"] if row["format"] == target}
                while template["name"] in used_names:
                    template["name"] += "_"
                template["default_marker"] = None
                template["content"] = wrap_template(template["content"], overlay, target)
                template["content"] = "{% set migrated %}" + template["content"] + (
                    "{% endset %}{{ migrated | migrate_xray_routing(" + json.dumps(
                        f"mb-auto-{owner['id']}-balancer") + ") | tojson }}")
                result["subscription_templates"].append(template)
                recipient = deepcopy(owner)
                recipient.update(id=next_host, balancer_settings=None, show_when_composed=True,
                                 remark=options.get("remark") or owner["remark"] + " · Auto")
                if len(recipient["remark"]) > 256:
                    raise RuntimeError(f"Host {owner['id']}: shorten the composite remark to at most 256 characters")
                result["hosts"].append(recipient)
                result["host_subscription_templates"].append({"host_id": next_host, "format": target,
                                                              "template_id": next_template})
                for group in snapshot["host_group_hosts"]:
                    if group["host_id"] == owner["id"]:
                        result["host_group_hosts"].append(dict(group, host_id=next_host))
                next_host += 1
                next_template += 1
            else:
                node = {"name" if target == "clash" else "tag":
                        options.get("remark") or owner["remark"] + " · Auto"}
                selection = {"selector": {"type": "ids", "values": members}, "selectFrom": "ALL"}
                if target == "clash":
                    node.update(type="url-test" if options["strategy"] == "least_ping" else "load-balance",
                                url=options["probe_url"], interval=options["probe_interval"], proxies=[],
                                marzban=dict(selection, **{"include-proxies": True}))
                    if options["strategy"] == "round_robin":
                        node["strategy"] = "round-robin"
                    node.update({key: options[key] for key in ("tolerance", "lazy") if key in options})
                else:
                    node.update(type="urltest", url=options["probe_url"], interval=f"{options['probe_interval']}s",
                                outbounds=[], marzban=dict(selection, includeProxies=True))
                    if "tolerance" in options:
                        node["tolerance"] = options["tolerance"]
                    if "idle_timeout" in options:
                        node["idle_timeout"] = f"{options['idle_timeout']}s"
                    if "interrupt_existing_connections" in options:
                        node["interrupt_exist_connections"] = options["interrupt_existing_connections"]
                # Only one common template per aggregate response; source templates remain separate.
                overlays.setdefault((target, template_id), []).append((owner["id"], node))
    for (target, template_id), entries in overlays.items():
        used = {row["template_id"] for row in result["host_subscription_templates"] if row["format"] == target
                and hosts.get(row["host_id"], {}).get("enabled", False)
                and hosts[row["host_id"]]["show_when_composed"]}
        if used - {template_id}:
            raise RuntimeError(f"{target}: incompatible aggregate templates {sorted(used | {template_id})}; "
                               "assign one shared template before upgrading")
        if not used and any(hosts[owner_id]["enabled"] for owner_id, _ in entries):
            raise RuntimeError(f"{target}: all hosts are hidden; keep one visible recipient before upgrading")
        template = templates[template_id]
        template["content"] = wrap_aggregate(template["content"], entries, target)
    # Persist only the new host contract; archives retain every removed value.
    for host in result["hosts"]:
        host["is_hidden"] = not host.pop("show_when_composed")
        host.pop("balancer_settings")
    result.pop("host_links")
    return result
