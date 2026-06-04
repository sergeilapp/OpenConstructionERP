#!/usr/bin/env python3
"""Create a TCG extract 2 BOQ organized by MasterFormat sections.

Builds a BOQ from the BEDROCK-TCG-EXTRACT-2 CostItems, grouped into
Division-level MasterFormat sections with nested sub-sections.

Run from OCERP/:

    python scripts/create_tcg_extract2_boq.py --replace
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_PROJECT_ID = "8e5817aa-16b6-428f-bd2c-a340d1283d1f"  # TCG Brentwood Sitework
DEFAULT_REGION = "BEDROCK-TCG-EXTRACT-2"
DEFAULT_BOQ_NAME = "TCG Extract 2 — Unitized CostItems by MasterFormat"

TOKEN: str | None = None
BASE_URL = DEFAULT_BASE_URL


def api(method: str, path: str, data: dict[str, Any] | None = None) -> Any:
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = raw
        print(f"ERROR {method} {path}: {detail}", file=sys.stderr)
        raise


def login(email: str, password: str | None) -> None:
    global TOKEN
    if password:
        res = api("POST", "/users/auth/login/", {"email": email, "password": password})
    else:
        res = api("POST", "/users/auth/demo-login/", {"email": email})
    TOKEN = res["access_token"]


def cost_items_by_code(region: str) -> dict[str, dict[str, Any]]:
    res = api("GET", f"/costs/?region={urllib.parse.quote(region)}&search=TCG&limit=50")
    items = res.get("items", [])
    return {item["code"]: item for item in items}


def existing_boqs(project_id: str) -> list[dict[str, Any]]:
    return api("GET", f"/boq/boqs/?project_id={project_id}&limit=100")


def create_boq(project_id: str, name: str) -> dict[str, Any]:
    return api(
        "POST",
        "/boq/boqs/",
        {
            "project_id": project_id,
            "name": name,
            "description": (
                "Review-only BOQ generated from BEDROCK-TCG-EXTRACT-2 CostItems. "
                "Organized by MasterFormat Division with nested sections. "
                "Includes 15 carried-forward DELIVER/scope items + 7 unitized CostItems."
            ),
            "estimate_type": "detailed_estimate",
            "base_date": "2026-Q2",
        },
    )


def create_section(boq_id: str, ordinal: str, description: str, parent_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ordinal": ordinal,
        "description": description,
        "metadata": {
            "review_only": True,
            "generated_by": "scripts/create_tcg_extract2_boq.py",
            "section_type": "masterformat",
        },
    }
    if parent_id:
        payload["parent_id"] = parent_id
    return api("POST", f"/boq/boqs/{boq_id}/sections/", payload)


def add_position(
    boq_id: str,
    parent_id: str,
    ordinal: str,
    description: str,
    unit: str,
    quantity: float,
    cost_item: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    classification = dict(cost_item.get("classification") or {})
    payload = {
        "boq_id": boq_id,
        "parent_id": parent_id,
        "ordinal": ordinal,
        "description": description,
        "unit": unit,
        "quantity": quantity,
        "unit_rate": float(cost_item["rate"]),
        "source": "cost_database",
        "classification": classification,
        "cost_item_id": cost_item["id"],
        "metadata": {
            "review_only": True,
            "cost_item_code": cost_item["code"],
            "cost_item_region": cost_item.get("region"),
            "source": "bedrock_tcg_model_job_extract_2",
            **(metadata or {}),
        },
    }
    return api("POST", f"/boq/boqs/{boq_id}/positions/", payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--name", default=DEFAULT_BOQ_NAME)
    parser.add_argument("--email", default="demo@openestimator.io")
    parser.add_argument("--password", default=None)
    parser.add_argument("--replace", action="store_true", help="Delete existing BOQ with the same name before creating")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.base_url.rstrip("/")
    login(args.email, args.password)

    if args.replace:
        for boq in existing_boqs(args.project_id):
            if boq.get("name") == args.name:
                print(f"Deleting existing BOQ {boq['id']} — {boq['name']}")
                api("DELETE", f"/boq/boqs/{boq['id']}")

    items = cost_items_by_code(args.region)
    required = [
        "TCG-CONCRETE-CURB-GUTTER-UNIT",
        "TCG-CRAWLSPACE-FOOTER-EXCAVATION-UNIT",
        "TCG-DELIVER-57-STONE-CF",
        "TCG-DELIVER-57-STONE-FD",
        "TCG-DELIVER-DRAIN-STONE-CE",
        "TCG-DELIVER-FILL-REVIEW",
        "TCG-DELIVER-SAND-FD",
        "TCG-EROSION-STABILIZATION-UNIT",
        "TCG-PAVING-ASPHALT-REPAIR-SUBCONTRACT-SCOPE",
        "TCG-PLACE-AGGREGATE-UNIT",
        "TCG-PLACE-COMPACT-FILL-REVIEW",
        "TCG-PLACE-COMPACT-FILL-UNIT",
        "TCG-PLACE-TOPSOIL-REVIEW",
        "TCG-PLACE-TOPSOIL-UNIT",
        "TCG-SITE-PREP-DEMO-DISPOSAL-SCOPE",
        "TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE",
        "TCG-UTILITY-TRENCHING-CONDUIT-UNIT",
    ]
    missing = [code for code in required if code not in items]
    if missing:
        raise SystemExit(f"Missing CostItems in {args.region}: {missing}")

    boq = create_boq(args.project_id, args.name)
    boq_id = boq["id"]
    print(f"Created BOQ {boq_id} — {args.name}")

    # -- MasterFormat Division 02: Existing Conditions --
    div02 = create_section(boq_id, "02 00 00", "Existing Conditions", None)
    demo = create_section(boq_id, "02 41 00", "Demolition & Site Preparation", div02["id"])

    positions: list[dict[str, Any]] = []

    positions.append(add_position(
        boq_id, demo["id"], "02 41 10",
        "Site prep demo/disposal — equipment, labor, and driving",
        "LS", 1.0, items["TCG-SITE-PREP-DEMO-DISPOSAL-SCOPE"],
        {"source_job_id": 38304, "review_flag": "TCG-RS-R1"},
    ))
    positions.append(add_position(
        boq_id, demo["id"], "02 41 20",
        "Deliver drain stone for construction entrance",
        "t", 92.0, items["TCG-DELIVER-DRAIN-STONE-CE"],
        {"source_job_id": 38304},
    ))

    # -- MasterFormat Division 03: Concrete --
    div03 = create_section(boq_id, "03 00 00", "Concrete", None)
    curb = create_section(boq_id, "03 31 00", "Concrete Curb & Gutter", div03["id"])

    positions.append(add_position(
        boq_id, curb["id"], "03 31 10",
        "Concrete curb and gutter per linear foot",
        "LF", 75.0, items["TCG-CONCRETE-CURB-GUTTER-UNIT"],
        {"source_job_id": 38447, "review_flag": "TCG-P7-R7"},
    ))

    # -- MasterFormat Division 31: Earthwork --
    div31 = create_section(boq_id, "31 00 00", "Earthwork", None)
    fill = create_section(boq_id, "31 23 00", "Fill & Compaction", div31["id"])
    crawl = create_section(boq_id, "31 20 00", "Crawlspace Footer Drainage", div31["id"])
    erosion = create_section(boq_id, "31 25 00", "Erosion Control & Stabilization", div31["id"])
    topsoil = create_section(boq_id, "31 92 00", "Topsoil Placement", div31["id"])

    positions.append(add_position(
        boq_id, fill["id"], "31 23 10",
        "Delivered fill material review rate",
        "CY", 1955.0, items["TCG-DELIVER-FILL-REVIEW"],
        {"source_job_id": 38254, "review_flag": "TCG-P7-R3"},
    ))
    positions.append(add_position(
        boq_id, fill["id"], "31 23 20",
        "Place and compact imported fill (LS review scope — labor only)",
        "LS", 1.0, items["TCG-PLACE-COMPACT-FILL-REVIEW"],
        {"source_job_id": 38254, "equipment_rate_missing": True},
    ))
    positions.append(add_position(
        boq_id, fill["id"], "31 23 30",
        "Place and compact imported fill per cubic yard — labor only",
        "CY", 1955.0, items["TCG-PLACE-COMPACT-FILL-UNIT"],
        {"source_job_id": 38254, "equipment_rate_missing": True},
    ))
    positions.append(add_position(
        boq_id, crawl["id"], "31 20 10",
        "Deliver #57 stone for crawlspace/footer drainage",
        "t", 257.2, items["TCG-DELIVER-57-STONE-CF"],
        {"source_job_id": 38577},
    ))
    positions.append(add_position(
        boq_id, crawl["id"], "31 20 20",
        "Crawlspace/footer excavation and drainage per linear foot",
        "LF", 1000.0, items["TCG-CRAWLSPACE-FOOTER-EXCAVATION-UNIT"],
        {"source_job_id": 38577},
    ))
    positions.append(add_position(
        boq_id, erosion["id"], "31 25 10",
        "Erosion control and site stabilization per linear foot of fence",
        "LF", 440.0, items["TCG-EROSION-STABILIZATION-UNIT"],
        {"source_job_id": 38304},
    ))
    positions.append(add_position(
        boq_id, topsoil["id"], "31 92 10",
        "Place stockpiled topsoil (LS review scope)",
        "LS", 1.0, items["TCG-PLACE-TOPSOIL-REVIEW"],
        {"source_job_id": 38578},
    ))
    positions.append(add_position(
        boq_id, topsoil["id"], "31 92 20",
        "Place stockpiled topsoil per cubic yard",
        "CY", 1955.0, items["TCG-PLACE-TOPSOIL-UNIT"],
        {"source_job_id": 38578},
    ))

    # -- MasterFormat Division 32: Exterior Improvements --
    div32 = create_section(boq_id, "32 00 00", "Exterior Improvements", None)
    pave = create_section(boq_id, "32 12 00", "Asphalt Paving & Utility Trench Repair", div32["id"])

    positions.append(add_position(
        boq_id, pave["id"], "32 12 10",
        "Subcontracted paving and asphalt utility trench repair",
        "LS", 1.0, items["TCG-PAVING-ASPHALT-REPAIR-SUBCONTRACT-SCOPE"],
        {"source_job_id": 38447},
    ))

    # -- MasterFormat Division 33: Utilities --
    div33 = create_section(boq_id, "33 00 00", "Utilities", None)
    storm = create_section(boq_id, "33 40 00", "Stormwater Drainage — French Drain Filtration Pit", div33["id"])
    trench = create_section(boq_id, "33 05 00", "Utility Trenching, Conduit, and Pipe", div33["id"])

    positions.append(add_position(
        boq_id, storm["id"], "33 40 10",
        "Deliver #57 stone for French drain",
        "t", 863.8, items["TCG-DELIVER-57-STONE-FD"],
        {"source_job_id": 38396},
    ))
    positions.append(add_position(
        boq_id, storm["id"], "33 40 20",
        "Deliver sand for French drain",
        "CY", 78.0, items["TCG-DELIVER-SAND-FD"],
        {"source_job_id": 38396},
    ))
    positions.append(add_position(
        boq_id, storm["id"], "33 40 30",
        "Place and level aggregate (stone/sand) per ton",
        "t", 863.8, items["TCG-PLACE-AGGREGATE-UNIT"],
        {"source_job_id": 38396, "allocation_note": "Draft split: 89 HR from 109 HR pool"},
    ))
    positions.append(add_position(
        boq_id, storm["id"], "33 40 40",
        "Stormwater drainage filtration scope — fabric, pipe, equipment, and labor",
        "LS", 1.0, items["TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE"],
        {"source_job_id": 38396},
    ))
    positions.append(add_position(
        boq_id, trench["id"], "33 05 10",
        "Utility trenching, conduit/pipe installation per linear foot of trench",
        "LF", 1300.0, items["TCG-UTILITY-TRENCHING-CONDUIT-UNIT"],
        {"source_job_id": 38522},
    ))

    total = sum(float(p["total"]) for p in positions)
    print(f"Created {len(positions)} positions linked to CostItems")
    print(f"Direct total: ${total:,.2f}")
    print(f"BOQ URL path: /boq/boqs/{boq_id}")


if __name__ == "__main__":
    main()
