"""Detached request data. Builders receive copies and never mutate the loaded snapshot."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class HostSnapshot:
    id: int
    inbound_id: int
    inbound_tag: str
    remark: str
    address: str
    port: int | None
    enabled: bool
    position: int
    is_hidden: bool
    overrides: dict
    group_ids: tuple[str, ...]
    subscription_template_ids: dict[str, int]


@dataclass(frozen=True)
class TemplateSnapshot:
    id: int
    format: str
    content: str
    migration_settings: dict | None = None


@dataclass(frozen=True)
class SubscriptionSnapshot:
    hosts: tuple[HostSnapshot, ...]
    inbounds: dict[int, dict]
    raw_inbounds: dict[int, dict]
    templates: dict[int, TemplateSnapshot]
    defaults: dict[str, str]
    external_config: str = ""
    default_template_ids: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectionInput:
    host: HostSnapshot
    inbound: dict
    raw_inbound: dict
    credentials: dict[str, Any]


@dataclass(frozen=True)
class ResolvedConnection:
    host_id: int
    remark: str
    address: str
    port: int
    inbound: dict
    credentials: dict[str, Any]
    context: dict
    client_options: dict = field(default_factory=dict)
    mapper: dict = field(default_factory=dict)
    stream: dict = field(default_factory=dict)
    mux: dict = field(default_factory=dict)
    raw_inbound: dict = field(default_factory=dict)
    security: dict = field(default_factory=dict)
    transport: dict = field(default_factory=dict)

    def template_record(self):
        from copy import deepcopy

        return deepcopy({
            "id": self.host_id, "host_id": self.host_id, "remark": self.remark,
            "address": self.address, "port": self.port, "inbound": self.inbound,
            "settings": self.credentials,
        })


@dataclass(frozen=True)
class ProfilePlan:
    owner: HostSnapshot
    connections: tuple[ResolvedConnection, ...]
    template: TemplateSnapshot
    remark: str
    sources: tuple[ResolvedConnection, ...] = ()
    hosts: tuple[HostSnapshot, ...] = ()
    visible_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class RenderInput:
    target: str
    profiles: tuple[ProfilePlan, ...]
    defaults: dict[str, str]
    external_config: str = ""
    reverse: bool = False
    as_base64: bool = False
    include_server_description: bool = False


@dataclass(frozen=True)
class GenerationResult:
    body: str
    media_type: str
    profile_count: int
    diagnostics: tuple[dict, ...] = ()


class SubscriptionGenerator(Protocol):
    def generate(self, data: RenderInput) -> GenerationResult: ...


class SubscriptionError(ValueError):
    def __init__(self, detail: str, status_code: int = 422):
        super().__init__(detail)
        self.status_code = status_code
