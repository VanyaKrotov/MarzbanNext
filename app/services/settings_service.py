import os
import shutil
import tempfile

from fastapi import Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from app.db import Session, get_db
from app.models.admin import Admin
from app.models.settings import (
    RuntimeSettingsModify,
)
from app.utils.backups import (
    create_full_backup_archive,
    database_backup_filename,
    dump_database_sql,
    full_backup_filename,
    restore_database_sql,
    restore_full_backup_archive,
)
from app.utils.runtime_settings import (
    get_runtime_settings,
    runtime_settings_response,
    update_runtime_settings,
)
from app.utils.xray_config_template import normalize_xray_config_template
from app.utils.xray_config_registry import XRAY_VALIDATION_API_PORT
from app.utils.subscription_template_defaults import GENERATOR_TEMPLATE_SOURCES
from app.utils.subscription_templates import validate_generator_settings


def _remove_file(path: str) -> None:
    if os.path.exists(path):
        os.unlink(path)


def get_settings(admin: Admin = Depends(Admin.check_sudo_admin)):
    return runtime_settings_response(get_runtime_settings())


def modify_settings(
    modified_settings: RuntimeSettingsModify,
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    for key in GENERATOR_TEMPLATE_SOURCES.keys() & modified_settings.model_fields_set:
        content = getattr(modified_settings, key)
        if content is None:
            raise HTTPException(status_code=422, detail=f"{key} settings cannot be null")
        try:
            validate_generator_settings(key, content)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if modified_settings.default_node_config is not None:
        modified_settings.default_node_config = normalize_xray_config_template(
            modified_settings.default_node_config,
            api_port=XRAY_VALIDATION_API_PORT,
        )
    settings = update_runtime_settings(db, modified_settings)
    return runtime_settings_response(settings)


def download_database_backup(admin: Admin = Depends(Admin.check_sudo_admin)):
    return Response(
        content=dump_database_sql(),
        media_type="application/sql",
        headers={
            "Content-Disposition": f'attachment; filename="{database_backup_filename()}"'
        },
    )


def restore_database_backup(
    file: UploadFile,
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    if not file.filename or not file.filename.lower().endswith(".sql"):
        raise HTTPException(status_code=422, detail="Upload a .sql backup file")
    restore_database_sql(file.file.read())
    return {"detail": "Database restored"}


def download_full_backup(admin: Admin = Depends(Admin.check_sudo_admin)):
    archive_path = create_full_backup_archive()
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=full_backup_filename(),
        background=BackgroundTask(_remove_file, archive_path),
    )


def restore_full_backup(
    file: UploadFile,
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="Upload a .zip backup archive")

    fd, archive_path = tempfile.mkstemp(prefix="marzbannext_restore_", suffix=".zip")
    os.close(fd)
    try:
        with open(archive_path, "wb") as target:
            shutil.copyfileobj(file.file, target)
        restore_full_backup_archive(archive_path)
    finally:
        try:
            os.unlink(archive_path)
        except FileNotFoundError:
            pass
    return {"detail": "Backup restored"}
