#!/usr/bin/env python3
"""Fix all $0 rate items across the BOQ."""

import json
import sys
import urllib.request
import urllib.error
import uuid

BOQ_ID = "61839ac6-2af4-41ca-a385-c9b1c3516bf1"
BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None

# Cost item IDs
DEM_CON_ID = "4b9154e7-443e-414c-8853-3a2e0abb5105"  # DEM-CON-01 $4.25/SF
DEM_ASP_ID = "79eaca0a-1fcb-4015-ad76-ececa014ebbb"  # DEM-ASP-01 $3.50/SF

UPDATES = {
    # Tier 1: Rates in description
    "2ea58e18-f90b-418f-a162-e2147a67b0d9": {  # 01.08 Erosion controls
        "unit_rate": 5.00,
    },
    "b260bf66-9aaa-4bac-85fc-95965904d186": {  # 01.10 Orange fence
        "unit_rate": 5.00,
    },
    "dabc0065-026c-40da-a348-b4230eb28e54": {  # 02.05 Shed/treehouse
        "unit_rate": 750.00,
    },
    "4f4b1efc-dc3b-4362-8694-74374b265431": {  # 02.08 Dumpster
        "unit_rate": 800.00,
    },
    "cb92fece-0307-4401-9e94-f1ac10527d58": {  # 02.09 Haul concrete
        "unit_rate": 450.00,
    },
    "ebbaffd3-cc66-4a25-b233-4b8c124c955b": {  # 02.10 Haul asphalt
        "unit_rate": 450.00,
    },
    "0e37675f-7b82-4267-9458-445442db396c": {  # 31.06 Straw mulch
        "unit": "SF",
        "quantity": 11500,
        "unit_rate": 0.08,
    },
    "d5bc85b8-ed28-4b8d-9f31-a23a83df6f58": {  # 33.40.02 Geotextile pit
        "unit_rate": 0.75,
    },
    "e447154b-c2eb-4a16-9969-32b481572058": {  # 33.40.03 Coarse sand
        "unit_rate": 35.00,
    },
    "894de9e4-13d3-4726-9e0f-7c3b6d88e90b": {  # 33.40.05 #8 stone
        "unit_rate": 55.00,
    },
    "7d8554b6-0ff3-47cd-a2a2-8ea2d1c51051": {  # 33.40.06 Observation wells
        "unit_rate": 300.00,
    },
    "47c8f6c7-80d4-40d3-b535-f2cc46bba566": {  # 33.40.07 Geotextile rolls
        "unit": "SF",
        "quantity": 6000,
        "unit_rate": 0.75,
    },
    "9cacc792-250c-423b-917a-e5993bdec2a2": {  # 33.40.08 Pipe for obs wells
        "unit_rate": 400.00,
    },
    "195f7846-5865-476b-9088-f9aef0ff5c96": {  # 32.06 Mill/overlay curb
        "unit_rate": 2500.00,
    },
    "8e28bc26-bf6d-4c56-8154-37a31f0e2651": {  # 32.07 Driveway ramp excav
        "unit_rate": 3500.00,
    },
    "8200662d-6d44-4818-9312-bd9e4f8a2d2f": {  # 32.08 Utility trench repair
        "unit_rate": 2500.00,
    },
}

# Items to update with cost_item_id link
LINKED_UPDATES = {
    "b1aec252-5dd9-4601-bf77-950b49863b38": {  # 02.06 Concrete removal
        "unit_rate": 4.25,
        "cost_item_id": DEM_CON_ID,
    },
    "9392874c-3420-4068-833d-aa848ea90ead": {  # 02.14 Asphalt driveway removal
        "unit_rate": 3.50,
        "cost_item_id": DEM_ASP_ID,
    },
}

# Items to delete
DELETIONS = [
    "b6ce3ae7-0a88-41e4-8004-81bfa1315ac0",  # 02.11 Demo labor (double-counted)
    "653cf96d-06ed-419f-9512-19b3a0bb628c",  # 01.13 Foundation elevation (part of 01.12)
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
    print("✗ Login failed")
    sys.exit(1)


def update_position(position_id, data):
    r = api("PATCH", f"/boq/positions/{position_id}", data)
    return r


def delete_position(position_id):
    r = api("DELETE", f"/boq/positions/{position_id}")
    return r is not None


def get_positions():
    r = api("GET", f"/boq/boqs/{BOQ_ID}")
    if r:
        return r.get("positions", [])
    return []


def reorder(position_ids):
    r = api("POST", f"/boq/boqs/{BOQ_ID}/positions/reorder/", {"position_ids": position_ids})
    return r


def main():
    login()

    print("\n--- Updating $0 rate items ---")
    for pid, changes in UPDATES.items():
        r = update_position(pid, changes)
        if r:
            print(f"  ✓ {r.get('ordinal', pid)}: {changes}")
        else:
            print(f"  ✗ Failed: {pid}")

    print("\n--- Updating items with cost item linkage ---")
    for pid, changes in LINKED_UPDATES.items():
        r = update_position(pid, changes)
        if r:
            print(f"  ✓ {r.get('ordinal', pid)}: rate=${changes.get('unit_rate','?')} + cost_item linked")
        else:
            print(f"  ✗ Failed: {pid}")

    print("\n--- Deleting duplicate items ---")
    for pid in DELETIONS:
        if delete_position(pid):
            print(f"  ✓ Deleted: {pid}")
        else:
            print(f"  ✗ Failed: {pid}")

    # Reorder to clean up
    print("\n--- Reordering ---")
    positions = get_positions()
    real = [p for p in positions if p.get("unit") != "section"]
    sections = [p for p in positions if p.get("unit") == "section"]

    by_div = {}
    for p in real:
        ord_ = p["ordinal"]
        div = ord_.split(".")[0]
        by_div.setdefault(div, []).append(p)
    for div in by_div:
        by_div[div].sort(key=lambda p: p["ordinal"])

    section_map = {s["ordinal"]: s["id"] for s in sections}
    ordered_ids = []
    for div in ["01", "02", "31", "32", "33", "33.40", "90"]:
        sid = section_map.get(div) or section_map.get({"33.40": "33S"}.get(div, ""))
        if sid:
            ordered_ids.append(sid)
        for p in by_div.get(div, []):
            ordered_ids.append(p["id"])

    r = reorder(ordered_ids)
    print(f"  {'✓' if r else '✗'} Reordered")

    # Summary
    print("\n" + "=" * 65)
    print("SUMMARY — All items with new rates")
    print("=" * 65)
    positions = get_positions()
    real = [p for p in positions if p.get("unit") != "section"]
    grand = 0
    for p in real:
        qty = float(p.get("quantity", 0) or 0)
        rate = float(p.get("unit_rate", 0) or 0)
        total = qty * rate
        grand += total
        print(f"  {p['ordinal']:<12} ${total:>8,.2f}  {p['description'][:60]}")
    print("-" * 65)
    print(f"  {'TOTAL':<12} ${grand:>8,.2f}")


if __name__ == "__main__":
    main()
