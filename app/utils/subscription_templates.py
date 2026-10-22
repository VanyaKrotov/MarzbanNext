import json
from uuid import UUID

import yaml
from jinja2 import StrictUndefined, TemplateError, pass_context
from jinja2.sandbox import SandboxedEnvironment

from app.models.subscription_template import SubscriptionFormat
from app.templates import env
from app.utils.helpers import UUIDEncoder

template_env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
template_env.filters.update(env.filters)
template_env.globals["now"] = env.globals["now"]
template_env.policies["json.dumps_kwargs"] = {"sort_keys": True, "cls": UUIDEncoder}


@pass_context
def merge_config(context, source, additions, format):
    """Preserve a complete Jinja template while appending native configuration sections."""
    document = parse_subscription_document(SubscriptionFormat(format), source)
    overlay = yaml.safe_load(additions)
    for node in overlay.get("proxy-groups", []) + overlay.get("outbounds", []):
        for key in ("name", "tag"):
            if key in node:
                node[key] = format_variables(context, node[key])

    def merge(current, extra):
        for key, value in extra.items():
            if key not in current:
                current[key] = value
            elif isinstance(value, list) and isinstance(current[key], list):
                if key in {"outbounds", "proxy-groups", "balancers"}:
                    identity = "name" if key == "proxy-groups" else "tag"
                    existing = {node.get(identity) for node in current[key] if isinstance(node, dict)}
                    incoming = [node.get(identity) for node in value if isinstance(node, dict)]
                    if existing.intersection(incoming) or len(incoming) != len(set(incoming)):
                        raise TemplateValidationError(f"Template composition contains duplicate {identity} values")
                current[key].extend(value)
            elif isinstance(value, dict) and isinstance(current[key], dict):
                merge(current[key], value)
            elif current[key] != value:
                raise TemplateValidationError(f"Template composition conflicts at {key}")
        return current

    return merge(document, overlay)


template_env.filters["merge_config"] = merge_config


@pass_context
def format_variables(context, value):
    from app.models.proxy import FormatVariables

    return value.format_map(FormatVariables(context.get_all()))


template_env.filters["format_variables"] = format_variables


def migrate_xray_routing(source, balancer_tag, owner_id=None, host_ids=None):
    document = parse_subscription_document(SubscriptionFormat.v2ray_json, source)
    if host_ids is not None:
        available = set(host_ids)
        directives = document.get("marzban", {})
        # Legacy members were optional. Keep the owner's injection mandatory, while
        # retaining stable per-host tags and costs for available optional members.
        directives["injectHosts"] = [entry for entry in directives.get("injectHosts", [])
                                     if any(host_id == owner_id or host_id in available
                                            for host_id in entry.get("selector", {}).get("values", []))]
        tags = {entry["tagPrefix"] for entry in directives["injectHosts"]}
        for balancer in document.get("routing", {}).get("balancers", []):
            if balancer.get("tag") == balancer_tag:
                settings = balancer.get("strategy", {}).get("settings", {})
                if "costs" in settings:
                    settings["costs"] = [cost for cost in settings["costs"] if cost.get("match") in tags]
    rules = document.setdefault("routing", {}).setdefault("rules", [])
    for rule in rules:
        if rule.get("outboundTag") == "proxy":
            rule.pop("outboundTag")
            rule["balancerTag"] = balancer_tag
    rules.append({"type": "field", "network": "tcp,udp", "balancerTag": balancer_tag})
    return document


template_env.filters["migrate_xray_routing"] = migrate_xray_routing


def preserve_clash_groups(source):
    """Keep legacy explicit membership when adopting template-controlled proxy injection."""
    document = parse_subscription_document(SubscriptionFormat.clash, source)
    for group in document.get("proxy-groups", []):
        group.setdefault("marzban", {"include-proxies": False})
    return document


template_env.filters["preserve_clash_groups"] = preserve_clash_groups


class TemplateValidationError(ValueError):
    """The rendered document does not satisfy the selected subscription format."""


def render_subscription_template(content: str, context: dict | None = None) -> str:
    try:
        return template_env.from_string(content).render(context or {})
    except (TemplateError, ValueError, TypeError, AttributeError, ArithmeticError, yaml.YAMLError) as exc:
        raise TemplateValidationError(f"Template rendering failed: {exc}") from exc


