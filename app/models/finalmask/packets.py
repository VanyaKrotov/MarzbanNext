"""Custom headers, byte expressions and UDP noise used by FinalMask."""

import re
from typing import Literal

from pydantic import ConfigDict, Field, StrictInt, StrictStr, model_serializer, model_validator

from .common import ByteRange, MaskOptions, Packet, Range, UInt64, Variable
from .common import decimal_pattern, exclusive_source_rules, packet_rules, range_bounds, validate_packet


Encoding = Literal["", "array", "str", "hex", "base64"]
Operation = Literal[
    "concat", "slice", "xor16", "xor32", "be16", "be32", "le16", "le32", "le64",
    "pad", "truncate", "add", "sub", "and", "or", "shl", "shr",
]
ARGUMENT_COUNTS = {
    "slice": 3, "xor16": 2, "xor32": 2, "be16": 1, "be32": 1, "le16": 1,
    "le32": 1, "le64": 1, "pad": 3, "truncate": 2, "add": 2, "sub": 2,
    "and": 2, "or": 2, "shl": 2, "shr": 2,
}
METADATA = Literal[
    "", "local_port", "remote_port", "src_port_u16", "dst_port_u16",
    "local_ip4_u32", "remote_ip4_u32", "src_ip4_u32", "dst_ip4_u32",
]
_HEADER_SOURCES = {
    "packet": {}, "rand": {"type": "integer", "minimum": 1},
    "reuse": {"type": "string", "minLength": 1}, "transform": {"type": "object"},
}
_ARGUMENT_SOURCES = {
    "bytes": {}, "u64": {"type": "integer"}, "reuse": {"type": "string", "minLength": 1},
    "metadata": {"type": "string", "minLength": 1}, "transform": {"type": "object"},
}


class PacketOptions(MaskOptions):
    @model_serializer(mode="wrap")
    def preserve_explicit_packet_null(self, handler):
        result = handler(self)
        # A present null RawMessage counts as a packet in Xray, unlike an omitted key.
        for name in ("packet", "bytes"):
            if name in self.model_fields_set and getattr(self, name, None) is None:
                result[name] = None
        return result


class TransformArgument(PacketOptions):
    """Exactly one byte value, integer, variable, metadata value or nested expression."""

    model_config = ConfigDict(json_schema_extra={
        "allOf": packet_rules("bytes") + exclusive_source_rules(_ARGUMENT_SOURCES, required=True),
    })
    type: Encoding | None = Field(None, description="Encoding of bytes; omitted/array accepts byte arrays or Base64.")
    bytes: Packet | None = Field(None, description="Literal bytes. Choose only one argument source.", examples=[[1, 2]])
    u64: UInt64 | None = Field(None, description="Unsigned 64-bit integer; zero is an explicit value.")
    reuse: Variable | None = Field(None, description="Name of a value captured by an earlier header item.")
    metadata: METADATA | None = Field(
        None, description="Endpoint port or IPv4 integer; requires matching runtime metadata.")
    transform: "CustomTransform | None" = Field(None, description="Nested expression evaluated by the client core.")

    @model_validator(mode="after")
    def check_source(self):
        sources = ["bytes" in self.model_fields_set, self.u64 is not None,
                   bool(self.reuse), bool(self.metadata), self.transform is not None]
        if sum(sources) != 1:
            raise ValueError("A transform argument must set exactly one source")
        if self.bytes is not None:
            validate_packet(self.bytes, self.type or "array")
        return self


class CustomTransform(MaskOptions):
    """Byte/integer expression. Types of intermediate values are checked by Xray at runtime."""

    model_config = ConfigDict(json_schema_extra={"allOf": [
        {"if": {"required": ["op"], "properties": {"op": {"const": op}}},
         "then": {"properties": {"args": {"minItems": count, "maxItems": count}}}}
        for op, count in ARGUMENT_COUNTS.items()
    ]})
    op: Operation = Field(description=(
        "concat joins bytes; slice(bytes,start,end); xor16/xor32(bytes,key); be/le encode integers; "
        "pad(bytes,length,fillBytes); truncate(bytes,length); add/sub/and/or/shl/shr operate on two integers."))
    args: list[TransformArgument] = Field(
        min_length=1, description="Ordered operands; nested transforms are supported.")

    @model_validator(mode="after")
    def check_arity(self):
        expected = ARGUMENT_COUNTS.get(self.op)
        if expected is not None and len(self.args) != expected:
            raise ValueError(f"{self.op} requires {expected} arguments")
        return self


class UDPHeaderItem(PacketOptions):
    """One header item: fixed bytes, random bytes, a captured value or a transform."""

    model_config = ConfigDict(json_schema_extra={
        "allOf": packet_rules() + exclusive_source_rules(_HEADER_SOURCES) + [{
            "if": {"required": ["capture"], "properties": {"capture": {"type": "string", "minLength": 1}}},
            "then": {"allOf": exclusive_source_rules(_HEADER_SOURCES, required=True)},
        }],
    })
    rand: StrictInt | None = Field(None, ge=0, le=2147483647,
                                   description="Number of random bytes; 0 disables randomness.")
    randRange: ByteRange | None = Field(None, description="Inclusive random byte range, default 0-255.")
    capture: Variable | None = Field(None, description="Save generated bytes under this variable name for later reuse.")
    type: Encoding | None = Field(None, description="Packet encoding; str is literal text, hex has no 0x prefix.")
    reuse: Variable | None = Field(None, description="Emit the bytes saved by an earlier capture.")
    transform: CustomTransform | None = Field(None, description="Compute bytes using the expression language.")
    packet: Packet | None = Field(None, description="Literal byte array or encoded string.", examples=[[22, 3, 1]])

    @model_validator(mode="after")
    def check_kind(self):
        kinds = ["packet" in self.model_fields_set, bool(self.rand), bool(self.reuse), self.transform is not None]
        if sum(kinds) > 1 or (self.capture and sum(kinds) != 1):
            raise ValueError("Choose one header item source: packet, positive rand, reuse or transform")
        if self.packet is not None:
            validate_packet(self.packet, self.type or "array")
        return self


