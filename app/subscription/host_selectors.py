"""Host selection contracts and bounded matching against resolved connection names."""

from functools import lru_cache
from time import monotonic
from typing import Literal

import regex
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from app.subscription.contracts import ResolvedConnection, SubscriptionError


NAME_SELECTORS = {"remarks", "remarkPrefix", "remarkRegex"}
REGEX_TIMEOUT = 0.05


def _selector_rule(kind, properties, required=()):
    return {
        "if": {"properties": {"type": {"const": kind}}, "required": ["type"]},
        "then": {"properties": properties, **({"required": list(required)} if required else {})},
    }


@lru_cache(maxsize=128)
def _compile_pattern(pattern: str):
    try:
        return regex.compile(pattern, regex.VERSION0)
    except (regex.error, RecursionError) as exc:
        raise ValueError(f"Invalid host name regular expression: {exc}") from exc


class Selector(BaseModel):
    """Select authorized hosts by ID, group or rendered name. Name matching is case-sensitive."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "allOf": [
            _selector_rule("ids", {"values": {"items": {"type": "integer", "minimum": 1}},
                                   "prefix": False, "pattern": False}),
            _selector_rule("groups", {"values": {"items": {"type": "string", "minLength": 1}},
                                      "prefix": False, "pattern": False}),
            _selector_rule("sameGroupsAsRecipient", {"values": {"maxItems": 0},
                                                     "prefix": False, "pattern": False}),
            _selector_rule("remarks", {"values": {"minItems": 1, "items": {"type": "string", "minLength": 1}},
                                       "prefix": False, "pattern": False}, ("values",)),
            _selector_rule("remarkPrefix", {"values": False, "pattern": False,
                                            "prefix": {"type": "string", "minLength": 1}}, ("prefix",)),
            _selector_rule("remarkRegex", {"values": False, "prefix": False,
                                           "pattern": {"type": "string", "minLength": 1}}, ("pattern",)),
        ],
        "defaultSnippets": [
            {"label": "Host IDs", "body": {"type": "ids", "values": [11, 12]}},
            {"label": "Exact host names", "body": {"type": "remarks", "values": ["Netherlands", "Finland"]}},
            {"label": "Host name prefix", "body": {"type": "remarkPrefix", "prefix": "EU-"}},
            {"label": "Host name regex", "body": {"type": "remarkRegex", "pattern": "^(NL|FI)-"}},
        ],
    })
    type: Literal["ids", "groups", "sameGroupsAsRecipient", "remarks", "remarkPrefix", "remarkRegex"] = Field(
        description="Select by host IDs, group IDs, exact names, a name prefix or a regular expression.")
    values: list[StrictInt | StrictStr] = Field(
        default_factory=list, description="Host IDs, group IDs or exact rendered names, according to type.",
        examples=[[11, 12], ["eu"], ["Netherlands", "Finland"]])
    prefix: StrictStr | None = Field(
        None, min_length=1, max_length=256,
        description="Literal prefix of the rendered host name, including spaces. Only for remarkPrefix.",
        examples=["EU-"])
    pattern: StrictStr | None = Field(
        None, min_length=1, max_length=1024,
        description=("Regular expression searched anywhere in the rendered host name. Use ^ for a prefix or ^...$ "
                     "for an exact match, without /.../ delimiters. Only for remarkRegex; checked by the server."),
        examples=["^(NL|FI)-", "^Netherlands$"])

    @model_validator(mode="after")
    def validate_values(self):
        allowed = {"type", "values"}
        if self.type == "remarkPrefix":
            allowed = {"type", "prefix"}
            if self.prefix is None:
                raise ValueError("remarkPrefix requires prefix")
        elif self.type == "remarkRegex":
            allowed = {"type", "pattern"}
            if self.pattern is None:
                raise ValueError("remarkRegex requires pattern")
            _compile_pattern(self.pattern)
        elif self.type == "ids":
            if any(type(value) is not int or value <= 0 for value in self.values):
                raise ValueError("Host IDs must be positive integers")
        elif self.type in {"groups", "remarks"}:
            if any(not isinstance(value, str) or not value for value in self.values):
                raise ValueError("Group IDs and host names must be nonempty strings")
            if self.type == "remarks" and not self.values:
                raise ValueError("remarks requires at least one host name")
        elif self.values:
            raise ValueError("sameGroupsAsRecipient does not accept values")
        if self.model_fields_set - allowed:
            raise ValueError(f"{self.type} accepts only {', '.join(sorted(allowed))}")
        return self


def select_by_name(connections: tuple[ResolvedConnection, ...], selector: Selector) -> list[int]:
    if selector.type == "remarks":
        names = set(selector.values)
        return [item.host_id for item in connections if item.remark in names]
    if selector.type == "remarkPrefix":
        return [item.host_id for item in connections if item.remark.startswith(selector.prefix)]
    if selector.type != "remarkRegex":
        raise ValueError("Expected a host name selector")
    pattern = _compile_pattern(selector.pattern)
    deadline = monotonic() + REGEX_TIMEOUT
    selected = []
    try:
        for item in connections:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError
            if pattern.search(item.remark, timeout=remaining):
                selected.append(item.host_id)
    except TimeoutError as exc:
        raise SubscriptionError("Host name regular expression exceeded its time limit") from exc
    return selected
