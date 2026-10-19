
from fastapi import APIRouter

from app.models.settings import RuntimeSettingsResponse, SubscriptionBalancerResponse
from app.utils import responses
from app.services import settings_service as service

router = APIRouter(tags=["Settings"], prefix="/api", responses={401: responses._401})

router.get("/settings", response_model=RuntimeSettingsResponse, responses={403: responses._403})(service.get_settings)

router.patch("/settings", response_model=RuntimeSettingsResponse,
             responses={403: responses._403})(service.modify_settings)

router.get(
    "/settings/subscription-balancers",
    response_model=list[SubscriptionBalancerResponse],
    responses={403: responses._403},
)(service.get_subscription_balancers)

router.post(
    "/settings/subscription-balancers",
    response_model=SubscriptionBalancerResponse,
    responses={400: responses._400, 403: responses._403, 409: responses._409},
)(service.create_subscription_balancer)

router.put(
    "/settings/subscription-balancers/reorder",
    response_model=list[SubscriptionBalancerResponse],
    responses={400: responses._400, 403: responses._403},
)(service.reorder_subscription_balancers)

router.put(
    "/settings/subscription-balancers/{balancer_id}",
    response_model=SubscriptionBalancerResponse,
    responses={400: responses._400, 403: responses._403, 404: responses._404, 409: responses._409},
)(service.update_subscription_balancer)

router.delete(
    "/settings/subscription-balancers/{balancer_id}",
    responses={403: responses._403, 404: responses._404},
)(service.delete_subscription_balancer)

router.get("/settings/backups/database", responses={403: responses._403})(service.download_database_backup)

router.post("/settings/backups/database", responses={403: responses._403})(service.restore_database_backup)

router.get("/settings/backups/full", responses={403: responses._403})(service.download_full_backup)

router.post("/settings/backups/full", responses={403: responses._403})(service.restore_full_backup)
