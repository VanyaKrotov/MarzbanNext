"""Format-specific assembly over an already authorized, resolved endpoint pool."""

from copy import deepcopy

from app.subscription.contracts import SubscriptionError
from app.subscription.template_directives import selected_sources, take_include, validate_directives


def append_unique(existing, incoming):
    return list(dict.fromkeys([*existing, *incoming]))


def required_sources(document, profile, target):
    """Avoid building unused hidden endpoints, including executing their optional mappers."""
    document = deepcopy(document)
    validate_directives(document, target)
    required = set(profile.visible_ids)
    sections = document.get("outbounds", []) if target == "sing-box" else (
        document.get("proxy-groups", []) + list(document.get("proxy-providers", {}).values()))
    for node in sections:
        options = take_include(node, target)
        if options is not None and options.includeProxies:
            required.update(item.host_id for item in selected_sources(profile, options))
    return [connection for connection in profile.sources if connection.host_id in required]


def assemble_clash(document, profile, nodes, diagnostics):
    validate_directives(document, "clash")
    visible = [nodes[host_id]["name"] for host_id in profile.visible_ids if host_id in nodes]
    required = set(profile.visible_ids)
    has_provider_sources = False
    for group in document.get("proxy-groups", []):
        options = take_include(group, "clash")
        if options is not None and not options.includeProxies:
            continue
        sources = selected_sources(profile, options, diagnostics=diagnostics) if options is not None else []
        names = [nodes[item.host_id]["name"] for item in sources if item.host_id in nodes]
        if options is None:
            names = visible
        required.update(item.host_id for item in sources)
        group["proxies"] = append_unique(group.get("proxies") or [], names)
        if options is not None and not group["proxies"] and not group.get("use"):
            return None
    for provider in document.get("proxy-providers", {}).values():
        options = take_include(provider, "clash")
        if options is None or not options.includeProxies:
            continue
        sources = selected_sources(profile, options, diagnostics=diagnostics)
        provider["payload"] = [deepcopy(nodes[item.host_id]) for item in sources if item.host_id in nodes]
        if not provider["payload"]:
            return None
        has_provider_sources = True
    if not required and not has_provider_sources:
        return None
    generated = [nodes[host_id] for host_id in nodes if host_id in required]
    # Jinja templates may already have inserted conf.proxies; append only missing endpoints.
    existing = {node["name"]: node for node in document["proxies"]}
    for node in generated:
        if node["name"] in existing:
            if existing[node["name"]] != node:
                raise SubscriptionError("Template proxy conflicts with a generated proxy")
        else:
            document["proxies"].append(deepcopy(node))
    return document


def assemble_singbox(document, profile, nodes, diagnostics):
    validate_directives(document, "sing-box")
    required = set(profile.visible_ids)
    generated_tags = {node["tag"] for node in nodes.values()}
    groups = [node for node in document["outbounds"] if node["tag"] not in generated_tags]
    for group in groups:
        options = take_include(group, "sing-box")
        if options is None or not options.includeProxies:
            continue
        sources = selected_sources(profile, options, diagnostics=diagnostics)
        selected = [nodes[item.host_id]["tag"] for item in sources if item.host_id in nodes]
        if group.get("type") == "selector" and options.selector is None:
            selected.extend(node["tag"] for node in groups
                            if node.get("type") == "urltest" and node["tag"] != group["tag"])
        group["outbounds"] = list(dict.fromkeys(selected))
        required.update(item.host_id for item in sources)
        if not group["outbounds"]:
            return None
    if not required:
        return None
    document["outbounds"] = groups + [deepcopy(node) for host_id, node in nodes.items() if host_id in required]
    return document
