"""Schemas for Bedrock calculator preview APIs."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

BillingType = Literal["hour", "mile", "load"]
QuantityUnit = Literal["CY", "ton", "load"]
TruckCostClassification = Literal["haul_only", "delivered_material", "subcontracted_hauling", "unknown"]


class ReviewFlag(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    requires_resolution: bool = False


class FormulaTraceStep(BaseModel):
    name: str
    formula: str
    value: str | int | None


class TruckOptionInput(BaseModel):
    kind: str = Field(..., min_length=1)
    volume_capacity: Decimal | None = Field(default=None, ge=0)
    weight_capacity: Decimal | None = Field(default=None, ge=0)
    cost_per_hour: Decimal | None = Field(default=None, ge=0)
    cost_per_mile: Decimal | None = Field(default=None, ge=0)
    miles_per_gallon: Decimal | None = Field(default=None, gt=0)


class TruckHaulingPreviewRequest(BaseModel):
    material_quantity: Decimal = Field(..., ge=0)
    quantity_unit: QuantityUnit
    material_name: str = Field(default="Material", min_length=1, max_length=120)
    material_unit_cost: Decimal | None = Field(default=None, ge=0)
    quarry_distance: Decimal = Field(..., ge=0)
    billing_type: BillingType
    truck_options: list[TruckOptionInput] = Field(..., min_length=1)
    truck_cost_per_load: Decimal | None = Field(default=None, ge=0)
    truck_cost_classification: TruckCostClassification = "unknown"
    fuel_cost_per_gallon: Decimal | None = Field(default=None, ge=0)
    speed_mph: Decimal = Field(default=Decimal("60"), gt=0)
    time_at_quarry_minutes: Decimal = Field(default=Decimal("0"), ge=0)
    time_at_job_site_minutes: Decimal = Field(default=Decimal("0"), ge=0)
    driving_labor_rate: Decimal | None = Field(default=None, ge=0)
    driving_laborer_count: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("quantity_unit", mode="before")
    @classmethod
    def normalize_quantity_unit(cls, value: str) -> str:
        normalized = value.strip().lower().replace("cubic_yard", "cy").replace("tons", "ton")
        if normalized in {"cy", "cubic yards", "cubic yard"}:
            return "CY"
        if normalized in {"ton", "tons"}:
            return "ton"
        if normalized in {"load", "loads"}:
            return "load"
        return value

    @field_validator("billing_type", mode="before")
    @classmethod
    def normalize_billing_type(cls, value: str) -> str:
        return value.strip().lower()


class TruckOptionPreview(BaseModel):
    truck_type: str
    truck_capacity: str | None
    truck_capacity_unit: str | None
    loads: int
    round_trip_distance_miles: str
    total_hours: str
    truck_cost: str | None
    driving_labor_cost: str | None
    material_cost: str | None
    total_cost: str | None
    unit_cost: str | None
    billing_type: BillingType
    cost_method: str
    warnings: list[ReviewFlag] = Field(default_factory=list)
    review_flags: list[ReviewFlag] = Field(default_factory=list)
    formula_trace: list[FormulaTraceStep] = Field(default_factory=list)


class TruckHaulingPreviewResponse(BaseModel):
    calculator_type: Literal["truck_hauling"] = "truck_hauling"
    calculator_version: str
    normalized_inputs: dict[str, str | int]
    options: list[TruckOptionPreview]
    review_flags: list[ReviewFlag] = Field(default_factory=list)
    warnings: list[ReviewFlag] = Field(default_factory=list)


class TruckHaulingApplyRequest(BaseModel):
    boq_id: UUID
    preview: TruckHaulingPreviewRequest
    selected_truck_type: str = Field(..., min_length=1)
    ordinal: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=5000)


class TruckHaulingApplyResponse(BaseModel):
    position_ids: list[UUID]
    calculator_run: dict[str, object]
    warnings: list[ReviewFlag] = Field(default_factory=list)
    skipped_candidates: list[str] = Field(default_factory=list)
    validation_status: Literal["applied"] = "applied"
