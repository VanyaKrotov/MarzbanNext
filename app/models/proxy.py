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


class InboundNodeRef(BaseModel):
    id: int
    name: str


class ProxyInbound(BaseModel):
    id: int | None = None
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
