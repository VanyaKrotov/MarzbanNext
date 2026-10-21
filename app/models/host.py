"""Administrative host contracts and sparse, explicitly validated client overrides."""

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

from app.models.proxy import FRAGMENT_PATTERN, HTTP_TOKEN_PATTERN, NOISE_PATTERN, HostGroupRef, FormatVariables
from app.models.subscription_template import normalize_template_bindings


class HostOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")


class XhttpMux(HostOptions):
    maxConcurrency: str | StrictInt | None = None
    maxConnections: int | None = None
    cMaxReuseTimes: str | StrictInt | None = None
    hMaxRequestTimes: str | StrictInt | None = None
    hMaxReusableSecs: str | StrictInt | None = None
    hKeepAlivePeriod: int | None = None


class XhttpExtra(HostOptions):
    scMaxBufferedPosts: StrictInt | None = Field(None, ge=0)
    xPaddingObfsMode: StrictBool | None = None
    uplinkHTTPMethod: str | None = Field(None, max_length=32)
    xPaddingBytes: str | StrictInt | None = None
    xPaddingKey: str | None = None
    xPaddingHeader: str | None = None
    xPaddingMethod: str | None = None
    xPaddingPlacement: str | None = None
    noGRPCHeader: StrictBool | None = None
    noSSEHeader: StrictBool | None = None
    scMaxEachPostBytes: str | StrictInt | None = None
    scMaxConcurrentPosts: str | StrictInt | None = None
    scMinPostsIntervalMs: str | StrictInt | None = None
    scStreamUpServerSecs: str | StrictInt | None = None
    headers: dict[str, str] | None = None
    xmux: XhttpMux | None = None

    @field_validator("uplinkHTTPMethod")
    @classmethod
    def validate_method(cls, value):
        if value is None:
            raise ValueError("Omit the HTTP method to use the client default")
        value = value.strip()
        if not value or not HTTP_TOKEN_PATTERN.fullmatch(value):
            raise ValueError("Uplink HTTP method must be a nonempty HTTP token")
        return value.upper()

    @model_validator(mode="after")
    def reject_explicit_null(self):
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Omit XHTTP extra keys instead of assigning null")
        return self


class SecurityOverrides(HostOptions):
    mode: Literal["tls", "none"] | None = None
    sni: str | None = Field(None, max_length=1000)
    keep_sni_blank: StrictBool | None = None
    sni_from_address: StrictBool | None = None
    alpn: list[str] | None = None
    fingerprint: str | None = None
    allow_insecure: StrictBool | None = None

    @model_validator(mode="after")
    def validate_sni(self):
        modes = [bool(self.keep_sni_blank), bool(self.sni_from_address), self.sni is not None]
        if sum(modes) > 1:
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
    sockopt: dict[str, Any] | None = None
    final_mask: dict[str, Any] | None = None


class ClashMetaOptions(HostOptions):
    ip_version: Literal["dual", "ipv4", "ipv6", "ipv4-prefer", "ipv6-prefer"] | None = None
    x25519: StrictBool | None = None


class ClientOverrides(HostOptions):
    clash_meta: ClashMetaOptions | None = Field(None, alias="clash-meta")
    server_description: str | None = None


class MapperOperation(HostOptions):
    op: Literal["set", "copy", "unset"]
    to: str = Field(min_length=1)
    source: str | None = Field(None, alias="from")
    value: Any = None

    @model_validator(mode="after")
    def validate_operation(self):
        if self.op == "copy" and not self.source:
            raise ValueError("Copy operations require a source")
        if self.op == "set" and "value" not in self.model_fields_set:
            raise ValueError("Set operations require a value")
        if any(part in self.to for part in ("__proto__", "__class__", "constructor")):
            raise ValueError("Invalid mapper path")
        return self


class HostMapperOptions(HostOptions):
    xrayJson: list[MapperOperation] | None = None
    clash_meta: list[MapperOperation] | None = Field(None, alias="clash-meta")
    singbox: list[MapperOperation] | None = None
    base64: list[MapperOperation] | None = None


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


