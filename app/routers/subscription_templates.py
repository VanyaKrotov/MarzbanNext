from fastapi import APIRouter

from app.models.subscription_template import (
    SubscriptionTemplateList,
    SubscriptionTemplateResponse,
)
from app.services import subscription_template_service as service
from app.utils import responses

router = APIRouter(tags=["Subscription templates"],
                   prefix="/api/subscription-templates", responses={401: responses._401})
router.get("", response_model=SubscriptionTemplateList)(service.list_templates)
router.post("", response_model=SubscriptionTemplateResponse, status_code=201)(service.create_template)
router.get("/capabilities")(service.get_capabilities)
router.get("/{template_id}", response_model=SubscriptionTemplateResponse)(service.get_template_by_id)
router.patch("/{template_id}", response_model=SubscriptionTemplateResponse)(service.update_template)
router.delete("/{template_id}", status_code=204)(service.delete_template)
router.post("/{template_id}/clone", response_model=SubscriptionTemplateResponse,
            status_code=201)(service.clone_template)
router.post("/{template_id}/set-default", response_model=SubscriptionTemplateResponse)(service.set_default_template)
