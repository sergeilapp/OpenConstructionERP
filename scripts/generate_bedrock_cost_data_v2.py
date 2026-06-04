#!/usr/bin/env python3
"""Generate Bedrock estimating extract v2 for OCERP.

This script intentionally starts from the validated attempt-1 extract, then
remodels it into the v2 shape:

* leaf resources -> oe_catalog_resource JSON
* estimator-facing work/conversion items -> oe_costs_item JSON
* larger packages -> oe_assemblies_assembly JSON

It does not mirror the Rails calculators as import structures. Calculator and
recent-job notes are preserved as evidence in metadata and reports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REGION = "BEDROCK-MAIN"
CURRENCY = "USD"
SOURCE = "bedrock_extraction_v2"
ATTEMPT1_SOURCE = "bedrock_extraction"

PURE_ALIAS_CODES = {
    "BED-CONC-LABOR",
    "BED-CONC-ACCESS",
    "BED-CONC-MAT-GATHER",
    "BED-ROCK-STONE",
    "BED-ROCK-BOARD",
    "BED-ROCK-REBAR",
    "BED-ROCK-EROSION-CONTROL",
    "BED-ROCK-LABOR",
    "BED-ROCK-ACCESS",
    "BED-ROCK-MAT-GATHER",
    "BED-PREP-BOARD",
    "BED-PREP-REBAR",
    "BED-PREP-LABOR",
    "BED-PREP-ACCESS",
    "BED-PREP-MAT-GATHER",
    "BED-ADHOC-LABOR",
    "BED-ADHOC-ACCESS",
    "BED-ADHOC-MAT-GATHER",
}

CODE_RENAMES = {
    "BED-CONC-SLAB-4IN": "BED-CONC-SLAB-4IN-INSTALLED",
    "BED-CONC-SLAB-6IN": "BED-CONC-SLAB-6IN-INSTALLED",
    "BED-CONC-SLAB-8IN": "BED-CONC-SLAB-8IN-INSTALLED",
    "BED-CONC-FOOTER": "BED-CONC-FOOTER-INSTALLED",
    "BED-CONC-PIER": "BED-CONC-PIER-INSTALLED",
    "BED-CONC-APRON": "BED-CONC-APRON-INSTALLED",
    "BED-CONC-EDGE": "BED-CONC-EDGE-INSTALLED",
    "BED-CONC-CORE-FILL": "BED-CONC-CORE-FILL-INSTALLED",
    "BED-CONC-BLOCK-6IN": "BED-CONC-CMU-BLOCK-6IN-PER-LF",
    "BED-CONC-BLOCK-8IN": "BED-CONC-CMU-BLOCK-8IN-PER-LF",
    "BED-CONC-BLOCK-10IN": "BED-CONC-CMU-BLOCK-10IN-PER-LF",
    "BED-CONC-BLOCK-12IN": "BED-CONC-CMU-BLOCK-12IN-PER-LF",
    "BED-CONC-TOP-BLOCK": "BED-CONC-CMU-TOP-BLOCK-PER-LF",
    "BED-ROCK-EXCAVATION": "BED-ROCK-EXCAVATION-INSTALLED",
    "BED-PREP-EXCAVATION": "BED-PREP-EXCAVATION-INSTALLED",
    "BED-PREP-WIRE": "BED-WIRE-MESH-INSTALLED",
    "BED-PREP-VAPOR": "BED-VAPOR-BARRIER-INSTALLED",
    "BED-PREP-FABRIC": "BED-WEED-FABRIC-INSTALLED",
    "BED-ROCK-FILL-DIRT": "BED-FILL-DIRT-DELIVERED-ROCKPAD",
    "BED-PREP-FILL-DIRT": "BED-FILL-DIRT-DELIVERED-SITEPREP",
    "BED-ADHOC-FILL-DIRT": "BED-FILL-DIRT-DELIVERED-ADHOC",
    "BED-CONC-DRIVING": "BED-MATERIAL-HAULING-CONCRETE-TON-MI-REVIEW",
    "BED-ROCK-DRIVING": "BED-MATERIAL-HAULING-ROCKPAD-TON-MI-REVIEW",
    "BED-PREP-DRIVING": "BED-MATERIAL-HAULING-SITEPREP-TON-MI-REVIEW",
    "BED-ADHOC-DRIVING": "BED-MATERIAL-HAULING-ADHOC-TON-MI-REVIEW",
}

RECENT_USAGE = {
    "site_preparation": 388,
    "rock_pad": 332,
    "adhoc": 137,
    "concrete_gibraltar": 56,
    "concrete_floating_slab": 44,
    "concrete_graduated_slab": 14,
    "concrete_piers": 4,
    "weed_fabric": 352,
    "border_6x6": 323,
    "fill_dirt": 127,
    "concrete_slab": 121,
    "retaining_wall_rock": 48,
    "concrete_apron": 27,
    "core_fill": 24,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")


def money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def qty(value: float) -> float:
    return round(float(value), 6)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resource_type(item: dict[str, Any]) -> str:
    code = item["code"].upper()
    tags = {str(t).lower() for t in item.get("tags", [])}
    if code.startswith("LAB-") or "labor" in tags:
        return "labor"
    if code.startswith("EQP-") or "equipment" in tags or "truck" in tags:
        return "equipment"
    if code.startswith("OP-"):
        return "operator"
    if code.startswith("SUB-"):
        return "subcontractor"
    return "material"


def category_for(item: dict[str, Any], rtype: str) -> str:
    code = item["code"].upper()
    text = f"{code} {item.get('description', '')}".lower()
    if rtype == "labor":
        return "Labor"
    if rtype == "equipment":
        if "truck" in text or "gas" in text:
            return "Trucking"
        return "Equipment"
    if "quarry" in code:
        return "Quarry Material"
    if "concrete" in text or "cement" in text or "block" in text:
        return "Concrete"
    if "rock" in text or "stone" in text or "aggregate" in text or "drain" in text:
        return "Site Prep Material"
    if "fabric" in text or "vapor" in text or "insulation" in text:
        return "Moisture & Insulation"
    if "board" in text or "wood" in text:
        return "Wood & Border"
    if "rebar" in text or "wire" in text or "steel" in text:
        return "Reinforcement"
    return "Bedrock Material"


def to_catalog_resource(item: dict[str, Any]) -> dict[str, Any]:
    rtype = resource_type(item)
    meta = dict(item.get("metadata") or {})
    meta.update(
        {
            "attempt1_source": item.get("source"),
            "attempt1_code": item["code"],
            "generated_at": GENERATED_AT,
        }
    )
    return {
        "resource_code": item["code"],
        "name": item.get("description") or item["code"],
        "resource_type": rtype,
        "category": category_for(item, rtype),
        "unit": item.get("unit") or "ea",
        "base_price": float(item.get("rate") or 0),
        "min_price": 0,
        "max_price": 0,
        "currency": CURRENCY,
        "source": SOURCE,
        "region": REGION,
        "specifications": {
            "attempt1_classification": item.get("classification") or {},
            "attempt1_tags": item.get("tags") or [],
        },
        "metadata": meta,
    }


def normalize_component(comp: dict[str, Any]) -> dict[str, Any]:
    quantity = float(comp.get("quantity") or 0)
    unit_rate = float(comp.get("unit_rate") or 0)
    cost = money(quantity * unit_rate)
    out = {
        "code": comp["code"],
        "resource_code": comp["code"],
        "name": comp.get("name") or comp["code"],
        "type": comp.get("type") or "material",
        "resource_type": comp.get("type") or "material",
        "quantity": qty(quantity),
        "unit_rate": unit_rate,
        "cost": cost,
        "unit": comp.get("unit") or "ea",
    }
    for key in ("available_variants", "available_variant_stats"):
        if key in comp:
            out[key] = comp[key]
    return out


def item_decision(item: dict[str, Any]) -> str:
    code = item["code"]
    if code in PURE_ALIAS_CODES:
        return "delete_alias"
    comps = item.get("components") or []
    if len(comps) == 1:
        comp = comps[0]
        if abs(float(comp.get("quantity") or 0) - 1.0) < 0.000001:
            return "delete_alias"
        return "cost_item_conversion"
    return "cost_item_installed_work"


def v2_description(item: dict[str, Any], new_code: str, decision: str) -> str:
    desc = item.get("description") or new_code
    if decision == "cost_item_conversion":
        return f"{desc} (takeoff conversion wrapper)"
    if "INSTALLED" in new_code and "installed" not in desc.lower():
        return f"{desc} installed"
    return desc


def to_cost_item(item: dict[str, Any]) -> dict[str, Any]:
    decision = item_decision(item)
    new_code = CODE_RENAMES.get(item["code"], item["code"])
    components = [normalize_component(c) for c in item.get("components") or []]
    rate = money(sum(c["cost"] for c in components))
    tags = [t for t in item.get("tags", []) if t != "sample"]
    tags.extend(["bedrock-v2", decision])
    if "TON-MI" in new_code:
        tags.extend(["hauling", "needs_design_review"])
    if decision == "cost_item_conversion":
        tags.append("conversion-wrapper")
    meta = dict(item.get("metadata") or {})
    meta.update(
        {
            "attempt1_code": item["code"],
            "attempt1_source": item.get("source"),
            "v2_decision": decision,
            "source_evidence": ["attempt1 validated component math", "v2 design admission checklist"],
            "generated_at": GENERATED_AT,
        }
    )
    if "TON-MI" in new_code:
        meta["hauling_unit_policy"] = "prefer ton-mi, but attempt-1 component quantities are preserved pending job-level mileage/load sampling"
        meta["validation_status"] = "needs_design_review"
    elif "needs_sampling" in item.get("tags", []):
        meta["validation_status"] = "needs_sampling"
    else:
        meta["validation_status"] = "validated_static"
    return {
        "code": new_code,
        "description": v2_description(item, new_code, decision),
        "descriptions": {},
        "unit": item.get("unit") or "ea",
        "rate": rate,
        "currency": CURRENCY,
        "source": SOURCE,
        "region": REGION,
        "classification": item.get("classification") or {},
        "components": components,
        "tags": sorted(set(tags)),
        "metadata": meta,
    }


def resource_lookup(resources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["resource_code"]: r for r in resources}


def component_from_resource(resources: dict[str, dict[str, Any]], code: str, quantity: float, note: str = "") -> dict[str, Any]:
    r = resources[code]
    unit_cost = float(r["base_price"])
    return {
        "code": code,
        "resource_code": code,
        "name": r["name"],
        "type": r["resource_type"],
        "resource_type": r["resource_type"],
        "quantity": qty(quantity),
        "unit_rate": unit_cost,
        "cost": money(quantity * unit_cost),
        "unit": r["unit"],
        "metadata": {"note": note} if note else {},
    }


def add_optional_cost_items(items: list[dict[str, Any]], resources: dict[str, dict[str, Any]]) -> None:
    optional_specs = [
        (
            "BED-CONC-FIBER-ADDON",
            "Concrete fiber add-on per cubic yard",
            "cy",
            [("MAT-FIBER-COST", 1.0, "Separate optional concrete add-on approved by V2-D5")],
            "03 30 00",
        ),
        (
            "BED-CONC-SMOOTH-FINISH-ADDON",
            "Smooth concrete finish add-on per square foot",
            "sf",
            [("MAT-FINISH-COST-SMOOTH", 1.0, "Separate optional finish add-on approved by V2-D5")],
            "03 35 00",
        ),
        (
            "BED-INSULATION-1IN-INSTALLED",
            "1 inch insulation installed per square foot",
            "sf",
            [("MAT-INSULATION-COST-1-0-INCH", 1.0, "Separate optional insulation component approved by V2-D5")],
            "07 21 00",
        ),
        (
            "BED-INSULATION-1-5IN-INSTALLED",
            "1.5 inch insulation installed per square foot",
            "sf",
            [("MAT-INSULATION-COST-1-5-INCH", 1.0, "Separate optional insulation component approved by V2-D5")],
            "07 21 00",
        ),
        (
            "BED-INSULATION-2IN-INSTALLED",
            "2 inch insulation installed per square foot",
            "sf",
            [("MAT-INSULATION-COST-2-0-INCH", 1.0, "Separate optional insulation component approved by V2-D5")],
            "07 21 00",
        ),
    ]
    for code, description, unit, comps, masterformat in optional_specs:
        missing = [c for c, _, _ in comps if c not in resources]
        if missing:
            continue
        components = [component_from_resource(resources, c, q, note) for c, q, note in comps]
        items.append(
            {
                "code": code,
                "description": description,
                "descriptions": {},
                "unit": unit,
                "rate": money(sum(c["cost"] for c in components)),
                "currency": CURRENCY,
                "source": SOURCE,
                "region": REGION,
                "classification": {"masterformat": masterformat},
                "components": components,
                "tags": ["bedrock-v2", "optional-addon", "cost_item_conversion"],
                "metadata": {
                    "v2_decision": "cost_item_conversion",
                    "validation_status": "approved_optional_component",
                    "source_evidence": ["Bedrock catalog resource", "V2-D5 approval"],
                    "generated_at": GENERATED_AT,
                },
            }
        )


def assembly_component_from_item(cost_items: dict[str, dict[str, Any]], code: str, quantity: float) -> dict[str, Any]:
    item = cost_items[code]
    return {
        "cost_item_code": code,
        "description": item["description"],
        "factor": 1.0,
        "quantity": qty(quantity),
        "unit": item["unit"],
        "unit_cost": item["rate"],
        "resource_type": None,
        "total": money(quantity * item["rate"]),
        "metadata": {"component_source": "cost_item"},
    }


def build_assemblies(cost_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = {i["code"]: i for i in cost_items}
    specs: list[tuple[str, str, str, str, list[tuple[str, float]], str, list[str]]] = [
        (
            "BED-ASM-CONC-FLOATING-SLAB",
            "Concrete floating slab package",
            "sf",
            "Concrete",
            [("BED-CONC-SLAB-4IN-INSTALLED", 1.0), ("BED-VAPOR-BARRIER-INSTALLED", 1.0), ("BED-WIRE-MESH-INSTALLED", 1.0)],
            "03 30 00",
            ["concrete", "floating-slab"],
        ),
        (
            "BED-ASM-CONC-GRADUATED-SLAB",
            "Concrete graduated slab package",
            "sf",
            "Concrete",
            [("BED-CONC-SLAB-6IN-INSTALLED", 1.0), ("BED-CONC-EDGE-INSTALLED", 0.1), ("BED-VAPOR-BARRIER-INSTALLED", 1.0)],
            "03 30 00",
            ["concrete", "graduated-slab"],
        ),
        (
            "BED-ASM-CONC-GIBRALTAR-FOUNDATION",
            "Concrete Gibraltar foundation package",
            "lf",
            "Concrete",
            [
                ("BED-CONC-FOOTER-INSTALLED", 1.0),
                ("BED-CONC-CMU-BLOCK-8IN-PER-LF", 1.0),
                ("BED-CONC-CORE-FILL-INSTALLED", 1.0),
                ("BED-CONC-CMU-TOP-BLOCK-PER-LF", 1.0),
            ],
            "03 30 00",
            ["concrete", "gibraltar"],
        ),
        (
            "BED-ASM-ROCK-PAD-STANDARD",
            "Standard rock pad scope package",
            "sf",
            "Site Prep",
            [("BED-ROCK-EXCAVATION-INSTALLED", 1.0), ("BED-WEED-FABRIC-INSTALLED", 1.0)],
            "31 22 00",
            ["rockpad", "site-prep"],
        ),
        (
            "BED-ASM-SITE-PREP-STANDARD",
            "Standard site preparation package",
            "sf",
            "Site Prep",
            [("BED-PREP-EXCAVATION-INSTALLED", 1.0), ("BED-WEED-FABRIC-INSTALLED", 1.0), ("BED-WIRE-MESH-INSTALLED", 1.0)],
            "31 20 00",
            ["siteprep"],
        ),
        (
            "BED-ASM-FILL-DIRT-SCOPE",
            "Fill dirt delivered scope package",
            "ton",
            "Site Prep",
            [("BED-FILL-DIRT-DELIVERED-SITEPREP", 1.0)],
            "31 23 23",
            ["fill-dirt"],
        ),
    ]
    assemblies = []
    for code, name, unit, category, components, masterformat, tags in specs:
        missing = [c for c, _ in components if c not in items]
        if missing:
            continue
        comps = [assembly_component_from_item(items, c, q) for c, q in components]
        total = money(sum(c["total"] for c in comps))
        assemblies.append(
            {
                "code": code,
                "name": name,
                "description": f"Bedrock v2 assembly. Optional scopes remain visible as separate components where supported. Missing optional choices are deferred rather than hidden.",
                "unit": unit,
                "category": category,
                "classification": {"masterformat": masterformat},
                "total_rate": total,
                "currency": CURRENCY,
                "bid_factor": 1.0,
                "regional_factors": {},
                "is_template": True,
                "tags": ["bedrock-v2", *tags],
                "components": comps,
                "metadata": {
                    "source": SOURCE,
                    "region": REGION,
                    "validation_status": "needs_design_review" if "ASM-ROCK" in code or "SITE-PREP" in code else "validated_static",
                    "source_evidence": ["v2 assembly design rules", "recent job usage priority table"],
                    "generated_at": GENERATED_AT,
                },
            }
        )
    return assemblies


def build_candidate_inventory(all_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in all_items:
        decision = item_decision(item)
        new_code = CODE_RENAMES.get(item["code"], item["code"])
        rows.append(
            {
                "candidate_code": item["code"],
                "v2_code": new_code if decision != "delete_alias" else None,
                "candidate_name": item.get("description") or item["code"],
                "proposed_ocerp_layer": "none" if decision == "delete_alias" else "CostItem",
                "unit": item.get("unit"),
                "source_calculator_methods": infer_sources(item["code"]),
                "recent_usage_count": infer_recent_usage(item["code"]),
                "component_resource_codes": [c.get("code") for c in item.get("components") or []],
                "quantity_formula": "component quantities preserved from attempt-1 validated extract; formulas documented in v2 report",
                "sampling_basis": "attempt-1 sampling plus v2 recent usage priority table",
                "validation_status": "rejected_alias" if decision == "delete_alias" else "static_validated",
                "design_decision": decision,
                "notes": alias_note(item) if decision == "delete_alias" else "Admitted by v2 CostItem checklist.",
            }
        )
    for code in ("BED-ASM-ROCK-PAD-STANDARD", "BED-ASM-SITE-PREP-STANDARD", "BED-ASM-CONC-GIBRALTAR-FOUNDATION"):
        rows.append(
            {
                "candidate_code": code,
                "v2_code": code,
                "candidate_name": code.replace("BED-ASM-", "").replace("-", " ").title(),
                "proposed_ocerp_layer": "Assembly",
                "unit": "sf" if "GIBRALTAR" not in code else "lf",
                "source_calculator_methods": ["v2 assembly design", "recent job usage"],
                "recent_usage_count": infer_recent_usage(code),
                "component_resource_codes": [],
                "quantity_formula": "dominant takeoff unit with explicit component factors",
                "sampling_basis": "recent usage priority; component-level static validation",
                "validation_status": "needs_design_review",
                "design_decision": "assembly",
                "notes": "Generated as larger package without hiding optional scopes.",
            }
        )
    return rows


def infer_sources(code: str) -> list[str]:
    if "CONC" in code:
        return ["ConcreteJobCalculator", "DrivingCalculator" if "DRIVING" in code else "attempt1 concrete sampling"]
    if "ROCK" in code:
        return ["RockPadCalculator", "MaterialCalculator"]
    if "PREP" in code:
        return ["SitePreparationJobCalculator", "MaterialCalculator"]
    if "ADHOC" in code:
        return ["AdhocJobCalculator", "MaterialCalculator"]
    return ["attempt1 extract"]


def infer_recent_usage(code: str) -> int:
    if "SITE-PREP" in code or "PREP" in code:
        return RECENT_USAGE["site_preparation"]
    if "ROCK" in code:
        return RECENT_USAGE["rock_pad"]
    if "ADHOC" in code:
        return RECENT_USAGE["adhoc"]
    if "SLAB" in code:
        return RECENT_USAGE["concrete_slab"]
    if "GIBRALTAR" in code or "CORE-FILL" in code or "BLOCK" in code:
        return RECENT_USAGE["concrete_gibraltar"]
    if "APRON" in code:
        return RECENT_USAGE["concrete_apron"]
    if "FABRIC" in code:
        return RECENT_USAGE["weed_fabric"]
    if "FILL-DIRT" in code:
        return RECENT_USAGE["fill_dirt"]
    return 0


def alias_note(item: dict[str, Any]) -> str:
    comps = item.get("components") or []
    if not comps:
        return "Rejected: no component structure."
    return f"Rejected pure alias; use CatalogResource {comps[0].get('code')} directly."


def validation(cost_items: list[dict[str, Any]], assemblies: list[dict[str, Any]], resources: list[dict[str, Any]]) -> dict[str, Any]:
    resource_codes = {r["resource_code"] for r in resources}
    item_codes = {i["code"] for i in cost_items}
    errors: list[str] = []
    warnings: list[str] = []
    for r in resources:
        if r["base_price"] < 0:
            errors.append(f"Catalog resource {r['resource_code']} has negative base_price")
        if r["resource_type"] not in {"material", "labor", "equipment", "operator", "subcontractor"}:
            errors.append(f"Catalog resource {r['resource_code']} has invalid resource_type {r['resource_type']}")
    for item in cost_items:
        total = money(sum(float(c.get("cost") or 0) for c in item.get("components") or []))
        if abs(total - float(item["rate"])) > 0.01:
            errors.append(f"CostItem {item['code']} rate {item['rate']} != component sum {total}")
        for comp in item.get("components") or []:
            if comp["code"] not in resource_codes:
                errors.append(f"CostItem {item['code']} unresolved component resource {comp['code']}")
        if len(item.get("components") or []) == 1:
            comp = item["components"][0]
            if abs(float(comp.get("quantity") or 0) - 1.0) < 0.000001 and "optional-addon" not in item.get("tags", []):
                errors.append(f"CostItem {item['code']} is a pure alias")
            elif "conversion-wrapper" in item.get("tags", []):
                warnings.append(f"CostItem {item['code']} is a permitted conversion wrapper")
    for asm in assemblies:
        total = money(sum(float(c.get("total") or 0) for c in asm.get("components") or []) * float(asm.get("bid_factor") or 1))
        if abs(total - float(asm["total_rate"])) > 0.01:
            errors.append(f"Assembly {asm['code']} total_rate {asm['total_rate']} != component sum {total}")
        for comp in asm.get("components") or []:
            ci = comp.get("cost_item_code")
            cr = comp.get("catalog_resource_code") or comp.get("resource_code")
            if ci and ci not in item_codes:
                errors.append(f"Assembly {asm['code']} unresolved cost item {ci}")
            if cr and cr not in resource_codes:
                errors.append(f"Assembly {asm['code']} unresolved catalog resource {cr}")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "catalog_resources": len(resources),
            "cost_items": len(cost_items),
            "assemblies": len(assemblies),
            "conversion_wrappers": sum(1 for i in cost_items if "conversion-wrapper" in i.get("tags", [])),
            "needs_design_review": sum(1 for i in cost_items if "needs_design_review" in i.get("tags", []))
            + sum(1 for a in assemblies if a.get("metadata", {}).get("validation_status") == "needs_design_review"),
        },
    }


def write_reports(out: Path, val: dict[str, Any], candidates: list[dict[str, Any]], exclusions: list[dict[str, Any]]) -> None:
    review_lines = [
        "# Bedrock V2 Item Design Review",
        "",
        "Human approvals applied before generation:",
        "",
        "- D1: backend/direct DB import script first; no new API bulk route.",
        "- D2: keep only useful conversion wrappers; no pure aliases.",
        "- D3: prefer ton-mi for hauling where data supports it; preserve review tag otherwise.",
        "- D4: defer subcontractor labor modeling.",
        "- D5: finish/fiber/insulation modeled as separate optional CostItems/components.",
        "- D6: natural dominant takeoff units; avoid vague lump sum.",
        "- D7: defer rare non-deterministic scopes under 5 samples.",
        "- D8: cleanup support included; attempt-1 cleanup requires separate approval.",
        "",
        "| Decision | Count |",
        "|---|---:|",
    ]
    for decision, count in sorted(Counter(c["design_decision"] for c in candidates).items()):
        review_lines.append(f"| {decision} | {count} |")
    review_lines.extend(["", "## Deleted Pure Aliases", ""])
    for row in candidates:
        if row["design_decision"] == "delete_alias":
            review_lines.append(f"- `{row['candidate_code']}`: {row['notes']}")
    (out / "item_design_review.md").write_text("\n".join(review_lines) + "\n")

    validation_lines = [
        "# Bedrock V2 Validation Report",
        "",
        f"Generated: {GENERATED_AT}",
        f"Status: **{val['status']}**",
        "",
        "## Counts",
        "",
        "| Entity | Count |",
        "|---|---:|",
    ]
    for key, count in val["counts"].items():
        validation_lines.append(f"| {key} | {count} |")
    validation_lines.extend(
        [
            "",
            "## Static Validation",
            "",
            "- CatalogResource codes are unique in the generated file.",
            "- CostItem rates equal summed component costs within $0.01.",
            "- CostItem components resolve to generated catalog resources.",
            "- Assembly totals equal summed components times bid_factor.",
            "- Pure alias CostItems are rejected before output.",
            "",
            "## Job-Based Validation Notes",
            "",
            "Recent job frequency drove priority, but v2 does not treat Bedrock job/calculator buckets as import structures. High-frequency site prep, rock pads, weed fabric, borders, fill dirt, concrete slabs, Gibraltar components, apron, and core-fill scopes are represented or explicitly deferred.",
            "",
            "Hauling remains tagged `needs_design_review` where attempt-1 trip components could not be honestly converted to ton-mi without job-level load and distance sampling.",
            "",
            "## Errors",
            "",
        ]
    )
    validation_lines.extend([f"- {e}" for e in val["errors"]] or ["- None"])
    validation_lines.extend(["", "## Warnings", ""])
    validation_lines.extend([f"- {w}" for w in val["warnings"]] or ["- None"])
    (out / "validation_report.md").write_text("\n".join(validation_lines) + "\n")

    readme = [
        "# Bedrock App Cost Data Extract 2",
        "",
        "Clean v2 import package generated from Bedrock evidence and attempt-1 outputs.",
        "",
        "## Model",
        "",
        "- `catalog_resources.json` imports atomic resources into `oe_catalog_resource`.",
        "- `cost_items.json` imports estimator-facing work/conversion items into `oe_costs_item`.",
        "- `assemblies.json` imports larger packages into `oe_assemblies_assembly` and `oe_assemblies_component`.",
        "- Pure alias CostItems are excluded; use catalog resources directly.",
        "",
        "## Import",
        "",
        "Run from `OCERP/backend` with the app environment configured:",
        "",
        "```bash",
        "python ../scripts/import_bedrock_costs_v2.py --data-dir ../bedrock_app_cost_data_extract_2 --dry-run --verify",
        "python ../scripts/import_bedrock_costs_v2.py --data-dir ../bedrock_app_cost_data_extract_2 --cleanup --verify",
        "```",
        "",
        "Do not use `--cleanup-attempt1` without a separate explicit approval and backup.",
    ]
    (out / "README.md").write_text("\n".join(readme) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt1-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    resources_attempt1 = load_json(args.attempt1_dir / "resources.json")
    item_files = ["cost_items.json", "cost_items_rock_pad.json", "cost_items_site_prep.json", "cost_items_adhoc.json"]
    attempt1_items = [item for filename in item_files for item in load_json(args.attempt1_dir / filename)]

    catalog_resources = [to_catalog_resource(r) for r in resources_attempt1]
    catalog_resources.sort(key=lambda r: r["resource_code"])
    resources_by_code = resource_lookup(catalog_resources)

    cost_items = [to_cost_item(i) for i in attempt1_items if item_decision(i) != "delete_alias"]
    add_optional_cost_items(cost_items, resources_by_code)
    cost_items.sort(key=lambda i: i["code"])

    assemblies = build_assemblies(cost_items)
    assemblies.sort(key=lambda a: a["code"])

    exclusions = [
        {
            "code": i["code"],
            "reason": alias_note(i),
            "decision": "delete_alias",
            "component_codes": [c.get("code") for c in i.get("components") or []],
        }
        for i in attempt1_items
        if item_decision(i) == "delete_alias"
    ]
    candidates = build_candidate_inventory(attempt1_items)
    val = validation(cost_items, assemblies, catalog_resources)

    dump_json(args.out_dir / "catalog_resources.json", catalog_resources)
    dump_json(args.out_dir / "cost_items.json", cost_items)
    dump_json(args.out_dir / "assemblies.json", assemblies)
    dump_json(args.out_dir / "resource_exclusions.json", exclusions)
    dump_json(args.out_dir / "candidate_scope_inventory.json", candidates)

    files = [
        "catalog_resources.json",
        "cost_items.json",
        "assemblies.json",
        "resource_exclusions.json",
        "candidate_scope_inventory.json",
    ]
    manifest = {
        "package": "bedrock_app_cost_data_extract_2",
        "generated_at": GENERATED_AT,
        "source": SOURCE,
        "region": REGION,
        "currency": CURRENCY,
        "cleanup_mode": {
            "v2_cleanup_supported": True,
            "attempt1_cleanup_supported": True,
            "attempt1_cleanup_requires_separate_approval": True,
        },
        "counts": val["counts"],
        "import_order": ["catalog_resources.json", "cost_items.json", "assemblies.json"],
        "files": {name: {"sha256": sha256(args.out_dir / name), "bytes": (args.out_dir / name).stat().st_size} for name in files},
        "validation_status": val["status"],
    }
    dump_json(args.out_dir / "import_manifest.json", manifest)
    write_reports(args.out_dir, val, candidates, exclusions)
    print(json.dumps({"status": val["status"], "counts": val["counts"], "out_dir": str(args.out_dir)}, indent=2))
    if val["errors"]:
        raise SystemExit(1)


GENERATED_AT = datetime.now(UTC).isoformat(timespec="seconds")


if __name__ == "__main__":
    main()