BalancerStrategy = Literal["least_ping", "least_load", "random", "round_robin"]
ClientTarget = Literal["v2ray-json", "clash-meta", "sing-box"]


class HostCost(HostOptions):
    host_id: StrictInt = Field(gt=0)
    value: float = Field(gt=0)


class LeastLoadOptions(HostOptions):
    expected: StrictInt | None = Field(None, ge=1)
    max_rtt_ms: StrictInt | None = Field(None, gt=0)
    failure_tolerance: float | None = Field(None, ge=0, le=1)
    baselines_ms: list[StrictInt] | None = None
    costs: list[HostCost] | None = None

    @field_validator("baselines_ms")
    @classmethod
    def positive_baselines(cls, values):
        if values is not None and any(value <= 0 for value in values):
            raise ValueError("RTT baselines must be positive")
        return values


class BalancerClientOptions(HostOptions):
    strategy: BalancerStrategy | None = None
    probe_url: str | None = Field(None, max_length=2048)
    probe_interval: StrictInt | None = Field(None, ge=10, le=86400)
    enable_concurrency: StrictBool | None = None
    strategy_settings: LeastLoadOptions | None = None
    tolerance: StrictInt | None = Field(None, ge=0)
    lazy: StrictBool | None = None
    idle_timeout: StrictInt | None = Field(None, gt=0)
    interrupt_existing_connections: StrictBool | None = None

    @field_validator("probe_url")
    @classmethod
    def validate_url(cls, value):
        if value is not None:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Probe URL must be an HTTP or HTTPS URL")
        return value


class BalancerSettings(HostOptions):
    remark: str | None = Field(None, max_length=256)
    strategy: BalancerStrategy = "least_ping"
    probe_url: str = Field("https://www.gstatic.com/generate_204", max_length=2048)
    probe_interval: StrictInt = Field(300, ge=10, le=86400)
    clients: dict[ClientTarget, BalancerClientOptions] = Field(default_factory=dict)

    _validate_url = field_validator("probe_url")(BalancerClientOptions.validate_url.__func__)


class HostCreate(HostOptions):
    inbound_id: StrictInt = Field(gt=0)
    remark: str = Field(min_length=1, max_length=256)
    address: str = Field(min_length=1, max_length=256)
    port: StrictInt | None = Field(None, ge=1, le=65535)
    enabled: StrictBool = True
    position: StrictInt | None = Field(None, ge=0)
    show_when_composed: StrictBool = True
    overrides: HostOverrides | None = None
    balancer_settings: BalancerSettings | None = None
    linked_host_ids: list[StrictInt] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    subscription_template_ids: dict[str, int] = Field(default_factory=dict)

    @field_validator("remark", "address")
    @classmethod
    def validate_text(cls, value):
        if not value.strip():
            raise ValueError("Value cannot be blank")
        value.format_map(FormatVariables())
        return value

    @field_validator("linked_host_ids", "group_ids")
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
    show_when_composed: StrictBool | None = None
    # Validate the merged document, so clearing one SNI mode and setting another is atomic.
    overrides: dict[str, Any] | None = None
    balancer_settings: dict[str, Any] | None = None
    linked_host_ids: list[StrictInt] | None = None
    group_ids: list[str] | None = None
    subscription_template_ids: dict[str, int] | None = None

    @model_validator(mode="after")
    def reject_invalid_nulls(self):
        nullable = {"port", "overrides", "balancer_settings"}
        for name in self.model_fields_set - nullable:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class HostRef(BaseModel):
    id: int
    remark: str


class HostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    inbound_id: int
    inbound_tag: str
    remark: str
    address: str
    port: int | None
    enabled: bool
    position: int
    show_when_composed: bool
    overrides: dict[str, Any]
    balancer_settings: dict[str, Any] | None
    linked_host_ids: list[int]
    member_of: list[HostRef]
    groups: list[HostGroupRef]
    subscription_template_ids: dict[str, int]
    created_at: datetime
    updated_at: datetime


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
    target: Literal["v2ray", "v2ray-json", "clash-meta", "sing-box", "outline"]