class TCPHeaderItem(UDPHeaderItem):
    """TCP header item, with an optional delay before sending it."""

    delay: Range | None = Field(None, description="Delay before this item in milliseconds, as an integer or A-B range.")


class TCPHeader(MaskOptions):
    """TCP handshake sequences. Each inner list is one sequence of header items."""

    clients: list[list[TCPHeaderItem]] | None = Field(None, description="Client handshake sequences, sent in order.")
    servers: list[list[TCPHeaderItem]] | None = Field(None, description="Matching server response sequences.")
    errors: list[list[TCPHeaderItem]] | None = Field(None, description="Server responses for an invalid handshake.")


class UDPHeader(MaskOptions):
    """Prefix each UDP datagram, or send separate standalone datagrams."""

    mode: Literal["", "prefix", "standalone"] | None = Field(
        None, description="Empty uses prefix; standalone sends separate packets.")
    client: list[UDPHeaderItem] | None = Field(None, description="Client packet sequence or prefix.")
    server: list[UDPHeaderItem] | None = Field(None, description="Server packet sequence or prefix.")


# Full-match tokens also let Monaco validate expressions without running Lua or client code.
_HEX_BYTES = r"(?:[0-9a-fA-F]\s*[0-9a-fA-F]\s*)+"
_COUNT = decimal_pattern(0, 65535)
_SIZE = rf"{_COUNT}(?:-{_COUNT})?"
NOISE_EXPRESSION = (
    rf"^\s*(?:<\s*(?:b\s+(?:0[xX])?{_HEX_BYTES}|r(?:c|d)?\s+{_SIZE}|[tcn])\s*>\s*)+$"
)


def validate_noise_expression(value: str):
    if not re.fullmatch(NOISE_EXPRESSION, value):
        raise ValueError("Expected noise tokens: <b HEX>, <r N>, <rc A-B>, <rd N>, <t>, <c> or <n>")
    for low, high in re.findall(r"<\s*r(?:c|d)?\s+([0-9]+)(?:-([0-9]+))?\s*>", value):
        if not 0 <= int(low) <= int(high or low) <= 65535:
            raise ValueError("Random expression lengths must be ordered and between 0 and 65535")


class NoiseItem(PacketOptions):
    """One UDP noise datagram, either random bytes, encoded bytes or an expression."""

    model_config = ConfigDict(json_schema_extra={"allOf": packet_rules() + exclusive_source_rules({
        "packet": {}, "rand": {"anyOf": [{"type": "integer", "minimum": 1},
                                         {"type": "string", "pattern": "[1-9]"}]},
    }) + [{
        "if": {"required": ["type"], "properties": {"type": {"const": "exp"}}},
        "then": {"required": ["packet"], "properties": {"packet": {"type": "string", "pattern": NOISE_EXPRESSION}}},
    }]})
    rand: Range | None = Field(None, description="Random packet length in bytes; conflicts with an explicit packet.")
    randRange: ByteRange | None = Field(None, description="Inclusive byte values for random data, default 0-255.")
    type: Literal["", "array", "str", "hex", "base64", "exp"] | None = Field(
        None, description="Payload encoding; exp enables token expressions.")
    packet: Packet | None = Field(None, description=(
        "Byte array or encoded string. exp tokens: <b HEX>, <r N|A-B> random bytes, "
        "<rc N|A-B> letters, <rd N|A-B> digits, <t> timestamp, <c> counter, <n> nonce."),
        examples=["<b 0001><r 8-16><t><c><n>"])
    delay: Range | None = Field(None, description="Delay after the noise item in milliseconds.")

    @model_validator(mode="after")
    def check_packet(self):
        if self.rand is not None and range_bounds(self.rand)[1] > 0 and "packet" in self.model_fields_set:
            raise ValueError("Random noise and an explicit packet cannot be combined")
        if self.type == "exp":
            if not isinstance(self.packet, str):
                raise ValueError("Noise expressions require a string packet")
            validate_noise_expression(self.packet)
        elif self.packet is not None:
            validate_packet(self.packet, self.type or "array")
        return self


class Noise(MaskOptions):
    """UDP noise schedule or a Lua script, executed by a compatible Xray client."""

    model_config = ConfigDict(json_schema_extra={"allOf": [{
        "if": {"required": ["script"], "properties": {"script": {"type": "string", "minLength": 1}}},
        "then": {"properties": {"noise": {"type": "array", "maxItems": 0}}},
    }]})
    reset: Range | None = Field(
        None, description="Restart the noise sequence after this number of seconds; 0 disables reset.")
    noise: list[NoiseItem] | None = Field(
        None, description="Ordered noise datagrams. Cannot be combined with a nonempty script.")
    script: StrictStr | None = Field(
        None, description="Lua noise script; syntax and execution are checked by the client core.")

    @model_validator(mode="after")
    def check_script(self):
        if self.script and self.noise:
            raise ValueError("script and noise cannot be used together")
        return self
