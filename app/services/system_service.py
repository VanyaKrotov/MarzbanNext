from copy import deepcopy
from typing import Dict, List, Union

from fastapi import Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from app import __version__
from app.db import Session, get_db
from app.models.admin import Admin
from app.models.proxy import (
    InboundCreate,
    InboundModify,
    InboundResponse,
    HostGroupAttachRequest,
    HostGroupCreate,
    HostGroupModify,
    OutboundCreate,
    OutboundModify,
    OutboundResponse,
    ProxyHost,
    ProxyHostCreate,
    ProxyHostModify,
    ProxyHostReorder,
    RUNTIME_API_PROTOCOLS,
    USER_ACCOUNT_PROTOCOLS,
    XRAY_INBOUND_PROTOCOLS,
    XRAY_LEGACY_TRANSPORT_ALIASES,
    XRAY_OUTBOUND_PROTOCOLS,
    XRAY_SECURITIES,
    XRAY_TRANSPORTS,
    XrayCapabilities,
)
from app.models.system import SystemStats
from app.models.user import UserStatus
from app.utils.node_restart_state import mark_nodes_pending_restart
from app.utils.system import cpu_usage, memory_usage, realtime_bandwidth
from app.utils.xray_config_registry import (
    XRAY_VALIDATION_API_PORT,
    build_validation_payload,
    get_enabled_inbound_registry,
)
from app.xray.config import XRayConfig
from app.db.crud.subscription_templates import TemplateBindingError
from app.db.crud import admins as admin_crud
from app.db.crud import node_certificates as certificate_crud
from app.db.crud import proxy_hosts as host_crud
from app.db.crud import proxy_inbounds as inbound_crud
from app.db.crud import notifications as notification_crud
from app.db.crud import proxy_outbounds as outbound_crud
from app.db.crud import settings as settings_crud
from app.db.crud import users as user_crud


def parse_groups_query(groups: Union[str, None]) -> List[str]:
    if not groups:
        return []
    return [
        group.strip()
        for group in groups.split(",")
        if group.strip()
    ]


def _inbound_response(inbound) -> InboundResponse:
    return InboundResponse(
        tag=inbound.tag,
        enabled=inbound.enabled,
        readonly=inbound.readonly,
        content=inbound.content,
        node_ids=[node.id for node in inbound.nodes],
    )


def _outbound_response(outbound) -> OutboundResponse:
    return OutboundResponse(
        tag=outbound.tag,
        enabled=outbound.enabled,
        readonly=outbound.readonly,
        content=outbound.content,
        node_ids=[node.id for node in outbound.nodes],
    )


def _validate_inbound_content(db: Session, tag: str, content: dict) -> dict:
    normalized = deepcopy(content)
    normalized["tag"] = tag
    if normalized.get("protocol") not in XRAY_INBOUND_PROTOCOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Inbound protocol must be one of {sorted(XRAY_INBOUND_PROTOCOLS)}",
        )

    payload = build_validation_payload(
        db,
        inbounds=[normalized],
        replace_inbound_tags={tag, "API_INBOUND"},
    )
    try:
        XRayConfig(payload, api_port=XRAY_VALIDATION_API_PORT)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return normalized


def _validate_outbound_content(db: Session, tag: str, content: dict) -> dict:
    normalized = deepcopy(content)
    normalized["tag"] = tag
    if normalized.get("protocol") not in XRAY_OUTBOUND_PROTOCOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Outbound protocol must be one of {sorted(XRAY_OUTBOUND_PROTOCOLS)}",
        )

    payload = build_validation_payload(
        db,
        outbounds=[normalized],
        replace_outbound_tags={tag},
    )
    try:
        XRayConfig(payload, api_port=XRAY_VALIDATION_API_PORT)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return normalized


