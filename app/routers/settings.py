
from fastapi import APIRouter

from app.models.settings import RuntimeSettingsResponse
from app.utils import responses
from app.services import settings_service as service

router = APIRouter(tags=["Settings"], prefix="/api", responses={401: responses._401})

router.get("/settings", response_model=RuntimeSettingsResponse, responses={403: responses._403})(service.get_settings)

router.patch("/settings", response_model=RuntimeSettingsResponse,
             responses={403: responses._403})(service.modify_settings)

router.get("/settings/backups/database", responses={403: responses._403})(service.download_database_backup)

router.post("/settings/backups/database", responses={403: responses._403})(service.restore_database_backup)

router.get("/settings/backups/full", responses={403: responses._403})(service.download_full_backup)

router.post("/settings/backups/full", responses={403: responses._403})(service.restore_full_backup)
