#!/usr/bin/env python3
"""Option A items 4-5: Consolidate rentals + remove duplicate compaction."""

import json
import sys
import urllib.request
import urllib.error

BOQ_ID = "61839ac6-2af4-41ca-a385-c9b1c3516bf1"
BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None

# Position IDs (from current BOQ state)
RENTAL_SITE = "5be8ae68-33f9-4efc-8e06-c566ac773794"   # 01.02 → keep + update
RENTAL_DEMO = "c5989aee-114d-4c71-86dd-f3970b8ef514"    # 01.04 → delete
RENTAL_STORM = "71a55184-70ab-4aa3-b6f9-9a7a8659156b"   # 01.05 → delete
SUBGRADE = "7bbf1de6-c41a-4f3a-8154-0fd9cff15b98"        # 31.02 → update description
COMPACT_DUP = "e3f6300b-9921-493c-861d-7d420d374527"     # 31.04 → delete


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

    print("\n--- Consolidating equipment rentals ---")

    r = update_position(RENTAL_SITE, {
        "description": "Equipment rental — excavator, skid steer, attachments (all phases)",
        "unit": "MO",
        "quantity": 3,
        "unit_rate": 2000,
    })
    if r:
        print(f"  ✓ 01.02 → Consolidated rental: 3 MO × $2,000 = $6,000")
    else:
        print(f"  ✗ Failed to update 01.02")

    for pid, label in [(RENTAL_DEMO, "01.04"), (RENTAL_STORM, "01.05")]:
        if delete_position(pid):
            print(f"  ✓ Deleted {label} (now covered by consolidated rental)")
        else:
            print(f"  ✗ Failed to delete {label}")

    print("\n--- Removing duplicate compaction line ---")

    r = update_position(SUBGRADE, {
        "description": "Excavate, grade, and compact subgrade — 5 building pads, 45,225 SF"
    })
    if r:
        print(f"  ✓ 31.02 → Updated to include compaction scope")
    else:
        print(f"  ✗ Failed to update 31.02")

    if delete_position(COMPACT_DUP):
        print(f"  ✓ Deleted 31.04 (duplicate — GRD-SIT-01 already includes compaction in 31.02)")
    else:
        print(f"  ✗ Failed to delete 31.04")

    # Reorder to clean up sequence
    print("\n--- Reordering positions ---")
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
    if r:
        print(f"  ✓ Reordered {len(ordered_ids)} items")
    else:
        print(f"  ✗ Reorder failed")

    # Print summary
    print("\n" + "=" * 60)
    print("Updated state")
    print("=" * 60)
    positions = get_positions()
    real = [p for p in positions if p.get("unit") != "section"]
    for p in real:
        ord_ = p["ordinal"]
        if ord_.startswith("01.") or ord_ in ["31.02", "31.03", "31.04"]:
            qty = float(p.get("quantity", 0) or 0)
            rate = float(p.get("unit_rate", 0) or 0)
            total = qty * rate
            print(f"  {ord_:<12} ${total:>8,.2f}  {p['description'][:60]}")


if __name__ == "__main__":
    main()
