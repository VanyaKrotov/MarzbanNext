"""Validated mapper operations and the editor schema exposed through host capabilities."""

from copy import deepcopy
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, WithJsonSchema, model_serializer


TARGET_PATH_PATTERN = r"^(?![\s\S]*(?:__proto__|__class__|constructor))[\s\S]+$"
SOURCE_EXAMPLES = [
    "$host.address", "$host.port", "$host.finalRemark", "$host.protocol", "$host.transport",
    "$host.security", "$host.protocolOptions", "$host.protocolOptions.id", "$host.protocolOptions.password",
    "$host.protocolOptions.auth", "$host.protocolOptions.method", "$host.protocolOptions.flow",
    "$host.metadata", "$host.metadata.remark", "port", "settings.clients[0].id",
    "streamSettings.tlsSettings.serverName", "streamSettings.wsSettings.headers.Host",
]

MapperValue = Annotated[JsonValue, WithJsonSchema({
    "anyOf": [
        {"type": "string", "description": "A string, including an explicit empty string."},
        {"type": "number", "description": "An integer or floating-point JSON number, including zero."},
        {"type": "boolean", "description": "An explicit true or false value."},
        {"type": "null", "description": "Assign null without removing the destination key."},
        {"type": "array", "items": {}, "description": "Replace with an array of arbitrary JSON values, including []."},
        {"type": "object", "additionalProperties": True,
         "description": "Replace with a JSON object of arbitrary depth, including {}. Keys are not merged."},
    ],
})]


class MapperTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: str = Field(
        min_length=1,
        strict=True,
        pattern=re.compile(TARGET_PATH_PATTERN),
        description=(
            "Destination inside one generated connection, not the full subscription. "
            "Xray/Clash/sing-box use dot-separated keys and array indices, "
            "e.g. options[0].enabled or options.0.enabled. "
            "Array indices must be below 1024. Missing containers are created by set/copy; unset never creates them. "
            "URI/VMess use the entire string as a literal query/payload key. "
            "Paths containing __proto__, __class__ or constructor are forbidden. "
            "Xray managed tags cannot change; removing required identity fields fails output validation."
        ),
        examples=["streamSettings.sockopt.tcpFastOpen", "ws-opts.headers.Host", "tls.server_name", "sni"],
    )


class MapperSet(MapperTarget):
    """Assign a JSON value, including explicit null."""

    model_config = ConfigDict(json_schema_extra={
        "description": "Set or replace the destination value. Both to and value are required; from is not allowed.",
        "defaultSnippets": [{"label": "set", "body": {"op": "set", "to": "udp", "value": True}}],
    })

    op: Literal["set"] = Field(description="Assign value to the destination, replacing any existing value.")
    value: MapperValue = Field(
        description=(
            "Required JSON value: string, number, boolean, null, array or object. "
            "False, zero, an empty string, empty containers and null are explicit values. "
            "Objects/arrays replace the destination; they are not merged."
        ),
        examples=["example.com", 0, False, None, [], {}, {"enabled": True}],
    )

    @model_serializer(mode="wrap")
    def preserve_null_value(self, handler):
        result = handler(self)
        # Sparse host serialization omits unset/null overrides, but set(value=null) is an actual mapper operation.
        if self.value is None:
            result["value"] = None
        return result


class MapperCopy(MapperTarget):
    model_config = ConfigDict(json_schema_extra={
        "description": (
            "Deep-copy a value from the original inbound or resolved host. Both from and to are required; "
            "value is not allowed. A missing source skips the operation; an explicit source null is copied."
        ),
        "defaultSnippets": [{
            "label": "copy", "body": {"op": "copy", "from": "streamSettings.tlsSettings.serverName", "to": "sni"},
        }],
    })

    op: Literal["copy"] = Field(description="Copy a source value to the destination without modifying the source.")
    source: str = Field(
        alias="from", min_length=1, strict=True,
        description=(
            "Source path in the raw inbound (port, settings.*, streamSettings.*), or in resolved host metadata "
            "using $host.address, $host.port, $host.finalRemark, $host.protocol, $host.transport, $host.security, "
            "$host.protocolOptions or $host.metadata.remark. protocolOptions contains this user's protocol credentials "
            "(id/password/auth/method/flow depending on protocol). Nested object and array paths are supported. "
            "Sources are read from the original inbound/host, not from previous mapper results. "
            "A nonexistent source is skipped."
        ),
        examples=SOURCE_EXAMPLES,
    )


