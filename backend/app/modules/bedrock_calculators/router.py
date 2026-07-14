"""Bedrock calculator API routes."""

from fastapi import APIRouter, Depends

from app.dependencies import CurrentUserId, CurrentUserPayload, RequirePermission, SessionDep
from app.modules.bedrock_calculators.schemas import (
    TruckHaulingApplyRequest,
    TruckHaulingApplyResponse,
    TruckHaulingPreviewRequest,
    TruckHaulingPreviewResponse,
)
from app.modules.bedrock_calculators.service import BedrockCalculatorService
from app.modules.boq.router import _verify_boq_owner
from app.modules.boq.service import BOQService

router = APIRouter(tags=["bedrock-calculators"])


def _get_service(session: SessionDep) -> BedrockCalculatorService:
    return BedrockCalculatorService(BOQService(session))


@router.post(
    "/truck-hauling/preview/",
    response_model=TruckHaulingPreviewResponse,
    dependencies=[Depends(RequirePermission("bedrock_calculators.read"))],
)
async def preview_truck_hauling(
    data: TruckHaulingPreviewRequest,
    service: BedrockCalculatorService = Depends(_get_service),
) -> TruckHaulingPreviewResponse:
    """Preview Truck / Hauling calculations for all provided truck options."""
    return service.preview_truck_hauling(data)


@router.post(
    "/truck-hauling/apply/",
    response_model=TruckHaulingApplyResponse,
    dependencies=[Depends(RequirePermission("bedrock_calculators.apply")), Depends(RequirePermission("boq.update"))],
)
async def apply_truck_hauling(
    data: TruckHaulingApplyRequest,
    user_id: CurrentUserId,
    payload: CurrentUserPayload,
    session: SessionDep,
    service: BedrockCalculatorService = Depends(_get_service),
) -> TruckHaulingApplyResponse:
    """Apply a selected Truck / Hauling preview result into a BOQ position."""
    await _verify_boq_owner(session, data.boq_id, user_id, payload)
    return await service.apply_truck_hauling(data)
