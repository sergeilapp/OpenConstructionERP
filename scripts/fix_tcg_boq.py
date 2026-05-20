#!/usr/bin/env python3
"""Fix MasterFormat classification and add missing credits/allowances."""

import json
import sys
import urllib.request
import urllib.error

BOQ_ID = "61839ac6-2af4-41ca-a385-c9b1c3516bf1"
BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None

# Position ID → new ordinal
FIXES = {
    # Division 01 items that should be elsewhere
    "01.03": "02.12",   # Asphalt driveway removal → Demolition
    "01.06": "32.07",   # Excavation for driveway ramp → Exterior
    "01.07": "32.08",   # Repair utility trenches → Exterior
    "01.08": "31.12",   # Crawlspace excavation → Earthwork
    "01.09": "31.13",   # Fine grade garage → Earthwork
    "01.10": "31.14",   # Fine grade porch → Earthwork
    # Division 02 items that should be elsewhere
    "02.12": "32.09",   # Stone base → Exterior
    # Division 31 items that should be elsewhere
    "31.07": "02.13",   # Orange construction fence → Demolition/erosion
    # Division 33S items that should be elsewhere
    "33S.09": "33.08",  # Foundation perimeter drain → Utilities
    "33S.10": "31.15",  # Fine grade crawlspace → Earthwork
}

MISSING = [
    {
        "ordinal": "33S.11",
        "description": "CREDIT: Remove #8 stone from scope",
        "unit": "LS", "quantity": 1, "unit_rate": 4500, "total": -4500,
        "source": "manual", "metadata": {"job": "38396", "credit": True}
    },
    {
        "ordinal": "32.10",
        "description": "CREDIT: Remove ribbon curb and walkway excavation from scope",
        "unit": "LS", "quantity": 1, "unit_rate": 37000, "total": -37000,
        "source": "manual", "metadata": {"job": "38447", "credit": True}
    },
    {
        "ordinal": "31.16",
        "description": "CREDIT: Remove fine grading of garage and porch areas from scope",
        "unit": "LS", "quantity": 1, "unit_rate": 3200, "total": -3200,
        "source": "manual", "metadata": {"job": "38577", "credit": True}
    },
    {
        "ordinal": "90.02",
        "description": "ROCK ALLOWANCE: T&M rock excavation at $450/hr — cap $49,000",
        "unit": "HR", "quantity": 108.89, "unit_rate": 450, "total": 49000.5,
        "source": "manual", "metadata": {"job": "38396", "rock_allowance": True, "cap": 49000}
    },
    {
        "ordinal": "90.03",
        "description": "ROCK ALLOWANCE: T&M rock excavation at $450/hr — cap $23,000",
        "unit": "HR", "quantity": 51.11, "unit_rate": 450, "total": 22999.5,
        "source": "manual", "metadata": {"job": "38522", "rock_allowance": True, "cap": 23000}
    },
    {
        "ordinal": "90.04",
        "description": "ROCK ALLOWANCE: T&M rock excavation at $450/hr — cap $23,000",
        "unit": "HR", "quantity": 51.11, "unit_rate": 450, "total": 22999.5,
        "source": "manual", "metadata": {"job": "38577", "rock_allowance": True, "cap": 23000}
    },
]


def api(method, path, data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            return json.loads(body) if body.strip() else True
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        try:
            detail = json.loads(detail)
            detail = detail.get("detail", detail)
        except json.JSONDecodeError:
            pass
        print(f"  ERROR {method} {path}: {detail}", file=sys.stderr)
        return None


def login():
    global TOKEN
    r = api("POST", "/users/auth/demo-login/", {"email": "estimator@openestimator.io"})
    if r and "access_token" in r:
        TOKEN = r["access_token"]
        print("✓ Logged in")
        return True
    print("✗ Login failed"); sys.exit(1)


def get_positions():
    r = api("GET", f"/boq/boqs/{BOQ_ID}")
    if r:
        return r.get("positions", [])
    return []


def update_ordinal(position_id, new_ordinal):
    r = api("PATCH", f"/boq/positions/{position_id}", {"ordinal": new_ordinal})
    return r is not None


def add_position(data):
    r = api("POST", f"/boq/boqs/{BOQ_ID}/positions/", data)
    return r


def reorder(position_ids):
    r = api("POST", f"/boq/boqs/{BOQ_ID}/positions/reorder/", {"position_ids": position_ids})
    return r


def main():
    login()

    positions = get_positions()
    real = [p for p in positions if p.get("unit") != "section"]
    sections = [p for p in positions if p.get("unit") == "section"]
    print(f"✓ Found {len(real)} positions, {len(sections)} sections")

    # Build lookup by ordinal
    by_ordinal = {}
    for p in real:
        by_ordinal[p["ordinal"]] = p

    # Fix misclassified items
    print("\nFixing misclassified items...")
    for old_ord, new_ord in FIXES.items():
        p = by_ordinal.get(old_ord)
        if p:
            if update_ordinal(p["id"], new_ord):
                print(f"  ✓ {old_ord} → {new_ord}: {p['description'][:40]}")
                by_ordinal[new_ord] = by_ordinal.pop(old_ord)
                by_ordinal[new_ord]["ordinal"] = new_ord
            else:
                print(f"  ✗ Failed: {old_ord} → {new_ord}")

    # Add missing positions
    print("\nAdding missing credits and rock allowances...")
    for item in MISSING:
        item["boq_id"] = BOQ_ID
        r = add_position(item)
        if r:
            print(f"  ✓ Added: {item['ordinal']} {item['description'][:40]}")
            by_ordinal[item["ordinal"]] = r
        else:
            print(f"  ✗ Failed: {item['ordinal']}")

    # Re-fetch to get updated list with new items
    positions = get_positions()
    real = [p for p in positions if p.get("unit") != "section"]
    sections = [p for p in positions if p.get("unit") == "section"]

    # Group by division prefix
    by_div = {}
    for p in real:
        ord_ = p["ordinal"]
        # Extract division prefix (01, 02, 31, 32, 33, 33S, 90)
        if ord_.startswith("33S"):
            div = "33S"
        else:
            div = ord_.split(".")[0]
        by_div.setdefault(div, []).append(p)

    # Sort each division by ordinal
    for div in by_div:
        by_div[div].sort(key=lambda p: p["ordinal"])

    # Build ordered list
    section_map = {s["ordinal"]: s["id"] for s in sections}
    ordered_ids = []
    for div in ["01", "02", "31", "32", "33", "33S", "90"]:
        sid = section_map.get(div)
        if sid:
            ordered_ids.append(sid)
        for p in by_div.get(div, []):
            ordered_ids.append(p["id"])

    # Reorder
    print(f"\nReordering {len(ordered_ids)} items...")
    r = reorder(ordered_ids)
    if r:
        print("✓ BOQ reordered")
        print("\nFinal structure:")
        for div in ["01", "02", "31", "32", "33", "33S", "90"]:
            count = len(by_div.get(div, []))
            name = {
                "01": "General Requirements",
                "02": "Existing Conditions / Demolition",
                "31": "Earthwork & Grading",
                "32": "Exterior Improvements",
                "33": "Utilities",
                "33S": "Stormwater Systems",
                "90": "Credits & Allowances"
            }.get(div, div)
            print(f"  {div:<5s} {name:<35s} {count:>3d} positions")
    else:
        print("✗ Reorder failed")


if __name__ == "__main__":
    main()
