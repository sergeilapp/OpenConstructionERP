from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bedrock_calculators.calculators.truck_hauling import preview_truck_hauling
from app.modules.bedrock_calculators.schemas import (
    TruckHaulingApplyRequest,
    TruckHaulingPreviewRequest,
    TruckOptionInput,
)
from app.modules.bedrock_calculators.service import BedrockCalculatorService
from tests._pg import transactional_session


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with transactional_session(disable_fks=True) as s:
        yield s


def _bedrock_example_request() -> TruckHaulingPreviewRequest:
    return TruckHaulingPreviewRequest(
        material_quantity=Decimal("1956"),
        quantity_unit="CY",
        quarry_distance=Decimal("9"),
        billing_type="load",
        truck_cost_per_load=Decimal("395"),
        truck_cost_classification="haul_only",
        speed_mph=Decimal("60"),
        time_at_quarry_minutes=Decimal("66"),
        truck_options=[
            TruckOptionInput(
                kind="Single Axle",
                volume_capacity=Decimal("3"),
                weight_capacity=Decimal("5"),
            ),
            TruckOptionInput(
                kind="Dual Axle",
                volume_capacity=Decimal("13"),
                weight_capacity=Decimal("15"),
            ),
            TruckOptionInput(
                kind="Tri Axle",
                volume_capacity=Decimal("20"),
                weight_capacity=Decimal("22"),
            ),
        ],
    )


def test_preview_matches_bedrock_volume_example() -> None:
    response = preview_truck_hauling(_bedrock_example_request())

    by_type = {option.truck_type: option for option in response.options}

    assert by_type["Single Axle"].loads == 652
    assert by_type["Single Axle"].round_trip_distance_miles == "11736"
    assert by_type["Single Axle"].total_hours == "912.8"
    assert by_type["Single Axle"].truck_cost == "257540"

    assert by_type["Dual Axle"].loads == 151
    assert by_type["Dual Axle"].round_trip_distance_miles == "2718"
    assert by_type["Dual Axle"].total_hours == "211.4"
    assert by_type["Dual Axle"].truck_cost == "59645"

    assert by_type["Tri Axle"].loads == 98
    assert by_type["Tri Axle"].round_trip_distance_miles == "1764"
    assert by_type["Tri Axle"].total_hours == "137.2"
    assert by_type["Tri Axle"].truck_cost == "38710"


def test_weight_unit_uses_weight_capacity() -> None:
    response = preview_truck_hauling(
        TruckHaulingPreviewRequest(
            material_quantity=Decimal("31"),
            quantity_unit="ton",
            quarry_distance=Decimal("4"),
            billing_type="hour",
            truck_options=[
                TruckOptionInput(
                    kind="Tri Axle",
                    volume_capacity=Decimal("20"),
                    weight_capacity=Decimal("10"),
                    cost_per_hour=Decimal("125"),
                )
            ],
        )
    )

    option = response.options[0]
    assert option.truck_capacity == "10"
    assert option.truck_capacity_unit == "ton"
    assert option.loads == 4
    assert option.truck_cost == "66.67"


def test_mile_billing_includes_fuel_and_maintenance() -> None:
    response = preview_truck_hauling(
        TruckHaulingPreviewRequest(
            material_quantity=Decimal("40"),
            quantity_unit="CY",
            quarry_distance=Decimal("5"),
            billing_type="mile",
            fuel_cost_per_gallon=Decimal("4"),
            truck_options=[
                TruckOptionInput(
                    kind="Tri Axle",
                    volume_capacity=Decimal("20"),
                    cost_per_mile=Decimal("2"),
                    miles_per_gallon=Decimal("4"),
                )
            ],
        )
    )

    option = response.options[0]
    assert option.loads == 2
    assert option.round_trip_distance_miles == "20"
    assert option.truck_cost == "60"


def test_missing_load_cost_returns_review_flag_and_no_cost() -> None:
    request = _bedrock_example_request().model_copy(update={"truck_cost_per_load": None})

    response = preview_truck_hauling(request)

    assert any(flag.code == "TRUCK_COST_PER_LOAD_REQUIRED" for flag in response.review_flags)
    assert response.options[0].truck_cost is None
    assert response.options[0].total_cost is None


