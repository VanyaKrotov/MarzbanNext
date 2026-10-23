"""Xray socket options shared by host overrides, ECH and the Monaco editor schema."""

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PrivateAttr, StrictBool, StrictInt, StrictStr
from pydantic import WithJsonSchema, model_serializer, model_validator


XRAY_SOCKET_SOURCE = (
    "https://github.com/XTLS/Xray-core/blob/1b1647cd9ddf0abc34b981d4611fc03bcac1ca74/"
    "infra/conf/transport_sockopt.go"
)
Int32 = Annotated[StrictInt, Field(ge=-2147483648, le=2147483647)]
UInt32 = Annotated[StrictInt, Field(ge=0, le=4294967295)]
UInt64 = Annotated[StrictInt, Field(ge=0, le=18446744073709551615)]


def case_insensitive_choices(*values: str):
    """Suggest documented spellings without rewriting values that Xray accepts in another case."""
    alternatives = ["".join(f"[{char.lower()}{char.upper()}]" if char.isalpha() else re.escape(char)
                            for char in value) for value in values]
    pattern = "^(?:" + "|".join(alternatives) + ")$"
    return Annotated[StrictStr, Field(pattern=pattern), WithJsonSchema({
        "type": "string", "anyOf": [{"enum": list(values)}, {"pattern": pattern}],
        "patternErrorMessage": "Choose one of: " + ", ".join(value or '""' for value in values),
    })]


DomainStrategy = case_insensitive_choices(
    "", "AsIs", "UseIP", "UseIPv4", "UseIPv6", "UseIPv4v6", "UseIPv6v4",
    "ForceIP", "ForceIPv4", "ForceIPv6", "ForceIPv4v6", "ForceIPv6v4",
)
AddressPortStrategy = case_insensitive_choices(
    "", "none", "SrvPortOnly", "SrvAddressOnly", "SrvPortAndAddress",
    "TxtPortOnly", "TxtAddressOnly", "TxtPortAndAddress",
)
TransparentMode = case_insensitive_choices("", "off", "redirect", "tproxy")


class SocketModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HappyEyeballs(SocketModel):
    """TCP address racing; needs non-AsIs resolution and no dialerProxy to take effect."""

    tryDelayMs: UInt64 | None = Field(
        None, description="Delay between TCP attempts in milliseconds. 0 disables racing; 250 is a common value.",
        examples=[250])
    prioritizeIPv6: StrictBool | None = Field(
        None, description="Try IPv6 addresses first; false (the core default) prioritizes IPv4.")
    interleave: UInt32 | None = Field(
        None, description="Addresses per family before switching; default 1. 0 keeps the first family together.",
        examples=[1, 2])
    maxConcurrentTry: UInt32 | None = Field(
        None, description="Concurrent TCP connection attempts; default 4. 0 disables racing.", examples=[4])


def validate_decimal(value: str) -> str:
    if not -9223372036854775808 <= int(value) <= 9223372036854775807:
        raise ValueError("Socket integer strings must fit in a signed 64-bit integer")
    return value


DecimalString = Annotated[StrictStr, Field(pattern=r"^[+-]?[0-9]+$"), AfterValidator(validate_decimal)]
SocketSystem = Literal["", "linux", "windows", "darwin", "android"]
SocketNetwork = Literal["", "tcp", "tcp4", "tcp6", "udp", "udp4", "udp6"]


class CustomSocketOption(SocketModel):
    system: SocketSystem | None = Field(
        None, description="Apply only on this client OS; empty applies on any OS. Android refers to Android builds.")
    network: SocketNetwork | None = Field(
        None, description="Socket network filter; tcp/udp includes both families. Empty applies to every network.")
    level: DecimalString | Literal[""] | None = Field(
        None, description="Socket protocol level as a decimal string; omitted/empty uses 6 (TCP).", examples=["6", "1"])
    opt: DecimalString = Field(
        description="Socket option number as a decimal string, not a JSON number.", examples=["13"])


