#!/usr/bin/env python3
"""Option A: Fix items 1-3 — Move misclassified items to correct divisions."""

import json
import sys
import urllib.request
import urllib.error

BOQ_ID = "61839ac6-2af4-41ca-a385-c9b1c3516bf1"
BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None

# Ordinal → new ordinal mapping
FIXES = {
    # Task 1: Move 33S stormwater items to 33.40.xxx
    "33S.01": "33.40.01",  # Stormwater excavation
    "33S.02": "33.40.02",  # Geotextile fabric — infiltration pit
    "33S.03": "33.40.03",  # Coarse sand bedding
    "33S.04": "33.40.04",  # #57 stone — infiltration pit
    "33S.05": "33.40.05",  # #8 stone top course
    "33S.06": "33.40.06",  # Observation wells
    "33S.07": "33.40.07",  # Geotextile fabric — 12 rolls
    "33S.08": "33.40.08",  # Pipe for observation wells

    # Task 2: Move erosion controls/fence to Division 01 (01 56 00 — Temporary Erosion & Sediment Control)
    "02.01": "01.08",  # Erosion controls — silt fence
    "02.02": "01.09",  # Construction entrance
    "02.13": "01.10",  # Orange construction fence

    # Task 3: Move foundation drain to Division 31 (31 20 00 — Earth Moving)
    "33.08": "31.16",  # Foundation perimeter drain
}


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


def get_positions():
    r = api("GET", f"/boq/boqs/{BOQ_ID}")
    if r:
        return r.get("positions", [])
    return []


def update_ordinal(position_id, new_ordinal):
    r = api("PATCH", f"/boq/positions/{position_id}", {"ordinal": new_ordinal})
    return r


def main():
    login()

    positions = get_positions()
    real = [p for p in positions if p.get("unit") != "section"]
    print(f"✓ Found {len(real)} positions")

    # Build lookup by ordinal
    by_ordinal = {p["ordinal"]: p for p in real}

    # Apply fixes
    print("\nApplying fixes...")
    success = 0
    failed = 0

    for old_ord, new_ord in FIXES.items():
        p = by_ordinal.get(old_ord)
        if p:
            r = update_ordinal(p["id"], new_ord)
            if r:
                desc = p["description"][:50]
                print(f"  ✓ {old_ord} → {new_ord}: {desc}")
                by_ordinal[new_ord] = r
                del by_ordinal[old_ord]
                success += 1
            else:
                print(f"  ✗ Failed: {old_ord} → {new_ord}")
                failed += 1
        else:
            print(f"  - Not found: {old_ord} (already moved?)")

    print(f"\nDone: {success} succeeded, {failed} failed")

    # Print new structure
    print("\n" + "=" * 60)
    print("Updated BOQ Structure (affected divisions)")
    print("=" * 60)

    positions = get_positions()
    real = [p for p in positions if p.get("unit") != "section"]
    by_ordinal = {p["ordinal"]: p for p in real}

    for div_label, prefix in [
        ("Division 01 — General Requirements", "01"),
        ("Division 31 — Earthwork & Grading", "31"),
        ("Division 33 — Utilities", "33"),
        ("Division 33.40 — Storm Drainage", "33.40"),
    ]:
        items = [(k, v) for k, v in by_ordinal.items() if k.startswith(prefix + ".") or k == prefix]
        if prefix == "33.40":
            items = [(k, v) for k, v in by_ordinal.items() if k.startswith("33.40")]
        if items:
            items.sort(key=lambda x: x[0])
            print(f"\n{div_label}:")
            for ord_, p in items:
                print(f"  {ord_:<12} {p['description'][:60]}")


if __name__ == "__main__":
    main()
