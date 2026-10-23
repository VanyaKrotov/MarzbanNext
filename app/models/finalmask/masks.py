"""Settings for the TCP and UDP mask loaders registered by Xray."""

import ipaddress
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, StrictBool, StrictInt, StrictStr, WithJsonSchema
from pydantic import field_validator, model_validator

from .common import MaskOptions, Range, UInt32, decimal_pattern, range_bounds, zero_or_integer, zero_or_range
from .quic import PortList, QuicParams, TLSOptions


class Filter(MaskOptions):
    """Inbound source-address filter; has no effect in a generated client outbound."""

    blockedSourceIPs: list[StrictStr] | None = Field(
        None, description="Blocked IPs/CIDRs/geoip rules. Inbound-only; not applied to client outbounds.")
    allowedSourceIPs: list[StrictStr] | None = Field(
        None, description="Allowed IPs/CIDRs/geoip rules. Inbound-only; not applied to client outbounds.")


_POSITIVE_RANGE = decimal_pattern(1, 2147483647)


class Fragment(MaskOptions):
    """Split outgoing TCP data into fragments, optionally targeting only TLS ClientHello."""

    model_config = ConfigDict(json_schema_extra={"anyOf": [
        {"required": ["lengths"], "properties": {"lengths": {"type": "array", "minItems": 1}}},
        {"required": ["length"], "properties": {"length": {
            "anyOf": [{"type": "integer", "minimum": 1},
                      {"type": "string", "pattern": f"^{_POSITIVE_RANGE}(?:-{_POSITIVE_RANGE})?$"}],
        }}},
    ]})
    packets: Annotated[StrictStr, Field(pattern=(
        f"^(?:|[tT][lL][sS][hH][eE][lL][lL][oO]|{_POSITIVE_RANGE}(?:-{_POSITIVE_RANGE})?)$"))] | None = Field(
        None, description=("Empty fragments all packets; tlshello targets TLS ClientHello; "
                           "e.g. 1-3 selects packet numbers."))
    length: Range | None = Field(
        None, description="Legacy fragment length in bytes, used when lengths is empty/omitted.")
    delay: Range | None = Field(
        None, description="Legacy delay between fragments in milliseconds; used if delays is empty.")
    lengths: list[Range] | None = Field(None, description=(
        "Fragment-length ranges in bytes. The last range must be positive; earlier zero entries skip fragmentation."),
        examples=[["100-200", "50-100"]])
    delays: list[Range] | None = Field(
        None, description="Delay ranges in milliseconds, paired with lengths; 0 means no delay.")
    maxSplit: Range | None = Field(None, description="Maximum number of splits; 0 means unlimited.")

    @model_validator(mode="after")
    def check_last_length(self):
        last = self.lengths[-1] if self.lengths else self.length
        if last is None or range_bounds(last)[0] == 0:
            raise ValueError("The last fragment length must be greater than zero")
        return self


class MkcpLegacy(MaskOptions):
    """Legacy UDP header imitation, or XOR/AES obfuscation when header is empty."""

    header: Literal["", "dns", "dtls", "srtp", "utp", "wechat", "wireguard"] | None = Field(
        None, description="Legacy header type. Empty header uses XOR without value or AES-128-GCM with value.")
    value: StrictStr | None = Field(
        None, description="DNS domain (default www.baidu.com) or AES password for an empty header.")


class Salamander(MaskOptions):
    """UDP Salamander obfuscation, optionally using Gecko fragmentation and padding."""

    password: StrictStr | None = Field(None, description="Shared obfuscation password; must match the peer.")
    packetSize: zero_or_range(1, 2048) | None = Field(
        None, description=("0 uses basic Salamander; a positive size/range up to 2048 "
                           "enables Gecko padding/fragmentation."))


def validate_table(value: str) -> str:
    cleaned = value.strip().lower().replace(" ", "")
    expected = {"x": 2, "p": 2, "v": 4}
    if cleaned and (len(cleaned) != 8 or any(cleaned.count(char) != count for char, count in expected.items())):
        raise ValueError("A Sudoku table must contain exactly two x, two p and four v characters")
    return value


SudokuTable = Annotated[StrictStr, AfterValidator(validate_table), WithJsonSchema({
    "type": "string",
    "pattern": (r"^(?: *|(?=(?:[^xX]*[xX]){2}[^xX]*$)(?=(?:[^pP]*[pP]){2}[^pP]*$)"
                r"(?=(?:[^vV]*[vV]){4}[^vV]*$)[ xXpPvV]*)$"),
    "examples": ["xpxpvvvv"],
})]


