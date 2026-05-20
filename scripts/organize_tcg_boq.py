#!/usr/bin/env python3
"""Add section headers to the TCG BOQ and reorder positions under each section."""

import json
import sys
import urllib.request
import urllib.error

BOQ_ID = "61839ac6-2af4-41ca-a385-c9b1c3516bf1"
BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None

SECTIONS = [
    ("01", "Job 38254: Economy Level Site"),
    ("02", "Job 38304: Demolition & Disposal"),
    ("03", "Job 38396: French Drain / Stormwater"),
    ("04", "Job 38447: Concrete Curb"),
    ("05", "Job 38522: Trenching"),
    ("06", "Job 38577: Excavation — Crawlspace & Footers"),
    ("07", "Job 38578: Additional Work"),
]


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

    # Group positions by job prefix (first two digits of ordinal)
    by_job = {}
    for p in positions:
        ordinal = p.get("ordinal", "")
        job_prefix = ordinal.split(".")[0] if "." in ordinal else ordinal[:2]
        by_job.setdefault(job_prefix, []).append(p)

    # Sort each group by ordinal
    for job in by_job:
        by_job[job].sort(key=lambda p: p.get("ordinal", ""))

    # Create sections
    section_ids = {}
    for ordinal, desc in SECTIONS:
        r = create_section(ordinal, desc)
        if r:
            section_ids[ordinal] = r["id"]
            print(f"  Created section: {desc}")
        else:
            print(f"  ✗ Failed to create section: {desc}")

    # Build ordered list: section → its positions
    ordered_ids = []
    for ordinal, desc in SECTIONS:
        sid = section_ids.get(ordinal)
        if sid:
            ordered_ids.append(sid)
        for p in by_job.get(ordinal, []):
            ordered_ids.append(p["id"])

    # Reorder
    print(f"\nReordering {len(ordered_ids)} items...")
    r = reorder(ordered_ids)
    if r:
        print("✓ BOQ reorganized with section headers")
    else:
        print("✗ Reorder failed")


if __name__ == "__main__":
    main()
