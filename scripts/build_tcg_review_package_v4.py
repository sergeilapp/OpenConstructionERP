#!/usr/bin/env python3
"""Build the broader review-only TCG v4 import package.

This generator intentionally uses reviewed CostItem boundaries from the TCG
planning docs. It produces JSON files that can be imported with
scripts/import_tcg_package.py for app review.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parents[1] / "bedrock_tcg_model_job_extract_v4_review"
SOURCE = "bedrock_tcg_model_job_extract_v4_review"
REGION = "BEDROCK-TCG-V4-REVIEW"
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
        "tags": ["tcg_v4_review", "review_only", *tags],
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
        "tags": ["tcg_v4_review", "review_only", "assembly"],
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
        resource("TCG-RES-CORRUGATED-PIPE-4IN-FT", "TCG 4in Corrugated Perforated Pipe per Foot", "material", "Drainage", "FT", money(2320.98 / 1000), "33 00 00", {"source_evidence": "job 38577: $2,320.98 / 1,000 ft = $2.32/ft", "rate_basis": "Derived from LS allowance ÷ 1,000 ft"}),
        resource("TCG-RES-DEMO-EQUIP-ALLOWANCE-LS", "TCG Demo Equipment Allowance", "equipment", "Demolition", "LS", 17450.0, "02 00 00", {"review_flag": "TCG-RS-R1"}),
        resource("TCG-RES-EROSION-SUB-LS", "TCG Erosion Control Sub Crew", "subcontractor", "Erosion", "LS", 4000.0, "31 00 00"),
        resource("TCG-RES-SILT-MATTING-LS", "TCG Silt Fence, Posts, Wire Mesh, and Matting", "material", "Erosion", "LS", 4000.0, "31 00 00"),
        resource("TCG-RES-ORANGE-FENCE-LS", "TCG Orange Construction Fence", "material", "Erosion", "LS", 2000.0, "31 00 00"),
        resource("TCG-RES-GEOTEXTILE-ALLOWANCE-LS", "TCG Geotextile/Fabric Allowance", "material", "Erosion", "LS", 600.0, "31 00 00"),
        resource("TCG-RES-STRAW-STABILIZATION-LS", "TCG Straw Stabilization", "material", "Erosion", "LS", 3200.0, "31 00 00"),
        resource("TCG-RES-EROSION-EQUIP-RENTAL-LS", "TCG Erosion Equipment Rental Allowance", "equipment", "Rental", "LS", 3000.0, "31 00 00"),
        resource("TCG-RES-MATERIAL-GATHERING-LABOR-LS", "TCG Material Gathering Labor Allowance", "labor", "Labor", "LS", 2000.0, "03 00 00", {"source_evidence": "AdhocJobCalculator material_gathering_labor_cost"}),
        resource("TCG-RES-EROSION-SUB-LF", "TCG Erosion Control Sub Crew per LF", "subcontractor", "Erosion", "LF", money(4000.0 / 440), "31 00 00", {"rate_basis": "$4,000 ÷ 440 LF"}),
        resource("TCG-RES-EROSION-EQUIP-LF", "TCG Erosion Equipment Rental per LF", "equipment", "Rental", "LF", money(3000.0 / 440), "31 00 00", {"rate_basis": "$3,000 ÷ 440 LF"}),
    ]

    cls = {
        "storm": {"masterformat": "33 00 00", "collection": "Stormwater", "category": "Sitework", "department": "Utilities", "section": "French Drain"},
        "utility": {"masterformat": "33 00 00", "collection": "Utilities", "category": "Sitework", "department": "Utilities", "section": "Utility Trenching"},
        "earth": {"masterformat": "31 00 00", "collection": "Earthwork", "category": "Sitework", "department": "Earthwork", "section": "General Earthwork"},
        "demo": {"masterformat": "02 00 00", "collection": "Existing Conditions", "category": "Sitework", "department": "Demo", "section": "Demolition"},
        "conc": {"masterformat": "03 00 00", "collection": "Concrete", "category": "Sitework", "department": "Concrete", "section": "Curb"},
        "pave": {"masterformat": "32 00 00", "collection": "Exterior Improvements", "category": "Sitework", "department": "Paving", "section": "Asphalt"},
    }

    costs = [
        cost_item("TCG-DELIVER-57-STONE-FD", "Deliver #57 stone for French drain", "t", cls["storm"], [comp("TCG-RES-57-STONE-TON", "#57 stone material", "material", 1.0, 38.0, "t"), comp("TCG-RES-HAUL-57-STONE-FD-LOAD", "#57 stone bundled hauling", "equipment", qty(38 / 863.8), 945.0, "LOAD")], ["deliver"], {"source_job_id": 38396}),
        cost_item("TCG-DELIVER-SAND-FD", "Deliver sand for French drain", "CY", cls["storm"], [comp("TCG-RES-SAND-CY", "Sand material", "material", 1.0, 25.0, "CY"), comp("TCG-RES-HAUL-SAND-FD-LOAD", "Sand bundled hauling", "equipment", qty(4 / 78), 745.0, "LOAD")], ["deliver"], {"source_job_id": 38396}),
        cost_item("TCG-PLACE-AGGREGATE-FD", "Place aggregate layers for French drain", "LS", cls["storm"], [comp("TCG-RES-LABOR-SITE-PREP-135HR", "Aggregate placement labor", "labor", 89.0, 135.0, "HR")], ["place"], {"source_job_id": 38396, "allocation_note": "Draft split from 109 HR pool"}),
        cost_item("TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE", "Stormwater filtration fabric, observation pipe, equipment, and specialty labor", "LS", cls["storm"], [comp("TCG-RES-FABRIC-ROLL", "Geotextile fabric", "material", 12.0, 200.0, "ROLL"), comp("TCG-RES-OBS-WELL-PIPE-LS", "Pipe for observation wells", "material", 1.0, 1100.0, "LS"), comp("TCG-RES-STORM-EQUIP-RENTAL-LS", "Stormwater equipment rental", "equipment", 1.0, 2000.0, "LS"), comp("TCG-RES-LABOR-SITE-PREP-135HR", "Stormwater specialty labor", "labor", 20.0, 135.0, "HR")], ["scope"], {"source_job_id": 38396}),
        cost_item("TCG-UTILITY-TRENCHING-CONDUIT-SCOPE", "Utility trenching, conduit/pipe installation, and backfill", "LS", cls["utility"], [comp("TCG-RES-UTILITY-PIPE-4IN-LS", "4in schedule 40 pipe and fittings", "material", 1.0, 12000.0, "LS"), comp("TCG-RES-UTILITY-CONDUIT-3IN-LS", "3in electrical conduit", "material", 1.0, 4000.0, "LS"), comp("TCG-RES-UTILITY-CONDUIT-1-5IN-LS", "1.5in conduit", "material", 1.0, 2500.0, "LS"), comp("TCG-RES-SCREENINGS-LOAD", "Screenings backfill", "material", 8.0, 1050.0, "LOAD"), comp("TCG-RES-UTILITY-MATERIAL-ALLOWANCE-LS", "Additional utility materials", "material", 1.0, 6500.0, "LS"), comp("TCG-RES-UTILITY-EQUIP-ALLOWANCE-LS", "Utility equipment allowance", "equipment", 1.0, 2500.0, "LS"), comp("TCG-RES-DRIVING-EQUIP-MI", "Driving equipment", "equipment", 336.0, 4.375, "MI"), comp("TCG-RES-LABOR-SITE-PREP-135HR", "Utility trenching labor", "labor", 115.0, 135.0, "HR"), comp("TCG-RES-DRIVING-LABOR-95HR", "Driving labor", "labor", 14.0, 95.0, "HR")], ["scope"], {"source_job_id": 38522, "draft_unit": "LS"}),
        cost_item("TCG-DELIVER-DRAIN-STONE-CE", "Deliver drain stone for construction entrance", "t", cls["demo"], [comp("TCG-RES-DRAIN-STONE-TON", "Drain stone material", "material", 1.0, 38.0, "t"), comp("TCG-RES-HAUL-DRAIN-STONE-LOAD", "Drain stone bundled hauling", "equipment", qty(4 / 92), 985.0, "LOAD")], ["deliver"], {"source_job_id": 38304}),
        cost_item("TCG-EROSION-STABILIZATION-SCOPE", "Erosion control and site stabilization scope", "LS", cls["earth"], [comp("TCG-RES-EROSION-SUB-LS", "Erosion controls sub crew", "subcontractor", 1.0, 4000.0, "LS"), comp("TCG-RES-SILT-MATTING-LS", "Silt fence, posts, wire mesh, and matting", "material", 1.0, 4000.0, "LS"), comp("TCG-RES-ORANGE-FENCE-LS", "Orange construction fence", "material", 1.0, 2000.0, "LS"), comp("TCG-RES-GEOTEXTILE-ALLOWANCE-LS", "Geotextile/fabric allowance", "material", 1.0, 600.0, "LS"), comp("TCG-RES-STRAW-STABILIZATION-LS", "Straw stabilization", "material", 1.0, 3200.0, "LS"), comp("TCG-RES-EROSION-EQUIP-RENTAL-LS", "Erosion equipment rental", "equipment", 1.0, 3000.0, "LS"), comp("TCG-RES-LABOR-SITE-PREP-135HR", "Erosion/stabilization labor", "labor", 50.0, 135.0, "HR")], ["scope"], {"source_job_id": 38304}),
        cost_item("TCG-SITE-PREP-DEMO-DISPOSAL-SCOPE", "Site prep demolition, tree removal, and disposal review scope", "LS", cls["demo"], [comp("TCG-RES-DEMO-EQUIP-ALLOWANCE-LS", "Demo equipment allowance", "equipment", 1.0, 17450.0, "LS"), comp("TCG-RES-LABOR-SITE-PREP-135HR", "Demo/disposal labor", "labor", 48.0, 135.0, "HR"), comp("TCG-RES-DRIVING-EQUIP-MI", "Demo driving equipment", "equipment", 168.0, 4.375, "MI")], ["scope"], {"source_job_id": 38304, "review_flag": "TCG-RS-R1"}),
        cost_item("TCG-CONCRETE-CURB-GUTTER-SCOPE", "Concrete curb and gutter internal work", "LS", cls["conc"], [comp("TCG-RES-CONCRETE-CY", "Concrete material", "material", 15.0, money(3800 / 15), "CY"), comp("TCG-RES-2A-STONE-LOAD", "2A stone", "material", 1.0, 800.0, "LOAD"), comp("TCG-RES-LABOR-ADHOC-125HR", "Adhoc concrete labor", "labor", 42.0, 125.0, "HR"), comp("TCG-RES-MATERIAL-GATHERING-LABOR-LS", "Material gathering labor", "labor", 1.0, 2000.0, "LS"), comp("TCG-RES-DRIVING-EQUIP-MI", "Driving equipment", "equipment", 84.0, 4.375, "MI"), comp("TCG-RES-DRIVING-LABOR-95HR", "Driving labor", "labor", 3.74, 95.0, "HR")], ["scope"], {"source_job_id": 38447, "review_flag": "TCG-P7-R7"}),
        cost_item("TCG-PAVING-ASPHALT-REPAIR-SUBCONTRACT-SCOPE", "Subcontracted paving and asphalt utility trench repair", "LS", cls["pave"], [comp("TCG-RES-PAVING-SUB-LS", "Paving sub crew", "subcontractor", 1.0, 9800.0, "LS"), comp("TCG-RES-ASPHALT-REPAIR-SUB-LS", "Asphalt utility trench repair sub crew", "subcontractor", 1.0, 1500.0, "LS")], ["scope", "subcontractor"], {"source_job_id": 38447}),
        cost_item("TCG-DELIVER-57-STONE-CF", "Deliver #57 stone for crawlspace/footer drainage", "t", cls["earth"], [comp("TCG-RES-57-STONE-TON", "#57 stone material", "material", 1.0, 38.0, "t"), comp("TCG-RES-HAUL-57-STONE-CF-LOAD", "#57 stone crawlspace hauling", "equipment", qty(12 / 257.2), 985.0, "LOAD")], ["deliver"], {"source_job_id": 38577}),
        cost_item("TCG-CRAWLSPACE-FOOTER-EXCAVATION-SCOPE", "Crawlspace/footer excavation and drainage scope", "LS", cls["earth"], [comp("TCG-RES-CORRUGATED-PIPE-4IN-LS", "4in corrugated perforated pipe", "material", 1.0, 2320.98, "LS"), comp("TCG-RES-LABOR-SITE-PREP-135HR", "Crawlspace/footer labor", "labor", 114.0, 135.0, "HR"), comp("TCG-RES-DRIVING-EQUIP-45MI", "Driving equipment", "equipment", 336.0, 4.5, "MI"), comp("TCG-RES-DRIVING-LABOR-95HR", "Driving labor", "labor", 12.25, 95.0, "HR")], ["scope"], {"source_job_id": 38577}),
        cost_item("TCG-DELIVER-FILL-REVIEW", "Delivered fill material and hauling review item", "CY", cls["earth"], [comp("TCG-RES-FILL-DELIVERED-CY", "Delivered fill material review rate", "material", 1.0, 6.5, "CY"), comp("TCG-RES-HAUL-FILL-LOAD", "Fill hauling", "equipment", qty(98 / 1955), 395.0, "LOAD")], ["deliver", "review"], {"source_job_id": 38254, "review_flag": "TCG-P7-R3"}),
        cost_item("TCG-PLACE-COMPACT-FILL-REVIEW", "Place and compact imported fill review item", "LS", cls["earth"], [comp("TCG-RES-LABOR-SITE-PREP-135HR", "Fill placement labor", "labor", 188.0, 135.0, "HR")], ["place", "review"], {"source_job_id": 38254, "equipment_rate_missing": True}),
        cost_item("TCG-PLACE-TOPSOIL-REVIEW", "Place stockpiled topsoil review item", "LS", cls["earth"], [comp("TCG-RES-LABOR-SITE-PREP-135HR", "Topsoil placement labor placeholder", "labor", 1.0, 135.0, "HR")], ["place", "review"], {"source_job_id": 38254, "single_component_exception_reason": "Review-only placeholder pending labor/equipment split"}),
    ]

    cost_map = {item["code"]: item for item in costs}
    assemblies = [
        assembly("TCG-V4-ASM-STORMWATER-FRENCH-DRAIN-DRAFT", "TCG v4 Stormwater French Drain Draft Assembly", "Review-only assembly grouping stormwater delivery, placement, and filtration scope.", "Stormwater", cls["storm"], [asm_component("TCG-DELIVER-57-STONE-FD", "Deliver #57 stone for French drain", 863.8, "t", cost_map["TCG-DELIVER-57-STONE-FD"]["rate"]), asm_component("TCG-DELIVER-SAND-FD", "Deliver sand for French drain", 78.0, "CY", cost_map["TCG-DELIVER-SAND-FD"]["rate"]), asm_component("TCG-PLACE-AGGREGATE-FD", "Place aggregate layers for French drain", 1.0, "LS", cost_map["TCG-PLACE-AGGREGATE-FD"]["rate"]), asm_component("TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE", "Stormwater filtration support scope", 1.0, "LS", cost_map["TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE"]["rate"])]),
        assembly("TCG-V4-ASM-CONCRETE-CURB-PAVING-DRAFT", "TCG v4 Concrete Curb and Paving Draft Assembly", "Review-only assembly grouping curb/gutter internal work and split subcontracted paving/asphalt repair.", "Concrete/Paving", cls["conc"], [asm_component("TCG-CONCRETE-CURB-GUTTER-SCOPE", "Concrete curb/gutter internal work", 1.0, "LS", cost_map["TCG-CONCRETE-CURB-GUTTER-SCOPE"]["rate"]), asm_component("TCG-PAVING-ASPHALT-REPAIR-SUBCONTRACT-SCOPE", "Subcontracted paving and asphalt repair", 1.0, "LS", cost_map["TCG-PAVING-ASPHALT-REPAIR-SUBCONTRACT-SCOPE"]["rate"])]),
        assembly("TCG-V4-ASM-CRAWLSPACE-FOOTER-DRAINAGE-DRAFT", "TCG v4 Crawlspace Footer Drainage Draft Assembly", "Review-only assembly for crawlspace/footer excavation, delivered stone, pipe, labor, and driving.", "Earthwork", cls["earth"], [asm_component("TCG-DELIVER-57-STONE-CF", "Deliver #57 stone for crawlspace/footer", 257.2, "t", cost_map["TCG-DELIVER-57-STONE-CF"]["rate"]), asm_component("TCG-CRAWLSPACE-FOOTER-EXCAVATION-SCOPE", "Crawlspace/footer excavation and drainage scope", 1.0, "LS", cost_map["TCG-CRAWLSPACE-FOOTER-EXCAVATION-SCOPE"]["rate"])]),
        assembly("TCG-V4-ASM-SITE-PREP-DEMO-EROSION-DRAFT", "TCG v4 Site Prep Demo and Erosion Draft Assembly", "Review-only assembly for construction entrance drain stone, erosion/stabilization, and demo/disposal scope.", "Site Prep", cls["demo"], [asm_component("TCG-DELIVER-DRAIN-STONE-CE", "Deliver construction entrance drain stone", 92.0, "t", cost_map["TCG-DELIVER-DRAIN-STONE-CE"]["rate"]), asm_component("TCG-EROSION-STABILIZATION-SCOPE", "Erosion and stabilization scope", 1.0, "LS", cost_map["TCG-EROSION-STABILIZATION-SCOPE"]["rate"]), asm_component("TCG-SITE-PREP-DEMO-DISPOSAL-SCOPE", "Site prep demo/disposal scope", 1.0, "LS", cost_map["TCG-SITE-PREP-DEMO-DISPOSAL-SCOPE"]["rate"])]),
        assembly("TCG-V4-ASM-FILL-PLACEMENT-REVIEW", "TCG v4 Fill Placement Review Assembly", "Review-only assembly for delivered fill and fill placement; blocked from final approval by TCG-P7-R3 and equipment-rate review.", "Earthwork", cls["earth"], [asm_component("TCG-DELIVER-FILL-REVIEW", "Deliver fill review item", 1955.0, "CY", cost_map["TCG-DELIVER-FILL-REVIEW"]["rate"], {"review_flag": "TCG-P7-R3"}), asm_component("TCG-PLACE-COMPACT-FILL-REVIEW", "Place and compact fill review item", 1.0, "LS", cost_map["TCG-PLACE-COMPACT-FILL-REVIEW"]["rate"], {"equipment_rate_missing": True})]),
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


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def main() -> None:
    catalog, costs, assemblies = build()
    validate(catalog, costs, assemblies)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    write_json(PACKAGE_DIR / "catalog_resources.json", catalog)
    write_json(PACKAGE_DIR / "cost_items.json", costs)
    write_json(PACKAGE_DIR / "assemblies.json", assemblies)
    write_json(
        PACKAGE_DIR / "import_manifest.json",
        {
            "manifest_version": "1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "package_name": "TCG Model Job Extract v4 Review",
            "package_path": "OCERP/bedrock_tcg_model_job_extract_v4_review/",
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
                "scope": "Reviewed TCG v4 CostItems and assemblies for app proof-of-concept review",
            },
            "carried_review_flags": ["TCG-P7-R2", "TCG-P7-R3", "TCG-P7-R5", "TCG-P7-R6", "TCG-P7-R7", "TCG-RS-R1"],
        },
    )
    (PACKAGE_DIR / "README.md").write_text(
        "# TCG Model Job Extract v4 Review\n\n"
        "Status: review-only import package for OCERP app inspection.\n\n"
        "Validate/import from `OCERP/backend`:\n\n"
        "```bash\n"
        "uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_v4_review --validate-only\n"
        "uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_v4_review --dry-run\n"
        "uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_v4_review --cleanup\n"
        "```\n\n"
        "This package is not final-approved. It is intended to get the reviewed CostItems and assemblies into OCERP for visual/app review.\n"
    )
    print(json.dumps({"package_dir": str(PACKAGE_DIR), "catalog_resources": len(catalog), "cost_items": len(costs), "assemblies": len(assemblies)}, indent=2))


if __name__ == "__main__":
    main()
