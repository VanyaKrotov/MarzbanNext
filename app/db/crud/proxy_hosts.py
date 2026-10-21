"""Host and group persistence. A host mutation commits exactly once after validation."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.models.proxies import HostGroup, HostLink, ProxyHost, ProxyInbound
from app.db.crud import subscription_templates as template_crud
from app.models.host import HostCreate, HostPatch, HostOverrides, BalancerSettings
from app.models.proxy import HostGroupCreate, HostGroupModify
from app.subscription.capabilities import validate_balancer


@dataclass
class PreparedHost:
    inbound: ProxyInbound
    groups: list[HostGroup]
    bindings: list
    overrides: dict
    balancer_settings: dict | None


def host_query(db: Session):
    return db.query(ProxyHost).options(
        joinedload(ProxyHost.inbound), selectinload(ProxyHost.groups),
        selectinload(ProxyHost.subscription_templates), selectinload(ProxyHost.outgoing_links),
        selectinload(ProxyHost.incoming_links).joinedload(HostLink.owner),
    )


def list_hosts(db: Session, group_id=None, group_ids=None, search=None, inbound_id=None,
               enabled=None, composition=None):
    query = host_query(db)
    groups = list(dict.fromkeys([value for value in [group_id, *(group_ids or [])] if value]))
    if groups:
        query = query.filter(ProxyHost.groups.any(HostGroup.id.in_(groups)))
    if search and search.strip():
        term = "%" + search.strip() + "%"
        query = query.filter(or_(ProxyHost.remark.ilike(term), ProxyHost.address.ilike(term),
                                 cast(ProxyHost.port, String).ilike(term)))
    if inbound_id is not None:
        query = query.filter(ProxyHost.inbound_id == inbound_id)
    if enabled is not None:
        query = query.filter(ProxyHost.enabled == enabled)
    if composition is not None:
        query = query.filter(ProxyHost.balancer_settings.is_not(None) if composition
                             else ProxyHost.balancer_settings.is_(None))
    return query.order_by(ProxyHost.position, ProxyHost.id)


def get_host(db: Session, host_id: int):
    return host_query(db).filter(ProxyHost.id == host_id).first()


def get_host_groups(db: Session) -> List[HostGroup]:
    return db.query(HostGroup).order_by(HostGroup.name, HostGroup.id).all()


def get_host_group(db: Session, group_id: str) -> Optional[HostGroup]:
    return db.query(HostGroup).filter(HostGroup.id == group_id).first()


def create_host_group(db: Session, group: HostGroupCreate) -> HostGroup:
    dbgroup = HostGroup(
        id=group.id,
        name=group.name,
        description=group.description,
        tags=group.tags,
    )
    db.add(dbgroup)
    db.commit()
    db.refresh(dbgroup)
    return dbgroup


def update_host_group(
    db: Session, dbgroup: HostGroup, group: HostGroupModify
) -> HostGroup:
    dbgroup.name = group.name
    dbgroup.description = group.description
    dbgroup.tags = group.tags
    db.commit()
    db.refresh(dbgroup)
    return dbgroup


def delete_host_group(db: Session, dbgroup: HostGroup) -> None:
    db.delete(dbgroup)
    db.commit()


def _get_existing_host_groups(db: Session, group_ids: List[str]) -> List[HostGroup]:
    unique_ids = list(dict.fromkeys(group_ids))
    if not unique_ids:
        return []
    groups = db.query(HostGroup).filter(HostGroup.id.in_(unique_ids)).all()
    if len(groups) != len(unique_ids):
        found_ids = {group.id for group in groups}
        missing_ids = [
            group_id for group_id in unique_ids if group_id not in found_ids
        ]
        raise ValueError(f"Host group not found: {', '.join(missing_ids)}")
    groups_by_id = {group.id: group for group in groups}
    return [groups_by_id[group_id] for group_id in unique_ids]


def merge_patch(current: dict, patch: dict, path: tuple[str, ...] = ()) -> dict:
    result = deepcopy(current) if isinstance(current, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and (*path, key) != ("transport", "xhttp", "extra"):
            result[key] = merge_patch(result.get(key, {}), value, (*path, key))
        else:
            result[key] = deepcopy(value)
    return result


def validate_connection_options(inbound: ProxyInbound, overrides: dict):
    transport = overrides.get("transport", {})
    xhttp = transport.get("xhttp", {})
    stream = inbound.content.get("streamSettings", {})
    network = stream.get("network", "tcp")
    if "extra" in xhttp:
        if network not in {"xhttp", "splithttp"}:
            raise ValueError("XHTTP extra requires an XHTTP inbound")
        settings = stream.get("xhttpSettings") or stream.get("splithttpSettings") or {}
        if xhttp["extra"].get("uplinkHTTPMethod") == "GET" and settings.get("mode", "auto") != "packet-up":
            raise ValueError("overrides.transport.xhttp.extra.uplinkHTTPMethod: GET requires packet-up mode")


def prepare_host(db: Session, data: HostCreate, host_id: int | None) -> PreparedHost:
    inbound = db.get(ProxyInbound, data.inbound_id)
    if inbound is None:
        raise ValueError("Inbound not found")
    if host_id in data.linked_host_ids:
        raise ValueError("A host cannot reference itself")
    members = db.query(ProxyHost).filter(ProxyHost.id.in_(data.linked_host_ids)).all() if data.linked_host_ids else []
    if len(members) != len(data.linked_host_ids):
        raise ValueError("Linked host not found")
    groups = _get_existing_host_groups(db, data.group_ids)
    bindings = template_crud.build_host_bindings(db, data.subscription_template_ids)
    overrides = (data.overrides.model_dump(exclude_unset=True, exclude_none=True, by_alias=True)
                 if data.overrides else {})
    validate_connection_options(inbound, overrides)
    balancer = data.balancer_settings
    if data.linked_host_ids and balancer is None:
        balancer = BalancerSettings()
    settings = balancer.model_dump(exclude_none=True, by_alias=True) if balancer is not None else None
    if settings is not None:
        validate_balancer(settings, data.subscription_template_ids, set(data.linked_host_ids) | {host_id})
    return PreparedHost(inbound, groups, bindings, overrides, settings)


def _apply(db: Session, host: ProxyHost, data: HostCreate, prepared: PreparedHost):
    host.inbound = prepared.inbound
    for name in ("remark", "address", "port", "enabled", "show_when_composed"):
        setattr(host, name, getattr(data, name))
    if data.position is not None:
        host.position = data.position
    host.groups = prepared.groups
    host.subscription_templates = prepared.bindings
    host.overrides = prepared.overrides
    host.balancer_settings = prepared.balancer_settings
    host.updated_at = datetime.now(UTC).replace(tzinfo=None)
    # Delete first so reordering cannot transiently violate the unique owner/position key.
    host.outgoing_links.clear()
    db.flush()
    host.outgoing_links = [HostLink(member_host_id=member_id, position=index)
                           for index, member_id in enumerate(data.linked_host_ids)]


def create_host(db: Session, data: HostCreate) -> ProxyHost:
    if "subscription_template_ids" not in data.model_fields_set:
        if not template_crud.get_defaults(db):
            template_crud.seed_defaults(db)
        data = data.model_copy(update={"subscription_template_ids": template_crud.get_default_bindings(db)})
    prepared = prepare_host(db, data, None)
    position = data.position
    if position is None:
        maximum = db.query(func.max(ProxyHost.position)).scalar()
        position = (maximum if maximum is not None else -1) + 1
    host = ProxyHost(position=position)
    db.add(host)
    _apply(db, host, data, prepared)
    db.add(host)
    db.commit()
    return get_host(db, host.id)


def update_host(db: Session, host: ProxyHost, patch: HostPatch) -> ProxyHost:
    values = {name: getattr(host, name) for name in
              ("inbound_id", "remark", "address", "port", "enabled", "position", "show_when_composed",
               "overrides", "balancer_settings", "linked_host_ids", "subscription_template_ids")}
    values["group_ids"] = [group.id for group in host.groups]
    changes = patch.model_dump(exclude_unset=True)
    for name in ("overrides", "balancer_settings"):
        if name in changes and isinstance(changes[name], dict):
            changes[name] = merge_patch(values[name] or {}, changes[name])
    values.update(changes)
    values["overrides"] = HostOverrides.model_validate(values["overrides"] or {})
    data = HostCreate.model_validate(values)
    prepared = prepare_host(db, data, host.id)
    _apply(db, host, data, prepared)
    db.commit()
    return get_host(db, host.id)


def remove_host(db: Session, host: ProxyHost):
    db.delete(host)
    db.commit()


def reorder_hosts(db: Session, ids: list[int]):
    hosts = list_hosts(db).all()
    if len(ids) != len(set(ids)) or set(ids) != {host.id for host in hosts}:
        raise ValueError("Host order must contain every host exactly once")
    by_id = {host.id: host for host in hosts}
    for position, host_id in enumerate(ids):
        by_id[host_id].position = position
    db.commit()
    return list_hosts(db).all()


def clone_host(db: Session, source: ProxyHost, remark: str):
    data = HostCreate(
        inbound_id=source.inbound_id, remark=remark, address=source.address, port=source.port,
        enabled=False, show_when_composed=source.show_when_composed,
        overrides=source.overrides, balancer_settings=source.balancer_settings,
        linked_host_ids=source.linked_host_ids, group_ids=[group.id for group in source.groups],
        subscription_template_ids=source.subscription_template_ids,
    )
    prepared = prepare_host(db, data, source.id)
    maximum = db.query(func.max(ProxyHost.position)).scalar()
    host = ProxyHost(position=(maximum if maximum is not None else -1) + 1)
    db.add(host)
    _apply(db, host, data, prepared)
    # Costs identify connections by host ID; the owner's cost must follow its clone.
    settings = deepcopy(host.balancer_settings)
    if settings:
        for options in settings.get("clients", {}).values():
            for cost in (options.get("strategy_settings") or {}).get("costs", []):
                if cost["host_id"] == source.id:
                    cost["host_id"] = host.id
        host.balancer_settings = settings
    db.commit()
    return get_host(db, host.id)
