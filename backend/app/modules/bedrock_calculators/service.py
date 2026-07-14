"""Service boundary for Bedrock calculator workflows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status

from app.modules.bedrock_calculators.calculators.truck_hauling import preview_truck_hauling
from app.modules.bedrock_calculators.schemas import (
    TruckHaulingApplyRequest,
    TruckHaulingApplyResponse,
    TruckHaulingPreviewRequest,
    TruckHaulingPreviewResponse,
    TruckOptionInput,
    TruckOptionPreview,
)
from app.modules.boq.schemas import PositionCreate
from app.modules.boq.service import BOQService


class BedrockCalculatorService:
    """Coordinates Bedrock calculator preview and apply workflows."""

    def __init__(self, boq_service: BOQService | None = None) -> None:
        self.boq_service = boq_service

    def preview_truck_hauling(self, data: TruckHaulingPreviewRequest) -> TruckHaulingPreviewResponse:
        return preview_truck_hauling(data)

    async def apply_truck_hauling(self, data: TruckHaulingApplyRequest) -> TruckHaulingApplyResponse:
        if self.boq_service is None:
            raise RuntimeError("BOQ service is required to apply calculator results")

        preview = preview_truck_hauling(data.preview)
        selected = next((option for option in preview.options if option.truck_type == data.selected_truck_type), None)
        if selected is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Selected truck type '{data.selected_truck_type}' was not present in the preview.",
            )
        blocking_flags = [flag for flag in selected.review_flags if flag.severity == "error"]
        if blocking_flags or selected.total_cost is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "Selected truck option cannot be applied until blocking review flags are resolved.",
                    "review_flags": [flag.model_dump() for flag in blocking_flags],
                },
            )

        run_id = str(uuid.uuid4())
        position = await self.boq_service.add_position(
            self._build_truck_hauling_position(data, preview, selected, run_id)
        )
        position_id = position.id
        return TruckHaulingApplyResponse(
            position_ids=[position_id],
            calculator_run={
                "run_id": run_id,
                "type": "truck_hauling",
                "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "position_ids": [str(position_id)],
                "status": "applied",
            },
            warnings=preview.warnings + selected.warnings,
            skipped_candidates=[
                option.truck_type for option in preview.options if option.truck_type != selected.truck_type
            ],
        )

    def _build_truck_hauling_position(
        self,
        data: TruckHaulingApplyRequest,
        preview: TruckHaulingPreviewResponse,
        selected: TruckOptionPreview,
        run_id: str,
    ) -> PositionCreate:
        total_cost = Decimal(selected.total_cost or "0")
        parent_quantity = data.preview.material_quantity
        unit_rate = Decimal("0") if parent_quantity == 0 else total_cost / parent_quantity
        description = data.description or f"Truck haul / delivery - {selected.truck_type}"
        metadata = {
            "calculator": {
                "module": "bedrock_calculators",
                "type": "truck_hauling",
                "version": preview.calculator_version,
                "run_id": run_id,
                "status": "generated",
                "inputs": data.preview.model_dump(mode="json"),
                "outputs": selected.model_dump(mode="json"),
                "selected_option": {"truck_type": selected.truck_type},
                "formula_trace": [step.model_dump(mode="json") for step in selected.formula_trace],
                "warnings": [flag.model_dump(mode="json") for flag in preview.warnings + selected.warnings],
                "review_flags": [flag.model_dump(mode="json") for flag in selected.review_flags],
            },
            "resources": _resources_for_selected_option(data.preview, selected),
            "currency": "USD",
        }
        return PositionCreate(
            boq_id=data.boq_id,
            ordinal=data.ordinal or f"BR-TRUCK-{run_id[:8]}",
            description=description,
            unit=data.preview.quantity_unit,
            quantity=float(parent_quantity),
            unit_rate=unit_rate,
            source="manual",
            metadata=metadata,
        )


def _resources_for_selected_option(
    request: TruckHaulingPreviewRequest,
    selected: TruckOptionPreview,
) -> list[dict[str, str]]:
    resources: list[dict[str, str]] = []
    parent_quantity = request.material_quantity if request.material_quantity > 0 else Decimal("1")
    truck_option = _selected_truck_input(request, selected)
    material_cost = Decimal(selected.material_cost or "0")
    if request.material_unit_cost is not None:
        material_quantity = request.material_quantity
        if (
            request.billing_type == "load"
            and request.truck_cost_per_load is None
            and selected.truck_capacity is not None
        ):
            material_quantity = Decimal(selected.truck_capacity) * Decimal(selected.loads)
        material_quantity_per_parent = material_quantity / parent_quantity
        resources.append(
            {
                "type": "material",
                "name": request.material_name,
                "unit": request.quantity_unit,
                "quantity": _format_decimal_string(material_quantity_per_parent),
                "unit_rate": _format_decimal_string(request.material_unit_cost or Decimal("0")),
                "total": _format_decimal_string(material_cost / parent_quantity),
            }
        )

    truck_cost = Decimal(selected.truck_cost or "0")
    if truck_cost > 0:
        resource_type = "equipment"
        resource_name = f"{selected.truck_type} truck hauling"
        resource_unit = "HR"
        resource_quantity = _decimal_from_preview(selected.total_hours) / parent_quantity
        resource_rate = truck_option.cost_per_hour or Decimal("0") if truck_option is not None else Decimal("0")
        if request.billing_type == "load" and request.truck_cost_classification == "subcontracted_hauling":
            resource_type = "subcontractor"
            resource_name = f"{selected.truck_type} subcontracted hauling"
            resource_unit = "LOAD"
            resource_quantity = Decimal(selected.loads) / parent_quantity
            resource_rate = request.truck_cost_per_load or Decimal("0")
        elif request.billing_type == "load":
            resource_unit = "LOAD"
            resource_quantity = Decimal(selected.loads) / parent_quantity
            resource_rate = request.truck_cost_per_load or Decimal("0")
        elif request.billing_type == "mile":
            distance_per_parent = _decimal_from_preview(selected.round_trip_distance_miles) / parent_quantity
            if (
                truck_option is not None
                and truck_option.miles_per_gallon is not None
                and request.fuel_cost_per_gallon is not None
            ):
                fuel_rate = request.fuel_cost_per_gallon / truck_option.miles_per_gallon
                resources.append(
                    {
                        "type": "material",
                        "name": f"{selected.truck_type} truck fuel",
                        "unit": "MI",
                        "quantity": _format_decimal_string(distance_per_parent),
                        "unit_rate": _format_decimal_string(fuel_rate),
                        "total": _format_decimal_string(distance_per_parent * fuel_rate),
                    }
                )
            resource_name = f"{selected.truck_type} truck maintenance"
            resource_unit = "MI"
            resource_quantity = distance_per_parent
            resource_rate = truck_option.cost_per_mile or Decimal("0") if truck_option is not None else Decimal("0")
        if resource_rate > 0:
            resources.append(
                {
                    "type": resource_type,
                    "name": resource_name,
                    "unit": resource_unit,
                    "quantity": _format_decimal_string(resource_quantity),
                    "unit_rate": _format_decimal_string(resource_rate),
                    "total": _format_decimal_string(resource_quantity * resource_rate),
                }
            )

    labor_cost = Decimal(selected.driving_labor_cost or "0")
    if labor_cost > 0:
        labor_quantity = (_decimal_from_preview(selected.total_hours) * request.driving_laborer_count) / parent_quantity
        resources.append(
            {
                "type": "labor",
                "name": "Driving labor",
                "unit": "HR",
                "quantity": _format_decimal_string(labor_quantity),
                "unit_rate": _format_decimal_string(request.driving_labor_rate or Decimal("0")),
                "total": _format_decimal_string(labor_cost / parent_quantity),
            }
        )
    return resources


def _selected_truck_input(request: TruckHaulingPreviewRequest, selected: TruckOptionPreview) -> TruckOptionInput | None:
    return next((option for option in request.truck_options if option.kind == selected.truck_type), None)


def _decimal_from_preview(value: str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _format_decimal_string(value: Decimal) -> str:
    if value.as_tuple().exponent < -6:
        value = value.quantize(Decimal("0.000001"))
    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")
