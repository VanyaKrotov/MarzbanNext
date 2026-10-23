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


class CompositionConverter:
    """One in-memory transfer plan; no database writes occur during conversion."""

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.result = {name: deepcopy(snapshot[name]) for name in TABLES}
        for template in self.result["subscription_templates"]:
            template["migration_settings"] = None
        self.hosts = {host["id"]: host for host in self.result["hosts"]}
        self.inbounds = {row["id"]: row for row in snapshot["inbounds"]}
        self.templates = {row["id"]: row for row in self.result["subscription_templates"]}
        self.bindings = {(row["host_id"], row["format"]): row["template_id"]
                         for row in self.result["host_subscription_templates"]}
        # MySQL/MariaDB DATETIME stores whole seconds; archive the value that will actually be persisted.
        self.now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
        self.next_host_id = max(self.hosts, default=0) + 1
        self.next_template_id = max(self.templates, default=0) + 1
        self.next_position = max((host["position"] for host in self.hosts.values()), default=-1) + 1
        self.aggregate_entries = {}

    def convert(self):
        from app.db.migrations.host_redesign_v1 import COMPOSITE_FORMATS

        self._normalize_hosts()
        balancers = sorted(self.snapshot["subscription_balancers"], key=lambda row: (row["position"], row["id"]))
        for balancer in balancers:
            if balancer["strategy"] not in {"least_ping", "least_load", "random", "round_robin"}:
                raise RuntimeError(f"Balancer {balancer['id']}: unsupported strategy {balancer['strategy']}")
            member_ids = {row["host_id"] for row in self.snapshot["subscription_balancer_hosts"]
                          if row["balancer_id"] == balancer["id"]}
            for target in COMPOSITE_FORMATS:
                members = self._eligible_members(member_ids, target)
                if not members:
                    continue
                template_id = self.bindings[members[0]["id"], target]
                selected_ids = [host["id"] for host in members]
                if target == "v2ray-json":
                    self._append_xray_profile(balancer, members[0], selected_ids, member_ids, template_id)
                else:
                    node = aggregate_node(balancer, selected_ids, target)
                    entry = {"member_ids": selected_ids, "enabled": bool(balancer["enabled"]), "node": node}
                    self.aggregate_entries.setdefault((target, template_id), []).append(entry)
        self._update_aggregate_templates()
        return self.result

    def _normalize_hosts(self):
        from app.db.migrations.host_redesign_v1 import legacy_overrides

        for host in self.hosts.values():
            overrides = legacy_overrides(host, self.inbounds[host["inbound_id"]])
            normalized = {key: host[key] for key in ("id", "remark", "address", "inbound_id", "position")}
            normalized.update(port=host["port"] or None, enabled=not bool(host["is_disabled"]),
                              is_hidden=False, overrides=overrides, created_at=self.now, updated_at=self.now)
            host.clear()
            host.update(normalized)

    def _eligible_members(self, member_ids, target):
        from app.db.migrations.host_redesign_v1 import supports_family

        members = [self.hosts[host_id] for host_id in member_ids
                   if (host_id, target) in self.bindings
                   and supports_family(target, self.inbounds[self.hosts[host_id]["inbound_id"]])]
        return sorted(members, key=lambda host: (not host["enabled"], host["position"], host["id"]))

    def _append_xray_profile(self, balancer, source, selected_ids, member_ids, template_id):
        template = deepcopy(self.templates[template_id])
        name = f"Migrated Xray balancer {balancer['id']} ({self.next_template_id})"
        used_names = {row["name"] for row in self.result["subscription_templates"] if row["format"] == "v2ray-json"}
        while name in used_names:
            name += "_"
        template.update(id=self.next_template_id, default_marker=None, name=name)
        # Stable per-host tags preserve selectors when an optional member becomes unavailable.
        template["migration_settings"] = {
            "version": 1, "overlay": xray_overlay(balancer, selected_ids),
            "xray_balancer_tag": f"mb-auto-{balancer['id']}-balancer",
        }
        self.result["subscription_templates"].append(template)
        recipient = deepcopy(source)
        recipient.update(id=self.next_host_id, remark=balancer["name"], enabled=bool(balancer["enabled"]),
                         position=self.next_position, created_at=balancer["created_at"],
                         updated_at=balancer["updated_at"])
        self.result["hosts"].append(recipient)
        self.result["host_subscription_templates"].append({
            "host_id": self.next_host_id, "format": "v2ray-json", "template_id": self.next_template_id,
        })
        groups = {row["group_id"] for row in self.snapshot["host_group_hosts"] if row["host_id"] in member_ids}
        self.result["host_group_hosts"].extend({"host_id": self.next_host_id, "group_id": group_id}
                                               for group_id in sorted(groups))
        self.next_host_id += 1
        self.next_template_id += 1
        self.next_position += 1

    def _update_aggregate_templates(self):
        for (target, template_id), entries in self.aggregate_entries.items():
            used = {row["template_id"] for row in self.result["host_subscription_templates"]
                    if row["format"] == target and self.hosts.get(row["host_id"], {}).get("enabled", False)}
            if used - {template_id}:
                raise RuntimeError(f"{target}: incompatible aggregate templates {sorted(used | {template_id})}; "
                                   "assign one shared template before upgrading")
            template = self.templates[template_id]
            template["migration_settings"] = {"version": 1, "aggregate": entries}
        for template in self.result["subscription_templates"]:
            if template["format"] == "clash":
                settings = template["migration_settings"] or {"version": 1}
                template["migration_settings"] = dict(settings, preserve_clash_groups=True)


def convert(snapshot):
    """Convert master rows directly to the final schema without touching the source snapshot."""
    return CompositionConverter(snapshot).convert()


def validate_conversion(original, converted):
    from app.models.subscription_template import SubscriptionFormat
    from app.utils.subscription_templates import validate_subscription_template

    before = {row["id"]: row["content"] for row in original["subscription_templates"]}
    context = {"host_ids": [row["id"] for row in original["hosts"]]}
    for template in converted["subscription_templates"]:
        if template["migration_settings"] or before.get(template["id"]) != template["content"]:
            try:
                validate_subscription_template(SubscriptionFormat(template["format"]), template["content"], context,
                                               template["migration_settings"])
            except ValueError as exc:
                raise RuntimeError(f"Template {template['id']} cannot be migrated safely: {exc}") from exc


def prepare(connection):
    """Build and validate one complete transfer plan for both CLI and Alembic."""
    from app.db.migrations.host_redesign_v1 import inspect_legacy

    original = read_snapshot(connection, LEGACY_TABLES)
    report = inspect_legacy(original)
    groups = sa.Table("host_groups", sa.MetaData(), autoload_with=connection)
    group_ids = set(connection.execute(sa.select(groups.c.id)).scalars())
    host_ids = {host["id"] for host in original["hosts"]}
    for link in original["host_group_hosts"]:
        if link["host_id"] not in host_ids or link["group_id"] not in group_ids:
            report["errors"].append({"host_id": link["host_id"], "group_id": link["group_id"],
                                     "reason": "dangling_host_group"})
    converted = None
    if not report["errors"]:
        try:
            converted = convert(original)
            validate_conversion(original, converted)
        except (ValueError, RuntimeError) as exc:
            report["errors"].append({"reason": str(exc)})
    return original, converted, report
