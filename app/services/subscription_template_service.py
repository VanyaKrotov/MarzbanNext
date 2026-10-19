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
)
from app.utils.subscription_templates import validate_subscription_template


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
    if template.is_default and name != template.name:
        raise HTTPException(status_code=409, detail="Default template names cannot be changed")
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
    if template.is_default or crud.is_used(db, template_id):
        raise HTTPException(status_code=409, detail="Default or assigned templates cannot be deleted")
    db.delete(template)
    _commit(db)
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
