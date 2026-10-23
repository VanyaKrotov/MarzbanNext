"""Validated template directives. Selection never expands the authorized source pool."""

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError, model_validator

from app.subscription.contracts import HostSnapshot, ProfilePlan, ResolvedConnection, SubscriptionError


class Selector(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"allOf": [
        {"if": {"properties": {"type": {"const": "ids"}}, "required": ["type"]},
         "then": {"properties": {"values": {"items": {"type": "integer", "minimum": 1}}}}},
        {"if": {"properties": {"type": {"const": "groups"}}, "required": ["type"]},
         "then": {"properties": {"values": {"items": {"type": "string", "minLength": 1}}}}},
        {"if": {"properties": {"type": {"const": "sameGroupsAsRecipient"}}, "required": ["type"]},
         "then": {"properties": {"values": {"maxItems": 0}}}},
    ]})
    type: Literal["ids", "groups", "sameGroupsAsRecipient"] = Field(
        description="Select hosts by positive integer IDs, group IDs, or the Xray recipient's groups.")
    values: list[StrictInt | str] = Field(
        default_factory=list, description="Host IDs or group IDs. Omit for sameGroupsAsRecipient.")

    @model_validator(mode="after")
    def validate_values(self):
        if self.type == "ids" and any(type(value) is not int or value <= 0 for value in self.values):
            raise ValueError("Host IDs must be positive integers")
        if self.type == "groups" and any(not isinstance(value, str) or not value for value in self.values):
            raise ValueError("Group IDs must be nonempty strings")
        if self.type == "sameGroupsAsRecipient" and self.values:
            raise ValueError("sameGroupsAsRecipient does not accept values")
        return self


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selector: Selector | None = Field(None, description="Restrict the authorized source pool to these hosts or groups.")
    selectFrom: Literal["ALL", "HIDDEN", "VISIBLE"] = Field(
        "VISIBLE", description=("Filter sources by host visibility. "
                                "Disabled hosts and excluded formats remain unavailable."))


class InjectHosts(Selection):
    selectFrom: Literal["ALL", "HIDDEN", "VISIBLE"] = Field(
        "HIDDEN", description="Inject hidden, visible, or all authorized sources. The recipient itself is excluded.")
    tagPrefix: str = Field(
        min_length=1, max_length=256,
        description="Stable unique prefix for generated outbound tags and balancer selectors.")


class XrayDirectives(BaseModel):
    model_config = ConfigDict(extra="forbid")
    addVirtualHostAsOutbound: StrictBool = Field(
        True, description="Include the recipient's own connection as an outbound.")
    injectHosts: list[InjectHosts] = Field(
        default_factory=list, description="Add connections from selected hosts to this Xray configuration.")


class IncludeProxies(Selection):
    includeProxies: StrictBool = Field(
        True, description="Fill this group or inline provider from the selected source pool.")


def parse_directive(schema, value):
    try:
        return schema.model_validate(value)
    except ValidationError as exc:
        raise SubscriptionError(f"Invalid marzban directive: {exc}") from exc


def _selected_ids(profile: ProfilePlan, options: Selection, recipient: HostSnapshot | None) -> list[int]:
    selector = options.selector
    if selector is None:
        if options.selectFrom == "VISIBLE":
            return list(profile.visible_ids)
        return [connection.host_id for connection in profile.sources]
    if selector.type == "ids":
        return list(dict.fromkeys(selector.values))
    groups = set(selector.values)
    if selector.type == "sameGroupsAsRecipient":
        if recipient is None:
            raise SubscriptionError("sameGroupsAsRecipient requires an Xray recipient")
        groups = set(recipient.group_ids)
    return [host.id for host in profile.hosts if groups.intersection(host.group_ids)]


def selected_sources(profile: ProfilePlan, options: Selection, *, recipient: HostSnapshot | None = None,
                     diagnostics: list[dict] | None = None) -> list[ResolvedConnection]:
    """Filter the authorized catalog; explicit selectors never grant additional access."""
    by_id = {connection.host_id: connection for connection in profile.sources}
    hosts = {host.id: host for host in profile.hosts}
    ids = _selected_ids(profile, options, recipient)
    selected = []
    for host_id in ids:
        if host_id not in by_id or (recipient is not None and host_id == recipient.id):
            continue
        if options.selectFrom != "ALL" and hosts[host_id].is_hidden != (options.selectFrom == "HIDDEN"):
            continue
        selected.append(by_id[host_id])
    if diagnostics is not None:
        chosen = {item.host_id for item in selected}
        for host_id in ids:
            reason = "selected" if host_id in chosen else "excluded_by_selection"
            if host_id not in by_id:
                reason = "unavailable"
            diagnostics.append({"host_id": host_id, "reason": reason})
    return selected


def take_include(node, target):
    if "marzban" not in node:
        return None
    raw = node.pop("marzban")
    if not isinstance(raw, dict):
        raise SubscriptionError("marzban directives must be an object")
    if target == "clash":
        raw = dict(raw)
        if "includeProxies" in raw:
            raise SubscriptionError("Clash uses marzban.include-proxies")
        if "include-proxies" in raw:
            raw["includeProxies"] = raw.pop("include-proxies")
    options = parse_directive(IncludeProxies, raw)
    if options.selector and options.selector.type == "sameGroupsAsRecipient":
        raise SubscriptionError("sameGroupsAsRecipient is supported only in Xray templates")
    return options


def validate_directives(document, target):
    """Metadata is legal only at defined locations, including during template validation."""
    document = deepcopy(document)
    if target == "v2ray-json" and "marzban" in document:
        parse_directive(XrayDirectives, document.pop("marzban"))
    if target == "sing-box":
        for node in document.get("outbounds", []):
            if "marzban" in node and node.get("type") not in {"selector", "urltest"}:
                raise SubscriptionError("sing-box directives require a selector or urltest outbound")
            take_include(node, target)
    if target == "clash":
        for node in document.get("proxy-groups", []):
            take_include(node, target)
        for node in document.get("proxy-providers", {}).values():
            if "marzban" in node and node.get("type") != "inline":
                raise SubscriptionError("Provider injection requires an inline provider")
            take_include(node, target)

    def check_remaining(value):
        if isinstance(value, dict):
            if "marzban" in value:
                raise SubscriptionError("Unsupported marzban directive location")
            for item in value.values():
                check_remaining(item)
        elif isinstance(value, list):
            for item in value:
                check_remaining(item)

    check_remaining(document)