def _ensure_inbound_users(db: Session, inbound_tag: str) -> None:
    registry = get_enabled_inbound_registry(db)
    inbound = registry.inbounds_by_tag.get(inbound_tag)
    if not inbound:
        return
    protocol = inbound["protocol"]
    inbound_crud.ensure_protocol_inbounds_for_users(
        db,
        protocol=protocol,
        included_tags=[inbound_tag],
        protocol_inbound_tags=[
            item["tag"]
            for item in registry.inbounds_by_protocol.get(protocol, [])
        ],
    )
    db.commit()


def get_system_stats(
    db: Session = Depends(get_db), admin: Admin = Depends(Admin.get_current)
):
    """Fetch system stats including memory, CPU, and user metrics."""
    mem = memory_usage()
    cpu = cpu_usage()
    system = settings_crud.get_system_usage(db)
    dbadmin: Union[Admin, None] = admin_crud.get_admin(db, admin.username)

    total_user = user_crud.get_users_count(db, admin=dbadmin if not admin.is_sudo else None)
    users_active = user_crud.get_users_count(
        db, status=UserStatus.active, admin=dbadmin if not admin.is_sudo else None
    )
    users_disabled = user_crud.get_users_count(
        db, status=UserStatus.disabled, admin=dbadmin if not admin.is_sudo else None
    )
    users_on_hold = user_crud.get_users_count(
        db, status=UserStatus.on_hold, admin=dbadmin if not admin.is_sudo else None
    )
    users_expired = user_crud.get_users_count(
        db, status=UserStatus.expired, admin=dbadmin if not admin.is_sudo else None
    )
    users_limited = user_crud.get_users_count(
        db, status=UserStatus.limited, admin=dbadmin if not admin.is_sudo else None
    )
    online_users = notification_crud.count_online_users(db, minutes=5)
    realtime_bandwidth_stats = realtime_bandwidth()

    return SystemStats(
        version=__version__,
        mem_total=mem.total,
        mem_used=mem.used,
        cpu_cores=cpu.cores,
        cpu_usage=cpu.percent,
        total_user=total_user,
        online_users=online_users,
        users_active=users_active,
        users_disabled=users_disabled,
        users_expired=users_expired,
        users_limited=users_limited,
        users_on_hold=users_on_hold,
        incoming_bandwidth=system.uplink,
        outgoing_bandwidth=system.downlink,
        incoming_bandwidth_speed=realtime_bandwidth_stats.incoming_bytes,
        outgoing_bandwidth_speed=realtime_bandwidth_stats.outgoing_bytes,
    )


def get_inbounds(
    assigned_only: bool = False,
    include_tag: str | None = None,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.get_current),
):
    """Retrieve inbound configurations grouped by protocol."""
    nodes_by_inbound_tag = {
        inbound.tag: [
            {"id": node.id, "name": node.name}
            for node in sorted(inbound.nodes, key=lambda node: (node.name, node.id))
        ]
        for inbound in inbound_crud.get_inbounds(db)
    }
    registry = get_enabled_inbound_registry(db)
    return {
        protocol: [
            {
                **inbound,
                "nodes": nodes_by_inbound_tag.get(inbound["tag"], []),
            }
            for inbound in inbounds
            if not assigned_only
            or nodes_by_inbound_tag.get(inbound["tag"])
            or inbound["tag"] == include_tag
        ]
        for protocol, inbounds in registry.inbounds_by_protocol.items()
    }


