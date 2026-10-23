"""JSON primitives shared by FinalMask models; values keep their original representation."""

import base64
import re
from functools import lru_cache
from itertools import combinations
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt, StrictStr, WithJsonSchema


XRAY_REVISION = "1b1647cd9ddf0abc34b981d4611fc03bcac1ca74"
XRAY_SOURCE = f"https://github.com/XTLS/Xray-core/blob/{XRAY_REVISION}/infra/conf/transport_finalmask.go"


class MaskOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _fixed_decimal(low: str, high: str) -> str:
    if low == high:
        return low
    if low == "0" * len(low) and high == "9" * len(high):
        return "[0-9]" if len(low) == 1 else f"[0-9]{{{len(low)}}}"
    if low[0] == high[0]:
        return low[0] + _fixed_decimal(low[1:], high[1:])
    if len(low) == 1:
        return f"[{low}-{high}]"
    start, end = int(low[0]), int(high[0])
    choices = [str(start) + _fixed_decimal(low[1:], "9" * (len(low) - 1))]
    if end > start + 1:
        choices.append(f"[{start + 1}-{end - 1}]" + _fixed_decimal("0" * (len(low) - 1), "9" * (len(low) - 1)))
    choices.append(str(end) + _fixed_decimal("0" * (len(low) - 1), high[1:]))
    return "(?:" + "|".join(choices) + ")"


@lru_cache
def decimal_pattern(minimum: int, maximum: int) -> str:
    """Bound numbers encoded as strings, which JSON Schema's numeric limits cannot validate."""
    choices = []
    for digits in range(len(str(minimum)), len(str(maximum)) + 1):
        low = max(minimum, 0 if digits == 1 else 10 ** (digits - 1))
        high = min(maximum, 10 ** digits - 1)
        if low <= high:
            choices.append(_fixed_decimal(str(low), str(high)))
    return "0*(?:" + "|".join(choices) + ")"


def range_bounds(value: int | str) -> tuple[int, int]:
    if isinstance(value, int):
        return value, value
    values = [int(item) for item in value.split("-")] if value else [0]
    return min(values), max(values)


@lru_cache
def integer_range(minimum: int = 0, maximum: int = 2147483647):
    number = decimal_pattern(minimum, maximum)
    empty = "|" if minimum == 0 else ""
    pattern = f"^(?:{number}(?:-{number})?{empty})$"

    def validate(value):
        if isinstance(value, int):
            valid = minimum <= value <= maximum
        else:
            valid = bool(re.fullmatch(pattern, value))
        if not valid:
            raise ValueError(f"Expected an integer or integer range between {minimum} and {maximum}")
        return value

    return Annotated[StrictInt | StrictStr, AfterValidator(validate), WithJsonSchema({
        "anyOf": [{"type": "integer", "minimum": minimum, "maximum": maximum},
                  {"type": "string", "pattern": pattern,
                   "patternErrorMessage": f"Use an integer or A-B range between {minimum} and {maximum}."}],
        "description": "Integer, numeric string or A-B range; reversed endpoints are supported by Xray.",
        "examples": [minimum, str(minimum), f"{minimum}-{min(maximum, minimum + 10)}"],
    })]


Range = integer_range()
ByteRange = integer_range(0, 255)
Byte = Annotated[StrictInt, Field(ge=0, le=255)]
UInt32 = Annotated[StrictInt, Field(ge=0, le=4294967295)]
UInt64 = Annotated[StrictInt, Field(ge=0, le=18446744073709551615)]
Variable = Annotated[StrictStr, Field(pattern=r"^(?:[A-Za-z_][A-Za-z0-9_]*)?$")]
Packet = list[Byte] | StrictStr
HEX_PATTERN = r"^(?:[0-9a-fA-F]{2})*$"
BASE64_PATTERN = r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$"


def validate_packet(value, encoding: str):
    if encoding in ("", "array"):
        if isinstance(value, str):
            base64.b64decode(value, validate=True)
    elif not isinstance(value, str):
        raise ValueError(f"{encoding} packet must be a string")
    elif encoding == "hex" and not re.fullmatch(HEX_PATTERN, value):
        raise ValueError("Hex packets must contain an even number of hexadecimal digits")
    elif encoding == "base64":
        try:
            base64.b64decode(value, validate=True)
        except ValueError as error:
            raise ValueError("Invalid padded Base64 packet") from error
    return value


def packet_rules(key="packet") -> list[dict]:
    """Mirror encoding-dependent payload rules in Monaco as well as Python validation."""
    rules = [
        {"if": {"required": ["type"], "properties": {"type": {"const": encoding}}},
         "then": {"properties": {key: {"anyOf": [
             {"type": "string", **({"pattern": pattern} if pattern else {})}, {"type": "null"},
         ]}}}}
        for encoding, pattern in (("str", None), ("hex", HEX_PATTERN), ("base64", BASE64_PATTERN))
    ]
    rules.append({
        "if": {"properties": {"type": {"enum": [None, "", "array"]}}},
        "then": {"properties": {key: {"anyOf": [
            {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 255}},
            {"type": "string", "pattern": BASE64_PATTERN}, {"type": "null"},
        ]}}},
    })
    return rules


def exclusive_source_rules(sources: dict[str, dict], *, required=False) -> list[dict]:
    """Exclude pairs of active sources; empty strings/zero need not activate a source."""
    conditions = [{"required": [name], "properties": {name: schema}} for name, schema in sources.items()]
    rules = [{"not": {"allOf": [left, right]}} for left, right in combinations(conditions, 2)]
    if required:
        rules.append({"anyOf": conditions})
    return rules


def zero_or_integer(minimum: int, maximum: int = 18446744073709551615):
    def validate(value):
        if value != 0 and not minimum <= value <= maximum:
            raise ValueError(f"Expected zero or an integer between {minimum} and {maximum}")
        return value

    return Annotated[StrictInt, AfterValidator(validate), WithJsonSchema({
        "type": "integer", "anyOf": [{"const": 0}, {"minimum": minimum, "maximum": maximum}],
    })]


def zero_or_range(minimum: int, maximum: int = 2147483647):
    """A disabled/default zero or an entirely positive range, with the same rule in Monaco."""
    positive = decimal_pattern(minimum, maximum)
    pattern = f"^(?:|0+(?:-0+)?|{positive}(?:-{positive})?)$"

    def validate(value):
        low, high = range_bounds(value)
        if high != 0 and (low < minimum or high > maximum):
            raise ValueError(f"Expected zero or a range between {minimum} and {maximum}")
        return value

    return Annotated[Range, AfterValidator(validate), WithJsonSchema({
        "anyOf": [{"type": "integer", "anyOf": [{"const": 0}, {"minimum": minimum, "maximum": maximum}]},
                  {"type": "string", "pattern": pattern,
                   "patternErrorMessage": f"Use zero or an A-B range between {minimum} and {maximum}."}],
    })]