def parse_subscription_document(format: SubscriptionFormat, rendered: str) -> dict:
    try:
        document = yaml.safe_load(rendered) if format == SubscriptionFormat.clash else json.loads(rendered)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise TemplateValidationError(f"Invalid {format.value} configuration: {exc}") from exc
    if not isinstance(document, dict):
        raise TemplateValidationError("The template must render an object")
    if format in (SubscriptionFormat.v2ray_json, SubscriptionFormat.sing_box) and (
        not isinstance(document.get("outbounds"), list) or any(
            not isinstance(outbound, dict) for outbound in document["outbounds"]
        )
    ):
        raise TemplateValidationError("The template must contain an outbounds array of objects")
    if format == SubscriptionFormat.clash:
        for key in ("proxies", "proxy-groups"):
            nodes = document.get(key, [] if key != "proxies" else None)
            if not isinstance(nodes, list) or any(not isinstance(node, dict) for node in nodes):
                raise TemplateValidationError(f"Clash {key} must be an array of objects")
        providers = document.get("proxy-providers", {})
        if not isinstance(providers, dict) or any(not isinstance(value, dict) for value in providers.values()):
            raise TemplateValidationError("Clash proxy-providers must be an object of providers")
    for key in ("routing", "route", "observatory"):
        if key in document and not isinstance(document[key], dict):
            raise TemplateValidationError(f"{key} must be an object")
    for section, keys in (("routing", ("rules", "balancers")), ("route", ("rules",))):
        for key in keys:
            if section in document and key in document[section]:
                values = document[section][key]
                if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
                    raise TemplateValidationError(f"{section}.{key} must be an array of objects")
    return document


def parse_subscription_links(rendered: str) -> list[str]:
    links = [line for line in rendered.splitlines() if line.strip()]
    if any("://" not in line for line in links):
        raise TemplateValidationError("Link templates must render one client URI per line")
    return links


def validate_subscription_template(format: SubscriptionFormat, content: str, extra_context: dict | None = None) -> None:
    sample = {
        "conf": {
            "proxies": [{"name": "Example", "type": "ss", "server": "example.com", "port": 443,
                         "cipher": "aes-256-gcm", "password": "example"}],
            "proxy-groups": [], "rules": [],
        },
        "proxy_remarks": ["Example"],
        "links": ["vless://00000000-0000-0000-0000-000000000000@example.com:443?security=none#Example"],
        "config": {"server": "example.com", "server_port": 443, "method": "aes-256-gcm", "password": "example", "tag": "Example"},
        "host": {
            "id": 1, "host_id": 1, "remark": "Example", "address": "example.com", "port": 443,
            "inbound": {"protocol": "vless", "network": "tcp", "port": 443, "tls": "none"},
            "settings": {"id": UUID(int=0), "password": "example", "method": "aes-256-gcm", "flow": ""},
        },
        "remarks": "Example",
        "host_ids": [1],
    }
    context_keys = {
        SubscriptionFormat.clash: ("conf", "proxy_remarks", "host_ids"),
        SubscriptionFormat.v2ray: ("links", "host"),
        SubscriptionFormat.v2ray_json: ("host", "remarks", "host_ids"),
        SubscriptionFormat.outline: ("config",),
        SubscriptionFormat.sing_box: ("host_ids",),
    }
    rendered = render_subscription_template(content, {
        **{key: sample[key] for key in context_keys[format]}, **(extra_context or {}),
    })
    if format == SubscriptionFormat.v2ray:
        if not parse_subscription_links(rendered):
            raise TemplateValidationError("Link templates must render one client URI per line")
        return
    document = parse_subscription_document(format, rendered)
    from app.subscription.template_directives import validate_directives

    validate_directives(document, format.value)


def validate_generator_settings(key: str, content: str) -> None:
    rendered = render_subscription_template(content)
    try:
        document = yaml.safe_load(rendered) if key == "clash_settings" else json.loads(rendered)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise TemplateValidationError(f"Invalid {key} settings: {exc}") from exc
    if not isinstance(document, dict):
        raise TemplateValidationError(f"{key} settings must contain an object")
    if key in ("user_agent", "grpc_user_agent") and (
        not isinstance(document.get("list"), list)
        or any(not isinstance(value, str) or not value for value in document["list"])
    ):
        raise TemplateValidationError(f"{key} settings must contain a list of non-empty strings")