class IntegerSocketOption(CustomSocketOption):
    """An integer setsockopt value, encoded as a decimal string."""

    type: Literal["int"] = Field(description="Use the client's integer setsockopt API.")
    value: DecimalString = Field(
        description="Signed 64-bit decimal integer string; the option's actual range depends on the OS.",
        examples=["1", "-1"])


class StringSocketOption(CustomSocketOption):
    """A string setsockopt value. The Xray Windows implementation does not support it."""

    system: Literal["", "linux", "darwin", "android"] | None = Field(
        None, description="Client OS filter. String socket values are unsupported by Xray on Windows.")
    type: Literal["str"] = Field(description="Use the client's string setsockopt API; unsupported on Windows.")
    value: StrictStr = Field(description="Literal socket option value; empty string is preserved.", examples=["bbr"])


CustomOption = Annotated[IntegerSocketOption | StringSocketOption, Field(discriminator="type")]
_KEEPALIVE_SIGN_RULES = [{
    "not": {"required": [negative, positive], "properties": {
        negative: {"type": "integer", "maximum": -1}, positive: {"type": "integer", "minimum": 1},
    }},
} for negative, positive in (("tcpKeepAliveIdle", "tcpKeepAliveInterval"),
                             ("tcpKeepAliveInterval", "tcpKeepAliveIdle"))]


