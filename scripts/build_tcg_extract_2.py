#!/usr/bin/env python3
"""Build extract 2 TCG import package with unitized CostItems.

Extends the v4 POC (15 CostItems) with 7 new unit-priced CostItems
derived from the LS-to-unitized decomposition review.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parents[1] / "bedrock_tcg_model_job_extract_2"
SOURCE = "bedrock_tcg_model_job_extract_2"
REGION = "BEDROCK-TCG-EXTRACT-2"
CURRENCY = "USD"


def money(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def qty(value: float | Decimal, places: str = "0.00001") -> float:
    return float(Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP))


def resource(
    code: str,
    name: str,
    resource_type: str,
    category: str,
    unit: str,
    base_price: float,
    masterformat: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "resource_code": code,
        "name": name,
        "resource_type": resource_type,
        "category": category,
        "unit": unit,
        "base_price": base_price,
        "min_price": 0,
        "max_price": 0,
        "currency": CURRENCY,
        "source": SOURCE,
        "region": REGION,
        "specifications": {"masterformat": masterformat},
        "metadata": {"review_only": True, **(metadata or {})},
    }


def comp(code: str, name: str, typ: str, quantity: float, unit_rate: float, unit: str) -> dict[str, Any]:
    return {
        "code": code,
        "resource_code": code,
        "name": name,
        "type": typ,
        "resource_type": typ,
        "quantity": quantity,
        "unit_rate": unit_rate,
        "cost": money(Decimal(str(quantity)) * Decimal(str(unit_rate))),
        "unit": unit,
    }


def cost_item(
    code: str,
    description: str,
    unit: str,
    classification: dict[str, str],
    components: list[dict[str, Any]],
    tags: list[str],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rate = money(sum(Decimal(str(c["cost"])) for c in components))
    return {
        "code": code,
        "description": description,
        "descriptions": {},
        "unit": unit,
        "rate": rate,
        "currency": CURRENCY,
        "source": SOURCE,
        "region": REGION,
        "classification": classification,
        "components": components,
        "tags": ["tcg_extract_2", "review_only", *tags],
        "metadata": {"review_only": True, **(metadata or {})},
    }


def asm_component(
    code: str,
    description: str,
    quantity: float,
    unit: str,
    unit_cost: float,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "cost_item_code": code,
        "description": description,
        "factor": 1.0,
        "quantity": quantity,
        "unit": unit,
        "unit_cost": unit_cost,
        "resource_type": None,
        "total": money(Decimal(str(quantity)) * Decimal(str(unit_cost))),
        "metadata": {"component_source": "cost_item", **(metadata or {})},
    }


def assembly(
    code: str,
    name: str,
    description: str,
    category: str,
    classification: dict[str, str],
    components: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total = money(sum(Decimal(str(c["total"])) for c in components))
    return {
        "code": code,
        "name": name,
        "description": description,
        "unit": "LS",
        "category": category,
        "classification": classification,
        "total_rate": total,
        "currency": CURRENCY,
        "bid_factor": 1.0,
        "regional_factors": {},
        "is_template": True,
        "tags": ["tcg_extract_2", "review_only", "assembly"],
        "components": components,
        "metadata": {"source": SOURCE, "region": REGION, "review_only": True, **(metadata or {})},
    }


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    catalog = [
        resource("TCG-RES-LABOR-SITE-PREP-135HR", "TCG Site Preparation Labor Crew", "labor", "Labor", "HR", 135.0, "31 00 00", {"source_evidence": "tcg_rate_card.md"}),
        resource("TCG-RES-LABOR-ADHOC-125HR", "TCG Adhoc Labor Crew", "labor", "Labor", "HR", 125.0, "03 00 00", {"review_flag": "TCG-P7-R7"}),
        resource("TCG-RES-DRIVING-LABOR-95HR", "TCG Driving Labor", "labor", "Labor", "HR", 95.0, "01 50 00", {"source_evidence": "tcg_rate_card.md"}),
        resource("TCG-RES-57-STONE-TON", "TCG #57 Stone Material", "material", "Aggregate", "t", 38.0, "31 00 00", {"review_flag": "TCG-P7-R5", "rate_basis": "Draft proxy from drain-stone quarry rate"}),
        resource("TCG-RES-DRAIN-STONE-TON", "TCG Ballast Drain Stone Material", "material", "Aggregate", "t", 38.0, "02 00 00", {"review_flag": "TCG-P7-R2", "rate_basis": "Reviewed quarry-rate draft basis"}),
        resource("TCG-RES-SAND-CY", "TCG Sand Material", "material", "Aggregate", "CY", 25.0, "33 00 00", {"review_flag": "TCG-P7-R6"}),
        resource("TCG-RES-HAUL-57-STONE-FD-LOAD", "TCG Haul #57 Stone for French Drain", "equipment", "Hauling", "LOAD", 945.0, "33 00 00", {"source_evidence": "SitePreparationMaterial 3016"}),
        resource("TCG-RES-HAUL-SAND-FD-LOAD", "TCG Haul Sand for French Drain", "equipment", "Hauling", "LOAD", 745.0, "33 00 00", {"source_evidence": "SitePreparationMaterial 3015"}),
        resource("TCG-RES-HAUL-DRAIN-STONE-LOAD", "TCG Haul Drain Stone", "equipment", "Hauling", "LOAD", 985.0, "02 00 00", {"source_evidence": "SitePreparationMaterial 3207"}),
        resource("TCG-RES-HAUL-57-STONE-CF-LOAD", "TCG Haul #57 Stone for Crawlspace Footer", "equipment", "Hauling", "LOAD", 985.0, "31 00 00", {"source_evidence": "SitePreparationMaterial 3110/3111"}),
        resource("TCG-RES-FILL-DELIVERED-CY", "TCG Delivered Fill Material Review Rate", "material", "Fill", "CY", 6.5, "31 00 00", {"review_flag": "TCG-P7-R3", "rate_basis": "Draft derived fill material rate"}),
        resource("TCG-RES-HAUL-FILL-LOAD", "TCG Fill Hauling Load", "equipment", "Hauling", "LOAD", 395.0, "31 00 00", {"review_flag": "TCG-P7-R3", "source_evidence": "job 38254 fill hauling"}),
        resource("TCG-RES-FABRIC-ROLL", "TCG Geotextile Fabric Roll", "material", "Drainage", "ROLL", 200.0, "33 00 00", {"source_evidence": "job 38396 fabric"}),
        resource("TCG-RES-OBS-WELL-PIPE-LS", "TCG Observation Well Pipe Allowance", "material", "Drainage", "LS", 1100.0, "33 00 00", {"source_evidence": "job 38396 pipe for observation wells"}),
        resource("TCG-RES-STORM-EQUIP-RENTAL-LS", "TCG Stormwater Equipment Rental Allowance", "equipment", "Rental", "LS", 2000.0, "33 00 00", {"team_review_item": "Identify equipment type"}),
        resource("TCG-RES-UTILITY-PIPE-4IN-LS", "TCG 4in Schedule 40 Pipe and Fittings Allowance", "material", "Utilities", "LS", 12000.0, "33 00 00"),
        resource("TCG-RES-UTILITY-PIPE-4IN-FT", "TCG 4in Schedule 40 Pipe per Foot", "material", "Utilities", "FT", money(12000.0 / 1900), "33 00 00", {"source_evidence": "job 38522: $12,000 / 1,900 ft = $6.32/ft"}),
        resource("TCG-RES-UTILITY-CONDUIT-3IN-LS", "TCG 3in Schedule 40 Electrical Conduit Allowance", "material", "Utilities", "LS", 4000.0, "33 00 00"),
        resource("TCG-RES-UTILITY-CONDUIT-3IN-FT", "TCG 3in Schedule 40 Electrical Conduit per Foot", "material", "Utilities", "FT", money(4000.0 / 900), "33 00 00", {"source_evidence": "job 38522: $4,000 / 900 ft = $4.44/ft"}),
        resource("TCG-RES-UTILITY-CONDUIT-1-5IN-LS", "TCG 1.5in Conduit Allowance", "material", "Utilities", "LS", 2500.0, "33 00 00"),
        resource("TCG-RES-UTILITY-CONDUIT-1-5IN-FT", "TCG 1.5in Conduit per Foot", "material", "Utilities", "FT", money(2500.0 / 900), "33 00 00", {"source_evidence": "job 38522: $2,500 / 900 ft = $2.78/ft"}),
        resource("TCG-RES-SCREENINGS-LOAD", "TCG Screenings Backfill Load", "material", "Backfill", "LOAD", 1050.0, "33 00 00"),
        resource("TCG-RES-UTILITY-MATERIAL-ALLOWANCE-LS", "TCG Utility Additional Materials Allowance", "material", "Utilities", "LS", 6500.0, "33 00 00", {"team_review_item": "Identify exact material meaning"}),
        resource("TCG-RES-UTILITY-EQUIP-ALLOWANCE-LS", "TCG Utility Equipment Allowance", "equipment", "Utilities", "LS", 2500.0, "33 00 00", {"team_review_item": "Identify machine type"}),
        resource("TCG-RES-DRIVING-EQUIP-MI", "TCG Driving Equipment Cost", "equipment", "Driving", "MI", 4.375, "01 50 00"),
        resource("TCG-RES-DRIVING-EQUIP-45MI", "TCG Driving Equipment Cost 4.50/mi", "equipment", "Driving", "MI", 4.5, "01 50 00"),
        resource("TCG-RES-CONCRETE-CY", "TCG Concrete Material", "material", "Concrete", "CY", money(3800 / 15), "03 00 00", {"source_evidence": "job 38447 15 CY concrete $3800"}),
        resource("TCG-RES-2A-STONE-LOAD", "TCG 2A Stone Load", "material", "Aggregate", "LOAD", 800.0, "31 00 00", {"source_evidence": "job 38447 one load 2A stone"}),
        resource("TCG-RES-PAVING-SUB-LS", "TCG Paving Subcontractor Allowance", "subcontractor", "Subcontractor", "LS", 9800.0, "32 00 00"),
        resource("TCG-RES-ASPHALT-REPAIR-SUB-LS", "TCG Asphalt Utility Trench Repair Subcontractor Allowance", "subcontractor", "Subcontractor", "LS", 1500.0, "32 00 00"),
        resource("TCG-RES-CORRUGATED-PIPE-4IN-LS", "TCG 4in Corrugated Perforated Pipe Allowance", "material", "Drainage", "LS", 2320.98, "33 00 00"),
        resource("TCG-RES-CORRUGATED-PIPE-4IN-FT", "TCG 4in Corrugated Perforated Pipe per Foot", "material", "Drainage", "FT", money(2320.98 / 1000), "33 00 00", {"source_evidence": "job 38577: $2,320.98 / 1,000 ft = $2.32/ft"}),
        resource("TCG-RES-DEMO-EQUIP-ALLOWANCE-LS", "TCG Demo Equipment Allowance", "equipment", "Demolition", "LS", 17450.0, "02 00 00", {"review_flag": "TCG-RS-R1"}),
        resource("TCG-RES-EROSION-SUB-LS", "TCG Erosion Control Sub Crew", "subcontractor", "Erosion", "LS", 4000.0, "31 00 00"),
        resource("TCG-RES-EROSION-SUB-LF", "TCG Erosion Control Sub Crew per LF", "subcontractor", "Erosion", "LF", money(4000.0 / 440), "31 00 00", {"rate_basis": "$4,000 ÷ 440 LF"}),
        resource("TCG-RES-SILT-MATTING-LS", "TCG Silt Fence, Posts, Wire Mesh, and Matting", "material", "Erosion", "LS", 4000.0, "31 00 00"),
        resource("TCG-RES-ORANGE-FENCE-LS", "TCG Orange Construction Fence", "material", "Erosion", "LS", 2000.0, "31 00 00"),
        resource("TCG-RES-GEOTEXTILE-ALLOWANCE-LS", "TCG Geotextile/Fabric Allowance", "material", "Erosion", "LS", 600.0, "31 00 00"),
        resource("TCG-RES-STRAW-STABILIZATION-LS", "TCG Straw Stabilization", "material", "Erosion", "LS", 3200.0, "31 00 00"),
        resource("TCG-RES-EROSION-EQUIP-RENTAL-LS", "TCG Erosion Equipment Rental Allowance", "equipment", "Rental", "LS", 3000.0, "31 00 00"),
        resource("TCG-RES-EROSION-EQUIP-LF", "TCG Erosion Equipment Rental per LF", "equipment", "Rental", "LF", money(3000.0 / 440), "31 00 00", {"rate_basis": "$3,000 ÷ 440 LF"}),
        resource("TCG-RES-MATERIAL-GATHERING-LABOR-LS", "TCG Material Gathering Labor Allowance", "labor", "Labor", "LS", 2000.0, "03 00 00", {"source_evidence": "AdhocJobCalculator material_gathering_labor_cost"}),
    ]

    cls = {
        "storm": {"masterformat": "33 00 00", "collection": "Stormwater", "category": "Sitework", "department": "Utilities", "section": "French Drain"},
        "utility": {"masterformat": "33 00 00", "collection": "Utilities", "category": "Sitework", "department": "Utilities", "section": "Utility Trenching"},
        "earth": {"masterformat": "31 00 00", "collection": "Earthwork", "category": "Sitework", "department": "Earthwork", "section": "General Earthwork"},
        "demo": {"masterformat": "02 00 00", "collection": "Existing Conditions", "category": "Sitework", "department": "Demo", "section": "Demolition"},
        "conc": {"masterformat": "03 00 00", "collection": "Concrete", "category": "Sitework", "department": "Concrete", "section": "Curb"},
        "pave": {"masterformat": "32 00 00", "collection": "Exterior Improvements", "category": "Sitework", "department": "Paving", "section": "Asphalt"},
        "erosion": {"masterformat": "31 00 00", "collection": "Earthwork", "category": "Sitework", "department": "Earthwork", "section": "Erosion Control"},
    }

    # -- carried-forward v4 items (15) --
    costs = [
        cost_item("TCG-DELIVER-57-STONE-FD", "Deliver #57 stone for French drain", "t", cls["storm"], [comp("TCG-RES-57-STONE-TON", "#57 stone material", "material", 1.0, 38.0, "t"), comp("TCG-RES-HAUL-57-STONE-FD-LOAD", "#57 stone bundled hauling", "equipment", qty(38 / 863.8), 945.0, "LOAD")], ["deliver"], {"source_job_id": 38396}),
        cost_item("TCG-DELIVER-SAND-FD", "Deliver sand for French drain", "CY", cls["storm"], [comp("TCG-RES-SAND-CY", "Sand material", "material", 1.0, 25.0, "CY"), comp("TCG-RES-HAUL-SAND-FD-LOAD", "Sand bundled hauling", "equipment", qty(4 / 78), 745.0, "LOAD")], ["deliver"], {"source_job_id": 38396}),
        cost_item("TCG-DELIVER-DRAIN-STONE-CE", "Deliver drain stone for construction entrance", "t", cls["demo"], [comp("TCG-RES-DRAIN-STONE-TON", "Drain stone material", "material", 1.0, 38.0, "t"), comp("TCG-RES-HAUL-DRAIN-STONE-LOAD", "Drain stone bundled hauling", "equipment", qty(4 / 92), 985.0, "LOAD")], ["deliver"], {"source_job_id": 38304}),
        cost_item("TCG-DELIVER-57-STONE-CF", "Deliver #57 stone for crawlspace/footer drainage", "t", cls["earth"], [comp("TCG-RES-57-STONE-TON", "#57 stone material", "material", 1.0, 38.0, "t"), comp("TCG-RES-HAUL-57-STONE-CF-LOAD", "#57 stone crawlspace hauling", "equipment", qty(12 / 257.2), 985.0, "LOAD")], ["deliver"], {"source_job_id": 38577}),
        cost_item("TCG-DELIVER-FILL-REVIEW", "Delivered fill material and hauling review item", "CY", cls["earth"], [comp("TCG-RES-FILL-DELIVERED-CY", "Delivered fill material review rate", "material", 1.0, 6.5, "CY"), comp("TCG-RES-HAUL-FILL-LOAD", "Fill hauling", "equipment", qty(98 / 1955), 395.0, "LOAD")], ["deliver", "review"], {"source_job_id": 38254, "review_flag": "TCG-P7-R3"}),
        cost_item("TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE", "Stormwater filtration fabric, observation pipe, equipment, and specialty labor", "LS", cls["storm"], [comp("TCG-RES-FABRIC-ROLL", "Geotextile fabric", "material", 12.0, 200.0, "ROLL"), comp("TCG-RES-OBS-WELL-PIPE-LS", "Pipe for observation wells", "material", 1.0, 1100.0, "LS"), comp("TCG-RES-STORM-EQUIP-RENTAL-LS", "Stormwater equipment rental", "equipment", 1.0, 2000.0, "LS"), comp("TCG-RES-LABOR-SITE-PREP-135HR", "Stormwater specialty labor", "labor", 20.0, 135.0, "HR")], ["scope"], {"source_job_id": 38396}),
        cost_item("TCG-SITE-PREP-DEMO-DISPOSAL-SCOPE", "Site prep demolition, tree removal, and disposal review scope", "LS", cls["demo"], [comp("TCG-RES-DEMO-EQUIP-ALLOWANCE-LS", "Demo equipment allowance", "equipment", 1.0, 17450.0, "LS"), comp("TCG-RES-LABOR-SITE-PREP-135HR", "Demo/disposal labor", "labor", 48.0, 135.0, "HR"), comp("TCG-RES-DRIVING-EQUIP-MI", "Demo driving equipment", "equipment", 168.0, 4.375, "MI")], ["scope"], {"source_job_id": 38304, "review_flag": "TCG-RS-R1"}),
        cost_item("TCG-PAVING-ASPHALT-REPAIR-SUBCONTRACT-SCOPE", "Subcontracted paving and asphalt utility trench repair", "LS", cls["pave"], [comp("TCG-RES-PAVING-SUB-LS", "Paving sub crew", "subcontractor", 1.0, 9800.0, "LS"), comp("TCG-RES-ASPHALT-REPAIR-SUB-LS", "Asphalt utility trench repair sub crew", "subcontractor", 1.0, 1500.0, "LS")], ["scope", "subcontractor"], {"source_job_id": 38447}),
        cost_item("TCG-PLACE-COMPACT-FILL-REVIEW", "Place and compact imported fill (LS review scope)", "LS", cls["earth"], [comp("TCG-RES-LABOR-SITE-PREP-135HR", "Fill placement labor", "labor", 188.0, 135.0, "HR")], ["place", "review"], {"source_job_id": 38254, "equipment_rate_missing": True}),
        cost_item("TCG-PLACE-TOPSOIL-REVIEW", "Place stockpiled topsoil (LS review scope)", "LS", cls["earth"], [comp("TCG-RES-LABOR-SITE-PREP-135HR", "Topsoil placement labor", "labor", 78.0, 135.0, "HR")], ["place", "review"], {"source_job_id": 38578}),
    ]

    # -- new unitized items (7) --
    unitized = [
        cost_item("TCG-CONCRETE-CURB-GUTTER-UNIT", "Concrete curb and gutter per linear foot", "LF", cls["conc"], [
            comp("TCG-RES-CONCRETE-CY", "Concrete material", "material", 0.200, money(3800 / 15), "CY"),
            comp("TCG-RES-2A-STONE-LOAD", "2A stone", "material", qty(1 / 75), 800.0, "LOAD"),
            comp("TCG-RES-LABOR-ADHOC-125HR", "Adhoc concrete labor (includes material gathering)", "labor", qty(58 / 75), 125.0, "HR"),
            comp("TCG-RES-DRIVING-EQUIP-MI", "Driving equipment", "equipment", qty(84 / 75), 4.375, "MI"),
            comp("TCG-RES-DRIVING-LABOR-95HR", "Driving labor", "labor", qty(3.74 / 75), 95.0, "HR"),
        ], ["unitized", "concrete"], {"source_job_id": 38447, "review_flag": "TCG-P7-R7", "allocation_note": "58 HR = 42 working HR + 16 material-gathering HR"}),
        cost_item("TCG-CRAWLSPACE-FOOTER-EXCAVATION-UNIT", "Crawlspace/footer excavation and drainage per linear foot", "LF", cls["earth"], [
            comp("TCG-RES-CORRUGATED-PIPE-4IN-FT", "4in corrugated perforated pipe", "material", 1.0, money(2320.98 / 1000), "FT"),
            comp("TCG-RES-LABOR-SITE-PREP-135HR", "Crawlspace/footer labor", "labor", qty(114 / 1000), 135.0, "HR"),
            comp("TCG-RES-DRIVING-EQUIP-45MI", "Driving equipment", "equipment", qty(336 / 1000), 4.5, "MI"),
            comp("TCG-RES-DRIVING-LABOR-95HR", "Driving labor", "labor", qty(12.25 / 1000), 95.0, "HR"),
        ], ["unitized", "earthwork", "drainage"], {"source_job_id": 38577}),
        cost_item("TCG-UTILITY-TRENCHING-CONDUIT-UNIT", "Utility trenching, conduit/pipe installation per linear foot of trench", "LF", cls["utility"], [
            comp("TCG-RES-UTILITY-PIPE-4IN-FT", "4in schedule 40 pipe", "material", qty(1900 / 1300), money(12000.0 / 1900), "FT"),
            comp("TCG-RES-UTILITY-CONDUIT-3IN-FT", "3in electrical conduit", "material", qty(900 / 1300), money(4000.0 / 900), "FT"),
            comp("TCG-RES-UTILITY-CONDUIT-1-5IN-FT", "1.5in conduit", "material", qty(900 / 1300), money(2500.0 / 900), "FT"),
            comp("TCG-RES-SCREENINGS-LOAD", "Screenings backfill", "material", qty(8 / 1300), 1050.0, "LOAD"),
            comp("TCG-RES-UTILITY-MATERIAL-ALLOWANCE-LS", "Additional utility materials", "material", qty(1 / 1300), 6500.0, "LS"),
            comp("TCG-RES-UTILITY-EQUIP-ALLOWANCE-LS", "Utility equipment allowance", "equipment", qty(1 / 1300), 2500.0, "LS"),
            comp("TCG-RES-DRIVING-EQUIP-MI", "Driving equipment", "equipment", qty(336 / 1300), 4.375, "MI"),
            comp("TCG-RES-LABOR-SITE-PREP-135HR", "Utility trenching labor", "labor", qty(115 / 1300), 135.0, "HR"),
            comp("TCG-RES-DRIVING-LABOR-95HR", "Driving labor", "labor", qty(14 / 1300), 95.0, "HR"),
        ], ["unitized", "utilities", "trenching"], {"source_job_id": 38522, "factor_note": "Pipe runs per LF: 4in=1.462, 3in=0.692, 1.5in=0.692; adjust per job plans"}),
        cost_item("TCG-EROSION-STABILIZATION-UNIT", "Erosion control and site stabilization per linear foot of fence", "LF", cls["erosion"], [
            comp("TCG-RES-SILT-MATTING-LS", "Silt fence, posts, wire mesh, and matting", "material", 1.0, money(4000.0 / 440), "LF"),
            comp("TCG-RES-ORANGE-FENCE-LS", "Orange construction fence", "material", 1.0, money(2000.0 / 440), "LF"),
            comp("TCG-RES-GEOTEXTILE-ALLOWANCE-LS", "Geotextile/fabric allowance", "material", 1.0, money(600.0 / 440), "LF"),
            comp("TCG-RES-STRAW-STABILIZATION-LS", "Straw stabilization", "material", 1.0, money(3200.0 / 440), "LF"),
            comp("TCG-RES-EROSION-SUB-LF", "Erosion sub crew", "subcontractor", 1.0, money(4000.0 / 440), "LF"),
            comp("TCG-RES-EROSION-EQUIP-LF", "Erosion equipment rental", "equipment", 1.0, money(3000.0 / 440), "LF"),
            comp("TCG-RES-LABOR-SITE-PREP-135HR", "Erosion/stabilization labor", "labor", qty(50 / 440), 135.0, "HR"),
        ], ["unitized", "erosion"], {"source_job_id": 38304, "fence_length_ft": 440}),
        cost_item("TCG-PLACE-COMPACT-FILL-UNIT", "Place and compact imported fill per cubic yard", "CY", cls["earth"], [
            comp("TCG-RES-LABOR-SITE-PREP-135HR", "Fill placement labor", "labor", qty(188 / 1955), 135.0, "HR"),
        ], ["unitized", "earthwork", "fill"], {"source_job_id": 38254, "equipment_rate_missing": True, "allocation_note": "Labor only; equipment rate TBD. Estimated all-in ~$18-25/CY."}),
        cost_item("TCG-PLACE-AGGREGATE-UNIT", "Place and level aggregate (stone/sand) per ton", "t", cls["storm"], [
            comp("TCG-RES-LABOR-SITE-PREP-135HR", "Aggregate placement labor", "labor", qty(89 / 863.8), 135.0, "HR"),
        ], ["unitized", "aggregate", "placement"], {"source_job_id": 38396, "allocation_note": "Draft split: 89 HR from 109 HR pool. Remaining 20 HR covers stormwater scope labor."}),
        cost_item("TCG-PLACE-TOPSOIL-UNIT", "Place stockpiled on-site topsoil per cubic yard", "CY", cls["earth"], [
            comp("TCG-RES-LABOR-SITE-PREP-135HR", "Topsoil placement labor", "labor", qty(78 / 1955), 135.0, "HR"),
        ], ["unitized", "earthwork", "topsoil"], {"source_job_id": 38578, "allocation_note": "78 HR from 38578 392 HR pool; remaining 314 HR covers broader earthwork/stone/excavator scope."}),
    ]

    costs.extend(unitized)
    cost_map = {item["code"]: item for item in costs}

    assemblies = [
        assembly("TCG-X2-ASM-STORMWATER-DRAINAGE", "TCG Extract 2 Stormwater Drainage Assembly", "Stormwater drainage package: delivered stone/sand, aggregate placement, filtration scope, and utility trenching.", "Stormwater", cls["storm"], [
            asm_component("TCG-DELIVER-57-STONE-FD", "Deliver #57 stone for French drain", 863.8, "t", cost_map["TCG-DELIVER-57-STONE-FD"]["rate"]),
            asm_component("TCG-DELIVER-SAND-FD", "Deliver sand for French drain", 78.0, "CY", cost_map["TCG-DELIVER-SAND-FD"]["rate"]),
            asm_component("TCG-PLACE-AGGREGATE-UNIT", "Place aggregate per ton", 863.8, "t", cost_map["TCG-PLACE-AGGREGATE-UNIT"]["rate"]),
            asm_component("TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE", "Stormwater filtration support scope", 1.0, "LS", cost_map["TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE"]["rate"]),
        ]),
        assembly("TCG-X2-ASM-CONCRETE-CURB-PAVING", "TCG Extract 2 Concrete Curb and Paving Assembly", "Concrete curb/gutter per LF plus subcontracted paving and asphalt repair.", "Concrete/Paving", cls["conc"], [
            asm_component("TCG-CONCRETE-CURB-GUTTER-UNIT", "Concrete curb/gutter per LF", 75.0, "LF", cost_map["TCG-CONCRETE-CURB-GUTTER-UNIT"]["rate"]),
            asm_component("TCG-PAVING-ASPHALT-REPAIR-SUBCONTRACT-SCOPE", "Subcontracted paving and asphalt repair", 1.0, "LS", cost_map["TCG-PAVING-ASPHALT-REPAIR-SUBCONTRACT-SCOPE"]["rate"]),
        ]),
        assembly("TCG-X2-ASM-CRAWLSPACE-FOOTER", "TCG Extract 2 Crawlspace Footer Drainage Assembly", "Crawlspace/footer drainage: delivered #57 stone plus excavation/drainage per LF.", "Earthwork", cls["earth"], [
            asm_component("TCG-DELIVER-57-STONE-CF", "Deliver #57 stone for crawlspace/footer", 257.2, "t", cost_map["TCG-DELIVER-57-STONE-CF"]["rate"]),
            asm_component("TCG-CRAWLSPACE-FOOTER-EXCAVATION-UNIT", "Crawlspace/footer excavation and drainage per LF", 1000.0, "LF", cost_map["TCG-CRAWLSPACE-FOOTER-EXCAVATION-UNIT"]["rate"]),
        ]),
        assembly("TCG-X2-ASM-SITE-PREP-EROSION", "TCG Extract 2 Site Prep and Erosion Control Assembly", "Site prep: construction entrance drain stone, erosion control per LF, and demo/disposal scope.", "Site Prep", cls["demo"], [
            asm_component("TCG-DELIVER-DRAIN-STONE-CE", "Deliver construction entrance drain stone", 92.0, "t", cost_map["TCG-DELIVER-DRAIN-STONE-CE"]["rate"]),
            asm_component("TCG-EROSION-STABILIZATION-UNIT", "Erosion control per LF fence", 440.0, "LF", cost_map["TCG-EROSION-STABILIZATION-UNIT"]["rate"]),
            asm_component("TCG-SITE-PREP-DEMO-DISPOSAL-SCOPE", "Site prep demo/disposal scope", 1.0, "LS", cost_map["TCG-SITE-PREP-DEMO-DISPOSAL-SCOPE"]["rate"]),
        ]),
        assembly("TCG-X2-ASM-FILL-PLACEMENT", "TCG Extract 2 Fill Placement Assembly", "Fill delivery and placement: delivered fill per CY plus place/compact per CY.", "Earthwork", cls["earth"], [
            asm_component("TCG-DELIVER-FILL-REVIEW", "Deliver fill per CY", 1955.0, "CY", cost_map["TCG-DELIVER-FILL-REVIEW"]["rate"], {"review_flag": "TCG-P7-R3"}),
            asm_component("TCG-PLACE-COMPACT-FILL-UNIT", "Place and compact fill per CY", 1955.0, "CY", cost_map["TCG-PLACE-COMPACT-FILL-UNIT"]["rate"], {"equipment_rate_missing": True}),
        ]),
        assembly("TCG-X2-ASM-EARTHWORK-TOPSOIL", "TCG Extract 2 Earthwork and Topsoil Assembly", "Topsoil placement per CY from on-site stockpiled cut.", "Earthwork", cls["earth"], [
            asm_component("TCG-PLACE-TOPSOIL-UNIT", "Place topsoil per CY", 1955.0, "CY", cost_map["TCG-PLACE-TOPSOIL-UNIT"]["rate"]),
        ]),
    ]
    return catalog, costs, assemblies


def validate(catalog: list[dict[str, Any]], costs: list[dict[str, Any]], assemblies: list[dict[str, Any]]) -> None:
    resources = {r["resource_code"] for r in catalog}
    costs_by_code = {c["code"] for c in costs}
    errors: list[str] = []
    for item in costs:
        total = money(sum(Decimal(str(c["cost"])) for c in item["components"]))
        if abs(total - item["rate"]) > 0.01:
            errors.append(f"{item['code']} rate mismatch {item['rate']} != {total}")
        for component in item["components"]:
            if component["resource_code"] not in resources:
                errors.append(f"{item['code']} unresolved resource {component['resource_code']}")
    for asm in assemblies:
        total = money(sum(Decimal(str(c["total"])) for c in asm["components"]))
        if abs(total - asm["total_rate"]) > 0.01:
            errors.append(f"{asm['code']} total mismatch {asm['total_rate']} != {total}")
        for component in asm["components"]:
            if component["cost_item_code"] not in costs_by_code:
                errors.append(f"{asm['code']} unresolved cost item {component['cost_item_code']}")
    if errors:
        raise SystemExit("\n".join(errors))


def check_validation_rules(costs: list[dict[str, Any]]) -> list[str]:
    total = len(costs)
    multi_comp = sum(1 for c in costs if len(c["components"]) >= 2)
    multi_type = sum(1 for c in costs if len({comp["type"] for comp in c["components"]}) >= 2)
    with_labor = sum(1 for c in costs if any(comp["type"] == "labor" for comp in c["components"]))
    single_comp = [c for c in costs if len(c["components"]) < 2]
    warns: list[str] = []
    pct_2comp = multi_comp / total * 100
    pct_2type = multi_type / total * 100
    pct_labor = with_labor / total * 100
    warns.append(f"2+ components: {multi_comp}/{total} = {pct_2comp:.1f}% (target >=70%) {'PASS' if pct_2comp >= 70 else 'FAIL'}")
    warns.append(f"2+ types: {multi_type}/{total} = {pct_2type:.1f}% (target >=60%) {'PASS' if pct_2type >= 60 else 'FAIL'}")
    warns.append(f"Labor attached: {with_labor}/{total} = {pct_labor:.1f}%")
    if single_comp:
        warns.append(f"Single-component items ({len(single_comp)}): {[c['code'] for c in single_comp]}")
    for item in costs:
        for comp in item["components"]:
            if comp["quantity"] > 10000:
                warns.append(f"WARN: {item['code']} component {comp['code']} qty={comp['quantity']} > 10000 — possible unscaled project total used as factor")
    return warns


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def main() -> None:
    catalog, costs, assemblies = build()
    validate(catalog, costs, assemblies)
    print("Validation rules:")
    for w in check_validation_rules(costs):
        print(f"  {w}")
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    write_json(PACKAGE_DIR / "catalog_resources.json", catalog)
    write_json(PACKAGE_DIR / "cost_items.json", costs)
    write_json(PACKAGE_DIR / "assemblies.json", assemblies)
    write_json(
        PACKAGE_DIR / "import_manifest.json",
        {
            "manifest_version": "1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "package_name": "TCG Model Job Extract 2 — Unitized CostItems",
            "package_path": "OCERP/bedrock_tcg_model_job_extract_2/",
            "source": SOURCE,
            "region": REGION,
            "review_only": True,
            "import_instructions": "Review-only package for OCERP app inspection. Run scripts/import_tcg_package.py with --dry-run first, then --cleanup to re-import.",
            "provenance": {
                "contact_id": 24929,
                "model_job_group_id": "tcg_24929_model_job",
                "member_job_ids": [38254, 38304, 38396, 38447, 38522, 38577, 38578],
                "source_docs": [
                    "app-bedrock/docs/TCG-project/tcg_costitem_composition_realignment_plan.md",
                    "app-bedrock/docs/TCG-project/tcg_demo_review_notes.md",
                    "app-bedrock/docs/TCG-project/tcg_proposed_composite_costitems_v4.md",
                ],
            },
            "summary": {
                "catalog_resources": len(catalog),
                "cost_items": len(costs),
                "assemblies": len(assemblies),
                "scope": "Extract 2: carried-forward v4 DELIVER/LS items + 7 new unitized CostItems with per-parent-unit factors",
            },
            "carried_review_flags": ["TCG-P7-R2", "TCG-P7-R3", "TCG-P7-R5", "TCG-P7-R6", "TCG-P7-R7", "TCG-RS-R1"],
        },
    )
    (PACKAGE_DIR / "README.md").write_text(
        "# TCG Model Job Extract 2 — Unitized CostItems\n\n"
        "Status: review-only import package for OCERP app inspection.\n\n"
        "Extends the v4 POC (15 CostItems) with 7 new unit-priced CostItems\n"
        "derived from LS-to-unitized decomposition review.\n\n"
        "Validate/import from `OCERP/backend`:\n\n"
        "```bash\n"
        "uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_2 --validate-only\n"
        "uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_2 --dry-run\n"
        "uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_2 --cleanup\n"
        "```\n\n"
        "This package is not final-approved. It is intended to get the unitized CostItems\n"
        "into OCERP for visual/app review and Bedrock team demo.\n"
    )
    print(json.dumps({"package_dir": str(PACKAGE_DIR), "catalog_resources": len(catalog), "cost_items": len(costs), "assemblies": len(assemblies)}, indent=2))


if __name__ == "__main__":
    main()
