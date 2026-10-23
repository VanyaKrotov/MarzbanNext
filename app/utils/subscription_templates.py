import json
from uuid import UUID

import yaml
from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment

from app.models.subscription_template import SubscriptionFormat
from app.templates import env
from app.utils.helpers import UUIDEncoder

template_env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
template_env.filters.update(env.filters)
template_env.globals["now"] = env.globals["now"]
template_env.policies["json.dumps_kwargs"] = {"sort_keys": True, "cls": UUIDEncoder}


class TemplateValidationError(ValueError):
    """The rendered document does not satisfy the selected subscription format."""


def render_subscription_template(content: str, context: dict | None = None) -> str:
    try:
        return template_env.from_string(content).render(context or {})
    except (TemplateError, ValueError, TypeError, AttributeError, ArithmeticError, yaml.YAMLError) as exc:
        raise TemplateValidationError(f"Template rendering failed: {exc}") from exc


def render_template_document(format: SubscriptionFormat, content: str, context: dict | None = None,
                             migration_settings: dict | None = None) -> dict:
    from app.subscription.template_migration import apply_template_migration, migration_context

    try:
        context = migration_context(migration_settings or {}, context or {})
        document = parse_subscription_document(format, render_subscription_template(content, context))
        return apply_template_migration(document, migration_settings, format.value, context)
    except TemplateValidationError:
        raise
    except (ValueError, TypeError, AttributeError, ArithmeticError) as exc:
        raise TemplateValidationError(f"Template migration failed: {exc}") from exc


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


def validate_subscription_template(format: SubscriptionFormat, content: str, extra_context: dict | None = None,
                                   migration_settings: dict | None = None) -> None:
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
    if migration_settings:
        # Exercise all saved groups when validating edits, including groups outside the sample host pool.
        host_ids = {1}
        for entry in migration_settings.get("aggregate", ()):
            host_ids.update(entry["member_ids"])
        injections = migration_settings.get("overlay", {}).get("marzban", {}).get("injectHosts", ())
        for entry in injections:
            host_ids.update(entry["selector"]["values"])
        sample["host_ids"] = sorted(host_ids)
    context = {
        **{key: sample[key] for key in context_keys[format]}, **(extra_context or {}),
    }
    if format == SubscriptionFormat.v2ray:
        if not parse_subscription_links(render_subscription_template(content, context)):
            raise TemplateValidationError("Link templates must render one client URI per line")
        return
    document = render_template_document(format, content, context, migration_settings)
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
