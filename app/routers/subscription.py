
from fastapi import APIRouter

from app.models.user import SubscriptionUserResponse
from config import XRAY_SUBSCRIPTION_PATH

from app.services import subscription_service as service

router = APIRouter(tags=['Subscription'], prefix=f'/{XRAY_SUBSCRIPTION_PATH}')

router.get("/{token}", include_in_schema=False)(service.user_subscription)

router.get("/{token}/info", response_model=SubscriptionUserResponse)(service.user_subscription_info)

router.get("/{token}/usage")(service.user_get_usage)

router.get("/{token}/{client_type}")(service.user_subscription_with_client_type)
