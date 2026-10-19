import json
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.system import random_password
from xray_api.types.account import (
    HysteriaAccount,
    ShadowsocksAccount,
    ShadowsocksMethods,
    TrojanAccount,
    VLESSAccount,
    VMessAccount,
    XTLSFlows,
)

FRAGMENT_PATTERN = re.compile(r'^((\d{1,4}-\d{1,4})|(\d{1,4})),((\d{1,3}-\d{1,3})|(\d{1,3})),(tlshello|\d|\d\-\d)$')

NOISE_PATTERN = re.compile(
    r'^(rand:(\d{1,4}-\d{1,4}|\d{1,4})|str:.+|hex:.+|base64:.+)(,(\d{1,4}-\d{1,4}|\d{1,4}))?(&(rand:(\d{1,4}-\d{1,4}|\d{1,4})|str:.+|hex:.+|base64:.+)(,(\d{1,4}-\d{1,4}|\d{1,4}))?)*$')
HTTP_TOKEN_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


class ProxyTypes(str, Enum):
    # User-account proxy type. Values match Xray inbound protocols.

    VMess = "vmess"
    VLESS = "vless"
    Trojan = "trojan"
    Shadowsocks = "shadowsocks"
    Hysteria = "hysteria"

    @property
    def account_model(self):
        if self == self.VMess:
            return VMessAccount
        if self == self.VLESS:
            return VLESSAccount
        if self == self.Trojan:
            return TrojanAccount
        if self == self.Shadowsocks:
            return ShadowsocksAccount
        if self == self.Hysteria:
            return HysteriaAccount

    @property
    def settings_model(self):
        if self == self.VMess:
            return VMessSettings
        if self == self.VLESS:
            return VLESSSettings
        if self == self.Trojan:
            return TrojanSettings
        if self == self.Shadowsocks:
            return ShadowsocksSettings
        if self == self.Hysteria:
            return HysteriaSettings

    @property
    def supports_runtime_api(self):
        return self.value in {"vmess", "vless", "trojan", "shadowsocks", "hysteria"}


class XrayInboundProtocol(str, Enum):
    DokodemoDoor = "dokodemo-door"
    HTTP = "http"
    Shadowsocks = "shadowsocks"
    Trojan = "trojan"
    VLESS = "vless"
    VMess = "vmess"
    WireGuard = "wireguard"
    Hysteria = "hysteria"
    TUN = "tun"


class XrayOutboundProtocol(str, Enum):
    Blackhole = "blackhole"
    DNS = "dns"
    Freedom = "freedom"
    HTTP = "http"
    Loopback = "loopback"
    Shadowsocks = "shadowsocks"
    Trojan = "trojan"
    VLESS = "vless"
    VMess = "vmess"
    WireGuard = "wireguard"
    Hysteria = "hysteria"


class XrayTransport(str, Enum):
    RAW = "raw"
    TCP = "tcp"
    MKCP = "mkcp"
    KCP = "kcp"
    WebSocket = "websocket"
    WS = "ws"
    HTTPUpgrade = "httpupgrade"
    SplitHTTP = "splithttp"
    XHTTP = "xhttp"
    GRPC = "grpc"
    HTTP = "http"
    H2 = "h2"
    H3 = "h3"
    QUIC = "quic"
    Hysteria = "hysteria"


class XraySecurity(str, Enum):
    none = "none"
    tls = "tls"
    reality = "reality"


XRAY_INBOUND_PROTOCOLS = {protocol.value for protocol in XrayInboundProtocol}
XRAY_OUTBOUND_PROTOCOLS = {protocol.value for protocol in XrayOutboundProtocol}
ACCOUNT_PROTOCOLS = {protocol.value for protocol in ProxyTypes}
USER_ACCOUNT_PROTOCOLS = {protocol.value for protocol in ProxyTypes}
RUNTIME_API_PROTOCOLS = {
    protocol.value for protocol in ProxyTypes if protocol.supports_runtime_api
}
XRAY_TRANSPORTS = {transport.value for transport in XrayTransport}
XRAY_SECURITIES = {security.value for security in XraySecurity}
XRAY_LEGACY_TRANSPORT_ALIASES = {
    "tcp": "raw",
    "kcp": "mkcp",
    "ws": "websocket",
    "splithttp": "xhttp",
}


