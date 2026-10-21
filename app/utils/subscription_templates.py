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
    if format == SubscriptionFormat.clash and not isinstance(document.get("proxies"), list):
        raise TemplateValidationError("Clash templates must contain a proxies array")
    return document


def parse_subscription_links(rendered: str) -> list[str]:
    links = [line for line in rendered.splitlines() if line.strip()]
    if any("://" not in line for line in links):
        raise TemplateValidationError("Link templates must render one client URI per line")
    return links


def validate_subscription_template(format: SubscriptionFormat, content: str) -> None:
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
    }
    context_keys = {
        SubscriptionFormat.clash: ("conf", "proxy_remarks"),
        SubscriptionFormat.v2ray: ("links", "host"),
        SubscriptionFormat.v2ray_json: ("host", "remarks"),
        SubscriptionFormat.outline: ("config",),
        SubscriptionFormat.sing_box: (),
    }
    rendered = render_subscription_template(content, {key: sample[key] for key in context_keys[format]})
    if format == SubscriptionFormat.v2ray:
        if not parse_subscription_links(rendered):
            raise TemplateValidationError("Link templates must render one client URI per line")
        return
    parse_subscription_document(format, rendered)


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
