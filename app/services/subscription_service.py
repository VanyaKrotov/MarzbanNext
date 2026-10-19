import re
from distutils.version import LooseVersion
from typing import Annotated, Union

from fastapi import Depends, Header, Path, Query, Request, Response, HTTPException
from fastapi.responses import HTMLResponse

from app.db import Session, get_db
from app.dependencies import get_validated_sub, validate_dates
from app.models.user import UserResponse
from app.models.subscription_template import normalize_subscription_client_type
from app.subscription.share import (
    encode_title,
    generate_subscription,
    generate_subscription_from_hosts,
)
from app.templates import render_template
from app.utils.runtime_settings import get_runtime_settings
from config import SUBSCRIPTION_PAGE_TEMPLATE
from app.db.crud import proxy_hosts as host_crud
from app.db.crud import users as user_crud

client_config = {
    "clash-meta": {"config_format": "clash-meta", "media_type": "text/yaml", "as_base64": False, "reverse": False},
    "sing-box": {"config_format": "sing-box", "media_type": "application/json", "as_base64": False, "reverse": False},
    "clash": {"config_format": "clash", "media_type": "text/yaml", "as_base64": False, "reverse": False},
    "v2ray": {"config_format": "v2ray", "media_type": "text/plain", "as_base64": True, "reverse": False},
    "outline": {"config_format": "outline", "media_type": "application/json", "as_base64": False, "reverse": False},
    "v2ray-json": {"config_format": "v2ray-json", "media_type": "application/json", "as_base64": False,
                   "reverse": False}
}


def _subscription_response(content: str, media_type: str, headers: dict) -> Response:
    if not content:
        return Response(status_code=204, headers=headers)
    return Response(content=content, media_type=media_type, headers=headers)


def parse_groups_query(groups: Union[str, None]) -> list[str]:
    if not groups:
        return []
    return [
        group.strip()
        for group in groups.split(",")
        if group.strip()
    ]


def get_subscription_user_info(user: UserResponse) -> dict:
    """Retrieve user subscription information including upload, download, total data, and expiry."""
    return {
        "upload": 0,
        "download": user.used_traffic,
        "total": user.data_limit if user.data_limit is not None else 0,
        "expire": user.expire if user.expire is not None else 0,
    }


def get_subscription_response_headers(request: Request, user: UserResponse) -> dict:
    settings = get_runtime_settings()
    return {
        "content-disposition": f'attachment; filename="{user.username}"',
        "profile-web-page-url": str(request.url),
        "support-url": settings.sub_support_url,
        "profile-title": encode_title(settings.sub_profile_title),
        "profile-update-interval": settings.sub_update_interval,
        "subscription-userinfo": "; ".join(
            f"{key}={val}"
            for key, val in get_subscription_user_info(user).items()
        )
    }