class ProxySettings(BaseModel, use_enum_values=True):
    @classmethod
    def from_dict(cls, proxy_type: ProxyTypes, _dict: dict):
        return ProxyTypes(proxy_type).settings_model.model_validate(_dict)

    def dict(self, *, no_obj=False, **kwargs):
        if no_obj:
            return json.loads(self.json())
        return super().dict(**kwargs)


class VMessSettings(ProxySettings):
    id: UUID = Field(default_factory=uuid4)

    def revoke(self):
        self.id = uuid4()


class VLESSSettings(ProxySettings):
    id: UUID = Field(default_factory=uuid4)
    flow: XTLSFlows = XTLSFlows.NONE

    def revoke(self):
        self.id = uuid4()


class TrojanSettings(ProxySettings):
    password: str = Field(default_factory=random_password)
    flow: XTLSFlows = XTLSFlows.NONE

    def revoke(self):
        self.password = random_password()


class ShadowsocksSettings(ProxySettings):
    password: str = Field(default_factory=random_password)
    method: ShadowsocksMethods = ShadowsocksMethods.CHACHA20_POLY1305

    def revoke(self):
        self.password = random_password()


class HysteriaSettings(ProxySettings):
    auth: str = Field(default_factory=random_password)

    def revoke(self):
        self.auth = random_password()


class XrayCapabilities(BaseModel):
    inbound_protocols: List[str]
    outbound_protocols: List[str]
    account_protocols: List[str]
    runtime_api_protocols: List[str]
    transports: List[str]
    securities: List[str]
    legacy_transport_aliases: Dict[str, str]


class ProxyHostSecurity(str, Enum):
    inbound_default = "inbound_default"
    none = "none"
    tls = "tls"


ProxyHostALPN = Enum(
    "ProxyHostALPN",
    {
        "none": "",
        "h3": "h3",
        "h2": "h2",
        "http/1.1": "http/1.1",
        "h3,h2,http/1.1": "h3,h2,http/1.1",
        "h3,h2": "h3,h2",
        "h2,http/1.1": "h2,http/1.1",
    },
)


ProxyHostFingerprint = Enum(
    "ProxyHostFingerprint",
    {
        "none": "",
        "chrome": "chrome",
        "firefox": "firefox",
        "safari": "safari",
        "ios": "ios",
        "android": "android",
        "edge": "edge",
        "360": "360",
        "qq": "qq",
        "random": "random",
        "randomized": "randomized",
    },
)


class FormatVariables(dict):
    def __missing__(self, key):
        return key.join("{}")


class ProxyHost(BaseModel):
    subscription_template_ids: dict[str, int] = Field(default_factory=dict)

    @field_validator("subscription_template_ids", mode="before")
    @classmethod
    def validate_template_bindings(cls, value):
        from app.models.subscription_template import normalize_template_bindings

        if not isinstance(value, dict):
            raise ValueError("Template assignments must be an object")
        return normalize_template_bindings(value)

    remark: str
    address: str
    port: Optional[int] = Field(None, nullable=True)
    sni: Optional[str] = Field(None, nullable=True)
    host: Optional[str] = Field(None, nullable=True)
    path: Optional[str] = Field(None, nullable=True)
    security: ProxyHostSecurity = ProxyHostSecurity.inbound_default
    alpn: ProxyHostALPN = ProxyHostALPN.none
    fingerprint: ProxyHostFingerprint = ProxyHostFingerprint.none
    allowinsecure: Union[bool, None] = None
    is_disabled: Union[bool, None] = None
    mux_enable: Union[bool, None] = None
    fragment_setting: Optional[str] = Field(None, nullable=True)
    noise_setting: Optional[str] = Field(None, nullable=True)
    random_user_agent: Union[bool, None] = None
    use_sni_as_host: Union[bool, None] = None
    sc_max_buffered_posts: Optional[int] = Field(None, ge=0)
    x_padding_obfs_mode: Optional[bool] = None
    uplink_http_method: Optional[str] = Field(None, max_length=32)
    model_config = ConfigDict(from_attributes=True)

    @field_validator("remark", mode="after")
    def validate_remark(cls, v):
        try:
            v.format_map(FormatVariables())
        except ValueError as exc:
            raise ValueError("Invalid formatting variables")

        return v

    @field_validator("address", mode="after")
    def validate_address(cls, v):
        try:
            v.format_map(FormatVariables())
        except ValueError as exc:
            raise ValueError("Invalid formatting variables")

        return v

    @field_validator("fragment_setting", check_fields=False)
    @classmethod
    def validate_fragment(cls, v):
        if v and not FRAGMENT_PATTERN.match(v):
            raise ValueError(
                "Fragment setting must be like this: length,interval,packet (10-100,100-200,tlshello)."
            )
        return v

    @field_validator("noise_setting", check_fields=False)
    @classmethod
    def validate_noise(cls, v):
        if v:
            if not NOISE_PATTERN.match(v):
                raise ValueError(
                    "Noise setting must be like this: packet,delay (rand:10-20,100-200)."
                )
            if len(v) > 2000:
                raise ValueError(
                    "Noise can't be longer that 2000 character"
                )
        return v

    @field_validator("uplink_http_method")
    @classmethod
    def validate_uplink_http_method(cls, v):
        if v is None:
            return None
        value = v.strip()
        if not value:
            return None
        if not HTTP_TOKEN_PATTERN.fullmatch(value):
            raise ValueError("Uplink HTTP method must be a valid HTTP token")
        return value.upper()