def test_load_billing_derives_material_load_cost_when_haul_load_cost_is_blank() -> None:
    request = _bedrock_example_request().model_copy(
        update={
            "material_quantity": Decimal("200"),
            "material_unit_cost": Decimal("50"),
            "quarry_distance": Decimal("14"),
            "truck_cost_per_load": None,
            "speed_mph": Decimal("45"),
            "time_at_quarry_minutes": Decimal("30"),
            "time_at_job_site_minutes": Decimal("15"),
            "driving_labor_rate": Decimal("95"),
            "driving_laborer_count": Decimal("1"),
        }
    )

    response = preview_truck_hauling(request)
    by_type = {option.truck_type: option for option in response.options}

    assert not any(flag.code == "TRUCK_COST_PER_LOAD_REQUIRED" for flag in response.review_flags)
    assert by_type["Single Axle"].material_cost == "10050"
    assert by_type["Dual Axle"].material_cost == "10400"
    assert by_type["Tri Axle"].material_cost == "10000"
    assert by_type["Tri Axle"].truck_cost == "0"
    assert by_type["Tri Axle"].driving_labor_cost == "1303.61"
    assert by_type["Tri Axle"].total_cost == "11303.61"


def test_zero_capacity_is_flagged_without_dividing_by_zero() -> None:
    response = preview_truck_hauling(
        TruckHaulingPreviewRequest(
            material_quantity=Decimal("10"),
            quantity_unit="CY",
            quarry_distance=Decimal("3"),
            billing_type="hour",
            truck_options=[
                TruckOptionInput(
                    kind="Custom",
                    volume_capacity=Decimal("0"),
                    cost_per_hour=Decimal("100"),
                )
            ],
        )
    )

    option = response.options[0]
    assert option.loads == 0
    assert option.truck_cost is None
    assert any(flag.code == "TRUCK_CAPACITY_MISSING" for flag in option.review_flags)


def test_driving_labor_is_added_when_supplied() -> None:
    request = _bedrock_example_request().model_copy(
        update={
            "truck_options": [TruckOptionInput(kind="Tri Axle", volume_capacity=Decimal("20"))],
            "driving_labor_rate": Decimal("30"),
            "driving_laborer_count": Decimal("1"),
        }
    )

    option = preview_truck_hauling(request).options[0]

    assert option.driving_labor_cost == "4116"
    assert option.total_cost == "42826"


def test_material_cost_is_added_when_supplied() -> None:
    request = _bedrock_example_request().model_copy(
        update={
            "material_name": "#57 stone",
            "material_unit_cost": Decimal("10"),
            "truck_options": [TruckOptionInput(kind="Tri Axle", volume_capacity=Decimal("20"))],
        }
    )

    option = preview_truck_hauling(request).options[0]

    assert option.material_cost == "19560"
    assert option.truck_cost == "38710"
    assert option.total_cost == "58270"


class _FakeBOQService:
    def __init__(self) -> None:
        self.created = None
        self.position_id = uuid.uuid4()

    async def add_position(self, data):
        self.created = data
        return SimpleNamespace(id=self.position_id)


@pytest.mark.asyncio
async def test_apply_selected_truck_creates_boq_position_payload() -> None:
    boq_id = uuid.uuid4()
    fake_boq = _FakeBOQService()
    service = BedrockCalculatorService(fake_boq)

    response = await service.apply_truck_hauling(
        TruckHaulingApplyRequest(
            boq_id=boq_id,
            preview=_bedrock_example_request(),
            selected_truck_type="Tri Axle",
            ordinal="BR-001",
        )
    )

    assert response.position_ids == [fake_boq.position_id]
    assert response.calculator_run["type"] == "truck_hauling"
    assert response.skipped_candidates == ["Single Axle", "Dual Axle"]

    created = fake_boq.created
    assert created.boq_id == boq_id
    assert created.ordinal == "BR-001"
    assert created.description == "Truck haul / delivery - Tri Axle"
    assert created.unit == "cy"
    assert created.quantity == 1956.0
    assert created.unit_rate == Decimal("19.79038854805725971370143149")
    assert created.source == "manual"
    assert created.metadata["calculator"]["type"] == "truck_hauling"
    assert created.metadata["calculator"]["selected_option"] == {"truck_type": "Tri Axle"}
    assert created.metadata["resources"] == [
        {
            "type": "equipment",
            "name": "Tri Axle truck hauling",
            "unit": "LOAD",
            "quantity": "0.050102",
            "unit_rate": "395",
            "total": "19.790389",
        }
    ]