def get_inbound_configs(
    node_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    return [
        _inbound_response(inbound)
        for inbound in inbound_crud.get_inbounds(db, node_id=node_id)
    ]


def _validate_host_xhttp_settings(host: ProxyHost, inbound) -> None:
    xhttp_fields = (
        "sc_max_buffered_posts",
        "x_padding_obfs_mode",
        "uplink_http_method",
    )
    if not any(getattr(host, field) is not None for field in xhttp_fields):
        return

    stream_settings = (inbound.content or {}).get("streamSettings", {})
    network = stream_settings.get("network", "tcp").lower()
    if network not in {"xhttp", "splithttp"}:
        raise HTTPException(status_code=400, detail="XHTTP host settings require an XHTTP inbound")

    xhttp_settings = stream_settings.get("xhttpSettings") or stream_settings.get("splithttpSettings") or {}
    if host.uplink_http_method == "GET" and xhttp_settings.get("mode", "auto") != "packet-up":
        raise HTTPException(
            status_code=400,
            detail="Uplink HTTP method GET requires XHTTP packet-up mode",
        )


def create_inbound_config(
    inbound: InboundCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    inbound.content = _validate_inbound_content(db, inbound.tag, inbound.content)
    try:
        created = inbound_crud.create_inbound(db, inbound)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Inbound tag already exists")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if inbound.auto_assign_users:
        _ensure_inbound_users(db, created.tag)
    else:
        inbound_crud.exclude_protocol_inbounds_for_users(
            db,
            protocol=created.content.get("protocol"),
            excluded_tags=[created.tag],
        )
        db.commit()
    mark_nodes_pending_restart(node.id for node in created.nodes)
    return _inbound_response(created)


def modify_inbound_config(
    inbound_tag: str,
    modified: InboundModify,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    dbinbound = inbound_crud.get_inbound(db, inbound_tag)
    if not dbinbound:
        raise HTTPException(status_code=404, detail="Inbound not found")
    if dbinbound.readonly and modified.content is not None:
        raise HTTPException(
            status_code=403,
            detail="Content of inbounds loaded from the Xray JSON config is read-only",
        )

    affected_node_ids = {node.id for node in dbinbound.nodes}
    was_enabled = dbinbound.enabled
    if modified.content is not None:
        modified.content = _validate_inbound_content(
            db,
            inbound_tag,
            modified.content,
        )
    try:
        updated = inbound_crud.update_inbound(db, dbinbound, modified)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    affected_node_ids.update(node.id for node in updated.nodes)
    if updated.enabled and not was_enabled:
        _ensure_inbound_users(db, updated.tag)
    mark_nodes_pending_restart(affected_node_ids)
    return _inbound_response(updated)


def delete_inbound_config(
    inbound_tag: str,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    dbinbound = inbound_crud.get_inbound(db, inbound_tag)
    if not dbinbound:
        raise HTTPException(status_code=404, detail="Inbound not found")
    if dbinbound.readonly:
        raise HTTPException(
            status_code=403,
            detail="Inbounds loaded from the Xray JSON config cannot be deleted",
        )
    affected_node_ids = {node.id for node in dbinbound.nodes}
    inbound_crud.remove_inbound(db, dbinbound)
    mark_nodes_pending_restart(affected_node_ids)


def get_outbound_configs(
    node_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    return [
        _outbound_response(outbound)
        for outbound in outbound_crud.get_outbounds(db, node_id=node_id)
    ]


def create_outbound_config(
    outbound: OutboundCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    outbound.content = _validate_outbound_content(db, outbound.tag, outbound.content)
    try:
        created = outbound_crud.create_outbound(db, outbound)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Outbound tag already exists")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    mark_nodes_pending_restart(node.id for node in created.nodes)
    return _outbound_response(created)


def modify_outbound_config(
    outbound_tag: str,
    modified: OutboundModify,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    dboutbound = outbound_crud.get_outbound(db, outbound_tag)
    if not dboutbound:
        raise HTTPException(status_code=404, detail="Outbound not found")
    if dboutbound.readonly and modified.content is not None:
        raise HTTPException(
            status_code=403,
            detail="Content of outbounds loaded from the Xray JSON config is read-only",
        )

    affected_node_ids = {node.id for node in dboutbound.nodes}
    if modified.content is not None:
        modified.content = _validate_outbound_content(
            db,
            outbound_tag,
            modified.content,
        )
    try:
        updated = outbound_crud.update_outbound(db, dboutbound, modified)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    affected_node_ids.update(node.id for node in updated.nodes)
    mark_nodes_pending_restart(affected_node_ids)
    return _outbound_response(updated)


def delete_outbound_config(
    outbound_tag: str,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    dboutbound = outbound_crud.get_outbound(db, outbound_tag)
    if not dboutbound:
        raise HTTPException(status_code=404, detail="Outbound not found")
    if dboutbound.readonly:
        raise HTTPException(
            status_code=403,
            detail="Outbounds loaded from the Xray JSON config cannot be deleted",
        )
    affected_node_ids = {node.id for node in dboutbound.nodes}
    outbound_crud.remove_outbound(db, dboutbound)
    mark_nodes_pending_restart(affected_node_ids)


def get_inbound_nodes(
    db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin)
):
    """Get node assignments for every managed inbound."""
    return inbound_crud.get_inbound_nodes(
        db,
        [inbound.tag for inbound in inbound_crud.get_inbounds(db)],
    )


def modify_inbound_nodes(
    inbound_nodes: Dict[str, List[int]],
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Update node assignments."""
    known_inbounds = {inbound.tag for inbound in inbound_crud.get_inbounds(db)}
    unknown_inbounds = set(inbound_nodes) - known_inbounds
    if unknown_inbounds:
        raise HTTPException(
            status_code=400,
            detail=f"Inbounds {sorted(unknown_inbounds)} don't exist",
        )

    before = inbound_crud.get_inbound_node_ids_map(db, list(inbound_nodes))
    try:
        result = inbound_crud.update_inbound_nodes(db, inbound_nodes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    changed_tags = {
        tag
        for tag, node_ids in result.items()
        if set(node_ids) != before.get(tag, set())
    }
    affected_node_ids = {
        node_id
        for tag in changed_tags
        for node_id in before.get(tag, set()) | set(result[tag])
    }
    mark_nodes_pending_restart(affected_node_ids)

    return result


def get_node_certificates(
    db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin)
):
    """Get certificate metadata for all nodes."""
    return certificate_crud.get_all_node_certificates(db)


def get_host_groups(
    db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin)
):
    """Get all host groups ordered by name."""
    return host_crud.get_host_groups(db)


def create_host_group(
    group: HostGroupCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Create a host group with an operator-provided slug id."""
    try:
        return host_crud.create_host_group(db, group)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Host group already exists") from exc


def get_host_group(
    group_id: str,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Get a host group by id."""
    dbgroup = host_crud.get_host_group(db, group_id)
    if not dbgroup:
        raise HTTPException(status_code=404, detail="Host group not found")
    return dbgroup


def update_host_group(
    group_id: str,
    group: HostGroupModify,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Update host group metadata without changing its id."""
    dbgroup = host_crud.get_host_group(db, group_id)
    if not dbgroup:
        raise HTTPException(status_code=404, detail="Host group not found")
    return host_crud.update_host_group(db, dbgroup, group)


def delete_host_group(
    group_id: str,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Delete a host group and detach it from all hosts."""
    dbgroup = host_crud.get_host_group(db, group_id)
    if not dbgroup:
        raise HTTPException(status_code=404, detail="Host group not found")
    host_crud.delete_host_group(db, dbgroup)
    return {}


def get_hosts(
    group_id: Union[str, None] = Query(None),
    groups: Union[str, None] = Query(None),
    search: Union[str, None] = Query(None),
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Get a list of proxy hosts grouped by inbound tag."""
    hosts = {
        tag: host_crud.get_hosts(
            db,
            tag,
            group_id=group_id,
            group_ids=parse_groups_query(groups),
            search=search,
        )
        for tag in [inbound.tag for inbound in inbound_crud.get_inbounds(db)]
    }
    return hosts


def get_hosts_v2(
    group_id: Union[str, None] = Query(None),
    groups: Union[str, None] = Query(None),
    search: Union[str, None] = Query(None),
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Get a flat list of proxy hosts ordered by position."""
    return host_crud.get_hosts_v2(
        db,
        group_id=group_id,
        group_ids=parse_groups_query(groups),
        search=search,
    )


def create_host_v2(
    host: ProxyHostCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Create a proxy host."""
    inbound = inbound_crud.get_inbound(db, host.inbound_tag)
    if not inbound:
        raise HTTPException(
            status_code=400, detail=f"Inbound {host.inbound_tag} doesn't exist"
        )
    _validate_host_xhttp_settings(host, inbound)
    try:
        dbhost = host_crud.create_host_v2(db, host)
    except TemplateBindingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return dbhost


def reorder_hosts_v2(
    payload: ProxyHostReorder,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Update the global proxy host order without changing inbound assignments."""
    try:
        hosts = host_crud.reorder_hosts_v2(db, payload.host_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return hosts


def update_host_v2(
    host_id: int,
    host: ProxyHostModify,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Update a proxy host."""
    inbound = inbound_crud.get_inbound(db, host.inbound_tag)
    if not inbound:
        raise HTTPException(
            status_code=400, detail=f"Inbound {host.inbound_tag} doesn't exist"
        )
    _validate_host_xhttp_settings(host, inbound)
    dbhost = host_crud.get_host_v2(db, host_id)
    if not dbhost:
        raise HTTPException(status_code=404, detail="Host not found")
    try:
        dbhost = host_crud.update_host_v2(db, dbhost, host)
    except TemplateBindingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return dbhost


def attach_host_groups(
    host_id: int,
    payload: HostGroupAttachRequest,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Attach a proxy host to one or more host groups."""
    dbhost = host_crud.get_host_v2(db, host_id)
    if not dbhost:
        raise HTTPException(status_code=404, detail="Host not found")
    try:
        return host_crud.attach_host_groups(db, dbhost, payload.group_ids)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def detach_host_groups(
    host_id: int,
    payload: HostGroupAttachRequest,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Detach a proxy host from one or more host groups."""
    dbhost = host_crud.get_host_v2(db, host_id)
    if not dbhost:
        raise HTTPException(status_code=404, detail="Host not found")
    try:
        return host_crud.detach_host_groups(db, dbhost, payload.group_ids)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def delete_host_v2(
    host_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Delete a proxy host."""
    dbhost = host_crud.get_host_v2(db, host_id)
    if not dbhost:
        raise HTTPException(status_code=404, detail="Host not found")
    host_crud.remove_host_v2(db, dbhost)
    return {}


def modify_hosts(
    modified_hosts: Dict[str, List[ProxyHost]],
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Modify proxy hosts and update the configuration."""
    known_inbounds = {inbound.tag for inbound in inbound_crud.get_inbounds(db)}
    for inbound_tag in modified_hosts:
        if inbound_tag not in known_inbounds:
            raise HTTPException(
                status_code=400, detail=f"Inbound {inbound_tag} doesn't exist"
            )

    for inbound_tag, hosts in modified_hosts.items():
        inbound = inbound_crud.get_inbound_or_raise(db, inbound_tag)
        for host in hosts:
            _validate_host_xhttp_settings(host, inbound)
        host_crud.update_hosts(db, inbound_tag, hosts)

    return {tag: host_crud.get_hosts(db, tag) for tag in known_inbounds}


def get_version():
    return __version__


def get_xray_capabilities(admin: Admin = Depends(Admin.get_current)):
    return XrayCapabilities(
        inbound_protocols=sorted(XRAY_INBOUND_PROTOCOLS),
        outbound_protocols=sorted(XRAY_OUTBOUND_PROTOCOLS),
        account_protocols=sorted(USER_ACCOUNT_PROTOCOLS),
        runtime_api_protocols=sorted(RUNTIME_API_PROTOCOLS),
        transports=sorted(XRAY_TRANSPORTS),
        securities=sorted(XRAY_SECURITIES),
        legacy_transport_aliases=XRAY_LEGACY_TRANSPORT_ALIASES,
    )
