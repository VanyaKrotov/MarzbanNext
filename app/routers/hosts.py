from fastapi import APIRouter

from app.models.host import HostList, HostResponse
from app.services import host_service as service
from app.utils import responses

router = APIRouter(tags=["Hosts"], prefix="/api/hosts", responses={401: responses._401, 403: responses._403})

router.get("", response_model=HostList)(service.list_hosts)
router.post("", response_model=HostResponse, status_code=201)(service.create_host)
router.get("/capabilities")(service.get_capabilities)
router.post("/preview")(service.preview_host)
router.post("/reorder", response_model=list[HostResponse])(service.reorder_hosts)
router.get("/{host_id}", response_model=HostResponse)(service.get_host)
router.patch("/{host_id}", response_model=HostResponse)(service.update_host)
router.delete("/{host_id}", status_code=204)(service.delete_host)
router.post("/{host_id}/clone", response_model=HostResponse, status_code=201)(service.clone_host)
