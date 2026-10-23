"""Administrative host contracts and sparse, explicitly validated client overrides."""

from copy import deepcopy
from datetime import datetime
from typing import Any, Literal

from pydantic import AliasPath, BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

from app.models.proxy import FRAGMENT_PATTERN, NOISE_PATTERN, HostGroupRef, FormatVariables
from app.models.subscription_template import normalize_template_bindings
from app.models.host_mapper import HostMapperOptions, normalize_stored_mapper_options
from app.models.finalmask import FinalMask
from app.models.socket_options import SocketOptions
from app.models.xhttp import XhttpExtra


def normalize_stored_host_overrides(overrides: dict | None) -> dict:
    """Read legacy overrides using the current contract without changing their behavior."""
    result = deepcopy(overrides or {})
    security = result.get("security", {})
    if isinstance(security, dict) and "keep_sni_blank" in security:
        if security.pop("keep_sni_blank"):
            security["sni"] = ""
        if not security:
            result.pop("security", None)
    if isinstance(result.get("mapper"), dict):
        result["mapper"] = normalize_stored_mapper_options(result["mapper"])
    return result


class HostOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SecurityOverrides(HostOptions):
    mode: Literal["tls", "none"] | None = None
    sni: str | None = Field(None, max_length=1000)
    sni_from_address: StrictBool | None = None
    alpn: list[str] | None = None
    fingerprint: str | None = None
    allow_insecure: StrictBool | None = None

    @model_validator(mode="after")
    def validate_sni(self):
        if self.sni_from_address and self.sni is not None:
            raise ValueError("Choose only one SNI override")
        return self


class XhttpOverrides(HostOptions):
    extra: XhttpExtra | None = None


class TransportOverrides(HostOptions):
    host: str | None = Field(None, max_length=1000)
    path: str | None = Field(None, max_length=256)
    use_sni_as_host: StrictBool | None = None
    random_user_agent: StrictBool | None = None
    xhttp: XhttpOverrides | None = None


class XrayMux(HostOptions):
    concurrency: StrictInt | None = Field(None, ge=-1)
    xudpConcurrency: StrictInt | None = Field(None, ge=-1)
    xudpProxyUDP443: Literal["reject", "allow", "skip"] | None = None


class SmuxOptions(HostOptions):
    enabled: StrictBool = False
    protocol: Literal["smux", "yamux", "h2mux"] = "smux"
    max_connections: StrictInt | None = Field(None, ge=1)
    min_streams: StrictInt | None = Field(None, ge=1)
    max_streams: StrictInt | None = Field(None, ge=1)
    padding: StrictBool | None = None


class MuxOverrides(HostOptions):
    enabled: StrictBool | None = None
    xray: XrayMux | None = None
    smux: SmuxOptions | None = None


class StreamOverrides(HostOptions):
    sockopt: SocketOptions | None = Field(
        None, description="Xray streamSettings.sockopt. TCP, DNS, interface and platform socket options.")
    final_mask: FinalMask | None = Field(
        None, description="Xray streamSettings.finalmask. TCP/UDP mask chains and optional QUIC parameters.")


class ClashOptions(HostOptions):
    ip_version: Literal["dual", "ipv4", "ipv6", "ipv4-prefer", "ipv6-prefer"] | None = Field(
        None, description="IP address preference for Clash.", examples=["ipv6-prefer"])
    x25519: StrictBool | None = Field(
        None, description="Enable X25519MLKEM768 for Clash REALITY.", examples=[False])


class ClientOverrides(HostOptions):
    clash: ClashOptions | None = Field(None, description="Clash IP and REALITY options.")
    server_description: str | None = Field(
        None, description="Server description for compatible extended clients. Enter plain text.", examples=["Europe"])


class HostOverrides(HostOptions):
    security: SecurityOverrides | None = None
    transport: TransportOverrides | None = None
    mux: MuxOverrides | None = None
    stream: StreamOverrides | None = None
    clients: ClientOverrides | None = None
    fragment: str | None = None
    noise: str | None = Field(None, max_length=2000)
    mapper: HostMapperOptions | None = None

    @field_validator("fragment", "noise")
    @classmethod
    def validate_packet_options(cls, value, info):
        pattern = FRAGMENT_PATTERN if info.field_name == "fragment" else NOISE_PATTERN
        if value and not pattern.fullmatch(value):
            raise ValueError(f"Invalid {info.field_name} settings")
        return value


class HostCreate(HostOptions):
    inbound_id: StrictInt = Field(gt=0)
    remark: str = Field(min_length=1, max_length=256)
    address: str = Field(min_length=1, max_length=256)
    port: StrictInt | None = Field(None, ge=1, le=65535)
    enabled: StrictBool = True
    position: StrictInt | None = Field(None, ge=0)
    is_hidden: StrictBool = False
    overrides: HostOverrides | None = None
    group_ids: list[str] = Field(default_factory=list)
    subscription_template_ids: dict[str, int] = Field(default_factory=dict)

    @field_validator("remark", "address")
    @classmethod
    def validate_text(cls, value):
        if not value.strip():
            raise ValueError("Value cannot be blank")
        value.format_map(FormatVariables())
        return value

    @field_validator("group_ids")
    @classmethod
    def unique_ids(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("IDs must be unique")
        if any(isinstance(value, int) and value <= 0 for value in values):
            raise ValueError("IDs must be positive")
        return values

    @field_validator("subscription_template_ids", mode="before")
    @classmethod
    def template_bindings(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Template assignments must be an object")
        return normalize_template_bindings(value)


class HostPatch(HostOptions):
    inbound_id: StrictInt | None = Field(None, gt=0)
    remark: str | None = Field(None, min_length=1, max_length=256)
    address: str | None = Field(None, min_length=1, max_length=256)
    port: StrictInt | None = Field(None, ge=1, le=65535)
    enabled: StrictBool | None = None
    position: StrictInt | None = Field(None, ge=0)
    is_hidden: StrictBool | None = None
    # Validate the merged document, so clearing one SNI mode and setting another is atomic.
    overrides: dict[str, Any] | None = None
    group_ids: list[str] | None = None
    subscription_template_ids: dict[str, int] | None = None

    @model_validator(mode="after")
    def reject_invalid_nulls(self):
        nullable = {"port", "overrides"}
        for name in self.model_fields_set - nullable:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class HostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    inbound_id: int
    inbound_tag: str
    inbound_port: int | str | None = Field(default=None, validation_alias=AliasPath("inbound", "content", "port"))
    remark: str
    address: str
    port: int | None
    enabled: bool
    position: int
    is_hidden: bool
    overrides: dict[str, Any]
    groups: list[HostGroupRef]
    subscription_template_ids: dict[str, int]
    created_at: datetime
    updated_at: datetime

    @field_validator("overrides", mode="before")
    @classmethod
    def normalize_overrides(cls, value):
        return normalize_stored_host_overrides(value)


class HostList(BaseModel):
    items: list[HostResponse]
    total: int


class HostReorder(HostOptions):
    host_ids: list[StrictInt]


class HostClone(HostOptions):
    remark: str = Field(min_length=1, max_length=256)


class HostPreview(HostOptions):
    host: HostCreate
    host_id: StrictInt | None = Field(None, gt=0)
    user_id: StrictInt = Field(gt=0)
    target: Literal["v2ray", "v2ray-json", "clash", "sing-box", "outline"]