class Sudoku(MaskOptions):
    """Shared TCP/UDP Sudoku encoding. Legacy spellings are preserved in stored JSON."""

    password: StrictStr | None = Field(None, description="Shared Sudoku encoding password; must match the peer.")
    ascii: Literal["", "entropy", "prefer_entropy", "ascii", "prefer_ascii"] | None = Field(
        None, description="ASCII or entropy preference; empty uses prefer_entropy.")
    customTable: SudokuTable | None = Field(
        None, description="Eight layout characters: two x, two p, four v.", examples=["xpxpvvvv"])
    customTables: list[SudokuTable] | None = Field(
        None, description="Multiple layouts, each with two x, two p and four v.")
    paddingMin: UInt32 | None = Field(
        None, description="Minimum padding probability (%); Xray clamps values above 100.")
    paddingMax: UInt32 | None = Field(
        None, description="Maximum padding probability (%); Xray clamps to 100 and at least paddingMin.")
    custom_table: SudokuTable | None = Field(
        None, description="Legacy customTable spelling; used if the camelCase value is empty.",
        json_schema_extra={"deprecated": True})
    custom_tables: list[SudokuTable] | None = Field(
        None, description="Legacy customTables spelling.", json_schema_extra={"deprecated": True})
    padding_min: UInt32 | None = Field(
        None, description="Legacy paddingMin spelling; used when paddingMin is zero.",
        json_schema_extra={"deprecated": True})
    padding_max: UInt32 | None = Field(
        None, description="Legacy paddingMax spelling; used when paddingMax is zero.",
        json_schema_extra={"deprecated": True})


class XDNSDomain(MaskOptions):
    """DNS tunnel domain and wire-format limits."""

    names: list[StrictStr] | None = Field(
        None, description="DNS tunnel domains configured on the peer.", examples=[["tunnel.example.com"]])
    lenLimit: StrictInt | None = Field(None, ge=0, le=255, description="Maximum full DNS name length; 0 uses 255.")
    labelLimit: StrictInt | None = Field(None, ge=0, le=63, description="Maximum DNS label length; 0 uses 63.")
    types: list[Literal[1, 5, 16, 28]] | None = Field(
        None, description="DNS record types: 1=A, 5=CNAME, 16=TXT, 28=AAAA.")
    edns0: zero_or_integer(512, 4096) | None = Field(
        None, description="EDNS0 UDP size: 0 disables it; otherwise 512-4096.")


class XDNSResolver(MaskOptions):
    """Resolver endpoints. Protocols supported by the Xray loader: UDP, TCP and HTTPS."""

    addrs: list[Annotated[StrictStr, Field(pattern=r"^(?:(?:udp|tcp|https)://)?[^\s/]+(?:/[^\s]*)?$")]] | None = Field(
        None, description="Resolver endpoints; no scheme means udp, no UDP/TCP port means 53.",
        examples=[["1.1.1.1:53", "https://dns.example.com/dns-query"]])
    worker: StrictInt | None = Field(None, ge=0, le=2147483647, description="Concurrent resolver workers; 0 uses 32.")
    tlsConfig: TLSOptions | None = Field(None, description="TLS settings for the resolver connection.")
    quicConfig: QuicParams | None = Field(None, description="QUIC tuning for compatible resolver connections.")

    @field_validator("addrs")
    @classmethod
    def check_protocols(cls, values):
        for value in values or []:
            parsed = urlsplit(value if "://" in value else "udp://" + value)
            if parsed.scheme not in ("tcp", "udp", "https") or not parsed.hostname:
                raise ValueError("XDNS resolver must use udp, tcp or https and contain a host")
            parsed.port  # Validate a supplied port without resolving or connecting to the host.
        return values


class XDNS(MaskOptions):
    """UDP-over-DNS masking, normally combined with mKCP; client/server roles use different lists."""

    domains: list[XDNSDomain] | None = Field(None, description="Tunnel domain definitions; must agree with the peer.")
    resolvers: list[XDNSResolver] | None = Field(
        None, description="Client DNS resolvers; server-only configurations may omit them.")
    extraPoll: StrictInt | None = Field(None, ge=0, le=3, description="Additional poll level, from 0 to 3.")


class XMCProfile(MaskOptions):
    """Signed Minecraft profile; cryptographic signatures are verified by Xray."""

    username: Annotated[StrictStr, Field(
        pattern=r"^[A-Za-z0-9_]{3,16}$")] = Field(description="Minecraft name, 3-16 ASCII letters/digits/underscores.")
    uuid: Annotated[StrictStr, Field(pattern=(
        r"^(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})$"))] = Field(
        description="Profile UUID, with or without hyphens.", examples=["12345678-1234-5678-1234-567812345678"])
    texturesValue: Annotated[StrictStr, Field(min_length=1)] = Field(
        description="Signed profile textures payload from the profile provider.")
    texturesSignature: Annotated[StrictStr, Field(min_length=1)] = Field(
        description="Signature of texturesValue, from the profile provider.")

    @field_validator("uuid")
    @classmethod
    def check_uuid(cls, value):
        UUID(value)
        return value


