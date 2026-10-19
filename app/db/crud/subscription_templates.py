from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.subscription_templates import (
    HostSubscriptionTemplate,
    SubscriptionTemplate,
)
from app.models.subscription_template import SubscriptionFormat


class TemplateBindingError(ValueError):
    """A host references an unavailable template or an incompatible format."""


def get_template(db: Session, template_id: int) -> SubscriptionTemplate | None:
    return db.get(SubscriptionTemplate, template_id)


def get_templates(db: Session, format=None, search=None, offset=0, limit=50):
    query = db.query(SubscriptionTemplate)
    if format is not None:
        query = query.filter(SubscriptionTemplate.format == format)
    if search and search.strip():
        query = query.filter(SubscriptionTemplate.name.ilike(f"%{search.strip()}%"))
    total = query.count()
    items = query.order_by(SubscriptionTemplate.format, SubscriptionTemplate.id).offset(offset).limit(limit).all()
    return items, total


def get_defaults(db: Session) -> list[SubscriptionTemplate]:
    return db.query(SubscriptionTemplate).filter(SubscriptionTemplate.default_marker == 1).all()


def is_used(db: Session, template_id: int) -> bool:
    return db.query(HostSubscriptionTemplate.host_id).filter(
        HostSubscriptionTemplate.template_id == template_id
    ).first() is not None


def name_exists(db: Session, format: str, name: str, exclude_id=None) -> bool:
    query = db.query(SubscriptionTemplate.id).filter(
        SubscriptionTemplate.format == format,
        func.lower(SubscriptionTemplate.name) == name.lower(),
    )
    if exclude_id is not None:
        query = query.filter(SubscriptionTemplate.id != exclude_id)
    return query.first() is not None


def get_default_bindings(db: Session) -> dict[str, int]:
    bindings = {template.format: template.id for template in get_defaults(db)}
    missing = set(SubscriptionFormat) - bindings.keys()
    if missing:
        raise TemplateBindingError("Default subscription templates are missing")
    return bindings


def build_host_bindings(db: Session, bindings: dict) -> list[HostSubscriptionTemplate]:
    templates = db.query(SubscriptionTemplate).filter(SubscriptionTemplate.id.in_(set(bindings.values()))).all()
    by_id = {template.id: template for template in templates}
    result = []
    for format, template_id in bindings.items():
        template = by_id.get(template_id)
        if template is None or template.format != format:
            raise TemplateBindingError(
                f"Template {template_id} does not match format {getattr(format, 'value', format)}")
        result.append(HostSubscriptionTemplate(format=format, template=template))
    return result


def seed_defaults(db: Session) -> None:
    """Initialize an empty installation; never assign or re-enable existing hosts."""
    from app.utils.subscription_template_defaults import default_subscription_content

    existing = {template.format for template in get_defaults(db)}
    for format in SubscriptionFormat:
        if format not in existing:
            db.add(SubscriptionTemplate(
                name="default", format=format.value, content=default_subscription_content(format.value), default_marker=1
            ))
    db.flush()


def build_default_host_bindings(db: Session) -> list[HostSubscriptionTemplate]:
    if not get_defaults(db):
        seed_defaults(db)
    return build_host_bindings(db, get_default_bindings(db))