@pytest.mark.asyncio
async def test_apply_adds_driving_labor_resource_when_supplied() -> None:
    fake_boq = _FakeBOQService()
    service = BedrockCalculatorService(fake_boq)
    preview = _bedrock_example_request().model_copy(
        update={
            "truck_options": [TruckOptionInput(kind="Tri Axle", volume_capacity=Decimal("20"))],
            "driving_labor_rate": Decimal("30"),
            "driving_laborer_count": Decimal("1"),
        }
    )

    await service.apply_truck_hauling(
        TruckHaulingApplyRequest(
            boq_id=uuid.uuid4(),
            preview=preview,
            selected_truck_type="Tri Axle",
        )
    )

    resources = fake_boq.created.metadata["resources"]
    assert resources[0]["total"] == "19.790389"
    assert resources[1] == {
        "type": "labor",
        "name": "Driving labor",
        "unit": "HR",
        "quantity": "0.070143",
        "unit_rate": "30",
        "total": "2.104294",
    }
    assert fake_boq.created.unit_rate == Decimal("21.89468302658486707566462168")


@pytest.mark.asyncio
async def test_apply_creates_material_equipment_and_labor_resources() -> None:
    fake_boq = _FakeBOQService()
    service = BedrockCalculatorService(fake_boq)
    preview = _bedrock_example_request().model_copy(
        update={
            "material_name": "#57 stone",
            "material_unit_cost": Decimal("10"),
            "truck_options": [TruckOptionInput(kind="Tri Axle", volume_capacity=Decimal("20"))],
            "driving_labor_rate": Decimal("30"),
            "driving_laborer_count": Decimal("1"),
        }
    )

    await service.apply_truck_hauling(
        TruckHaulingApplyRequest(
            boq_id=uuid.uuid4(),
            preview=preview,
            selected_truck_type="Tri Axle",
        )
    )

    assert fake_boq.created.unit_rate == Decimal("31.89468302658486707566462168")
    assert fake_boq.created.metadata["resources"] == [
        {
            "type": "material",
            "name": "#57 stone",
            "unit": "CY",
            "quantity": "1",
            "unit_rate": "10",
            "total": "10",
        },
        {
            "type": "equipment",
            "name": "Tri Axle truck hauling",
            "unit": "LOAD",
            "quantity": "0.050102",
            "unit_rate": "395",
            "total": "19.790389",
        },
        {
            "type": "labor",
            "name": "Driving labor",
            "unit": "HR",
            "quantity": "0.070143",
            "unit_rate": "30",
            "total": "2.104294",
        },
    ]


@pytest.mark.asyncio
async def test_apply_uses_full_load_material_quantity_when_derived_by_load() -> None:
    fake_boq = _FakeBOQService()
    service = BedrockCalculatorService(fake_boq)
    preview = _bedrock_example_request().model_copy(
        update={
            "material_quantity": Decimal("200"),
            "material_name": "#57 stone",
            "material_unit_cost": Decimal("50"),
            "truck_options": [TruckOptionInput(kind="Dual Axle", volume_capacity=Decimal("13"))],
            "truck_cost_per_load": None,
        }
    )

    await service.apply_truck_hauling(
        TruckHaulingApplyRequest(
            boq_id=uuid.uuid4(),
            preview=preview,
            selected_truck_type="Dual Axle",
        )
    )

    material = fake_boq.created.metadata["resources"][0]
    assert material["type"] == "material"
    assert material["quantity"] == "1.04"
    assert material["unit_rate"] == "50"
    assert material["total"] == "52"