class HostGroupBase(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v):
        if v is None:
            return []
        if any(not isinstance(tag, str) for tag in v):
            raise ValueError("Tags must be strings")
        return v


class HostGroupCreate(HostGroupBase):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class HostGroupModify(HostGroupBase):
    pass


class HostGroupRef(BaseModel):
    id: str
    name: str
    tags: List[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class HostGroupResponse(HostGroupBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class HostGroupAttachRequest(BaseModel):
    group_ids: List[str] = Field(default_factory=list)


class ProxyHostV2(ProxyHost):
    id: int
    inbound_id: int
    inbound_tag: str
    position: int
    groups: List[HostGroupRef] = Field(default_factory=list)


class ProxyHostCreate(ProxyHost):
    inbound_tag: str = Field(min_length=1, max_length=256)
    position: Optional[int] = None
    group_ids: List[str] = Field(default_factory=list)


class ProxyHostModify(ProxyHost):
    inbound_tag: str = Field(min_length=1, max_length=256)
    position: Optional[int] = None
    group_ids: List[str] = Field(default_factory=list)


class ProxyHostReorder(BaseModel):
    host_ids: List[int]


class InboundNodeRef(BaseModel):
    id: int
    name: str


class ProxyInbound(BaseModel):
    tag: str
    protocol: ProxyTypes
    network: str
    tls: str
    port: Union[int, str]
    nodes: List[InboundNodeRef] = Field(default_factory=list)


def validate_config_tag(content: Dict[str, Any], entity: str) -> str:
    value = content.get("tag")
    if not isinstance(value, str):
        raise ValueError(f"{entity} content tag must be a string")

    value = value.strip()
    if not value:
        raise ValueError(f"{entity} tag cannot be empty")
    if len(value) > 256:
        raise ValueError(f"{entity} tag cannot be longer than 256 characters")
    if "," in value:
        raise ValueError(f"Character ',' is not allowed in {entity.lower()} tag")
    return value


class InboundCreate(BaseModel):
    enabled: bool = True
    auto_assign_users: bool = True
    content: Dict[str, Any]
    node_ids: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content_tag(self):
        validate_config_tag(self.content, "Inbound")
        return self

    @property
    def tag(self) -> str:
        return validate_config_tag(self.content, "Inbound")


class InboundModify(BaseModel):
    enabled: Optional[bool] = None
    content: Optional[Dict[str, Any]] = None
    node_ids: Optional[List[int]] = None


class InboundResponse(BaseModel):
    tag: str
    enabled: bool
    readonly: bool
    content: Dict[str, Any]
    node_ids: List[int]


class OutboundCreate(BaseModel):
    enabled: bool = True
    content: Dict[str, Any]
    node_ids: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content_tag(self):
        validate_config_tag(self.content, "Outbound")
        return self

    @property
    def tag(self) -> str:
        return validate_config_tag(self.content, "Outbound")


class OutboundModify(BaseModel):
    enabled: Optional[bool] = None
    content: Optional[Dict[str, Any]] = None
    node_ids: Optional[List[int]] = None


class OutboundResponse(BaseModel):
    tag: str
    enabled: bool
    readonly: bool
    content: Dict[str, Any]
    node_ids: List[int]
