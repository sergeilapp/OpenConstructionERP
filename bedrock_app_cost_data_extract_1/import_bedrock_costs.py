#!/usr/bin/env python3
"""
Import Bedrock Siteworks Cost Items into OCERP.

Imports Phase 1 leaf resources, then Phase 2 composite CostItems.
Run after `rake estimating:extraction:cost_items` generates JSON files.

Usage:
    python scripts/import_bedrock_costs.py

Requires OCERP backend running at http://localhost:8000
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None

parser = argparse.ArgumentParser(description="Import Bedrock cost items into OCERP")
parser.add_argument("--email", default="sergeilapp@gmail.com")
parser.add_argument("--password", default="OpenEstimate2026!")
parser.add_argument("--port", default="8000")
parser.add_argument(
    "--data-dir",
    default="docs/estimating/extraction",
    help="Directory containing resources.json and cost_items.json",
)


def api_call(method, path, data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp_body = resp.read().decode()
            return json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        try:
            err = json.loads(err_body)
        except json.JSONDecodeError:
            err = err_body
        print(f"  ERROR {method} {path}: {err.get('detail', err) if isinstance(err, dict) else err}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ERROR {method} {path}: {e}", file=sys.stderr)
        return None


def login(email, password):
    global TOKEN
    resp = api_call("POST", "/users/auth/login/", {"email": email, "password": password})
    if resp and "access_token" in resp:
        TOKEN = resp["access_token"]
        print(f"  Logged in as {email}")
        return True
    print(f"  Login failed for {email}")
    return False


def validate_item(item):
    total = item.get("rate", 0)
    components = item.get("components", [])
    calculated = sum(c.get("cost", 0) for c in components)
    if abs(total - calculated) > 0.01:
        print(f"  {item['code']}: rate={total}, calculated={calculated:.2f} (diff={total - calculated:.2f})")
        return False
    return True


def import_file(filepath, label):
    print(f"\nLoading {label} from {filepath}...")
    with open(filepath, "r") as f:
        items = json.load(f)
    print(f"  Found {len(items)} items")

    print("  Validating component math...")
    invalid = []
    for item in items:
        if not validate_item(item):
            invalid.append(item["code"])
    if invalid:
        print(f"  Validation failed for {len(invalid)} items: {', '.join(invalid)}")
        return None, 0
    print("  All items pass validation")

    print("  Importing to OCERP...")
    result = api_call("POST", "/costs/bulk/", items, token=TOKEN)

    if result is None:
        print("  Bulk import failed")
        return None, 0

    imported = len(result)
    if imported < len(items):
        print(f"  WARNING: only {imported}/{len(items)} items were imported ({len(items) - imported} skipped)")
    print(f"  Imported {imported} items")
    return items, imported


def verify_items(items, sample_size=3):
    print("\nVerifying import...")
    for item in items[:sample_size]:
        search = urllib.parse.quote(item["code"])
        resp = api_call("GET", f"/costs/?search={search}&region=BEDROCK-MAIN", token=TOKEN)
        if resp and resp.get("total", 0) > 0:
            print(f"  {item['code']} found in database")
        else:
            print(f"  {item['code']} not found (may have been skipped)")


def extract_catalog():
    print("\nTriggering catalog extraction...")
    result = api_call("POST", "/catalog/extract/", {}, token=TOKEN)
    if result:
        total = result.get("total_extracted", 0)
        by_type = result.get("by_type", {})
        print(f"  Extracted {total} resources: {by_type}")
        return True
    print("  Catalog extraction failed (admin permission may be required)")
    return False


def check_catalog_stats():
    print("\nChecking catalog stats...")
    resp = api_call("GET", "/catalog/stats/", token=TOKEN)
    if resp:
        total = resp.get("total", 0)
        by_type = resp.get("by_type", [])
        print(f"  Total catalog resources: {total}")
        if by_type:
            print("  By type:")
            for t in by_type:
                print(f"    {t['resource_type']}: {t['count']}")
    else:
        print("  Could not fetch catalog stats")


def main():
    args = parser.parse_args()
    global BASE_URL
    BASE_URL = f"http://localhost:{args.port}/api/v1"

    print("=" * 60)
    print("Bedrock Siteworks Cost Database Import + Catalog Extraction")
    print("=" * 60)

    print("\nAuthenticating...")
    if not login(args.email, args.password):
        sys.exit(1)

    data_dir = args.data_dir.rstrip("/")
    files = [
        (f"{data_dir}/resources.json", "Phase 1 leaf resources"),
        (f"{data_dir}/cost_items.json", "Phase 2 concrete CostItems"),
        (f"{data_dir}/cost_items_rock_pad.json", "Phase 2 rock pad CostItems"),
        (f"{data_dir}/cost_items_site_prep.json", "Phase 2 site prep CostItems"),
        (f"{data_dir}/cost_items_adhoc.json", "Phase 2 adhoc CostItems"),
    ]

    total_imported = 0
    all_items = []

    for filepath, label in files:
        items, count = import_file(filepath, label)
        if items is not None:
            total_imported += count
            all_items.extend(items)
        else:
            print(f"  Skipping {label} due to errors")

    if all_items:
        verify_items(all_items)

    extract_catalog()
    check_catalog_stats()

    print("\n" + "=" * 60)
    print("Import complete!")
    print("=" * 60)
    print(f"\nTotal items imported: {total_imported}")
    print(f"\nView in OCERP:")
    print(f"  Costs: http://localhost:{args.port}/costs?region=BEDROCK-MAIN")
    print(f"  Catalog: http://localhost:{args.port}/catalog")


if __name__ == "__main__":
    main()
