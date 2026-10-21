from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubscriptionFormat(str, Enum):
    v2ray = "v2ray"
    v2ray_json = "v2ray-json"
    clash = "clash"
    sing_box = "sing-box"
    outline = "outline"


FORMAT_ALIASES = {
    "singbox": "sing-box",
    "json": "v2ray-json",
    "xray-json": "v2ray-json",
}


def normalize_subscription_format(value: str) -> SubscriptionFormat:
    return SubscriptionFormat(FORMAT_ALIASES.get(value, value))


def normalize_subscription_client_type(value: str) -> str:
    return normalize_subscription_format(value).value


class SubscriptionTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    format: SubscriptionFormat
    content: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Template name cannot be blank")
        return value


class SubscriptionTemplateModify(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    format: SubscriptionFormat | None = None
    content: str | None = Field(default=None, min_length=1)

    _strip_name = field_validator("name")(SubscriptionTemplateCreate.strip_name.__func__)


class SubscriptionTemplateClone(BaseModel):
    name: str = Field(min_length=1, max_length=128)

    _strip_name = field_validator("name")(SubscriptionTemplateCreate.strip_name.__func__)


class SubscriptionTemplatePreview(BaseModel):
    format: SubscriptionFormat
    content: str = Field(min_length=1)
    user_id: int = Field(gt=0)
    recipient_host_id: int | None = Field(None, gt=0)


class SubscriptionTemplateSummary(BaseModel):
    id: int
    name: str
    format: SubscriptionFormat
    is_default: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SubscriptionTemplateResponse(SubscriptionTemplateSummary):
    content: str


class SubscriptionTemplateList(BaseModel):
    items: list[SubscriptionTemplateSummary]
    total: int


def normalize_template_bindings(value: dict) -> dict[SubscriptionFormat, int]:
    result = {}
    for key, template_id in value.items():
        format = normalize_subscription_format(key)
        if format in result:
            raise ValueError(f"Duplicate template assignment for {format.value}")
        if isinstance(template_id, bool) or not isinstance(template_id, int) or template_id <= 0:
            raise ValueError("Template IDs must be positive integers")
        result[format] = template_id
    return result
