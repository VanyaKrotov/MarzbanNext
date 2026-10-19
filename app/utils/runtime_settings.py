from functools import lru_cache

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import GetDB
from app.db.models.settings import RuntimeSettings as DBRuntimeSettings
from app.models.settings import (
    RuntimeSettings,
    RuntimeSettingsModify,
    RuntimeSettingsResponse,
    default_node_config,
)
from config import (
    ACTIVE_STATUS_TEXT,
    DISABLED_STATUS_TEXT,
    EXPIRED_STATUS_TEXT,
    EXTERNAL_CONFIG,
    LIMITED_STATUS_TEXT,
    LOGIN_NOTIFY_WHITE_LIST,
    NOTIFY_DAYS_LEFT,
    NOTIFY_IF_DATA_USAGE_PERCENT_REACHED,
    NOTIFY_IF_DAYS_LEFT_REACHED,
    NOTIFY_LOGIN,
    NOTIFY_REACHED_USAGE_PERCENT,
    NOTIFY_STATUS_CHANGE,
    NOTIFY_USER_CREATED,
    NOTIFY_USER_DATA_USED_RESET,
    NOTIFY_USER_DELETED,
    NOTIFY_USER_SUB_REVOKED,
    NOTIFY_USER_UPDATED,
    NUMBER_OF_RECURRENT_NOTIFICATIONS,
    ONHOLD_STATUS_TEXT,
    RECURRENT_NOTIFICATIONS_TIMEOUT,
    SUB_PROFILE_TITLE,
    SUB_SUPPORT_URL,
    SUB_UPDATE_INTERVAL,
    USE_CUSTOM_JSON_DEFAULT,
    USE_CUSTOM_JSON_FOR_HAPP,
    USE_CUSTOM_JSON_FOR_STREISAND,
    USE_CUSTOM_JSON_FOR_V2RAYN,
    USE_CUSTOM_JSON_FOR_V2RAYNG,
    WEBHOOK_ADDRESS,
    WEBHOOK_SECRET,
)


def clear_runtime_settings_cache() -> None:
    get_runtime_settings.cache_clear()


def build_default_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(
        sub_profile_title=SUB_PROFILE_TITLE,
        sub_support_url=SUB_SUPPORT_URL,
        sub_update_interval=SUB_UPDATE_INTERVAL,
        external_config=EXTERNAL_CONFIG,
        use_custom_json_default=USE_CUSTOM_JSON_DEFAULT,
        use_custom_json_for_v2rayn=USE_CUSTOM_JSON_FOR_V2RAYN,
        use_custom_json_for_v2rayng=USE_CUSTOM_JSON_FOR_V2RAYNG,
        use_custom_json_for_streisand=USE_CUSTOM_JSON_FOR_STREISAND,
        use_custom_json_for_happ=USE_CUSTOM_JSON_FOR_HAPP,
        active_status_text=ACTIVE_STATUS_TEXT,
        expired_status_text=EXPIRED_STATUS_TEXT,
        limited_status_text=LIMITED_STATUS_TEXT,
        disabled_status_text=DISABLED_STATUS_TEXT,
        onhold_status_text=ONHOLD_STATUS_TEXT,
        notify_status_change=NOTIFY_STATUS_CHANGE,
        notify_user_created=NOTIFY_USER_CREATED,
        notify_user_updated=NOTIFY_USER_UPDATED,
        notify_user_deleted=NOTIFY_USER_DELETED,
        notify_user_data_used_reset=NOTIFY_USER_DATA_USED_RESET,
        notify_user_sub_revoked=NOTIFY_USER_SUB_REVOKED,
        notify_if_data_usage_percent_reached=NOTIFY_IF_DATA_USAGE_PERCENT_REACHED,
        notify_if_days_left_reached=NOTIFY_IF_DAYS_LEFT_REACHED,
        notify_login=NOTIFY_LOGIN,
        notify_days_left=NOTIFY_DAYS_LEFT,
        notify_reached_usage_percent=NOTIFY_REACHED_USAGE_PERCENT,
        login_notify_white_list=LOGIN_NOTIFY_WHITE_LIST,
        webhook_addresses=WEBHOOK_ADDRESS,
        webhook_secret=WEBHOOK_SECRET,
        recurrent_notifications_timeout=RECURRENT_NOTIFICATIONS_TIMEOUT,
        number_of_recurrent_notifications=NUMBER_OF_RECURRENT_NOTIFICATIONS,
        default_node_config=default_node_config(),
        **build_default_generator_templates(),
    )


def runtime_settings_response(settings: RuntimeSettings) -> RuntimeSettingsResponse:
    data = settings.model_dump(exclude={"webhook_secret"})
    data["webhook_secret_set"] = bool(settings.webhook_secret)
    return RuntimeSettingsResponse(**data)


def _get_or_create_settings(db: Session) -> DBRuntimeSettings:
    db_settings = db.get(DBRuntimeSettings, 1)
    if db_settings:
        return db_settings

    defaults = build_default_runtime_settings()
    db_settings = DBRuntimeSettings(id=1, **defaults.model_dump())
    db.add(db_settings)
    db.commit()
    db.refresh(db_settings)
    return db_settings


@lru_cache(maxsize=1)
def get_runtime_settings() -> RuntimeSettings:
    try:
        with GetDB() as db:
            return RuntimeSettings.model_validate(_get_or_create_settings(db))
    except SQLAlchemyError:
        return build_default_runtime_settings()


def update_runtime_settings(db: Session, payload: RuntimeSettingsModify) -> RuntimeSettings:
    db_settings = _get_or_create_settings(db)
    updates = payload.model_dump(exclude_unset=True, exclude={"clear_webhook_secret"})

    if "webhook_secret" not in updates:
        updates["webhook_secret"] = db_settings.webhook_secret
    if payload.clear_webhook_secret:
        updates["webhook_secret"] = None

    current = RuntimeSettings.model_validate(db_settings).model_dump()
    current.update(updates)
    validated = RuntimeSettings(**current)

    for key, value in validated.model_dump().items():
        setattr(db_settings, key, value)

    db.add(db_settings)
    db.commit()
    db.refresh(db_settings)
    clear_runtime_settings_cache()
    return RuntimeSettings.model_validate(db_settings)


def build_default_generator_templates() -> dict[str, str]:
    from app.utils.subscription_template_defaults import GENERATOR_TEMPLATE_SOURCES, read_template_source

    return {key: read_template_source(name) for key, name in GENERATOR_TEMPLATE_SOURCES.items()}


def get_generator_template(key: str) -> str:
    from app.utils.subscription_template_defaults import GENERATOR_TEMPLATE_SOURCES

    if key not in GENERATOR_TEMPLATE_SOURCES:
        raise KeyError(key)
    return getattr(get_runtime_settings(), key)