class MapperUnset(MapperTarget):
    model_config = ConfigDict(json_schema_extra={
        "description": (
            "Remove the destination key or array element. Only op and to are allowed. "
            "A missing destination is ignored. Removing an array element shifts subsequent indices."
        ),
        "defaultSnippets": [{"label": "unset", "body": {"op": "unset", "to": "udp"}}],
    })

    op: Literal["unset"] = Field(description="Remove the destination without creating intermediate containers.")


MapperOperation = Annotated[MapperSet | MapperCopy | MapperUnset, Field(discriminator="op")]


class HostMapperOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "description": (
            "Ordered transformations applied separately to each generated connection after its host overrides. "
            "The four keys select the output family: xrayJson, clash, singbox and base64 (URI/VMess). "
            "Outline does not use the mapper. Omitted/null families have no operations; [] also does nothing. "
            "Operations run in array order. Destination paths are arbitrary client fields, not a fixed allowlist."
        ),
        "defaultSnippets": [
            {"label": "Xray JSON", "body": {"xrayJson": [
                {"op": "set", "to": "streamSettings.sockopt.tcpFastOpen", "value": True},
            ]}},
            {"label": "Clash: set, copy and unset", "body": {"clash": [
                {"op": "set", "to": "udp", "value": True},
                {"op": "copy", "from": "streamSettings.tlsSettings.serverName", "to": "sni"},
                {"op": "unset", "to": "skip-cert-verify"},
            ]}},
            {"label": "sing-box", "body": {"singbox": [
                {"op": "set", "to": "tls.server_name", "value": "example.com"},
            ]}},
            {"label": "URI / VMess", "body": {"base64": [
                {"op": "set", "to": "sni", "value": "example.com"},
            ]}},
        ],
    })

    xrayJson: list[MapperOperation] | None = Field(None, description=(
        "Xray JSON (v2ray-json): one outbound object. Paths use dot notation and array indices. "
        "The managed tag is immutable; this cannot modify routing, DNS or the full document."
    ), examples=[[{"op": "set", "to": "streamSettings.sockopt.tcpFastOpen", "value": True}]])
    clash: list[MapperOperation] | None = Field(None, description=(
        "Clash: one proxy object. Paths use native Clash keys, including hyphens, and array indices. "
        "This cannot modify proxy-groups or rules. The final name must remain nonempty and unique."
    ), examples=[[{"op": "set", "to": "ws-opts.headers.Host", "value": "cdn.example.com"}]])
    singbox: list[MapperOperation] | None = Field(None, description=(
        "sing-box: one outbound object. Paths use native sing-box keys and array indices. "
        "This cannot modify route or the full document. The final tag must remain nonempty and unique."
    ), examples=[[{"op": "set", "to": "tls.server_name", "value": "example.com"}]])
    base64: list[MapperOperation] | None = Field(None, description=(
        "v2ray URI/Base64: query parameters; VMess: top-level JSON payload keys before Base64 encoding. "
        "The complete to string is a literal key: dots/brackets do not create nested objects. "
        "The URL scheme, credentials, address, port and fragment cannot be changed by query operations. "
        "VMess payload keys such as add, port and ps can be changed. copy.from still reads nested source paths."
    ), examples=[[{"op": "copy", "from": "$host.address", "to": "sni"}]])


def normalize_stored_mapper_options(mapper: dict) -> dict:
    """Preserve the behavior of old operations whose unused fields were accepted and ignored."""
    result = deepcopy(mapper)
    for operations in result.values():
        if not isinstance(operations, list):
            continue
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            action = operation.get("op")
            if action == "set":
                operation.pop("from", None)
                # Old exclude_none serialization omitted explicit set(value=null).
                operation.setdefault("value", None)
            elif action == "copy":
                operation.pop("value", None)
            elif action == "unset":
                operation.pop("from", None)
                operation.pop("value", None)
    return result
