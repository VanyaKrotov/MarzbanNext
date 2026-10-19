"""File sources used only when importing defaults, never to resolve a host assignment."""

from pathlib import Path

from config import (
    CLASH_SETTINGS_TEMPLATE,
    CLASH_SUBSCRIPTION_TEMPLATE,
    CUSTOM_TEMPLATES_DIRECTORY,
    GRPC_USER_AGENT_TEMPLATE,
    MUX_TEMPLATE,
    SINGBOX_SETTINGS_TEMPLATE,
    SINGBOX_SUBSCRIPTION_TEMPLATE,
    USER_AGENT_TEMPLATE,
    V2RAY_SETTINGS_TEMPLATE,
    V2RAY_SUBSCRIPTION_TEMPLATE,
)

FULL_TEMPLATE_SOURCES = {
    "clash": ("clash_subscription", CLASH_SUBSCRIPTION_TEMPLATE),
    "sing-box": ("singbox_subscription", SINGBOX_SUBSCRIPTION_TEMPLATE),
    "v2ray-json": ("v2ray_subscription", V2RAY_SUBSCRIPTION_TEMPLATE),
}
GENERATOR_TEMPLATE_SOURCES = {
    "clash_settings": CLASH_SETTINGS_TEMPLATE,
    "singbox_settings": SINGBOX_SETTINGS_TEMPLATE,
    "v2ray_settings": V2RAY_SETTINGS_TEMPLATE,
    "mux": MUX_TEMPLATE,
    "user_agent": USER_AGENT_TEMPLATE,
    "grpc_user_agent": GRPC_USER_AGENT_TEMPLATE,
}
WRAPPER_TEMPLATES = {
    "v2ray": "{{ links | join('\\n') }}",
    "outline": "{{ config | tojson }}",
}


def read_template_source(name: str) -> str:
    roots = [Path(__file__).resolve().parents[1] / "templates"]
    if CUSTOM_TEMPLATES_DIRECTORY:
        roots.insert(0, Path(CUSTOM_TEMPLATES_DIRECTORY))
    for root in roots:
        path = root / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Subscription template source not found: {name}")


def default_subscription_content(format: str) -> str:
    if format in WRAPPER_TEMPLATES:
        return WRAPPER_TEMPLATES[format]
    return read_template_source(FULL_TEMPLATE_SOURCES[format][1])
