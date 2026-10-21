"""Public subscription entry points; all formats share snapshot resolution and planning."""

import base64
from collections import defaultdict
from datetime import datetime as dt, timedelta
from functools import lru_cache
from jdatetime import date as jd
from fastapi import HTTPException

from app.models.subscription_template import normalize_subscription_client_type
from app.subscription.contracts import RenderInput, SubscriptionError
from app.subscription.generators import GeneratorRegistry
from app.subscription.loader import SubscriptionSnapshotLoader
from app.subscription.planning import ProfilePlanner
from app.subscription.resolver import ResolveContext
from app.utils.system import get_public_ip, get_public_ipv6, readable_size

STATUS_EMOJIS = {
    "active": "✅",
    "expired": "⌛️",
    "limited": "🪫",
    "disabled": "❌",
    "on_hold": "🔌",
}


def get_status_texts(settings=None) -> dict:
    from app.utils.runtime_settings import get_runtime_settings

    settings = settings or get_runtime_settings()
    return {
        "active": settings.active_status_text,
        "expired": settings.expired_status_text,
        "limited": settings.limited_status_text,
        "disabled": settings.disabled_status_text,
        "on_hold": settings.onhold_status_text,
    }


def format_time_left(seconds_left: int) -> str:
    if not seconds_left or seconds_left <= 0:
        return "∞"

    minutes, seconds = divmod(seconds_left, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    months, days = divmod(days, 30)

    result = []
    if months:
        result.append(f"{months}m")
    if days:
        result.append(f"{days}d")
    if hours and (days < 7):
        result.append(f"{hours}h")
    if minutes and not (months or days):
        result.append(f"{minutes}m")
    if seconds and not (months or days):
        result.append(f"{seconds}s")
    return " ".join(result)


def setup_format_variables(extra_data: dict, settings=None, now=None) -> dict:
    from app.models.user import UserStatus

    user_status = extra_data.get("status")
    expire_timestamp = extra_data.get("expire")
    on_hold_expire_duration = extra_data.get("on_hold_expire_duration")
    now = now or dt.utcnow()
    now_ts = now.timestamp()

    if user_status != UserStatus.on_hold:
        if expire_timestamp is not None and expire_timestamp >= 0:
            seconds_left = expire_timestamp - int(now.timestamp())
            expire_datetime = dt.fromtimestamp(expire_timestamp)
            expire_date = expire_datetime.date()
            jalali_expire_date = jd.fromgregorian(
                year=expire_date.year, month=expire_date.month, day=expire_date.day
            ).strftime("%Y-%m-%d")
            if now_ts < expire_timestamp:
                days_left = (expire_datetime - now).days + 1
                time_left = format_time_left(seconds_left)
            else:
                days_left = "0"
                time_left = "0"

        else:
            days_left = "∞"
            time_left = "∞"
            expire_date = "∞"
            jalali_expire_date = "∞"
    else:
        if on_hold_expire_duration is not None and on_hold_expire_duration >= 0:
            days_left = timedelta(seconds=on_hold_expire_duration).days
            time_left = format_time_left(on_hold_expire_duration)
            expire_date = "-"
            jalali_expire_date = "-"
        else:
            days_left = "∞"
            time_left = "∞"
            expire_date = "∞"
            jalali_expire_date = "∞"

    if extra_data.get("data_limit"):
        data_limit = readable_size(extra_data["data_limit"])
        data_left = extra_data["data_limit"] - extra_data["used_traffic"]
        if data_left < 0:
            data_left = 0
        data_left = readable_size(data_left)
    else:
        data_limit = "∞"
        data_left = "∞"

    status_emoji = STATUS_EMOJIS.get(extra_data.get("status")) or ""
    status_text = (get_status_texts(settings)).get(extra_data.get("status")) or ""

    format_variables = defaultdict(
        lambda: "<missing>",
        {
            "SERVER_IP": extra_data.get("SERVER_IP", "{SERVER_IP}"),
            "SERVER_IPV6": extra_data.get("SERVER_IPV6", "{SERVER_IPV6}"),
            "USERNAME": extra_data.get("username", "{USERNAME}"),
            "DATA_USAGE": readable_size(extra_data.get("used_traffic")),
            "DATA_LIMIT": data_limit,
            "DATA_LEFT": data_left,
            "DAYS_LEFT": days_left,
            "EXPIRE_DATE": expire_date,
            "JALALI_EXPIRE_DATE": jalali_expire_date,
            "TIME_LEFT": time_left,
            "STATUS_EMOJI": status_emoji,
            "STATUS_TEXT": status_text,
        },
    )

    return format_variables


def generate_subscription_config(proxies, inbounds, extra_data, config_format, as_base64=False,
                                 reverse=False, hosts_by_inbound=None, template_id=None, root_ids=None):
    from app.db import GetDB
    from app.utils.runtime_settings import get_runtime_settings

    target = normalize_subscription_client_type(config_format)
    if target == "clash-meta":
        target = "mihomo"
    settings = get_runtime_settings()
    with GetDB() as db:
        snapshot = SubscriptionSnapshotLoader().load(db, settings)
    extra_data = dict(extra_data)
    for variable, lookup in (("SERVER_IP", _server_ip), ("SERVER_IPV6", _server_ipv6)):
        if any("{" + variable + "}" in host.address or "{" + variable + "}" in host.remark
               or variable in str(host.overrides) for host in snapshot.hosts):
            extra_data[variable] = lookup()
    if hosts_by_inbound is not None:
        root_ids = {host.id for rows in hosts_by_inbound.values() for host in rows}
    try:
        profiles, diagnostics = ProfilePlanner().plan(
            snapshot, target, proxies, inbounds, ResolveContext(setup_format_variables(extra_data, settings)),
            root_ids=root_ids, template_id=template_id,
        )
        if not profiles:
            return ""
        result = GeneratorRegistry().for_target(target).generate(RenderInput(
            target, profiles, snapshot.defaults, snapshot.external_config, reverse, as_base64,
        ))
        return result.body
    except SubscriptionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid subscription configuration: {exc}") from exc


def generate_subscription(user, config_format, as_base64=False, reverse=False, template_id=None):
    return generate_subscription_config(user.proxies, user.inbounds, user.__dict__, config_format,
                                        as_base64, reverse, template_id=template_id)


def generate_subscription_from_hosts(user, hosts, config_format, as_base64=False, reverse=False, template_id=None):
    return generate_subscription_config(user.proxies, user.inbounds, user.__dict__, config_format,
                                        as_base64, reverse, template_id=template_id,
                                        root_ids={host.id for host in hosts})


def generate_v2ray_links(proxies, inbounds, extra_data, reverse=False, hosts_by_inbound=None, template_id=None):
    content = generate_subscription_config(proxies, inbounds, extra_data, "v2ray", reverse=reverse,
                                          hosts_by_inbound=hosts_by_inbound, template_id=template_id)
    return content.splitlines() if content else []


def build_subscription_hosts_by_inbound(hosts):
    from app.subscription.loader import snapshot_host

    result = defaultdict(list)
    for host in hosts:
        if host.enabled:
            result[host.inbound_tag].append(snapshot_host(host))
    return dict(result)


def encode_title(text: str) -> str:
    return f"base64:{base64.b64encode(text.encode()).decode()}"


@lru_cache(maxsize=1)
def _server_ip():
    return get_public_ip()


@lru_cache(maxsize=1)
def _server_ipv6():
    return get_public_ipv6()