@pytest.mark.asyncio
async def test_apply_rejects_missing_selected_option() -> None:
    service = BedrockCalculatorService(_FakeBOQService())

    with pytest.raises(HTTPException) as exc:
        await service.apply_truck_hauling(
            TruckHaulingApplyRequest(
                boq_id=uuid.uuid4(),
                preview=_bedrock_example_request(),
                selected_truck_type="Quad Axle",
            )
        )

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_apply_rejects_blocking_review_flags() -> None:
    service = BedrockCalculatorService(_FakeBOQService())
    preview = _bedrock_example_request().model_copy(update={"truck_cost_per_load": None})

    with pytest.raises(HTTPException) as exc:
        await service.apply_truck_hauling(
            TruckHaulingApplyRequest(
                boq_id=uuid.uuid4(),
                preview=preview,
                selected_truck_type="Tri Axle",
            )
        )

    assert exc.value.status_code == 422
    assert exc.value.detail["review_flags"][0]["code"] == "TRUCK_COST_PER_LOAD_REQUIRED"


@pytest.mark.asyncio
async def test_apply_creates_real_boq_position_with_calculator_metadata(session: AsyncSession) -> None:
    from app.modules.boq.models import Position
    from app.modules.boq.schemas import BOQCreate
    from app.modules.boq.service import BOQService
    from app.modules.projects.models import Project

    project = Project(
        name=f"Bedrock Truck {uuid.uuid4().hex[:6]}",
        owner_id=uuid.uuid4(),
        currency="USD",
        region="BEDROCK-REVIEW",
    )
    session.add(project)
    await session.flush()

    boq_service = BOQService(session)
    boq = await boq_service.create_boq(BOQCreate(project_id=project.id, name="Bedrock Truck BOQ"))
    response = await BedrockCalculatorService(boq_service).apply_truck_hauling(
        TruckHaulingApplyRequest(
            boq_id=boq.id,
            preview=_bedrock_example_request(),
            selected_truck_type="Tri Axle",
            ordinal="BR-TRUCK-001",
        )
    )

    position = await session.get(Position, response.position_ids[0])
    assert position is not None
    assert position.boq_id == boq.id
    assert position.ordinal == "BR-TRUCK-001"
    assert position.description == "Truck haul / delivery - Tri Axle"
    assert position.unit == "cy"
    assert position.quantity == "1956.0000"
    assert position.unit_rate == "19.7904"
    assert position.total == "38710.0000"
    assert position.source == "manual"

    metadata = position.metadata_
    assert metadata["calculator"]["type"] == "truck_hauling"
    assert metadata["calculator"]["status"] == "generated"
    assert metadata["calculator"]["selected_option"] == {"truck_type": "Tri Axle"}
    assert metadata["calculator"]["outputs"]["loads"] == 98
    assert metadata["resources"][0]["name"] == "Tri Axle truck hauling"
    assert metadata["resource_breakdown"]["equipment"]["total"] == 19.790389


@pytest.mark.asyncio
async def test_apply_persists_material_equipment_labor_breakdown(session: AsyncSession) -> None:
    from app.modules.boq.models import Position
    from app.modules.boq.schemas import BOQCreate
    from app.modules.boq.service import BOQService
    from app.modules.projects.models import Project

    project = Project(
        name=f"Bedrock MEL {uuid.uuid4().hex[:6]}",
        owner_id=uuid.uuid4(),
        currency="USD",
        region="BEDROCK-REVIEW",
    )
    session.add(project)
    await session.flush()

    boq_service = BOQService(session)
    boq = await boq_service.create_boq(BOQCreate(project_id=project.id, name="Bedrock MEL BOQ"))
    preview = _bedrock_example_request().model_copy(
        update={
            "material_name": "#57 stone",
            "material_unit_cost": Decimal("10"),
            "truck_options": [TruckOptionInput(kind="Tri Axle", volume_capacity=Decimal("20"))],
            "driving_labor_rate": Decimal("30"),
            "driving_laborer_count": Decimal("1"),
        }
    )

    response = await BedrockCalculatorService(boq_service).apply_truck_hauling(
        TruckHaulingApplyRequest(
            boq_id=boq.id,
            preview=preview,
            selected_truck_type="Tri Axle",
            ordinal="BR-MEL-001",
        )
    )

    position = await session.get(Position, response.position_ids[0])
    assert position is not None
    assert position.unit == "cy"
    assert position.quantity == "1956.0000"
    assert position.unit_rate == "31.8947"
    assert position.total == "62386.0000"
    breakdown = position.metadata_["resource_breakdown"]
    assert breakdown["material"]["total"] == 10.0
    assert breakdown["equipment"]["total"] == 19.790389
    assert breakdown["labor"]["total"] == 2.104294
