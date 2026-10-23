"""Complete XHTTP extra contract, including native downstream stream settings."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from app.models.finalmask import FinalMask
from app.models.finalmask.quic import TLSOptions
from app.models.socket_options import SocketOptions
from .common import INT32_MAX, Int64, NonnegativeInt64, TOKEN_PATTERN, XRAY_XHTTP_SOURCE
from .common import XhttpModel, XhttpRange, range_bounds, range_schema, signed_number_pattern


Mode = Literal["", "auto", "packet-up", "stream-up", "stream-one"]
Placement = Literal["", "path", "cookie", "header", "query"]
_TABLE_SIZES = {"ALPHABET": 26, "Alphabet": 52, "BASE36": 36, "Base62": 62,
                "HEX": 16, "alphabet": 26, "base36": 36, "hex": 16, "number": 10}
_POSITIVE_NUMBER = signed_number_pattern(1)
_SIGNED_NUMBER = signed_number_pattern()
_ACTIVE_RANGE = {"anyOf": [
    {"type": "integer", "minimum": 1},
    {"type": "string", "pattern": (
        f"^(?:{_POSITIVE_NUMBER}(?:-{_SIGNED_NUMBER})?|{_SIGNED_NUMBER}-{_POSITIVE_NUMBER})$")},
]}


class XhttpMux(XhttpModel):
    """XHTTP HTTP connection reuse. Ranges accept numbers, numeric strings and reversed A-B endpoints."""

    model_config = ConfigDict(json_schema_extra={"allOf": [{"not": {
        "required": ["maxConnections", "maxConcurrency"],
        "properties": {"maxConnections": _ACTIVE_RANGE, "maxConcurrency": _ACTIVE_RANGE},
    }}]})
    maxConcurrency: XhttpRange | None = Field(
        None, description="Concurrent streams per HTTP connection. Cannot be positive with maxConnections.",
        examples=[0, "8-16"])
    maxConnections: XhttpRange | None = Field(
        None, description="Number of HTTP connections. Cannot be positive with maxConcurrency; core pool default is 3.",
        examples=[3, "2-4"])
    cMaxReuseTimes: XhttpRange | None = Field(
        None, description="Connection reuse count; 0 leaves this limit unlimited.", examples=[0, "32-64"])
    hMaxRequestTimes: XhttpRange | None = Field(
        None, description="HTTP requests per connection; the default pool uses 600-900.", examples=["600-900"])
    hMaxReusableSecs: XhttpRange | None = Field(
        None, description="HTTP connection lifetime in seconds; the default pool uses 1800-3000.",
        examples=["1800-3000"])
    hKeepAlivePeriod: Int64 | None = Field(
        None, description="HTTP/2 KeepAlive period in seconds. 0 uses the core default; negative disables it.",
        examples=[0, 30, -1])

    @model_validator(mode="after")
    def check_limits(self):
        if range_bounds(self.maxConnections)[1] > 0 and range_bounds(self.maxConcurrency)[1] > 0:
            raise ValueError("maxConnections cannot be positive together with maxConcurrency")
        return self


class XhttpExtra(XhttpModel):
    """Advanced XHTTP settings. This object replaces inbound extra atomically; omitted keys use core defaults."""

    model_config = ConfigDict(json_schema_extra={
        "$comment": XRAY_XHTTP_SOURCE,
        "defaultSnippets": [
            {"label": "XHTTP: upload method", "description": "Use PUT for uplink requests.",
             "body": {"uplinkHTTPMethod": "PUT"}},
            {"label": "XHTTP: packet-up GET", "description": "The inbound must use packet-up mode.",
             "body": {"uplinkHTTPMethod": "GET", "uplinkDataPlacement": "header", "uplinkChunkSize": "3000-4000"}},
            {"label": "XHTTP: connection reuse",
             "description": "Choose a connection-count range, without maxConcurrency.",
             "body": {"xmux": {"maxConnections": "2-4", "hMaxRequestTimes": "600-900"}}},
            {"label": "XHTTP: separate download", "description": "Requires a mode other than stream-one.",
             "body": {"downloadSettings": {"address": "download.example.com", "port": 443, "network": "xhttp",
                                           "security": "tls", "tlsSettings": {"serverName": "download.example.com"},
                                           "xhttpSettings": {"path": "/download"}}}},
        ],
        "allOf": [{
            "if": {"required": ["sessionIDTable"], "properties": {"sessionIDTable": {"minLength": 1}}},
            "then": {"required": ["sessionIDLength"], "properties": {"sessionIDLength": range_schema(1, empty=False)}},
        }],
    })
    scMaxBufferedPosts: NonnegativeInt64 | None = Field(
        None, description="Server-side buffered packet-up requests per session; 0 uses the core default 30.",
        examples=[0, 30])
    xPaddingObfsMode: StrictBool | None = Field(
        None, description="Enable configurable padding placement/method. False retains legacy Referer padding.",
        examples=[False, True])
    uplinkHTTPMethod: StrictStr | None = Field(
        None, max_length=32, description="Upload HTTP method; default POST. GET requires packet-up mode.",
        examples=["POST", "PUT", "GET"], json_schema_extra={"anyOf": [
            {"enum": ["POST", "PUT", "PATCH", "GET", "HEAD", "OPTIONS", "DELETE"]},
            {"type": "string", "pattern": TOKEN_PATTERN},
        ]})
    xPaddingBytes: XhttpRange | None = Field(
        None, description="Padding bytes: positive integer/range; 0 or empty uses the core default 100-1000.",
        examples=["100-1000"], json_schema_extra={"anyOf": [
            {"type": "integer", "minimum": 0, "maximum": INT32_MAX},
            {"type": "string", "pattern": (
                f"^(?:{_POSITIVE_NUMBER}(?:-{_POSITIVE_NUMBER})?|[+-]?0+(?:-[+-]?0+)?|)$")},
        ]})
    xPaddingKey: StrictStr | None = Field(
        None, description="Padding cookie/query key; empty uses x_padding.", examples=["x_padding"])
    xPaddingHeader: StrictStr | None = Field(
        None, description="Padding HTTP header; empty uses X-Padding when obfuscation is enabled.",
        examples=["X-Padding"])
    xPaddingMethod: Literal["", "repeat-x", "tokenish"] | None = Field(
        None, description="Padding generator; empty uses repeat-x.", examples=["repeat-x", "tokenish"])
    xPaddingPlacement: Literal["", "cookie", "header", "query", "queryInHeader"] | None = Field(
        None, description="Padding location; empty uses queryInHeader.", examples=["header", "queryInHeader"])
    noGRPCHeader: StrictBool | None = Field(
        None, description="Omit application/grpc Content-Type on streaming upload requests.", examples=[False])
    noSSEHeader: StrictBool | None = Field(
        None, description="Server-side: omit text/event-stream Content-Type on the download response.",
        examples=[False])
    scMaxEachPostBytes: XhttpRange | None = Field(
        None, description=("Packet-up upload size in bytes; 0 uses 1000000. "
                           "Client and server limits must be compatible."),
        examples=[1000000, "500000-1000000"])
    scMaxConcurrentPosts: XhttpRange | None = Field(
        None, description="Legacy concurrent POST limit. Preserved for older clients; absent from current Xray.",
        examples=[100], json_schema_extra={"deprecated": True})
    scMinPostsIntervalMs: XhttpRange | None = Field(
        None, description="Minimum packet-up request interval in milliseconds; 0 uses 30.", examples=[30, "10-30"])
    scStreamUpServerSecs: XhttpRange | None = Field(
        None, description="Server-side stream-up connection lifetime in seconds; 0 uses 20-80.", examples=["20-80"])
    sessionIDPlacement: Placement | None = Field(
        None, description="Session ID location; empty uses path. Client and server settings must match.",
        examples=["header"])
    sessionIDKey: StrictStr | None = Field(
        None, description="Session cookie/query/header key; defaults to x_session or X-Session according to placement.",
        examples=["X-Session"])
    sessionIDTable: StrictStr | None = Field(
        None, pattern=r"^[\x00-\x7f]*$", description=(
            "Session alphabet: named preset or ASCII characters. Empty uses UUID. With a custom alphabet, "
            "sessionIDLength must be positive and offer at least 2^31 possibilities; checked by the server."),
        examples=["Base62", "hex"], json_schema_extra={"anyOf": [
            {"enum": list(_TABLE_SIZES)}, {"type": "string", "pattern": r"^[\x00-\x7f]*$"},
        ]})
    sessionIDLength: XhttpRange | None = Field(
        None, description="Session ID character count/range when sessionIDTable is nonempty; ignored for UUID mode.",
        examples=[16, "16-24"])
    seqPlacement: Placement | None = Field(
        None, description="Packet sequence number location; empty uses path. Must match the server.",
        examples=["query"])
    seqKey: StrictStr | None = Field(
        None, description="Sequence cookie/query/header key; defaults to x_seq or X-Seq according to placement.",
        examples=["x_seq"])
    uplinkDataPlacement: Literal["", "auto", "body", "cookie", "header"] | None = Field(
        None, description=("Upload payload location; cookie/header require packet-up. "
                           "Auto chooses a method-aware default."),
        examples=["auto", "body", "header"])
    uplinkDataKey: StrictStr | None = Field(
        None, description="Upload payload cookie/header prefix; empty uses x_data or X-Data.", examples=["X-Data"])
    uplinkChunkSize: XhttpRange | None = Field(
        None, description=("Encoded payload chunk size in bytes for headers/cookies; 0 chooses a placement default. "
                           "The core clamps a nonzero range below 64 to at least 64."), examples=["3000-4000"])
    serverMaxHeaderBytes: Annotated[StrictInt, Field(ge=0, le=INT32_MAX)] | None = Field(
        None, description="Server-side HTTP header size limit in bytes; 0 uses 8192.", examples=[8192, 16384])
    headers: dict[StrictStr, StrictStr] | None = Field(
        None, description="Extra HTTP request headers. Host is configured by the host field, not in this object.",
        examples=[{"User-Agent": "Mozilla/5.0"}], json_schema_extra={
            "propertyNames": {"pattern": r"^(?!(?:[Hh][Oo][Ss][Tt])$)[!#$%&'*+.^_`|~0-9A-Za-z-]+$"},
            "additionalProperties": {"type": "string", "pattern": r"^[^\r\n\x00]*$"},
        })
    xmux: XhttpMux | None = Field(
        None, description="HTTP connection reuse pool; incompatible with ordinary mux on the same connection.",
        examples=[{"maxConnections": "2-4"}])
    downloadSettings: XhttpDownloadSettings | None = Field(
        None, description=("Separate XHTTP download stream. "
                           "Requires address/port and XHTTP network; not for stream-one."))

    @field_validator("uplinkHTTPMethod")
    @classmethod
    def validate_method(cls, value):
        if value is None or not re.fullmatch(TOKEN_PATTERN, value.strip()):
            raise ValueError("Uplink HTTP method must be a nonempty HTTP token")
        return value.strip().upper()

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, value):
        if value is not None:
            for name, content in value.items():
                if not re.fullmatch(TOKEN_PATTERN, name) or name.lower() == "host":
                    raise ValueError("Use HTTP header names other than Host")
                if any(char in content for char in "\r\n\x00"):
                    raise ValueError("HTTP header values cannot contain CR, LF or NUL")
        return value

    @model_validator(mode="after")
    def check_padding_and_session(self):
        # Native downstream settings can replace sibling options with their own extra.
        if getattr(self, "extra", None) is not None:
            return self
        low, high = range_bounds(self.xPaddingBytes)
        if low <= 0 and (low != 0 or high != 0):
            raise ValueError("xPaddingBytes cannot be disabled; use a positive range or 0 for the core default")
        if self.sessionIDTable:
            low, high = range_bounds(self.sessionIDLength)
            size = _TABLE_SIZES.get(self.sessionIDTable, len(self.sessionIDTable))
            # Avoid unbounded big-integer work on user-supplied int32 lengths.
            enough = size >= 2 and (high >= 31 or sum(size ** k for k in range(max(1, low), high + 1)) >= 2**31)
            if low <= 0 or not enough:
                raise ValueError(
                    "sessionIDTable/sessionIDLength must be positive and offer at least 2^31 possibilities")
        return self

    def validate_mode(self, mode: str):
        if self.uplinkHTTPMethod == "GET" and mode != "packet-up":
            raise ValueError("GET requires packet-up mode")
        if self.uplinkDataPlacement in {"cookie", "header"} and mode != "packet-up":
            raise ValueError("uplinkDataPlacement cookie/header requires packet-up mode")
        if self.downloadSettings is not None and mode == "stream-one":
            raise ValueError("downloadSettings cannot be used in stream-one mode")


def _mode_rule(condition, constraints, *, require_mode=False):
    when = {"properties": {"mode": condition}}
    if require_mode:
        when["required"] = ["mode"]
    return {"if": when, "then": {"anyOf": [
        {"required": ["extra"], "properties": {"extra": constraints}},
        {"allOf": [{"not": {"required": ["extra"]}}, constraints]},
    ]}}


def _native_settings_schema():
    # Match Xray's atomic extra semantics in Monaco as well as API validation.
    return {"allOf": [
        {"if": {"not": {"required": ["extra"]}},
         "then": {"allOf": XhttpExtra.model_config["json_schema_extra"]["allOf"]}},
        _mode_rule({"enum": ["", "auto", "stream-up", "stream-one"]}, {"properties": {
            "uplinkHTTPMethod": {"not": {"pattern": "^[Gg][Ee][Tt]$"}},
            "uplinkDataPlacement": {"not": {"enum": ["cookie", "header"]}},
        }}),
        _mode_rule({"const": "stream-one"}, {"not": {"required": ["downloadSettings"]}}, require_mode=True),
    ]}


class XhttpSettings(XhttpExtra):
    """Native downstream xhttpSettings. Host/path/mode stay outside the optional atomic extra object."""

    model_config = ConfigDict(json_schema_extra=_native_settings_schema())
    host: StrictStr | None = Field(
        None, description="HTTP host for the separate download endpoint.", examples=["cdn.example.com"])
    path: StrictStr | None = Field(
        None, description="Download endpoint path and optional query.", examples=["/download"])
    mode: Mode | None = Field(None, description="XHTTP mode; empty/omitted uses auto.", examples=["auto", "stream-up"])
    extra: XhttpExtra | None = Field(None, description="Atomic advanced settings; replaces sibling advanced options.")

    @model_validator(mode="after")
    def check_mode(self):
        (self.extra if self.extra is not None else self).validate_mode(self.mode or "auto")
        return self


class XhttpTLS(TLSOptions):
    """Native TLS settings for the separate XHTTP download connection."""


class XhttpReality(XhttpModel):
    """Client REALITY settings for the separate download connection; cryptographic keys are checked by Xray."""

    show: StrictBool | None = Field(None, description="Enable REALITY diagnostic output.")
    masterKeyLog: StrictStr | None = Field(None, description="Client-machine path to the REALITY TLS key log.")
    fingerprint: StrictStr | None = Field(
        None, description="ClientHello profile; Xray requires a supported uTLS profile.", examples=["chrome"])
    serverName: StrictStr | None = Field(None, description="REALITY server name/SNI.", examples=["www.example.com"])
    password: StrictStr | None = Field(
        None, description="Server X25519 public key, in unpadded Base64URL. Takes priority over publicKey.")
    publicKey: StrictStr | None = Field(None, description="Legacy spelling of the REALITY server public key.")
    shortId: StrictStr | None = Field(
        None, pattern=r"^(?:[0-9a-fA-F]{2}){0,8}$",
        description="Even-length hexadecimal short ID, up to 16 characters.", examples=["0123456789abcdef"])
    mldsa65Verify: StrictStr | None = Field(
        None, description="Optional ML-DSA-65 verification key in unpadded Base64URL.")
    spiderX: StrictStr | None = Field(None, pattern=r"^(?:/.*)?$",
                                      description="REALITY spider path; empty uses /.", examples=["/"])


class XhttpDownloadSettings(XhttpModel):
    """Separate XHTTP download stream with its own address/port, TLS/REALITY and socket options; not for stream-one."""

    model_config = ConfigDict(json_schema_extra={
        "anyOf": [{"required": ["network"]}, {"required": ["method"]}],
        "allOf": [{
            "if": {"required": ["security"], "properties": {"security": {"const": "reality"}}},
            "then": {"required": ["realitySettings"]},
        }],
    })
    address: StrictStr = Field(min_length=1, description="Separate download server address.",
                               examples=["download.example.com"])
    port: Annotated[StrictInt, Field(ge=1, le=65535)] = Field(
        description="Separate download server port.", examples=[443])
    network: Literal["xhttp", "splithttp"] | None = Field(
        None, description="Download transport; must be XHTTP.", examples=["xhttp"])
    method: Literal["xhttp", "splithttp"] | None = Field(
        None, description="Legacy network spelling; takes precedence over network.")
    security: Literal["", "none", "tls", "reality"] | None = Field(
        None, description="Download transport security; omitted/empty uses none.", examples=["tls"])
    tlsSettings: XhttpTLS | None = Field(None, description="Native TLS options for the download stream.")
    realitySettings: XhttpReality | None = Field(
        None, description="Native client REALITY options for the download stream.")
    xhttpSettings: XhttpSettings | None = Field(
        None, description="Download XHTTP settings; takes precedence over splithttpSettings.")
    splithttpSettings: XhttpSettings | None = Field(None, description="Legacy spelling of download xhttpSettings.")
    sockopt: SocketOptions | None = Field(
        None, description="Download socket options, unless parent sockopt.penetrate overrides them.")
    finalmask: FinalMask | None = Field(None, description="Final stream masks for the separate download connection.")

    @model_validator(mode="after")
    def check_transport(self):
        if self.network is None and self.method is None:
            raise ValueError("downloadSettings requires XHTTP network or method")
        if self.security == "reality" and self.realitySettings is None:
            raise ValueError("downloadSettings security=reality requires realitySettings")
        return self


XhttpExtra.model_rebuild()
XhttpSettings.model_rebuild()
XhttpDownloadSettings.model_rebuild()