class XMC(MaskOptions):
    """TCP Minecraft session imitation; requires matching credentials and signed profiles."""

    hostname: StrictStr | None = Field(
        None, description="Minecraft handshake host; defaults to the outbound destination.")
    profiles: list[XMCProfile] = Field(min_length=1, description="At least one signed Minecraft profile.")
    password: Annotated[StrictStr, Field(min_length=1)] = Field(description="Shared XMC password; must match the peer.")


def validate_ip(value: str) -> str:
    ipaddress.ip_address(value)
    return value


IPAddress = Annotated[StrictStr, AfterValidator(validate_ip), WithJsonSchema({
    "anyOf": [{"type": "string", "format": "ipv4"}, {"type": "string", "format": "ipv6"}],
})]


class XICMP(MaskOptions):
    """Wrap UDP traffic in ICMP; client OS permissions and peer support are required."""

    dgram: StrictBool | None = Field(None, description="Use an ICMP datagram socket instead of a raw socket.")
    ips: list[IPAddress] | None = Field(
        None, description="IP literals for ICMP endpoints; CIDR ranges are not accepted.")


class PortMapping(MaskOptions):
    """Realm automatic port mapping on supported networks."""

    enabled: StrictBool | None = Field(None, description="Enable Realm port mapping.")
    timeout: StrictInt | None = Field(None, ge=0, le=9223372036854775807,
                                      description="Port mapping request timeout in seconds.")
    lifetime: StrictInt | None = Field(None, ge=0, le=9223372036854775807,
                                       description="Requested port mapping lifetime in seconds.")


class Realm(MaskOptions):
    """UDP rendezvous through Realm signaling and STUN."""

    url: Annotated[StrictStr, Field(pattern=r"^realm(?:\+http)?://[^\s/@]+@[^\s/]+/.+$")] = Field(
        description="Signaling URL: realm://token@host/id (HTTPS) or realm+http://token@host/id.",
        examples=["realm://token@signal.example.com/session"])
    stunServers: list[StrictStr] = Field(
        min_length=1, description="STUN endpoints as host:port, with brackets around IPv6.",
        examples=[["stun.example.com:3478"]])
    tlsConfig: TLSOptions | None = Field(None, description="TLS settings for the signaling server.")
    ipMode: Literal["", "dual", "ipv4", "ipv6"] | None = Field(
        None, description="Realm IP family preference; empty uses the core default.")
    portMapping: PortMapping | None = Field(None, description="Automatic port mapping settings.")

    @field_validator("url")
    @classmethod
    def check_url(cls, value):
        parsed = urlsplit(value)
        if not parsed.hostname or not parsed.username or not parsed.path.lstrip("/"):
            raise ValueError("Realm URL requires a host, token and session ID")
        parsed.port
        return value

    @field_validator("stunServers")
    @classmethod
    def check_stun(cls, values):
        for value in values:
            parsed = urlsplit("//" + value)
            if not parsed.hostname or parsed.port is None or parsed.path or parsed.username:
                raise ValueError("STUN endpoints must be host:port")
        return values


def validate_network(value: str) -> str:
    ipaddress.ip_network(value, strict=False)
    return value


IPNetwork = Annotated[StrictStr, AfterValidator(validate_network)]
HOP_MODE = r"^(?:intervallocal|intervalremote|perconnremote)(?:,(?:intervallocal|intervalremote|perconnremote))*$"


class UDPHop(MaskOptions):
    """UDP endpoint hopping. Remote hopping requires matching server-side port routing."""

    mode: Annotated[StrictStr, Field(pattern=HOP_MODE)] = Field(
        description=("Comma-separated intervallocal, intervalremote, perconnremote. "
                     "Local mode needs a supported transport."),
        examples=["intervalremote", "intervallocal,intervalremote"])
    interval: zero_or_range(5) | None = Field(
        None, description="Hop interval in seconds: 0 uses 30, otherwise at least 5; ranges are allowed.")
    remoteIPs: list[IPNetwork] | None = Field(
        None, description="Remote IPs/CIDRs; omitted list inherits the destination.")
    remotePorts: PortList | None = Field(
        None, description="Remote port or comma-separated ports/ranges; omitted inherits the destination.")
