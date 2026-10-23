"""QUIC and nested TLS settings accepted by Xray FinalMask."""

import re
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, ConfigDict, Field, StrictBool, StrictInt, StrictStr, WithJsonSchema
from pydantic import model_validator

from app.models.socket_options import SocketOptions

from .common import MaskOptions, UInt64, decimal_pattern, integer_range, zero_or_integer


Bandwidth = Annotated[StrictStr, Field(pattern=(
    r"^\s*(?:(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\s*"
    r"(?:[bB](?:[pP][sS])?|[kKmMgGtT](?:[bB](?:[pP][sS])?)?)?)?\s*$"))]


def bandwidth_bytes(value: str) -> int:
    if not value.strip():
        return 0
    match = re.fullmatch(r"\s*([0-9.]+)\s*([a-z]*)\s*", value.lower())
    amount, unit = match.groups()
    prefix = unit[:1] if unit else ""
    # Xray's Bandwidth parser uses binary multipliers, despite the kbps/mbps names.
    multiplier = 1024 ** {"": 0, "b": 0, "k": 1, "m": 2, "g": 3, "t": 4}[prefix]
    return int(Decimal(amount) * multiplier) // 8


def validate_bandwidth(value):
    rate = bandwidth_bytes(value)
    if 0 < rate < 65536 or rate > 18446744073709551615:
        raise ValueError("Brutal bandwidth must be zero or at least 524288 bits/s (65536 bytes/s)")
    return value


BrutalBandwidth = Annotated[Bandwidth, AfterValidator(validate_bandwidth)]


def validate_ports(value):
    if isinstance(value, int):
        if not 0 <= value <= 65535:
            raise ValueError("Port must be between 0 and 65535; zero uses an empty list")
        return value
    for segment in value.split(","):
        segment = segment.strip()
        if not segment or re.fullmatch(r"env:[A-Za-z_][A-Za-z0-9_]*", segment):
            continue
        parts = segment.split("-")
        if len(parts) > 2 or not all(part.isdecimal() and 0 <= int(part) <= 65535 for part in parts):
            raise ValueError("Expected a comma-separated list of ports or port ranges")
    return value


_PORT = decimal_pattern(0, 65535)
_PORT_SEGMENT = rf"\s*(?:{_PORT}(?:-{_PORT})?|env:[A-Za-z_][A-Za-z0-9_]*)?\s*"
PortList = Annotated[StrictInt | StrictStr, AfterValidator(validate_ports), WithJsonSchema({
    "anyOf": [{"type": "integer", "minimum": 0, "maximum": 65535},
              {"type": "string", "pattern": f"^{_PORT_SEGMENT}(?:,{_PORT_SEGMENT})*$",
               "patternErrorMessage": "Use ports from 0 to 65535, comma-separated ranges, or env:NAME."}],
    "description": "Port/ranges or env:NAME resolved by the client; empty string/zero means an empty list.",
    "examples": [443, "443,20000-50000"],
})]


class LegacyQuicHop(MaskOptions):
    """Port hopping settings used by older Xray QUIC configurations."""

    ports: PortList | None = Field(None, description="Legacy port list/ranges, e.g. 443,20000-50000.")
    interval: integer_range(5) | None = Field(None, description="Legacy hopping interval in seconds, at least 5.")


class QuicParams(MaskOptions):
    """QUIC tuning shared by FinalMask and XDNS resolvers; zero keeps core defaults."""

    model_config = ConfigDict(json_schema_extra={"allOf": [{
        "if": {"required": ["congestion"], "properties": {"congestion": {"const": "force-brutal"}}},
        "then": {"required": ["brutalUp"], "properties": {"brutalUp": {"not": {"enum": [None, "", "0"]}}}},
    }]})
    congestion: Literal["", "reno", "bbr", "brutal", "force-brutal"] | None = Field(
        None, description="QUIC congestion algorithm. force-brutal requires a nonzero brutalUp.")
    bbrProfile: Literal["", "conservative", "standard", "aggressive"] | None = Field(
        None, description="BBR aggressiveness; omitted/empty uses standard.")
    debug: StrictBool | None = Field(None, description="Enable QUIC BBR/Brutal diagnostic logs.")
    brutalUp: BrutalBandwidth | None = Field(None, description=(
        "Upload limit in bits/s as a string, e.g. 60 mbps. Prefixes use 1024-based multipliers. "
        "0 means automatic/negotiated. Nonzero rates must be at least 524288 bits/s."),
        examples=["0", "60 mbps"])
    brutalDown: BrutalBandwidth | None = Field(None, description="Download limit, same units and bounds as brutalUp.")
    brutalDisableLossCompensation: StrictBool | None = Field(None, description="Disable Brutal loss compensation.")
    initStreamReceiveWindow: zero_or_integer(16384) | None = Field(
        None, description="Initial QUIC stream window in bytes; 0 uses the core default.")
    maxStreamReceiveWindow: zero_or_integer(16384) | None = Field(
        None, description="Maximum QUIC stream window in bytes; nonzero minimum 16384.")
    initConnectionReceiveWindow: zero_or_integer(16384) | None = Field(
        None, description="Initial connection window in bytes; nonzero minimum 16384.")
    maxConnectionReceiveWindow: zero_or_integer(16384) | None = Field(
        None, description="Maximum connection window in bytes; nonzero minimum 16384.")
    maxIdleTimeout: zero_or_integer(4, 120) | None = Field(
        None, description="Idle timeout in seconds: 0 (default) or 4-120.")
    keepAlivePeriod: zero_or_integer(2, 60) | None = Field(
        None, description="KeepAlive in seconds: 0 (disabled) or 2-60.")
    disablePathMTUDiscovery: StrictBool | None = Field(None, description="Disable QUIC path MTU discovery.")
    disableChromeParrot: StrictBool | None = Field(None, description="Disable Chrome QUIC fingerprint imitation.")
    disableGSO: StrictBool | None = Field(None, description="Disable UDP Generic Segmentation Offload.")
    maxIncomingStreams: zero_or_integer(8, 9223372036854775807) | None = Field(
        None, description="Server-side incoming streams: 0 (default) or at least 8.")
    disableStatelessReset: StrictBool | None = Field(None, description="Disable QUIC stateless reset packets.")
    udpHop: LegacyQuicHop | None = Field(
        None, description="Legacy Xray port hopping object. New Xray versions use the udp udphop mask.",
        json_schema_extra={"deprecated": True})

    @model_validator(mode="after")
    def check_forced_rate(self):
        if self.congestion == "force-brutal" and (not self.brutalUp or bandwidth_bytes(self.brutalUp) == 0):
            raise ValueError("force-brutal requires a nonzero brutalUp")
        return self


