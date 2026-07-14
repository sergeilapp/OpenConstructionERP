"""Pure Truck / Hauling calculator preview logic."""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from app.modules.bedrock_calculators.schemas import (
    FormulaTraceStep,
    ReviewFlag,
    TruckHaulingPreviewRequest,
    TruckHaulingPreviewResponse,
    TruckOptionInput,
    TruckOptionPreview,
)

CALCULATOR_VERSION = "2026-07-14.1"
_MONEY = Decimal("0.01")
_HOURS = Decimal("0.01")
_DISTANCE = Decimal("0.01")


def preview_truck_hauling(data: TruckHaulingPreviewRequest) -> TruckHaulingPreviewResponse:
    """Calculate the Bedrock truck comparison grid without database writes."""

    request_flags = _request_review_flags(data)
    options = [_calculate_option(data, option) for option in data.truck_options]
    warnings = [flag for flag in request_flags if flag.severity != "error"]
    return TruckHaulingPreviewResponse(
        calculator_version=CALCULATOR_VERSION,
        normalized_inputs={
            "material_quantity": _format_decimal(data.material_quantity),
            "quantity_unit": data.quantity_unit,
            "material_name": data.material_name,
            "material_unit_cost": _format_decimal(data.material_unit_cost or Decimal("0")),
            "quarry_distance": _format_decimal(data.quarry_distance),
            "billing_type": data.billing_type,
            "speed_mph": _format_decimal(data.speed_mph),
            "time_at_quarry_minutes": _format_decimal(data.time_at_quarry_minutes),
            "time_at_job_site_minutes": _format_decimal(data.time_at_job_site_minutes),
            "truck_option_count": len(data.truck_options),
        },
        options=options,
        review_flags=request_flags,
        warnings=warnings,
    )


def _calculate_option(data: TruckHaulingPreviewRequest, option: TruckOptionInput) -> TruckOptionPreview:
    flags = _option_review_flags(data, option)
    capacity, capacity_unit = _capacity_for_unit(data, option)

    loads = 0
    if capacity is not None and capacity > 0 and data.material_quantity > 0:
        loads = int((data.material_quantity / capacity).to_integral_value(rounding=ROUND_CEILING))

    distance = data.quarry_distance * Decimal(loads) * Decimal("2")
    handling_hours_per_load = (data.time_at_quarry_minutes / Decimal("60")) + (
        data.time_at_job_site_minutes / Decimal("60")
    )
    total_hours = (distance / data.speed_mph) + (Decimal(loads) * handling_hours_per_load)

    truck_cost = _truck_cost(data, option, loads, distance, total_hours, flags)
    driving_labor_cost = _driving_labor_cost(data, total_hours)
    material_cost = _material_cost(data, capacity, loads)
    total_cost = None if truck_cost is None else truck_cost + (driving_labor_cost or Decimal("0")) + material_cost
    unit_cost = None
    if total_cost is not None and data.material_quantity > 0:
        unit_cost = total_cost / data.material_quantity

    return TruckOptionPreview(
        truck_type=option.kind,
        truck_capacity=_format_decimal(capacity) if capacity is not None else None,
        truck_capacity_unit=capacity_unit,
        loads=loads,
        round_trip_distance_miles=_format_decimal(distance.quantize(_DISTANCE)),
        total_hours=_format_decimal(total_hours.quantize(_HOURS, rounding=ROUND_HALF_UP)),
        truck_cost=_format_money(truck_cost),
        driving_labor_cost=_format_money(driving_labor_cost),
        material_cost=_format_money(material_cost),
        total_cost=_format_money(total_cost),
        unit_cost=_format_money(unit_cost),
        billing_type=data.billing_type,
        cost_method=_cost_method(data.billing_type),
        warnings=[flag for flag in flags if flag.severity != "error"],
        review_flags=flags,
        formula_trace=[
            FormulaTraceStep(
                name="loads",
                formula="ceil(material_quantity / truck_capacity)",
                value=loads,
            ),
            FormulaTraceStep(
                name="round_trip_distance",
                formula="quarry_distance * loads * 2",
                value=_format_decimal(distance),
            ),
            FormulaTraceStep(
                name="handling_hours_per_load",
                formula="time_at_quarry / 60 + time_at_job_site / 60",
                value=_format_decimal(handling_hours_per_load),
            ),
            FormulaTraceStep(
                name="total_hours",
                formula="round_trip_distance / speed_mph + loads * handling_hours_per_load",
                value=_format_decimal(total_hours),
            ),
        ],
    )


def _truck_cost(
    data: TruckHaulingPreviewRequest,
    option: TruckOptionInput,
    loads: int,
    distance: Decimal,
    total_hours: Decimal,
    flags: list[ReviewFlag],
) -> Decimal | None:
    if any(flag.severity == "error" for flag in flags):
        return None
    if data.billing_type == "hour":
        if option.cost_per_hour is None:
            return None
        return (total_hours * option.cost_per_hour).quantize(_MONEY, rounding=ROUND_HALF_UP)
    if data.billing_type == "mile":
        if option.cost_per_mile is None or option.miles_per_gallon is None or data.fuel_cost_per_gallon is None:
            return None
        fuel_total = (data.fuel_cost_per_gallon / option.miles_per_gallon) * distance
        maintenance_total = option.cost_per_mile * distance
        return (fuel_total + maintenance_total).quantize(_MONEY, rounding=ROUND_HALF_UP)
    if data.truck_cost_per_load is None:
        return Decimal("0") if data.material_unit_cost is not None else None
    return (data.truck_cost_per_load * Decimal(loads)).quantize(_MONEY, rounding=ROUND_HALF_UP)


