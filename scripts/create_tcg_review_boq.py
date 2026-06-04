#!/usr/bin/env python3
"""Create a small TCG review BOQ from the review-slice CostItems.

This script is intentionally for app review/testing, not the final TCG import.
It creates a BOQ with nested MasterFormat-style sections and positions linked
to the imported `BEDROCK-TCG-REVIEW` CostItems.

Run from OCERP/:

    python scripts/create_tcg_review_boq.py --replace
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
DEFAULT_REGION = "BEDROCK-TCG-REVIEW"
DEFAULT_BOQ_NAME = "TCG Review Slice BOQ — Stormwater + Utilities"

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
                "Review-only BOQ generated from BEDROCK-TCG-REVIEW CostItems. "
                "Used to inspect resource/component/CostItem organization before full TCG import."
            ),
            "estimate_type": "review_slice",
            "base_date": "2026-Q2",
        },
    )


def create_section(boq_id: str, ordinal: str, description: str, parent_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ordinal": ordinal,
        "description": description,
        "metadata": {
            "review_only": True,
            "generated_by": "scripts/create_tcg_review_boq.py",
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
            "source": "bedrock_tcg_review_slice_import_1",
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
        "TCG-DELIVER-57-STONE-FD",
        "TCG-DELIVER-SAND-FD",
        "TCG-PLACE-AGGREGATE-FD",
        "TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE",
        "TCG-UTILITY-TRENCHING-CONDUIT-SCOPE",
    ]
    missing = [code for code in required if code not in items]
    if missing:
        raise SystemExit(f"Missing CostItems in {args.region}: {missing}")

    boq = create_boq(args.project_id, args.name)
    boq_id = boq["id"]
    print(f"Created BOQ {boq_id} — {args.name}")

    utilities = create_section(boq_id, "33 00 00", "Utilities", None)
    stormwater = create_section(
        boq_id,
        "33 40 00",
        "Stormwater Drainage — French Drain Filtration Pit",
        utilities["id"],
    )
    trenching = create_section(
        boq_id,
        "33 05 00",
        "Utility Trenching, Conduit, Pipe, and Backfill",
        utilities["id"],
    )

    positions = [
        add_position(
            boq_id,
            stormwater["id"],
            "33 40 10",
            "Deliver #57 stone for French drain filtration pit",
            "t",
            863.8,
            items["TCG-DELIVER-57-STONE-FD"],
            {"source_job_id": 38396, "assembly_code": "TCG-ASM-STORMWATER-FRENCH-DRAIN-DRAFT"},
        ),
        add_position(
            boq_id,
            stormwater["id"],
            "33 40 20",
            "Deliver sand bedding for French drain filtration pit",
            "CY",
            78.0,
            items["TCG-DELIVER-SAND-FD"],
            {"source_job_id": 38396, "assembly_code": "TCG-ASM-STORMWATER-FRENCH-DRAIN-DRAFT"},
        ),
        add_position(
            boq_id,
            stormwater["id"],
            "33 40 30",
            "Place aggregate layers for French drain filtration pit",
            "LS",
            1.0,
            items["TCG-PLACE-AGGREGATE-FD"],
            {"source_job_id": 38396, "assembly_code": "TCG-ASM-STORMWATER-FRENCH-DRAIN-DRAFT"},
        ),
        add_position(
            boq_id,
            stormwater["id"],
            "33 40 40",
            "Stormwater filtration fabric, observation pipe, rental equipment, and specialty labor",
            "LS",
            1.0,
            items["TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE"],
            {"source_job_id": 38396, "assembly_code": "TCG-ASM-STORMWATER-FRENCH-DRAIN-DRAFT"},
        ),
        add_position(
            boq_id,
            trenching["id"],
            "33 05 10",
            "Utility trenching, pipe/conduit installation, screenings backfill, equipment, and labor",
            "LS",
            1.0,
            items["TCG-UTILITY-TRENCHING-CONDUIT-SCOPE"],
            {"source_job_id": 38522, "draft_unit": "LS", "team_review_item": "Reconcile LF basis before final approval"},
        ),
    ]

    total = sum(float(p["total"]) for p in positions)
    print(f"Created sections: {utilities['id']}, {stormwater['id']}, {trenching['id']}")
    print(f"Created {len(positions)} linked CostItem positions")
    print(f"Direct total: ${total:,.2f}")
    print(f"BOQ URL path: /boq/boqs/{boq_id}")


if __name__ == "__main__":
    main()
