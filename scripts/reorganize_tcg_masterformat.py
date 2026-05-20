#!/usr/bin/env python3
"""Reorganize TCG BOQ into MasterFormat divisions with chronological ordering."""

import json
import sys
import urllib.request
import urllib.error
import uuid

BOQ_ID = "61839ac6-2af4-41ca-a385-c9b1c3516bf1"
BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None

# MasterFormat divisions with description → (ordinal_prefix, description)
DIVISIONS = [
    ("01", "Division 01 — General Requirements"),
    ("02", "Division 02 — Existing Conditions / Demolition"),
    ("31", "Division 31 — Earthwork & Grading"),
    ("32", "Division 32 — Exterior Improvements (Concrete & Paving)"),
    ("33", "Division 33 — Utilities"),
    ("33S", "Division 33 — Stormwater Systems"),
    ("90", "Addenda — Credits & Allowances"),
]

# Map position ordinal/description to new division + sequence
def classify_position(p):
    """Classify a position into a MasterFormat division."""
    ordinal = p.get("ordinal", "")
    desc = p.get("description", "").lower()
    meta = p.get("metadata", {})
    
    # Credits and allowances go to Addenda
    if meta.get("credit") or meta.get("rock_allowance"):
        return "90"
    
    # General Requirements
    if any(k in desc for k in ["consultation", "layout", "staking", "elevation", "compaction test", "equipment rental"]):
        return "01"
    
    # Existing Conditions / Demolition
    if any(k in desc for k in ["demolish", "demolition", "concrete removal", "asphalt removal", "tree removal", 
                                "dumpster", "haul", "erosion controls", "construction entrance", "orange fence", "shed", "demo labor"]):
        return "02"
    
    # Earthwork & Grading
    if any(k in desc for k in ["topsoil", "bulk excavation", "fill import", "site grading", "compact", "berm", "straw mulch", 
                                "excavate and level", "import and compact", "cut and stockpile"]):
        return "31"
    
    # Exterior Improvements
    if any(k in desc for k in ["concrete curb", "ribbon curb", "asphalt pavement", "stone base", "subgrade", "mill and overlay", "utility trench repair"]):
        return "32"
    
    # Utilities
    if any(k in desc for k in ["sewer", "water service", "electrical conduit", "communications conduit", "gas line trench", "rcp storm pipe", "headwall"]):
        return "33"
    
    # Stormwater
    if any(k in desc for k in ["stormwater", "french drain", "geotextile", "observation well", "#57 stone", "#8 stone", "coarse sand", "fabric"]):
        return "33S"
    
    # Default
    return "01"


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


def delete_position(position_id):
    r = api("DELETE", f"/boq/positions/{position_id}")
    return r is not None


def update_position(position_id, data):
    r = api("PATCH", f"/boq/positions/{position_id}", data)
    return r


def create_section(ordinal, description):
    r = api("POST", f"/boq/boqs/{BOQ_ID}/sections/", {"ordinal": ordinal, "description": description})
    return r


def reorder(position_ids):
    r = api("POST", f"/boq/boqs/{BOQ_ID}/positions/reorder/", {"position_ids": position_ids})
    return r


def main():
    login()

    positions = get_positions()
    if not positions:
        print("✗ No positions found")
        sys.exit(1)
    print(f"✓ Found {len(positions)} positions")

    # Separate sections from real positions
    real_positions = []
    old_sections = []
    for p in positions:
        if p.get("unit") == "section":
            old_sections.append(p)
        else:
            real_positions.append(p)
    
    print(f"  Real positions: {len(real_positions)}")
    print(f"  Old sections: {len(old_sections)}")

    # Delete old sections
    print("\nDeleting old sections...")
    for s in old_sections:
        if delete_position(s["id"]):
            print(f"  ✓ Deleted: {s.get('description', s['id'])[:40]}")

    # Classify and assign new ordinals
    print("\nClassifying positions...")
    by_division = {}
    for p in real_positions:
        div = classify_position(p)
        by_division.setdefault(div, []).append(p)

    # Within each division, sort chronologically by original ordinal
    for div in by_division:
        by_division[div].sort(key=lambda p: p.get("ordinal", ""))

    # Update ordinals
    print("\nUpdating ordinals...")
    for div, div_positions in by_division.items():
        for idx, p in enumerate(div_positions):
            new_ordinal = f"{div}.{(idx+1):02d}"
            if p.get("ordinal") != new_ordinal:
                r = update_position(p["id"], {"ordinal": new_ordinal})
                if r:
                    print(f"  {new_ordinal} ← {p.get('ordinal')}  {p.get('description','')[:40]}")
                else:
                    print(f"  ✗ Failed to update: {p.get('ordinal')} {p.get('description','')[:40]}")
            p["ordinal"] = new_ordinal  # Update local copy

    # Create new sections
    print("\nCreating MasterFormat sections...")
    section_ids = {}
    for ordinal, desc in DIVISIONS:
        r = create_section(ordinal, desc)
        if r:
            section_ids[ordinal] = r["id"]
            print(f"  ✓ Created: {desc}")
        else:
            print(f"  ✗ Failed: {desc}")

    # Build ordered list
    ordered_ids = []
    for ordinal, desc in DIVISIONS:
        sid = section_ids.get(ordinal)
        if sid:
            ordered_ids.append(sid)
        for p in by_division.get(ordinal, []):
            ordered_ids.append(p["id"])

    # Reorder
    print(f"\nReordering {len(ordered_ids)} items...")
    r = reorder(ordered_ids)
    if r:
        print("✓ BOQ reorganized into MasterFormat divisions")
        
        # Print summary
        print("\n" + "=" * 60)
        print("New BOQ Structure")
        print("=" * 60)
        for ordinal, desc in DIVISIONS:
            count = len(by_division.get(ordinal, []))
            print(f"  {ordinal:<5s} {desc:<40s} {count:>3d} positions")
        print("=" * 60)
    else:
        print("✗ Reorder failed")


if __name__ == "__main__":
    main()
