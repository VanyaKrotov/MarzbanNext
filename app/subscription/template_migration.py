"""Apply archived balancer settings to rendered documents, never to Jinja source."""

from copy import deepcopy


def _active_entries(settings, context):
    available = set(context.get("host_ids", ()))
    return [entry for entry in settings.get("aggregate", ())
            if entry["enabled"] and available.intersection(entry["member_ids"])]


def migration_context(settings, context):
    """Legacy Clash selectors also referenced balancer names through proxy_remarks."""
    from app.models.proxy import FormatVariables

    context = dict(context)
    if "proxy_remarks" in context:
        names = [entry["node"]["name"].format_map(FormatVariables(context))
                 for entry in _active_entries(settings, context)]
        context["proxy_remarks"] = [*context["proxy_remarks"], *names]
    return context


def _merge(document, overlay):
    from app.utils.subscription_templates import TemplateValidationError

    for key, value in overlay.items():
        if key not in document:
            document[key] = deepcopy(value)
        elif isinstance(value, list) and isinstance(document[key], list):
            if key in {"outbounds", "proxy-groups", "balancers"}:
                identity = "name" if key == "proxy-groups" else "tag"
                existing = {node.get(identity) for node in document[key] if isinstance(node, dict)}
                incoming = [node.get(identity) for node in value if isinstance(node, dict)]
                if existing.intersection(incoming) or len(incoming) != len(set(incoming)):
                    raise TemplateValidationError(f"Template composition contains duplicate {identity} values")
            document[key].extend(deepcopy(value))
        elif isinstance(value, dict) and isinstance(document[key], dict):
            _merge(document[key], value)
        elif document[key] != value:
            raise TemplateValidationError(f"Template composition conflicts at {key}")


def _xray_routing(document, balancer_tag, context):
    available = set(context.get("host_ids", ()))
    directives = document["marzban"]
    directives["injectHosts"] = [entry for entry in directives["injectHosts"]
                                 if available.intersection(entry["selector"]["values"])]
    tags = {entry["tagPrefix"] for entry in directives["injectHosts"]}
    for balancer in document["routing"]["balancers"]:
        if balancer.get("tag") == balancer_tag:
            settings = balancer.get("strategy", {}).get("settings", {})
            if "costs" in settings:
                settings["costs"] = [cost for cost in settings["costs"] if cost.get("match") in tags]
    rules = document["routing"].setdefault("rules", [])
    for rule in rules:
        if rule.get("outboundTag") == "proxy":
            rule.pop("outboundTag")
            rule["balancerTag"] = balancer_tag
    rules.append({"type": "field", "network": "tcp,udp", "balancerTag": balancer_tag})


def apply_template_migration(document, settings, target, context):
    """Return an independent document; missing sources retain legacy optionality."""
    from app.models.proxy import FormatVariables
    from app.utils.subscription_templates import TemplateValidationError

    if not settings:
        return document
    if settings.get("version") != 1:
        raise TemplateValidationError("Unsupported template migration settings version")
    document = deepcopy(document)
    overlay = deepcopy(settings.get("overlay", {}))
    entries = _active_entries(settings, context)
    if entries:
        section = "proxy-groups" if target == "clash" else "outbounds"
        overlay.setdefault(section, []).extend(deepcopy(entry["node"]) for entry in entries)
    for node in overlay.get("proxy-groups", []) + overlay.get("outbounds", []):
        for key in ("name", "tag"):
            if key in node:
                node[key] = node[key].format_map(FormatVariables(context))
    _merge(document, overlay)
    if settings.get("xray_balancer_tag"):
        _xray_routing(document, settings["xray_balancer_tag"], context)
    if settings.get("preserve_clash_groups"):
        for group in document.get("proxy-groups", []):
            group.setdefault("marzban", {"include-proxies": False})
    return document