class SocketOptions(SocketModel):
    """Low-level Xray client socket behavior; effects depend on the client OS and transport."""

    model_config = ConfigDict(json_schema_extra={
        "$comment": f"Xray SocketConfig definitions: {XRAY_SOCKET_SOURCE}",
        "allOf": _KEEPALIVE_SIGN_RULES,
        "defaultSnippets": [{
            "label": "TCP: Fast Open and KeepAlive",
            "description": "KeepAlive values are seconds; Fast Open requires client OS support.",
            "body": {"tcpFastOpen": True, "tcpKeepAliveIdle": 45, "tcpKeepAliveInterval": 45},
        }, {
            "label": "DNS: Happy Eyeballs",
            "description": "Race resolved IPv4/IPv6 addresses for a TCP destination.",
            "body": {"domainStrategy": "UseIP", "happyEyeballs": {
                "tryDelayMs": 250, "prioritizeIPv6": False, "interleave": 1, "maxConcurrentTry": 4,
            }},
        }, {
            "label": "Linux: custom TCP congestion option",
            "description": "Example of a string customSockopt; the client must provide the bbr algorithm.",
            "body": {"customSockopt": [{
                "system": "linux", "network": "tcp", "type": "str", "level": "6", "opt": "13", "value": "bbr",
            }]},
        }],
    })
    mark: Int32 | None = Field(
        None, description=("Linux SO_MARK, signed 32-bit representation; 0 leaves it unset. "
                           "Requires appropriate privileges."),
        examples=[0, 255])
    tcpFastOpen: StrictBool | Int32 | None = Field(
        None, description=("TCP Fast Open: true/positive enables it; false/negative disables it; "
                           "0/omitted uses OS default. "
                           "On listeners a positive integer is the pending-request limit; true means 256."),
        examples=[True, False, 0, 256, -1])
    tcpMaxSeg: Int32 | None = Field(
        None, description="Linux TCP maximum segment size in bytes; nonpositive leaves the OS value unchanged.",
        examples=[1440])
    tcpWindowClamp: Int32 | None = Field(
        None, description="Linux advertised receive-window clamp in bytes; nonpositive leaves it unchanged.")
    tcpUserTimeout: Int32 | None = Field(
        None, description="Linux TCP timeout for unacknowledged data in milliseconds; nonpositive leaves it unchanged.",
        examples=[10000])
    tcpKeepAliveIdle: Int32 | None = Field(
        None, description=("Idle time before TCP KeepAlive probes in seconds; "
                           "0 uses the core default (outbound: 45). "
                           "Negative disables KeepAlive; cannot be paired with a positive interval."),
        examples=[45, -1])
    tcpKeepAliveInterval: Int32 | None = Field(
        None, description=("TCP KeepAlive probe interval in seconds; 0 uses the core default (outbound: 45). "
                           "Negative disables KeepAlive; cannot be paired with a positive idle time."),
        examples=[45, -1])
    tcpcongestion: StrictStr | None = Field(
        None, description="Linux TCP congestion algorithm, checked on the client; empty keeps the OS default.",
        examples=["bbr", "cubic", "reno"])
    tcpCongestion: StrictStr | None = Field(
        None, description="Alternate Xray spelling of tcpcongestion; preserved for saved configurations.")
    tcpMptcp: StrictBool | None = Field(
        None, description="Use Multipath TCP on supported client OS/kernel; false is the core default.")
    tproxy: TransparentMode | None = Field(
        None, description=("Linux transparent proxy mode: off/empty, redirect or tproxy. "
                           "Requires OS rules and privileges."))
    domainStrategy: DomainStrategy | None = Field(
        None, description=("Resolve the proxy server's address: AsIs/empty uses system DNS; Use* uses Xray DNS with "
                           "system fallback; Force* fails if resolution cannot satisfy the selected IP family."))
    addressPortStrategy: AddressPortStrategy | None = Field(
        None, description=("Rewrite the destination using system DNS SRV/TXT records before domainStrategy; "
                           "PortOnly, AddressOnly or PortAndAddress selects the parts to replace. "
                           "none/empty disables it."))
    happyEyeballs: HappyEyeballs | None = Field(
        None, description="TCP address racing parameters; ignored with AsIs resolution or a nonempty dialerProxy.")
    dialerProxy: StrictStr | None = Field(
        None, description=("Existing outbound tag used to dial this connection; empty disables chaining. "
                           "A generated fragment/noise dialer takes priority."), examples=["upstream", ""])
    interface: StrictStr | None = Field(
        None, description="Client network interface name for outbound connections; empty does not bind an interface.",
        examples=["wg0", "eth0"])
    V6Only: StrictBool | None = Field(
        None, description="Linux inbound listener on :: accepts only IPv6; has no effect on a host's client outbound.")
    v6only: StrictBool | None = Field(
        None, description="Alternate Xray spelling of V6Only; preserved for saved configurations.")
    acceptProxyProtocol: StrictBool | None = Field(
        None, description="Inbound-only PROXY protocol acceptance; has no effect on a host's client outbound.")
    trustedXForwardedFor: list[StrictStr] | None = Field(
        None, description=("Inbound HTTP transport header names: if any is present, Xray trusts X-Forwarded-For. "
                           "Has no effect on a host's client outbound."), examples=[["X-Trusted-Proxy"]])
    penetrate: StrictBool | None = Field(
        None, description=("For XHTTP with separate downloadSettings: "
                           "use the upload socket options for the download too."))
    customSockopt: list[CustomOption] | None = Field(
        None, description=("Platform setsockopt calls; type selects int/str and their value schema. "
                           "[] applies no custom options."))

    _input_order: tuple[str, ...] = PrivateAttr(default=())

    @model_validator(mode="wrap")
    @classmethod
    def preserve_input_order(cls, value, handler):
        result = handler(value)
        if isinstance(value, dict):
            result._input_order = tuple(value)
        return result

    @model_serializer(mode="wrap")
    def serialize_in_input_order(self, handler):
        result = handler(self)
        # Go accepts both case variants and the last JSON key wins. Keep their relative order.
        return {key: result[key] for key in dict.fromkeys((*self._input_order, *result)) if key in result}

    @model_validator(mode="after")
    def check_keepalive_signs(self):
        idle, interval = self.tcpKeepAliveIdle or 0, self.tcpKeepAliveInterval or 0
        if idle * interval < 0:
            raise ValueError("TCP KeepAlive idle and interval cannot have opposite signs")
        return self