class TLSCertificate(MaskOptions):
    """Inline certificate material or paths read by the client core."""

    certificateFile: StrictStr | None = Field(None, description="Client-machine path to a PEM certificate file.")
    certificate: list[StrictStr] | None = Field(None, description="Inline PEM certificate lines.")
    keyFile: StrictStr | None = Field(None, description="Client-machine path to the private key file.")
    key: list[StrictStr] | None = Field(None, description="Inline PEM private-key lines.")
    usage: Literal["", "encipherment", "verify", "issue"] | None = Field(
        None, description="Certificate purpose; empty uses encipherment.")
    ocspStapling: UInt64 | None = Field(None, description="OCSP refresh interval in seconds; 0 uses the core default.")
    oneTimeLoading: StrictBool | None = Field(None, description="Read certificate files only once.")
    buildChain: StrictBool | None = Field(None, description="Build the certificate chain.")


StringList = StrictStr | list[StrictStr]


class TLSOptions(MaskOptions):
    """TLS settings for XDNS resolvers or Realm signaling connections."""

    allowInsecure: StrictBool | None = Field(
        None, description="Legacy certificate verification bypass; removed in recent Xray versions.",
        json_schema_extra={"deprecated": True})
    certificates: list[TLSCertificate] | None = Field(
        None, description="TLS certificates; files and cryptographic material are checked by the client core.")
    serverName: StrictStr | None = Field(None, description="TLS server name/SNI.")
    alpn: StringList | None = Field(
        None, description="ALPN list or comma-separated string. fromMitm must be the only entry.",
        examples=[["h2", "http/1.1"]])
    enableSessionResumption: StrictBool | None = Field(None, description="Enable TLS session resumption.")
    disableSystemRoot: StrictBool | None = Field(None, description="Exclude system trust roots.")
    minVersion: Literal["", "1.0", "1.1", "1.2", "1.3"] | None = Field(
        None, description="Minimum TLS protocol version.")
    maxVersion: Literal["", "1.0", "1.1", "1.2", "1.3"] | None = Field(
        None, description="Maximum TLS protocol version.")
    cipherSuites: StrictStr | None = Field(None, description="Colon-separated Go TLS cipher-suite names.")
    fingerprint: StrictStr | None = Field(
        None, description="uTLS ClientHello fingerprint; availability depends on the client core.",
        examples=["chrome", "firefox", "randomized", "unsafe"])
    rejectUnknownSni: StrictBool | None = Field(
        None, description="Reject inbound TLS names not covered by certificates.")
    curvePreferences: StringList | None = Field(
        None, description="ECDHE curve names, as a list or comma-separated string.")
    masterKeyLog: StrictStr | None = Field(None, description="Client-machine path for TLS key logging.")
    pinnedPeerCertSha256: StrictStr | None = Field(
        None, description="Pinned certificate SHA-256 fingerprints; checked by Xray.")
    verifyPeerCertByName: StrictStr | None = Field(
        None, description="Certificate names to verify, interpreted by Xray.")
    echServerKeys: StrictStr | None = Field(None, description="ECH server key material.")
    echConfigList: StrictStr | None = Field(None, description="ECH client configuration list.")
    echSockopt: SocketOptions | None = Field(
        None, description="Xray socket options for ECH resolution; same schema as streamSettings.sockopt.")
    useSystemCA: StrictBool | None = Field(None, description="Use the operating-system certificate verification path.")
