#!/usr/bin/env python3
"""
TCG Brentwood Sitework → OCERP Unified Import Script

Imports all 7 TCG sub-jobs into a single BOQ with:
- BOQ positions linked to USA_TENNESSEE cost database items
- Rock excavation allowances as separate T&M positions
- Credits/deductions as negative positions
- Dynamic rate loading from cost database
- Validation against TCG estimate totals

Usage:
    python scripts/import_tcg_job.py [--base-url URL] [--project-id ID] [--boq-id ID]
                                     [--email EMAIL] [--password PASSWORD]

Requires OCERP backend running.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None
PROJECT_ID = None
BOQ_ID = None

ROCK_HOURLY_RATE = 450.00

COST_IDS = {
    "ASP-PAV-01": None,
    "CON-CUR-01": None,
    "CON-RCB-01": None,
    "DEM-ASH-01": None,
    "DEM-CNC-01": None,
    "DEM-HSE-01": None,
    "DEM-TR-01": None,
    "DRN-PRM-01": None,
    "EQP-RNT-HMR": None,
    "EQP-RNT-STD": None,
    "EXC-BLK-01": None,
    "EXC-CRW-01": None,
    "EXC-STW-01": None,
    "EXC-TRE-01": None,
    "FILL-CMP-01": None,
    "GRD-BRM-01": None,
    "GRD-CRW-01": None,
    "GRD-SIT-01": None,
    "STN-BSE-01": None,
    "STN-FIL-01": None,
    "STR-HDW-01": None,
    "STR-RCP-18": None,
    "TST-CMP-01": None,
    "UT-COM-01": None,
    "UT-ELC-01": None,
    "UT-GAS-01": None,
    "UT-SWR-01": None,
    "UT-WTR-01": None,
}

MANUAL_RATES = {
    "SIT-LAY-01": 1200.00,
    "EQP-RNT-STD": 2000.00,
    "EQP-RNT-HMR": 24000.00,
    "TST-CMP-01": 900.00,
    "GRD-BRM-01": 15.00,
    "STN-FIL-01": 45.00,
    "DEM-TR-01": 750.00,
    "EXC-STW-01": 12.00,
    "EXC-TRE-01": 12.00,
    "ROCK-ALL-01": ROCK_HOURLY_RATE,
}

CREDIT_AMOUNTS = {
    "03.01.0100": 4500.00,
    "04.02.0080": 37000.00,
    "06.03.0040": 3200.00,
}


def api(method, path, data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        try:
            detail = json.loads(detail)
            detail = detail.get("detail", detail)
        except json.JSONDecodeError:
            pass
        print(f"  ERROR {method} {path}: {detail}", file=sys.stderr)
        return None


def login(email, password):
    global TOKEN
    if password:
        r = api("POST", "/users/auth/login/", {"email": email, "password": password})
    else:
        r = api("POST", "/users/auth/demo-login/", {"email": email})
    if r and "access_token" in r:
        TOKEN = r["access_token"]
        print(f"✓ Logged in as {email}")
        return True
    print(f"✗ Login failed for {email}"); sys.exit(1)


def load_cost_rates():
    r = api("GET", "/costs/?region=USA_TENNESSEE&limit=100")
    rates = {}
    ids = {}
    for item in r.get("items", []):
        rates[item["code"]] = item["rate"]
        if item["code"] in COST_IDS:
            ids[item["code"]] = item["id"]
    return rates, ids


def build_positions():
    positions = []

    # ── Job 1: Economy Level Site (38254) ──
    positions.extend([
        ["01.01.0010", "Cut and stockpile topsoil — 45,225 SF, stockpile on site", "CY", 200, "EXC-BLK-01", {"job": "38254"}],
        ["01.01.0020", "Excavate and level site for 5 building pads — 45,225 SF", "SF", 45225, "GRD-SIT-01", {"job": "38254"}],
        ["01.01.0030", "Import, place, and compact fill material — 1,955 CY", "CY", 1955, "FILL-CMP-01", {"job": "38254"}],
        ["01.01.0040", "Compact to 95% — subgrade preparation for 5 building sites", "SF", 45225, "GRD-SIT-01", {"job": "38254"}],
        ["01.01.0050", "Excavate and grade 6\" berms behind units 3, 4, 5", "LF", 500, "GRD-BRM-01", {"job": "38254"}],
        ["01.01.0060", "Straw mulch stabilization — all disturbed areas", "LS", 1, None, {"job": "38254"}],
        ["01.01.0070", "Soil compaction testing — 5 building sites", "EA", 5, "TST-CMP-01", {"job": "38254"}],
        ["01.01.0080", "Equipment rental — site preparation", "LS", 1, "EQP-RNT-STD", {"job": "38254"}],
    ])

    # ── Job 2: Demolition & Disposal (38304) ──
    positions.extend([
        ["02.01.0010", "Erosion controls — silt fence with steel posts and wire mesh", "LF", 325, None, {"job": "38304"}],
        ["02.01.0020", "Construction entrance 20'x100' — geotextile fabric + 8\" ballast stone", "LS", 1, None, {"job": "38304"}],
        ["02.01.0030", "Orange construction fence — NE side and around berms, 325 LF", "LF", 325, None, {"job": "38304"}],
        ["02.02.0010", "Demolish existing residence including foundation — 1,500 SF", "SF", 1500, "DEM-HSE-01", {"job": "38304"}],
        ["02.02.0020", "Demolish existing garage structure and foundation — 400 SF", "SF", 400, "DEM-HSE-01", {"job": "38304"}],
        ["02.02.0030", "Shed and treehouse removal", "EA", 2, None, {"job": "38304"}],
        ["02.02.0040", "Concrete removal — walkway, driveway, patio — 1,500 SF", "SF", 1500, "DEM-CNC-01", {"job": "38304"}],
        ["02.02.0050", "Asphalt driveway removal — 8,400 SF", "SF", 8400, "DEM-ASH-01", {"job": "38304"}],
        ["02.02.0060", "Tree removal — 12 trees", "EA", 12, "DEM-TR-01", {"job": "38304"}],
        ["02.02.0070", "Dumpster disposal — 11 loads at $800/load", "EA", 11, None, {"job": "38304"}],
        ["02.02.0080", "Haul concrete debris — 6 loads at $450/load", "EA", 6, None, {"job": "38304"}],
        ["02.02.0090", "Haul asphalt debris — 7 loads at $450/load", "EA", 7, None, {"job": "38304"}],
        ["02.02.0100", "Equipment rental — demolition", "LS", 1, "EQP-RNT-STD", {"job": "38304"}],
        ["02.02.0110", "Demo labor and supervision — 779 hours", "HR", 779, None, {"job": "38304"}],
    ])

    # ── Job 3: French Drain / Stormwater (38396) ──
    positions.extend([
        ["03.01.0010", "Stormwater excavation — 860 CY", "CY", 860, "EXC-STW-01", {"job": "38396"}],
        ["03.01.0020", "Geotextile fabric — infiltration pit, 8,326 SF", "SF", 8326, None, {"job": "38396"}],
        ["03.01.0030", "Coarse sand bedding — 3\" depth, 130 CY", "CY", 130, None, {"job": "38396"}],
        ["03.01.0040", "#57 stone — 24\" depth in infiltration pit, 620 CY", "CY", 620, "STN-FIL-01", {"job": "38396"}],
        ["03.01.0050", "#8 stone top course — 2\" depth, 50 CY", "CY", 50, None, {"job": "38396"}],
        ["03.01.0060", "Observation wells — 4 per approved plan", "EA", 4, None, {"job": "38396"}],
        ["03.01.0070", "Geotextile fabric — 12 rolls", "EA", 12, None, {"job": "38396"}],
        ["03.01.0080", "Pipe for observation wells", "LS", 1, None, {"job": "38396"}],
        ["03.01.0090", "Equipment rental — stormwater work", "LS", 1, "EQP-RNT-STD", {"job": "38396"}],
        ["03.01.0100", "Remove #8 stone from scope", "LS", 1, None, {"job": "38396", "credit": True}],
    ])
    positions.append([
        "03.02.0010",
        "ROCK ALLOWANCE: T&M rock excavation at $450/hr — cap $49,000",
        "HR", round(49000 / ROCK_HOURLY_RATE, 2), None,
        {"job": "38396", "rock_allowance": True, "cap": 49000}
    ])

    # ── Job 4: Concrete Curb (38447) ──
    positions.extend([
        ["04.01.0010", "Concrete curb and gutter — 75 LF street frontage, 3500 PSI", "LF", 75, "CON-CUR-01", {"job": "38447"}],
        ["04.01.0020", "Concrete ribbon curb — 844 LF driveway/parking perimeter, 3500 PSI", "LF", 844, "CON-RCB-01", {"job": "38447"}],
        ["04.02.0010", "Subgrade preparation — curb and walkway areas, 1,500 SF", "SF", 1500, "GRD-SIT-01", {"job": "38447"}],
        ["04.02.0020", "Stone base — 8\" #2A crushed aggregate under asphalt, 500 SF", "SF", 500, "STN-BSE-01", {"job": "38447"}],
        ["04.02.0030", "Asphalt pavement — 3.5\" hot mix, road widening area, 500 SF", "SF", 500, "ASP-PAV-01", {"job": "38447"}],
        ["04.02.0040", "Subgrade preparation — walkway areas, 2,000 SF", "SF", 2000, "GRD-SIT-01", {"job": "38447"}],
        ["04.02.0050", "Excavation and grading for driveway ramp, sidewalk, walkways", "LS", 1, None, {"job": "38447"}],
        ["04.02.0060", "Repair utility trenches on street — asphalt repair", "LS", 1, None, {"job": "38447"}],
        ["04.02.0070", "Mill and overlay existing curb", "LS", 1, None, {"job": "38447"}],
        ["04.02.0080", "Remove ribbon curb and walkway excavation from scope", "LS", 1, None, {"job": "38447", "credit": True}],
    ])

    # ── Job 5: Trenching (38522) ──
    positions.extend([
        ["05.01.0010", "Sanitary sewer — 4\" PVC SDR-35, 3' deep, 200 LF", "LF", 200, "UT-SWR-01", {"job": "38522"}],
        ["05.01.0020", "Water service — 4\" PVC C900, 3' deep, 200 LF", "LF", 200, "UT-WTR-01", {"job": "38522"}],
        ["05.02.0010", "Electrical conduit — 3\" PVC SCH 40, stone dust bed, red tracer tape, 900 LF", "LF", 900, "UT-ELC-01", {"job": "38522"}],
        ["05.02.0020", "Communications conduit — 1.5\" PVC, shared trench, 900 LF", "LF", 900, "UT-COM-01", {"job": "38522"}],
        ["05.03.0010", "Gas line trench — 3'W x 3'D, stone dust backfill, yellow tape, 400 LF", "LF", 400, "UT-GAS-01", {"job": "38522"}],
        ["05.04.0010", "18\" RCP storm pipe — Class III, 125 LF", "LF", 125, "STR-RCP-18", {"job": "38522"}],
        ["05.04.0020", "Precast concrete headwall — 18\" with outlet protection rip rap", "EA", 2, "STR-HDW-01", {"job": "38522"}],
    ])
    positions.append([
        "05.05.0010",
        "ROCK ALLOWANCE: T&M rock excavation at $450/hr — cap $23,000",
        "HR", round(23000 / ROCK_HOURLY_RATE, 2), None,
        {"job": "38522", "rock_allowance": True, "cap": 23000}
    ])

    # ── Job 6: Excavation — Crawlspace & Footers (38577) ──
    positions.extend([
        ["06.01.0010", "Crawlspace and footer excavation — 5 foundations, 720 CY", "CY", 720, "EXC-CRW-01", {"job": "38577"}],
        ["06.02.0010", "Foundation perimeter drain — 4\" corrugated perforated, geotextile wrap, #57 stone, 1,000 LF", "LF", 1000, "DRN-PRM-01", {"job": "38577"}],
        ["06.03.0010", "Fine grade crawlspace — vapor barrier + 4\" #57 stone, 5 foundations, 5,000 SF", "SF", 5000, "GRD-CRW-01", {"job": "38577"}],
        ["06.03.0020", "Fine grade garage areas — 5 garages, 2,400 SF", "SF", 2400, "GRD-SIT-01", {"job": "38577"}],
        ["06.03.0030", "Fine grade porch areas — 5 porches, 1,000 SF", "SF", 1000, "GRD-SIT-01", {"job": "38577"}],
        ["06.03.0040", "Remove fine grading of garage and porch areas from scope", "LS", 1, None, {"job": "38577", "credit": True}],
    ])
    positions.append([
        "06.04.0010",
        "ROCK ALLOWANCE: T&M rock excavation at $450/hr — cap $23,000",
        "HR", round(23000 / ROCK_HOURLY_RATE, 2), None,
        {"job": "38577", "rock_allowance": True, "cap": 23000}
    ])

    # ── Job 7: Additional Work (38578) ──
    positions.extend([
        ["07.01.0010", "Site consultation — confirm structure location, utilities, permit coordination", "LS", 1, None, {"job": "38578"}],
        ["07.01.0020", "Site layout and staking — square, stake, establish 4 building corners", "LS", 1, "SIT-LAY-01", {"job": "38578"}],
        ["07.01.0030", "Establish finished foundation elevation — positive drainage away from structure", "LS", 1, None, {"job": "38578"}],
        ["07.02.0010", "Topsoil strip and stockpile — 6\" cut, stockpile on site, 200 CY", "CY", 200, "EXC-BLK-01", {"job": "38578"}],
        ["07.02.0020", "Bulk excavation — cut to design subgrade, stockpile on site, 200 CY", "CY", 200, "EXC-BLK-01", {"job": "38578"}],
        ["07.02.0030", "Structural fill import — placement, moisture condition, compact to 95%, 200 CY", "CY", 200, "FILL-CMP-01", {"job": "38578"}],
        ["07.02.0040", "Site grading and fine grade — entire 8,400 SF disturbed area", "SF", 8400, "GRD-SIT-01", {"job": "38578"}],
    ])
    positions.append([
        "07.03.0010",
        "ROCK ALLOWANCE: T&M rock excavation at $450/hr — cap $88,000",
        "HR", round(88000 / ROCK_HOURLY_RATE, 2), None,
        {"job": "38578", "rock_allowance": True, "cap": 88000}
    ])

    return positions


def main():
    parser = argparse.ArgumentParser(description="Import TCG Brentwood jobs into OCERP BOQ")
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1", help="OCERP API base URL")
    parser.add_argument("--project-id", default="7aa0a1a5-f20e-4653-b77b-b67883c47f2e", help="Project UUID")
    parser.add_argument("--boq-id", required=True, help="BOQ UUID")
    parser.add_argument("--email", default="estimator@openestimator.io", help="Login email")
    parser.add_argument("--password", default=None, help="Login password (omit for demo login)")
    args = parser.parse_args()

    global BASE_URL, PROJECT_ID, BOQ_ID
    BASE_URL = args.base_url.rstrip("/")
    PROJECT_ID = args.project_id
    BOQ_ID = args.boq_id

    print("=" * 60)
    print("TCG Brentwood Sitework — Unified BOQ Import")
    print("=" * 60)

    login(args.email, args.password)
    cost_rates, cost_ids = load_cost_rates()
    COST_IDS.update(cost_ids)
    print(f"✓ Loaded rates for {len(cost_rates)} USA_TENNESSEE items\n")

    positions = build_positions()
    items = []
    grand_total = 0.0
    credits_total = 0.0
    rock_allowance_total = 0.0

    for ordinal, desc, unit, qty, code, meta in positions:
        is_credit = meta.get("credit", False)
        is_rock = meta.get("rock_allowance", False)

        if is_credit:
            credit_amt = CREDIT_AMOUNTS.get(ordinal, 0.0)
            rate = credit_amt
            total = -abs(credit_amt)
            credits_total += total
            desc = f"CREDIT: {desc}"
        elif is_rock:
            rate = ROCK_HOURLY_RATE
            total = round(qty * rate, 2)
            rock_allowance_total += total
        elif code and code in cost_rates:
            rate = cost_rates[code]
            total = round(qty * rate, 2)
        elif code and code in MANUAL_RATES:
            rate = MANUAL_RATES[code]
            total = round(qty * rate, 2)
        else:
            rate = 0.0
            total = 0.0

        grand_total += total

        item = {
            "ordinal": ordinal,
            "description": desc,
            "unit": unit,
            "quantity": qty,
            "unit_rate": rate,
            "source": "manual" if code is None else "cost_database",
            "classification": {},
            "metadata": meta,
        }
        if code and code in COST_IDS and COST_IDS[code]:
            item["cost_item_id"] = COST_IDS[code]
        items.append(item)

    print(f"{'Ordinal':<14} {'Description':<55} {'Qty':>7} {'Unit':>4} {'Rate':>9} {'Total':>11}")
    print("─" * 105)

    for item in items:
        total = round(item["quantity"] * item["unit_rate"], 2)
        if item["metadata"].get("credit"):
            total = -abs(total)
        sign = "−" if total < 0 else ""
        print(f"{item['ordinal']:<14} {item['description'][:55]:<55} {item['quantity']:>7} {item['unit']:>4} ${item['unit_rate']:>8.2f} {sign}${abs(total):>10,.2f}")

    print("─" * 105)
    print(f"{'POSITIONS:':<74} {len(items):>7} {'DIRECT COST:':>20} ${grand_total:>10,.2f}")
    print(f"{'Rock allowances:':<74} ${rock_allowance_total:>10,.2f}")
    print(f"{'Credits:':<74} ${credits_total:>10,.2f}")
    print("─" * 105)

    payload = {"items": items}
    print(f"\nImporting {len(items)} positions to BOQ {BOQ_ID}...")
    result = api("POST", f"/boq/boqs/{BOQ_ID}/positions/bulk/", payload)

    if result is None:
        print("✗ Import failed")
        sys.exit(1)

    print(f"✓ Imported {len(result)} positions")

    expected_total = 445447.80
    print(f"\nImported total: ${grand_total:,.2f}")
    print(f"TCG estimate total: ${expected_total:,.2f}")
    diff = abs(grand_total - expected_total)
    pct = (diff / expected_total) * 100
    if pct < 10:
        print(f"✓ Within {pct:.1f}% of TCG estimate total")
    else:
        print(f"⚠ {pct:.1f}% variance from TCG estimate total — review rates")

    print(f"\nBOQ URL: /boq/boqs/{BOQ_ID}")


if __name__ == "__main__":
    main()
