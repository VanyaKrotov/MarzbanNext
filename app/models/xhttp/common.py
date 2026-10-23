"""Xray JSON ranges and sparse models shared by XHTTP settings and their editor schema."""

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt, StrictStr, WithJsonSchema, model_validator

from app.models.finalmask.common import decimal_pattern


XRAY_REVISION = "1b1647cd9ddf0abc34b981d4611fc03bcac1ca74"
XRAY_XHTTP_SOURCE = f"https://github.com/XTLS/Xray-core/blob/{XRAY_REVISION}/infra/conf/transport_method.go"
INT32_MIN, INT32_MAX = -2147483648, 2147483647
Int64 = Annotated[StrictInt, Field(ge=-9223372036854775808, le=9223372036854775807)]
NonnegativeInt64 = Annotated[StrictInt, Field(ge=0, le=9223372036854775807)]
TOKEN_PATTERN = r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$"
RANGE_PARTS = re.compile(r"^([+-]?[0-9]+)(?:-([+-]?[0-9]+))?$")


def signed_number_pattern(minimum=INT32_MIN, maximum=INT32_MAX):
    choices = []
    if maximum >= 0:
        choices.append(r"\+?" + decimal_pattern(max(0, minimum), maximum))
    if minimum < 0:
        choices.append("-" + decimal_pattern(max(0, -maximum), -minimum))
    return "(?:" + "|".join(choices) + ")"


def range_schema(minimum=INT32_MIN, maximum=INT32_MAX, *, empty=True):
    number = signed_number_pattern(minimum, maximum)
    pattern = f"^(?:{number}(?:-{number})?{'|' if empty else ''})$"
    return {"anyOf": [
        {"type": "integer", "minimum": minimum, "maximum": maximum},
        {"type": "string", "pattern": pattern,
         "patternErrorMessage": "Use a signed 32-bit integer, numeric string or A-B range."},
    ]}


def range_bounds(value: int | str | None) -> tuple[int, int]:
    if value is None or value == "":
        return 0, 0
    if isinstance(value, int):
        values = [value]
    else:
        match = RANGE_PARTS.fullmatch(value)
        if match is None:
            raise ValueError("Expected an integer, numeric string or A-B range")
        values = [int(part) for part in match.groups() if part is not None]
    if any(not INT32_MIN <= item <= INT32_MAX for item in values):
        raise ValueError("XHTTP range endpoints must fit in signed 32-bit integers")
    return min(values), max(values)


def validate_range(value):
    range_bounds(value)
    return value


XhttpRange = Annotated[StrictInt | StrictStr, AfterValidator(validate_range), WithJsonSchema(range_schema())]


class XhttpModel(BaseModel):
    """Omitted keys inherit core defaults; explicit null inside extra is not a setting."""

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler.resolve_ref_schema(handler(core_schema))
        for value in schema.get("properties", {}).values():
            if "anyOf" in value:
                alternatives = [item for item in value["anyOf"] if item != {"type": "null"}]
                if len(alternatives) == 1:
                    value.pop("anyOf")
                    for key, item in alternatives[0].items():
                        value.setdefault(key, item)
                else:
                    value["anyOf"] = alternatives
            if value.get("default", ...) is None:
                value.pop("default")
        return schema

    @model_validator(mode="after")
    def validate_explicit_values(self):
        for name in self.model_fields_set:
            value = getattr(self, name)
            if value is None:
                raise ValueError(f"Omit {name} instead of assigning null")
        return self
