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
    show_when_composed: bool
    overrides: dict
    balancer_settings: dict | None
    linked_host_ids: tuple[int, ...]
    group_ids: tuple[str, ...]
    subscription_template_ids: dict[str, int]


@dataclass(frozen=True)
class TemplateSnapshot:
    id: int
    format: str
    content: str


@dataclass(frozen=True)
class SubscriptionSnapshot:
    hosts: tuple[HostSnapshot, ...]
    inbounds: dict[int, dict]
    raw_inbounds: dict[int, dict]
    templates: dict[int, TemplateSnapshot]
    defaults: dict[str, str]
    external_config: str = ""


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
    balancer: dict | None = None

    @property
    def automatic(self):
        return self.balancer is not None


@dataclass(frozen=True)
class RenderInput:
    target: str
    profiles: tuple[ProfilePlan, ...]
    defaults: dict[str, str]
    external_config: str = ""
    reverse: bool = False
    as_base64: bool = False


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


class TemplateConflict(SubscriptionError):
    def __init__(self):
        super().__init__("Hosts use different subscription templates. Select template_id or a group with one template.", 409)