def _driving_labor_cost(data: TruckHaulingPreviewRequest, total_hours: Decimal) -> Decimal | None:
    if data.driving_labor_rate is None or data.driving_laborer_count == 0:
        return None
    return (total_hours * data.driving_labor_rate * data.driving_laborer_count).quantize(
        _MONEY,
        rounding=ROUND_HALF_UP,
    )


def _material_cost(data: TruckHaulingPreviewRequest, capacity: Decimal | None, loads: int) -> Decimal:
    if data.material_unit_cost is None:
        return Decimal("0")
    if data.billing_type == "load" and data.truck_cost_per_load is None and capacity is not None and capacity > 0:
        return (capacity * Decimal(loads) * data.material_unit_cost).quantize(_MONEY, rounding=ROUND_HALF_UP)
    return (data.material_quantity * data.material_unit_cost).quantize(_MONEY, rounding=ROUND_HALF_UP)


def _capacity_for_unit(
    data: TruckHaulingPreviewRequest,
    option: TruckOptionInput,
) -> tuple[Decimal | None, str | None]:
    if data.quantity_unit == "ton":
        return option.weight_capacity, "ton"
    if data.quantity_unit == "load":
        return Decimal("1"), "load"
    return option.volume_capacity, "CY"


def _request_review_flags(data: TruckHaulingPreviewRequest) -> list[ReviewFlag]:
    flags: list[ReviewFlag] = []
    if data.billing_type == "load" and data.truck_cost_per_load is None and data.material_unit_cost is None:
        flags.append(
            ReviewFlag(
                code="TRUCK_COST_PER_LOAD_REQUIRED",
                severity="error",
                message="Cost per load or material unit cost is required when billing by load.",
                requires_resolution=True,
            )
        )
    if data.billing_type == "load" and data.truck_cost_classification == "unknown":
        flags.append(
            ReviewFlag(
                code="DELIVERED_PRICE_AMBIGUOUS",
                severity="warning",
                message=(
                    "Classify the per-load price as haul-only, delivered material, "
                    "or subcontracted hauling before applying."
                ),
                requires_resolution=True,
            )
        )
    if data.quarry_distance == 0 and data.material_quantity > 0:
        flags.append(
            ReviewFlag(
                code="ZERO_DISTANCE_WITH_LOADS",
                severity="warning",
                message="Material quantity is nonzero but quarry distance is zero.",
                requires_resolution=False,
            )
        )
    return flags


def _option_review_flags(data: TruckHaulingPreviewRequest, option: TruckOptionInput) -> list[ReviewFlag]:
    flags = list(_request_review_flags(data))
    capacity, capacity_unit = _capacity_for_unit(data, option)
    if capacity is None or capacity <= 0:
        flags.append(
            ReviewFlag(
                code="TRUCK_CAPACITY_MISSING",
                severity="error",
                message=f"{option.kind} is missing a positive {capacity_unit or data.quantity_unit} capacity.",
                requires_resolution=True,
            )
        )
    if data.billing_type == "hour" and option.cost_per_hour is None:
        flags.append(
            ReviewFlag(
                code="TRUCK_COST_PER_HOUR_REQUIRED",
                severity="error",
                message=f"{option.kind} is missing cost per hour for hourly billing.",
                requires_resolution=True,
            )
        )
    if data.billing_type == "mile":
        if data.fuel_cost_per_gallon is None:
            flags.append(
                ReviewFlag(
                    code="FUEL_COST_PER_GALLON_REQUIRED",
                    severity="error",
                    message="Fuel cost per gallon is required when billing by mile.",
                    requires_resolution=True,
                )
            )
        if option.cost_per_mile is None:
            flags.append(
                ReviewFlag(
                    code="TRUCK_COST_PER_MILE_REQUIRED",
                    severity="error",
                    message=f"{option.kind} is missing maintenance cost per mile for mileage billing.",
                    requires_resolution=True,
                )
            )
        if option.miles_per_gallon is None:
            flags.append(
                ReviewFlag(
                    code="TRUCK_MPG_REQUIRED",
                    severity="error",
                    message=f"{option.kind} is missing miles per gallon for mileage billing.",
                    requires_resolution=True,
                )
            )
    return flags


def _cost_method(billing_type: str) -> str:
    if billing_type == "hour":
        return "total_hours * truck_cost_per_hour"
    if billing_type == "mile":
        return "fuel_cost_per_mile * round_trip_distance + maintenance_cost_per_mile * round_trip_distance"
    return "truck_cost_per_load * loads"


def _format_money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return _format_decimal(value.quantize(_MONEY, rounding=ROUND_HALF_UP))


def _format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")