def user_subscription(
    request: Request,
    db: Session = Depends(get_db),
    dbuser: UserResponse = Depends(get_validated_sub),
    user_agent: str = Header(default=""),
    template_id: Annotated[int | None, Query(gt=0)] = None,
):
    """Provides a subscription link based on the user agent (Clash, V2Ray, etc.)."""
    user: UserResponse = UserResponse.model_validate(dbuser)

    accept_header = request.headers.get("Accept", "")
    if "text/html" in accept_header:
        return HTMLResponse(
            render_template(
                SUBSCRIPTION_PAGE_TEMPLATE,
                {"user": user}
            )
        )

    user_crud.update_user_sub(db, dbuser, user_agent)
    response_headers = get_subscription_response_headers(request, user)
    settings = get_runtime_settings()

    if re.match(r'^([Cc]lash-verge|[Cc]lash[-\.]?[Mm]eta|[Ff][Ll][Cc]lash|[Mm]ihomo)', user_agent):
        conf = generate_subscription(user=user, config_format="clash-meta",
                                     as_base64=False, reverse=False, template_id=template_id)
        return _subscription_response(content=conf, media_type="text/yaml", headers=response_headers)

    elif re.match(r'^([Cc]lash|[Ss]tash)', user_agent):
        conf = generate_subscription(user=user, config_format="clash", as_base64=False,
                                     reverse=False, template_id=template_id)
        return _subscription_response(content=conf, media_type="text/yaml", headers=response_headers)

    elif re.match(r'^(SFA|SFI|SFM|SFT|[Kk]aring|[Hh]iddify[Nn]ext)', user_agent):
        conf = generate_subscription(user=user, config_format="sing-box", as_base64=False,
                                     reverse=False, template_id=template_id)
        return _subscription_response(content=conf, media_type="application/json", headers=response_headers)

    elif re.match(r'^(SS|SSR|SSD|SSS|Outline|Shadowsocks|SSconf)', user_agent):
        conf = generate_subscription(user=user, config_format="outline", as_base64=False,
                                     reverse=False, template_id=template_id)
        return _subscription_response(content=conf, media_type="application/json", headers=response_headers)

    elif (
        settings.use_custom_json_default or settings.use_custom_json_for_v2rayn
    ) and re.match(r'^v2rayN/(\d+\.\d+)', user_agent):
        version_str = re.match(r'^v2rayN/(\d+\.\d+)', user_agent).group(1)
        if LooseVersion(version_str) >= LooseVersion("6.40"):
            conf = generate_subscription(user=user, config_format="v2ray-json",
                                         as_base64=False, reverse=False, template_id=template_id)
            return _subscription_response(content=conf, media_type="application/json", headers=response_headers)
        else:
            conf = generate_subscription(user=user, config_format="v2ray", as_base64=True,
                                         reverse=False, template_id=template_id)
            return _subscription_response(content=conf, media_type="text/plain", headers=response_headers)

    elif (
        settings.use_custom_json_default or settings.use_custom_json_for_v2rayng
    ) and re.match(r'^v2rayNG/(\d+\.\d+\.\d+)', user_agent):
        version_str = re.match(r'^v2rayNG/(\d+\.\d+\.\d+)', user_agent).group(1)
        if LooseVersion(version_str) >= LooseVersion("1.8.29"):
            conf = generate_subscription(user=user, config_format="v2ray-json",
                                         as_base64=False, reverse=False, template_id=template_id)
            return _subscription_response(content=conf, media_type="application/json", headers=response_headers)
        elif LooseVersion(version_str) >= LooseVersion("1.8.18"):
            conf = generate_subscription(user=user, config_format="v2ray-json",
                                         as_base64=False, reverse=True, template_id=template_id)
            return _subscription_response(content=conf, media_type="application/json", headers=response_headers)
        else:
            conf = generate_subscription(user=user, config_format="v2ray", as_base64=True,
                                         reverse=False, template_id=template_id)
            return _subscription_response(content=conf, media_type="text/plain", headers=response_headers)

    elif re.match(r'^[Ss]treisand', user_agent):
        if settings.use_custom_json_default or settings.use_custom_json_for_streisand:
            conf = generate_subscription(user=user, config_format="v2ray-json",
                                         as_base64=False, reverse=False, template_id=template_id)
            return _subscription_response(content=conf, media_type="application/json", headers=response_headers)
        else:
            conf = generate_subscription(user=user, config_format="v2ray", as_base64=True,
                                         reverse=False, template_id=template_id)
            return _subscription_response(content=conf, media_type="text/plain", headers=response_headers)

    elif (
        settings.use_custom_json_default or settings.use_custom_json_for_happ
    ) and re.match(r'^[Hh]app/(\d+\.\d+\.\d+)(?:/|$)', user_agent):
        version_str = re.match(r'^[Hh]app/(\d+\.\d+\.\d+)(?:/|$)', user_agent).group(1)
        if LooseVersion(version_str) >= LooseVersion("1.63.1"):
            conf = generate_subscription(user=user, config_format="v2ray-json",
                                         as_base64=False, reverse=False, template_id=template_id)
            return _subscription_response(content=conf, media_type="application/json", headers=response_headers)
        else:
            conf = generate_subscription(user=user, config_format="v2ray", as_base64=True,
                                         reverse=False, template_id=template_id)
            return _subscription_response(content=conf, media_type="text/plain", headers=response_headers)

    else:
        conf = generate_subscription(user=user, config_format="v2ray", as_base64=True,
                                     reverse=False, template_id=template_id)
        return _subscription_response(content=conf, media_type="text/plain", headers=response_headers)


def user_subscription_info(
    dbuser: UserResponse = Depends(get_validated_sub),
):
    """Retrieves detailed information about the user's subscription."""
    return dbuser


def user_get_usage(
    dbuser: UserResponse = Depends(get_validated_sub),
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db)
):
    """Fetches the usage statistics for the user within a specified date range."""
    start, end = validate_dates(start, end)

    usages = user_crud.get_user_usages(db, dbuser, start, end)

    return {"usages": usages, "username": dbuser.username}


def user_subscription_with_client_type(
    request: Request,
    dbuser: UserResponse = Depends(get_validated_sub),
    client_type: str = Path(...,
                            pattern="^(sing-box|singbox|clash-meta|mihomo|clash|outline|v2ray|v2ray-json|xray-json|json)$"),
    groups: Union[str, None] = Query(None),
    db: Session = Depends(get_db),
    user_agent: str = Header(default=""),
    template_id: Annotated[int | None, Query(gt=0)] = None,
):
    """Provides a subscription link based on the specified client type (e.g., Clash, V2Ray)."""
    user: UserResponse = UserResponse.model_validate(dbuser)

    response_headers = get_subscription_response_headers(request, user)

    client_type = normalize_subscription_client_type(client_type)
    config = client_config.get(client_type)
    if config is None:
        raise HTTPException(status_code=422, detail="Unsupported subscription format")
    hosts = host_crud.get_hosts_v2(db, group_ids=parse_groups_query(groups))
    conf = generate_subscription_from_hosts(
        user=user,
        hosts=hosts,
        config_format=config["config_format"],
        as_base64=config["as_base64"],
        reverse=config["reverse"],
        template_id=template_id,
    )

    return _subscription_response(content=conf, media_type=config["media_type"], headers=response_headers)
