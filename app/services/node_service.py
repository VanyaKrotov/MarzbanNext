import asyncio
import time
from datetime import datetime, timezone

import requests
from fastapi import (
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from starlette.websockets import WebSocketDisconnect

from app import logger, xray
from app.db import Session, get_db
from app.dependencies import get_dbnode, validate_dates
from app.models.admin import Admin
from app.models.node import (
    NodeCreate,
    NodeCertificateImport,
    NodeCertificateIssue,
    NodeCertificateModify,
    NodeGeoResourceBulkDelete,
    NodeGeoResourceRemoteCreate,
    NodeGeoResourceRename,
    NodeGeoResourceResponse,
    NodeGeoResourceScheduleModify,
    NodeModify,
    NodeResponse,
    NodeSettings,
    validate_static_log_filename,
    NodeStatus,
    validate_geo_resource_filename,
)
from app.xray.node import NodeAPIError
from app.models.host import HostCreate
from app.utils.node_geo_resources import (
    download_geo_resource,
    get_next_run_at,
    get_remote_node,
    upload_remote_geo_resource,
)
from app.utils.node_restart_state import (
    clear_node_pending_restart,
    is_node_pending_restart,
    mark_nodes_pending_restart,
)
from app.db.crud import node_certificates as certificate_crud
from app.db.crud import node_geo_resources as geo_resource_crud
from app.db.crud import proxy_hosts as host_crud
from app.db.crud import nodes as node_crud
from app.db.crud import routing as routing_crud
from app.db.crud import settings as settings_crud
from app.utils.runtime_settings import get_runtime_settings
from app.utils.xray_config_template import normalize_xray_config_template


def add_host_if_needed(new_node: NodeCreate, dbnode, db: Session):
    """Add a host if specified in the new node settings."""
    if new_node.add_as_new_host:
        for inbound in dbnode.inbounds:
            host_crud.create_host(db, HostCreate(
                inbound_id=inbound.id,
                remark=f"{new_node.name} ({{USERNAME}}) [{{PROTOCOL}} - {{TRANSPORT}}]",
                address=new_node.address,
            ))


def get_node_settings(
    db: Session = Depends(get_db), admin: Admin = Depends(Admin.check_sudo_admin)
):
    """Retrieve the current node settings, including TLS certificate."""
    tls = settings_crud.get_tls_certificate(db)
    return NodeSettings(certificate=tls.certificate)


def add_node(
    new_node: NodeCreate,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Add a new node to the database and optionally add it as a host."""
    config_template = normalize_xray_config_template(
        get_runtime_settings().default_node_config,
        api_port=new_node.api_port,
    )
    try:
        dbnode = node_crud.create_node(db, new_node, config_template=config_template)
        routing_crud.sync_readonly_node_config(db, dbnode, config_template)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f'Node "{new_node.name}" already exists'
        )
    except ValueError as exc:
        db.rollback()
        if "dbnode" in locals():
            node_crud.remove_node(db, dbnode)
        raise HTTPException(status_code=400, detail=str(exc))

    add_host_if_needed(new_node, dbnode, db)

    bg.add_task(xray.operations.connect_node, node_id=dbnode.id)

    logger.info(f'New node "{dbnode.name}" added')
    dbnode.restart_required = False
    return dbnode


def get_node(
    dbnode: NodeResponse = Depends(get_dbnode),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Retrieve details of a specific node by its ID."""
    return dbnode


def get_node_config_template(
    dbnode: NodeResponse = Depends(get_node),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Retrieve the Xray config template assigned to a remote node."""
    return dbnode.config_template or {}


def modify_node_config_template(
    payload: dict,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Update a node-specific Xray config template."""
    config_template = normalize_xray_config_template(payload, api_port=dbnode.api_port)
    try:
        updated_node = node_crud.update_node_config_template(db, dbnode, config_template)
        routing_crud.sync_readonly_node_config(db, updated_node, config_template)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    mark_nodes_pending_restart([updated_node.id])
    logger.info(f'Node "{updated_node.name}" config template modified')
    return updated_node.config_template


async def node_logs(node_id: int, websocket: WebSocket, db: Session = Depends(get_db)):
    token = websocket.query_params.get("token") or websocket.headers.get(
        "Authorization", ""
    ).removeprefix("Bearer ")
    admin = Admin.get_admin(token, db)
    if not admin:
        return await websocket.close(reason="Unauthorized", code=4401)

    if not admin.is_sudo:
        return await websocket.close(reason="You're not allowed", code=4403)

    if not xray.nodes.get(node_id):
        return await websocket.close(reason="Node not found", code=4404)

    if not xray.nodes[node_id].connected:
        return await websocket.close(reason="Node is not connected", code=4400)

    interval = websocket.query_params.get("interval")
    if interval:
        try:
            interval = float(interval)
        except ValueError:
            return await websocket.close(reason="Invalid interval value", code=4400)
        if interval > 10:
            return await websocket.close(
                reason="Interval must be more than 0 and at most 10 seconds", code=4400
            )

    await websocket.accept()

    cache = ""
    last_sent_ts = 0
    node = xray.nodes[node_id]
    with node.get_logs() as logs:
        while True:
            if not node == xray.nodes[node_id]:
                break

            if interval and time.time() - last_sent_ts >= interval and cache:
                try:
                    await websocket.send_text(cache)
                except (WebSocketDisconnect, RuntimeError):
                    break
                cache = ""
                last_sent_ts = time.time()

            if not logs:
                try:
                    await asyncio.wait_for(websocket.receive(), timeout=0.2)
                    continue
                except asyncio.TimeoutError:
                    continue
                except (WebSocketDisconnect, RuntimeError):
                    break

            log = logs.popleft()

            if interval:
                cache += f"{log}\n"
                continue

            try:
                await websocket.send_text(log)
            except (WebSocketDisconnect, RuntimeError):
                break


def get_nodes(
    db: Session = Depends(get_db), _: Admin = Depends(Admin.check_sudo_admin)
):
    """Retrieve a list of all nodes. Accessible only to sudo admins."""
    nodes = node_crud.get_nodes(db)
    for node in nodes:
        node.restart_required = is_node_pending_restart(node.id)
    return nodes


def modify_node(
    modified_node: NodeModify,
    bg: BackgroundTasks,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Update a node's details. Only accessible to sudo admins."""
    updated_node = node_crud.update_node(db, dbnode, modified_node)
    xray.operations.remove_node(updated_node.id)
    if updated_node.status != NodeStatus.disabled:
        bg.add_task(xray.operations.connect_node, node_id=updated_node.id)

    logger.info(f'Node "{dbnode.name}" modified')
    return dbnode


def reconnect_node(
    bg: BackgroundTasks,
    dbnode: NodeResponse = Depends(get_node),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Trigger a reconnection for the specified node. Only accessible to sudo admins."""
    bg.add_task(xray.operations.connect_node, node_id=dbnode.id)
    return {"detail": "Reconnection task scheduled"}


def restart_node(
    bg: BackgroundTasks,
    dbnode: NodeResponse = Depends(get_node),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Restart Xray core on one remote node using its current generated config."""
    bg.add_task(xray.operations.restart_node, node_id=dbnode.id)
    return {"detail": "Restart task scheduled"}


def _raise_geo_resource_error(exc: Exception) -> None:
    if isinstance(exc, NodeAPIError):
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=f"Node geo resource request failed: {exc.detail}",
        )
    if isinstance(exc, requests.RequestException):
        raise HTTPException(status_code=502, detail=f"Resource download failed: {exc}")
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc))
    raise HTTPException(status_code=502, detail=f"Node geo resource request failed: {exc}")


def _validate_geo_resource_path(filename: str) -> str:
    try:
        return validate_geo_resource_filename(filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _validate_static_log_path(log_type: str, filename: str) -> tuple[str, str]:
    if log_type not in {"access", "error"}:
        raise HTTPException(status_code=422, detail="Unknown log type")
    try:
        return log_type, validate_static_log_filename(filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _raise_static_log_error(exc: Exception) -> None:
    if isinstance(exc, NodeAPIError):
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=f"Node static log request failed: {exc.detail}",
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise HTTPException(status_code=502, detail=f"Node static log request failed: {exc}") from exc


def get_node_static_logs(
    dbnode: NodeResponse = Depends(get_node),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    try:
        return get_remote_node(dbnode).list_static_logs()
    except Exception as exc:
        _raise_static_log_error(exc)


def download_node_static_log(
    log_type: str,
    filename: str,
    dbnode: NodeResponse = Depends(get_node),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    log_type, filename = _validate_static_log_path(log_type, filename)
    try:
        stream = get_remote_node(dbnode).download_static_log(log_type, filename)
    except Exception as exc:
        _raise_static_log_error(exc)
    return StreamingResponse(
        stream,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def delete_node_static_log(
    log_type: str,
    filename: str,
    dbnode: NodeResponse = Depends(get_node),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    log_type, filename = _validate_static_log_path(log_type, filename)
    try:
        return get_remote_node(dbnode).delete_static_log(log_type, filename)
    except Exception as exc:
        _raise_static_log_error(exc)


def get_node_geo_resources(
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    try:
        files = get_remote_node(dbnode).list_geo_resources()
    except Exception as exc:
        _raise_geo_resource_error(exc)

    updates = {
        resource.filename: resource
        for resource in geo_resource_crud.get_node_geo_resource_updates(db, dbnode.id)
    }
    result = []
    for file in files:
        filename = file.get("filename")
        if not isinstance(filename, str):
            continue
        update = updates.get(filename)
        result.append(
            NodeGeoResourceResponse(
                filename=filename,
                size=file.get("size", 0),
                modified_at=file.get("modified_at"),
                auto_update=update is not None,
                url=update.url if update else None,
                cron=update.cron if update else None,
                last_updated_at=update.last_updated_at if update else None,
                next_run_at=update.next_run_at if update else None,
                last_error=update.last_error if update else None,
                last_error_at=update.last_error_at if update else None,
            )
        )
    return result


def upload_node_geo_resource(
    file: UploadFile = File(...),
    overwrite: bool = Query(False),
    dbnode: NodeResponse = Depends(get_node),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    try:
        upload_remote_geo_resource(
            dbnode, file.filename or "", file.file, overwrite=overwrite
        )
    except Exception as exc:
        _raise_geo_resource_error(exc)
    mark_nodes_pending_restart([dbnode.id])
    return {}


def create_remote_node_geo_resource(
    request: NodeGeoResourceRemoteCreate,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    try:
        with download_geo_resource(request.url) as chunks:
            upload_remote_geo_resource(
                dbnode, request.filename, chunks, overwrite=request.overwrite
            )
        resource = geo_resource_crud.upsert_node_geo_resource_update(
            db,
            node_id=dbnode.id,
            filename=request.filename,
            url=request.url,
            cron=request.cron,
            next_run_at=get_next_run_at(request.cron),
        )
        resource = geo_resource_crud.update_node_geo_resource_result(
            db, resource, next_run_at=resource.next_run_at
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Geo resource already exists")
    except Exception as exc:
        _raise_geo_resource_error(exc)

    mark_nodes_pending_restart([dbnode.id])
    return NodeGeoResourceResponse(
        filename=resource.filename,
        auto_update=True,
        url=resource.url,
        cron=resource.cron,
        last_updated_at=resource.last_updated_at,
        next_run_at=resource.next_run_at,
        last_error=resource.last_error,
        last_error_at=resource.last_error_at,
    )


def modify_node_geo_resource_schedule(
    filename: str,
    request: NodeGeoResourceScheduleModify,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    filename = _validate_geo_resource_path(filename)
    resource = geo_resource_crud.get_node_geo_resource_update(db, dbnode.id, filename)
    if not resource:
        raise HTTPException(status_code=404, detail="Auto-update configuration not found")
    try:
        resource = geo_resource_crud.upsert_node_geo_resource_update(
            db,
            node_id=dbnode.id,
            filename=filename,
            url=request.url,
            cron=request.cron,
            next_run_at=get_next_run_at(request.cron),
        )
    except Exception as exc:
        _raise_geo_resource_error(exc)
    mark_nodes_pending_restart([dbnode.id])
    return NodeGeoResourceResponse(
        filename=resource.filename,
        auto_update=True,
        url=resource.url,
        cron=resource.cron,
        last_updated_at=resource.last_updated_at,
        next_run_at=resource.next_run_at,
        last_error=resource.last_error,
        last_error_at=resource.last_error_at,
    )


def refresh_node_geo_resource(
    filename: str,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    filename = _validate_geo_resource_path(filename)
    resource = geo_resource_crud.get_node_geo_resource_update(db, dbnode.id, filename)
    if not resource:
        raise HTTPException(status_code=404, detail="Auto-update configuration not found")
    try:
        with download_geo_resource(resource.url) as chunks:
            upload_remote_geo_resource(dbnode, filename, chunks, overwrite=True)
        geo_resource_crud.update_node_geo_resource_result(
            db, resource, next_run_at=get_next_run_at(resource.cron)
        )
    except Exception as exc:
        geo_resource_crud.update_node_geo_resource_result(
            db,
            resource,
            next_run_at=get_next_run_at(resource.cron),
            error=str(exc),
        )
        _raise_geo_resource_error(exc)
    mark_nodes_pending_restart([dbnode.id])
    return {}


def download_node_geo_resource(
    filename: str,
    dbnode: NodeResponse = Depends(get_node),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    filename = _validate_geo_resource_path(filename)
    try:
        stream = get_remote_node(dbnode).download_geo_resource(filename)
    except Exception as exc:
        _raise_geo_resource_error(exc)
    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def rename_node_geo_resource(
    filename: str,
    request: NodeGeoResourceRename,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    filename = _validate_geo_resource_path(filename)
    resource = geo_resource_crud.get_node_geo_resource_update(db, dbnode.id, filename)
    target_resource = (
        geo_resource_crud.get_node_geo_resource_update(db, dbnode.id, request.filename)
        if filename != request.filename
        else None
    )
    if target_resource and not request.overwrite:
        raise HTTPException(
            status_code=409, detail="Auto-update configuration already exists"
        )
    try:
        get_remote_node(dbnode).rename_geo_resource(
            filename, request.filename, request.overwrite
        )
        if target_resource:
            geo_resource_crud.remove_node_geo_resource_update(db, target_resource)
        if resource:
            geo_resource_crud.rename_node_geo_resource_update(db, resource, request.filename)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Geo resource already exists")
    except Exception as exc:
        _raise_geo_resource_error(exc)
    mark_nodes_pending_restart([dbnode.id])
    return {}


def bulk_delete_node_geo_resources(
    request: NodeGeoResourceBulkDelete,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    try:
        get_remote_node(dbnode).delete_geo_resources(request.filenames)
        for filename in request.filenames:
            resource = geo_resource_crud.get_node_geo_resource_update(db, dbnode.id, filename)
            if resource:
                geo_resource_crud.remove_node_geo_resource_update(db, resource)
    except Exception as exc:
        _raise_geo_resource_error(exc)
    mark_nodes_pending_restart([dbnode.id])
    return {}


def delete_node_geo_resource(
    filename: str,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    filename = _validate_geo_resource_path(filename)
    try:
        get_remote_node(dbnode).delete_geo_resources([filename])
        resource = geo_resource_crud.get_node_geo_resource_update(db, dbnode.id, filename)
        if resource:
            geo_resource_crud.remove_node_geo_resource_update(db, resource)
    except Exception as exc:
        _raise_geo_resource_error(exc)
    mark_nodes_pending_restart([dbnode.id])
    return {}


def get_node_certificates(
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    return certificate_crud.get_node_certificates(db, dbnode.id)


def _upsert_node_certificate_from_result(
    db: Session,
    node_id: int,
    domain: str,
    result: dict,
):
    certificate = result.get("certificate") or result.get("fullchain")
    private_key = result.get("private_key") or result.get("key")
    if (
        not isinstance(certificate, str)
        or "BEGIN CERTIFICATE" not in certificate
        or not isinstance(private_key, str)
        or "BEGIN " not in private_key
        or "PRIVATE KEY" not in private_key
    ):
        raise HTTPException(status_code=502, detail="Node returned invalid PEM data")

    expires_at = result.get("expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires_at.tzinfo:
                expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(
                status_code=502, detail="Node returned invalid certificate expiry"
            )
    elif expires_at is not None and not isinstance(expires_at, datetime):
        raise HTTPException(
            status_code=502, detail="Node returned invalid certificate expiry"
        )

    return certificate_crud.upsert_node_certificate(
        db,
        node_id=node_id,
        domain=domain,
        certificate=certificate,
        private_key=private_key,
        certificate_file=(
            result.get("certificate_file")
            or result.get("certificateFile")
            or result.get("fullchain_file")
            or result.get("fullchainFile")
        ),
        key_file=(
            result.get("key_file")
            or result.get("keyFile")
            or result.get("private_key_file")
            or result.get("privateKeyFile")
        ),
        expires_at=expires_at,
    )


def issue_node_certificate(
    request: NodeCertificateIssue,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    try:
        node = xray.nodes.get(dbnode.id) or xray.operations.add_node(dbnode)
        result = node.issue_certificate(**request.model_dump())
    except NodeAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=f"Node certificate request failed: {exc.detail}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Node certificate request failed: {exc}"
        )

    dbcertificate = _upsert_node_certificate_from_result(
        db,
        node_id=dbnode.id,
        domain=request.domain,
        result=result,
    )
    mark_nodes_pending_restart([dbnode.id])
    return dbcertificate


def import_node_certificate(
    request: NodeCertificateImport,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    try:
        node = xray.nodes.get(dbnode.id) or xray.operations.add_node(dbnode)
        result = node.import_certificate(**request.model_dump())
    except NodeAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=f"Node certificate import failed: {exc.detail}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Node certificate import failed: {exc}"
        )

    dbcertificate = _upsert_node_certificate_from_result(
        db,
        node_id=dbnode.id,
        domain=request.domain,
        result=result,
    )
    mark_nodes_pending_restart([dbnode.id])
    return dbcertificate


def modify_node_certificate(
    certificate_id: int,
    modified: NodeCertificateModify,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    dbcertificate = certificate_crud.get_node_certificate(db, dbnode.id, certificate_id)
    if not dbcertificate:
        raise HTTPException(status_code=404, detail="Node certificate not found")
    try:
        updated = certificate_crud.update_node_certificate(db, dbcertificate, modified)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    mark_nodes_pending_restart([dbnode.id])
    return updated


def remove_node_certificate(
    certificate_id: int,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    dbcertificate = certificate_crud.get_node_certificate(db, dbnode.id, certificate_id)
    if not dbcertificate:
        raise HTTPException(status_code=404, detail="Node certificate not found")
    certificate_crud.remove_node_certificate(db, dbcertificate)
    mark_nodes_pending_restart([dbnode.id])
    return {}


def remove_node(
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Delete a node and remove it from xray in the background."""
    node_id = dbnode.id
    node_name = dbnode.name
    node_crud.remove_node(db, dbnode)
    xray.operations.remove_node(node_id)
    clear_node_pending_restart(node_id)

    logger.info(f'Node "{node_name}" deleted')
    return {}


def get_usage(
    db: Session = Depends(get_db),
    start: str = "",
    end: str = "",
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Retrieve usage statistics for nodes within a specified date range."""
    start, end = validate_dates(start, end)

    usages = node_crud.get_nodes_usage(db, start, end)

    return {"usages": usages}
