from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


DEFAULT_NODE_CONFIG: Dict[str, Any] = {
    "log": {
        "loglevel": "warning",
    },
    "routing": {
        "rules": [
            {
                "ruleTag": "xray-rule-1",
                "ip": [
                    "geoip:private",
                ],
                "outboundTag": "BLOCK",
                "type": "field",
            },
        ],
    },
    "inbounds": [
        {
            "tag": "Shadowsocks TCP",
            "listen": "0.0.0.0",
            "port": 1080,
            "protocol": "shadowsocks",
            "settings": {
                "clients": [],
                "network": "tcp,udp",
            },
        },
    ],
    "outbounds": [
        {
            "protocol": "freedom",
            "tag": "DIRECT",
        },
        {
            "protocol": "blackhole",
            "tag": "BLOCK",
        },
    ],
}


def default_node_config() -> Dict[str, Any]:
    return deepcopy(DEFAULT_NODE_CONFIG)


class RuntimeSettingsBase(BaseModel):
    sub_profile_title: str = Field(min_length=1, max_length=256)
    sub_support_url: str = Field(max_length=2048)
    sub_update_interval: str = Field(min_length=1, max_length=32)
    external_config: str = ""
    use_custom_json_default: bool = False
    use_custom_json_for_v2rayn: bool = False
    use_custom_json_for_v2rayng: bool = False
    use_custom_json_for_streisand: bool = False
    use_custom_json_for_happ: bool = False

    active_status_text: str = Field(min_length=1, max_length=128)
    expired_status_text: str = Field(min_length=1, max_length=128)
    limited_status_text: str = Field(min_length=1, max_length=128)
    disabled_status_text: str = Field(min_length=1, max_length=128)
    onhold_status_text: str = Field(min_length=1, max_length=128)

    notify_status_change: bool = True
    notify_user_created: bool = True
    notify_user_updated: bool = True
    notify_user_deleted: bool = True
    notify_user_data_used_reset: bool = True
    notify_user_sub_revoked: bool = True
    notify_if_data_usage_percent_reached: bool = True
    notify_if_days_left_reached: bool = True
    notify_login: bool = True
    notify_days_left: list[int] = Field(default_factory=lambda: [3])
    notify_reached_usage_percent: list[int] = Field(default_factory=lambda: [80])
    login_notify_white_list: list[str] = Field(default_factory=list)

    webhook_addresses: list[str] = Field(default_factory=list)
    recurrent_notifications_timeout: int = Field(ge=1)
    number_of_recurrent_notifications: int = Field(ge=0)
    default_node_config: Dict[str, Any] = Field(default_factory=default_node_config)
    clash_settings: str = ""
    singbox_settings: str = ""
    v2ray_settings: str = ""
    mux: str = ""
    user_agent: str = ""
    grpc_user_agent: str = ""

    @field_validator("sub_support_url")
    @classmethod
    def validate_optional_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("must be an http or https URL")
        return value

    @field_validator("sub_update_interval")
    @classmethod
    def validate_update_interval(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = str(value).strip()
        if not value.isdigit() or int(value) <= 0:
            raise ValueError("must be a positive integer")
        return value

    @field_validator("notify_days_left")
    @classmethod
    def validate_days_left(cls, value: Optional[list[int]]) -> Optional[list[int]]:
        if value is None:
            return value
        if any(item <= 0 for item in value):
            raise ValueError("must contain positive integers")
        return value

    @field_validator("notify_reached_usage_percent")
    @classmethod
    def validate_usage_percent(cls, value: Optional[list[int]]) -> Optional[list[int]]:
        if value is None:
            return value
        if any(item < 1 or item > 100 for item in value):
            raise ValueError("must contain integers between 1 and 100")
        return value

    @field_validator("webhook_addresses")
    @classmethod
    def validate_webhook_addresses(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return value
        addresses = []
        for address in value:
            address = address.strip()
            if not address:
                continue
            parsed = urlparse(address)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("webhook addresses must be http or https URLs")
            addresses.append(address)
        return addresses


class RuntimeSettings(RuntimeSettingsBase):
    webhook_secret: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class RuntimeSettingsResponse(RuntimeSettingsBase):
    webhook_secret_set: bool = False
    model_config = ConfigDict(from_attributes=True)


class RuntimeSettingsModify(BaseModel):
    sub_profile_title: Optional[str] = Field(default=None, min_length=1, max_length=256)
    sub_support_url: Optional[str] = Field(default=None, max_length=2048)
    sub_update_interval: Optional[str] = Field(default=None, min_length=1, max_length=32)
    external_config: Optional[str] = None
    use_custom_json_default: Optional[bool] = None
    use_custom_json_for_v2rayn: Optional[bool] = None
    use_custom_json_for_v2rayng: Optional[bool] = None
    use_custom_json_for_streisand: Optional[bool] = None
    use_custom_json_for_happ: Optional[bool] = None

    active_status_text: Optional[str] = Field(default=None, min_length=1, max_length=128)
    expired_status_text: Optional[str] = Field(default=None, min_length=1, max_length=128)
    limited_status_text: Optional[str] = Field(default=None, min_length=1, max_length=128)
    disabled_status_text: Optional[str] = Field(default=None, min_length=1, max_length=128)
    onhold_status_text: Optional[str] = Field(default=None, min_length=1, max_length=128)

    notify_status_change: Optional[bool] = None
    notify_user_created: Optional[bool] = None
    notify_user_updated: Optional[bool] = None
    notify_user_deleted: Optional[bool] = None
    notify_user_data_used_reset: Optional[bool] = None
    notify_user_sub_revoked: Optional[bool] = None
    notify_if_data_usage_percent_reached: Optional[bool] = None
    notify_if_days_left_reached: Optional[bool] = None
    notify_login: Optional[bool] = None
    notify_days_left: Optional[list[int]] = None
    notify_reached_usage_percent: Optional[list[int]] = None
    login_notify_white_list: Optional[list[str]] = None

    webhook_addresses: Optional[list[str]] = None
    webhook_secret: Optional[str] = None
    clear_webhook_secret: bool = False
    recurrent_notifications_timeout: Optional[int] = Field(default=None, ge=1)
    number_of_recurrent_notifications: Optional[int] = Field(default=None, ge=0)
    default_node_config: Optional[Dict[str, Any]] = None
    clash_settings: Optional[str] = None
    singbox_settings: Optional[str] = None
    v2ray_settings: Optional[str] = None
    mux: Optional[str] = None
    user_agent: Optional[str] = None
    grpc_user_agent: Optional[str] = None

    _validate_optional_url = field_validator("sub_support_url")(RuntimeSettingsBase.validate_optional_url.__func__)
    _validate_update_interval = field_validator(
        "sub_update_interval"
    )(RuntimeSettingsBase.validate_update_interval.__func__)
    _validate_days_left = field_validator("notify_days_left")(RuntimeSettingsBase.validate_days_left.__func__)
    _validate_usage_percent = field_validator(
        "notify_reached_usage_percent"
    )(RuntimeSettingsBase.validate_usage_percent.__func__)
    _validate_webhook_addresses = field_validator(
        "webhook_addresses"
    )(RuntimeSettingsBase.validate_webhook_addresses.__func__)


SubscriptionBalancerStrategy = Literal[
    "least_ping",
    "least_load",
    "random",
    "round_robin",
]


class SubscriptionBalancerBase(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    enabled: bool = True
    strategy: SubscriptionBalancerStrategy = "least_ping"
    probe_url: str = Field(min_length=1, max_length=2048)
    probe_interval: int = Field(default=300, ge=10, le=86400)
    host_ids: list[int] = Field(default_factory=list)

    @field_validator("probe_url")
    @classmethod
    def validate_probe_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("must be an http or https URL")
        return value


class SubscriptionBalancerCreate(SubscriptionBalancerBase):
    pass


class SubscriptionBalancerModify(SubscriptionBalancerBase):
    pass


class SubscriptionBalancerReorder(BaseModel):
    balancer_ids: list[int]


class SubscriptionBalancerResponse(SubscriptionBalancerBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
