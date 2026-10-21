"""Administrative host contracts and sparse, explicitly validated client overrides."""

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasPath, BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

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


class ClashOptions(HostOptions):
    ip_version: Literal["dual", "ipv4", "ipv6", "ipv4-prefer", "ipv6-prefer"] | None = None
    x25519: StrictBool | None = None


class ClientOverrides(HostOptions):
    clash: ClashOptions | None = None
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
    clash: list[MapperOperation] | None = None
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
