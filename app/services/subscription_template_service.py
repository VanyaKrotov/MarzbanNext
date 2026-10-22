from fastapi import Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from app import logger
from app.db import Session, get_db
from app.db.crud import subscription_templates as crud
from app.db.models.subscription_templates import SubscriptionTemplate
from app.models.admin import Admin
from app.models.subscription_template import (
    SubscriptionFormat,
    SubscriptionTemplateClone,
    SubscriptionTemplateCreate,
    SubscriptionTemplateModify,
    SubscriptionTemplatePreview,
)
from app.utils.subscription_templates import validate_subscription_template


def get_capabilities(admin: Admin = Depends(Admin.check_sudo_admin)):
    from copy import deepcopy
    from app.subscription.template_directives import IncludeProxies, XrayDirectives

    include = IncludeProxies.model_json_schema()
    include["$defs"]["Selector"]["properties"]["type"]["enum"] = ["ids", "groups"]
    clash = deepcopy(include)
    clash["properties"]["include-proxies"] = clash["properties"].pop("includeProxies")
    return {"v2ray-json": XrayDirectives.model_json_schema(), "clash": clash, "sing-box": include}


def preview_users(search: str = "", limit: int = Query(50, ge=1, le=100),
                  db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin)):
    from app.db.models.users import User

    query = db.query(User.id, User.username)
    if search.strip():
        query = query.filter(User.username.contains(search.strip(), autoescape=True))
    return [{"id": row.id, "username": row.username} for row in query.order_by(User.username).limit(limit)]


def preview_template(payload: SubscriptionTemplatePreview, db: Session = Depends(get_db),
                     admin: Admin = Depends(Admin.check_sudo_admin)):
    from dataclasses import replace

    from app.db.models.users import User
    from app.subscription.contracts import RenderInput, SubscriptionError, TemplateSnapshot
    from app.subscription.generators import GeneratorRegistry
    from app.subscription.loader import SubscriptionSnapshotLoader
    from app.subscription.planning import ProfilePlanner
    from app.subscription.resolver import ResolveContext
    from app.subscription.share import setup_format_variables

    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    _validate(payload.format, payload.content)
    snapshot = SubscriptionSnapshotLoader().load(db)
    if payload.recipient_host_id is not None and not any(
        host.id == payload.recipient_host_id for host in snapshot.hosts
    ):
        raise HTTPException(status_code=404, detail="Recipient host not found")
    snapshot = replace(snapshot, templates={**snapshot.templates,
                       -1: TemplateSnapshot(-1, payload.format.value, payload.content)})
    proxies = {proxy.type.value: proxy.settings for proxy in user.proxies}
    context = setup_format_variables({"username": user.username, "used_traffic": user.used_traffic,
                                      "data_limit": user.data_limit, "expire": user.expire, "status": user.status})
    try:
        plans, diagnostics = ProfilePlanner().plan(
            snapshot, payload.format.value, proxies, user.inbounds, ResolveContext(context),
            root_ids={payload.recipient_host_id} if payload.recipient_host_id is not None else None, template_id=-1,
        )
        result = GeneratorRegistry().for_target(payload.format.value).generate(
            RenderInput(payload.format.value, plans, snapshot.defaults, snapshot.external_config))
        return {"body": result.body, "media_type": result.media_type,
                "recipient_host_ids": [plan.owner.id for plan in plans],
                "diagnostics": [*diagnostics, *result.diagnostics]}
    except ValueError as exc:
        raise HTTPException(status_code=exc.status_code if isinstance(exc, SubscriptionError) else 422,
                            detail=str(exc)) from exc


def _get_template(db: Session, template_id: int) -> SubscriptionTemplate:
    template = crud.get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Subscription template not found")
    return template


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Template name or default assignment already exists") from exc


def _validate(format: SubscriptionFormat, content: str) -> None:
    try:
        validate_subscription_template(format, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def list_templates(
    format: SubscriptionFormat | None = None,
    search: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    items, total = crud.get_templates(db, format, search, offset, limit)
    return {"items": items, "total": total}


def get_template_by_id(
    template_id: int, db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin),
):
    return _get_template(db, template_id)


def create_template(
    payload: SubscriptionTemplateCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    _validate(payload.format, payload.content)
    if crud.name_exists(db, payload.format, payload.name):
        raise HTTPException(status_code=409, detail="Template name already exists for this format")
    template = SubscriptionTemplate(**payload.model_dump())
    db.add(template)
    _commit(db)
    db.refresh(template)
    logger.info("Subscription template %s created by %s", template.id, admin.username)
    return template


def update_template(
    template_id: int, payload: SubscriptionTemplateModify,
    db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin),
):
    template = _get_template(db, template_id)
    updates = payload.model_dump(exclude_unset=True)
    if any(value is None for value in updates.values()):
        raise HTTPException(status_code=422, detail="Template fields cannot be null")
    format = updates.get("format", template.format)
    if format != template.format and (template.is_default or crud.is_used(db, template_id)):
        raise HTTPException(status_code=409, detail="Cannot change the format of a default or assigned template")
    name = updates.get("name", template.name)
    if crud.name_exists(db, format, name, template_id):
        raise HTTPException(status_code=409, detail="Template name already exists for this format")
    _validate(SubscriptionFormat(format), updates.get("content", template.content))
    for key, value in updates.items():
        setattr(template, key, value)
    _commit(db)
    db.refresh(template)
    logger.info("Subscription template %s updated by %s", template.id, admin.username)
    return template


def delete_template(
    template_id: int, db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin),
):
    template = _get_template(db, template_id)
    if template.is_default:
        raise HTTPException(status_code=409, detail="Default templates cannot be deleted")
    if crud.is_used(db, template_id):
        raise HTTPException(status_code=409, detail="Templates assigned to hosts cannot be deleted")
    db.delete(template)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # A host can bind the template between the usage check and the DELETE.
        raise HTTPException(status_code=409, detail="Templates assigned to hosts cannot be deleted") from exc
    logger.info("Subscription template %s deleted by %s", template_id, admin.username)


def clone_template(
    template_id: int, payload: SubscriptionTemplateClone,
    db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin),
):
    template = _get_template(db, template_id)
    return create_template(
        SubscriptionTemplateCreate(name=payload.name, format=template.format, content=template.content), db, admin
    )


def set_default_template(
    template_id: int, db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin),
):
    template = _get_template(db, template_id)
    # Updating the existing default first serializes competing writers on this format.
    db.query(SubscriptionTemplate).filter(
        SubscriptionTemplate.format == template.format, SubscriptionTemplate.default_marker == 1
    ).update({SubscriptionTemplate.default_marker: None}, synchronize_session="fetch")
    db.flush()
    template.default_marker = 1
    _commit(db)
    db.refresh(template)
    return template
