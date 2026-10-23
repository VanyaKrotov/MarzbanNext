"""Administrative host operations, without transport or client-generation details."""

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app import logger
from app.db import Session, get_db
from app.db.crud import proxy_hosts as crud
from app.models.admin import Admin
from app.models.host import HostCreate, HostPatch, HostReorder, HostClone, HostPreview


def require_host(db, host_id):
    host = crud.get_host(db, host_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")
    return host


def _mutate(db, action):
    try:
        result = action()
        logger.info("Host configuration updated")
        return result
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Host configuration conflicts with existing data") from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def list_hosts(search: str | None = None, groups: str | None = None, inbound_id: int | None = None,
               enabled: bool | None = None, offset: int = 0, limit: int = 100,
               db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin)):
    if offset < 0 or not 1 <= limit <= 1000:
        raise HTTPException(status_code=422, detail="Invalid pagination")
    query = crud.list_hosts(db, group_ids=groups.split(",") if groups else [], search=search,
                            inbound_id=inbound_id, enabled=enabled)
    return {"items": query.offset(offset).limit(limit).all(), "total": query.count()}


def get_host(host_id: int, db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin)):
    return require_host(db, host_id)


def create_host(host: HostCreate, db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin)):
    return _mutate(db, lambda: crud.create_host(db, host))


def update_host(host_id: int, host: HostPatch, db: Session = Depends(get_db),
                admin: Admin = Depends(Admin.check_sudo_admin)):
    row = require_host(db, host_id)
    return _mutate(db, lambda: crud.update_host(db, row, host))


def delete_host(host_id: int, db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin)):
    row = require_host(db, host_id)
    _mutate(db, lambda: crud.remove_host(db, row))


def reorder_hosts(payload: HostReorder, db: Session = Depends(get_db),
                  admin: Admin = Depends(Admin.check_sudo_admin)):
    return _mutate(db, lambda: crud.reorder_hosts(db, payload.host_ids))


def clone_host(host_id: int, payload: HostClone, db: Session = Depends(get_db),
               admin: Admin = Depends(Admin.check_sudo_admin)):
    source = require_host(db, host_id)
    return _mutate(db, lambda: crud.clone_host(db, source, payload.remark))


def get_capabilities(admin: Admin = Depends(Admin.check_sudo_admin)):
    from app.subscription.capabilities import host_capabilities

    return host_capabilities()


def preview_host(payload: HostPreview, db: Session = Depends(get_db),
                 admin: Admin = Depends(Admin.check_sudo_admin)):
    from dataclasses import replace
    from app.db.models.users import User
    from app.db.crud.subscription_templates import get_default_bindings
    from app.subscription.contracts import HostSnapshot, SubscriptionError, RenderInput
    from app.subscription.generators import GeneratorRegistry
    from app.subscription.loader import SubscriptionSnapshotLoader
    from app.subscription.planning import ProfilePlanner
    from app.subscription.resolver import ResolveContext
    from app.subscription.share import setup_format_variables

    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.host_id is not None:
        require_host(db, payload.host_id)
    data = payload.host
    if "subscription_template_ids" not in data.model_fields_set:
        data = data.model_copy(update={"subscription_template_ids": get_default_bindings(db)})
    try:
        prepared = crud.prepare_host(db, data)
        snapshot = SubscriptionSnapshotLoader().load(db)
        host_id = payload.host_id or max([host.id for host in snapshot.hosts] + [0]) + 1
        host = HostSnapshot(host_id, data.inbound_id, prepared.inbound.tag, data.remark, data.address, data.port,
                            data.enabled, data.position or 0, data.is_hidden,
                            prepared.overrides, tuple(data.group_ids), data.subscription_template_ids)
        snapshot = replace(snapshot, hosts=tuple(row for row in snapshot.hosts if row.id != host_id) + (host,))
        proxies = {proxy.type.value: proxy.settings for proxy in user.proxies}
        context = setup_format_variables({"username": user.username, "used_traffic": user.used_traffic,
                                          "data_limit": user.data_limit, "expire": user.expire, "status": user.status})
        plans, diagnostics = ProfilePlanner().plan(snapshot, payload.target, proxies, user.inbounds,
                                                   ResolveContext(context), root_ids={host_id})
        GeneratorRegistry().for_target(payload.target).generate(RenderInput(payload.target, plans, snapshot.defaults))
        return {"profiles": [{"owner_host_id": plan.owner.id,
                              "member_host_ids": [connection.host_id for connection in plan.connections],
                              "template_id": plan.template.id}
                             for plan in plans], "diagnostics": diagnostics}
    except SubscriptionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
