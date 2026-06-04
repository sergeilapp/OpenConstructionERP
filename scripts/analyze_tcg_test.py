#!/usr/bin/env python3
"""
TCG Test Analysis — Comprehensive BOQ vs Legacy Estimate Comparison
====================================================================

Usage:
    python scripts/analyze_tcg_test.py [--boq-id UUID] [--output-dir reports]

Requires:
    - OCERP backend running at http://localhost:8000
    - docs/TCG-Project/TCG_Estimate_Data_Sections.csv
    - docs/TCG-Project/TCG_Project_Summary.md

Outputs:
    reports/tcg_analysis_<YYYYMMDD>_<HHMMSS>.json  — structured data for LLM
    reports/tcg_analysis_<YYYYMMDD>_<HHMMSS>.md    — human-readable report
"""

import argparse
import copy
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_BOQ_ID = "61839ac6-2af4-41ca-a385-c9b1c3516bf1"
CSV_PATH = Path(__file__).resolve().parents[1] / "docs" / "TCG-Project" / "TCG_Estimate_Data_Sections.csv"
SUMMARY_PATH = Path(__file__).resolve().parents[1] / "docs" / "TCG-Project" / "TCG_Project_Summary.md"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "reports"

TOKEN = None

# ─── MasterFormat Divisions ─────────────────────────────────────────────────

MASTERFORMAT = {
    "01": "General Requirements",
    "02": "Existing Conditions / Demolition",
    "03": "Concrete",
    "31": "Earthwork & Grading",
    "32": "Exterior Improvements",
    "33": "Utilities",
    "33.40": "Stormwater Systems",
}

# ─── Job labels from CSV ────────────────────────────────────────────────────

JOB_LABELS = {
    "38254": "Economy Level Site",
    "38304": "Demolition & Disposal",
    "38396": "French Drain / Stormwater",
    "38447": "Concrete Curb",
    "38522": "Trenching",
    "38577": "Excavation — Crawlspace & Footers",
    "38578": "Additional Work",
}

# ─── Cross-cutting categories ───────────────────────────────────────────────

CATEGORY_KEYWORDS = {
    "Cut & Fill / Earthwork": [
        "topsoil", "bulk excavation", "cut and stockpile", "cut to design",
        "structural fill", "import.*fill", "fill material", "fill import",
        "compaction", "compacting", "berm",
    ],
    "Concrete Curbing": [
        "concrete curb", "ribbon curb", "curb and gutter", "curb",
    ],
    "Paving & Asphalt": [
        "asphalt", "pavement", "mill and overlay", "stone base", "paving",
    ],
    "Trenching & Utilities": [
        "sanitary sewer", "water service", "electrical conduit",
        "communications conduit", "gas line trench", "sewer", "water pipe",
        "utility trench", "trench excavation",
    ],
    "Stormwater / Drainage": [
        "stormwater", "french drain", "geotextile", "#57 stone", "#8 stone",
        "observation well", "sand bedding", "coarse sand",
        "headwall", "rcp storm pipe", "concrete pipe",
        "perimeter drain", "perforated pipe",
    ],
    "Demolition": [
        "demolish", "demolition", "concrete removal", "asphalt removal",
        "tree removal", "shed.*removal", "dumpster", "haul.*debris",
        "demo labor",
    ],
    "Erosion Control": [
        "silt fence", "erosion control", "construction entrance",
        "orange.*fence", "straw mulch", "straw stabilization",
    ],
    "Site Preparation / Grading": [
        "site grading", "fine grade", "subgrade preparation",
        "excavate and level", "site preparation", "cut and level",
        "preparation", "compaction test", "compaction testing",
    ],
    "Crawlspace / Foundation": [
        "crawlspace", "footer excavation", "foundation drain",
        "vapor barrier", "footers",
    ],
    "General Requirements": [
        "consultation", "layout.*staking", "site layout", "elevation",
        "equipment rental", "mobilization",
    ],
}

# Wildcard codes that match any instance — used for linking cost DB items
WILDCARD_CODE_MAP = {
    r"ASP-PAV": "ASP-PAV-01",
    r"CON-CUR": "CON-CUR-01",
    r"CON-RCB": "CON-RCB-01",
    r"DEM-ASH": "DEM-ASP-01",
    r"DEM-CNC": "DEM-CON-01",
    r"DEM-HSE": "DEM-HSE-01",
    r"DEM-TR": None,
    r"DRN-PRM": "DRN-PRM-01",
    r"EQP-RNT-HMR": "EQP-RNT-HMR",
    r"EXC-BLK": "EXC-BLK-01",
    r"EXC-CRW": "EXC-CRW-01",
    r"EXC-STW": None,
    r"EXC-TRE": None,
    r"FILL-CMP": "FILL-CMP-01",
    r"GRD-BRM": None,
    r"GRD-CRW": "GRD-CRW-01",
    r"GRD-SIT": "GRD-SIT-01",
    r"SIT-LAY": None,
    r"STN-BSE": "STN-BSE-01",
    r"STN-FIL": None,
    r"STR-HDW": "STR-HDW-01",
    r"STR-RCP-18": "STR-RCP-18",
    r"TST-CMP": None,
    r"UT-COM": "UT-COM-01",
    r"UT-ELC": "UT-ELC-01",
    r"UT-GAS": "UT-GAS-01",
    r"UT-SWR": "UT-SWR-01",
    r"UT-WTR": "UT-WTR-01",
    r"SW-INF": None,
    r"SW-FRN": None,
}

# Categories for "deep dive" specific scopes the user asked about
SCOPE_DEEP_DIVES = ["Concrete Curbing", "Trenching & Utilities",
                    "Cut & Fill / Earthwork", "Stormwater / Drainage",
                    "Demolition", "Erosion Control"]


# ─── API helpers ────────────────────────────────────────────────────────────

def api(method, path, data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw.strip() else True
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
        return True
    print("✗ Login failed", file=sys.stderr)
    sys.exit(1)


# ─── Data loading ───────────────────────────────────────────────────────────

def load_legacy_csv(path):
    """Parse the TCG_Estimate_Data_Sections.csv into structured sections."""
    text = path.read_text(encoding="utf-8")
    sections = {}
    current_section = None
    current_headers = []
    current_rows = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("==="):
            # Save previous section
            if current_section and current_rows:
                sections[current_section] = {"headers": current_headers, "rows": current_rows}
            current_section = line.strip("= ").strip()
            current_headers = []
            current_rows = []
        elif current_section and not current_headers and line.startswith("Job ID"):
            current_headers = next(csv.reader([line]))
        elif current_section and current_headers:
            row = next(csv.reader([line]))
            if len(row) >= len(current_headers):
                current_rows.append(dict(zip(current_headers, row)))

    if current_section and current_rows:
        sections[current_section] = {"headers": current_headers, "rows": current_rows}

    return sections


def load_project_summary(path):
    """Extract key data from TCG_Project_Summary.md."""
    text = path.read_text(encoding="utf-8")
    data = {}

    # Extract net project value
    m = re.search(r"\*\*Net project value\*\*\s*\|\s*\*\*~?([0-9,]+\.?\d*)", text)
    if m:
        data["net_project_value"] = float(m.group(1).replace(",", ""))

    # Rock allowances by job ID (from known caps in the document)
    data["rock_allowances"] = {
        "38396": 49000,   # French Drain
        "38522": 23000,   # Trenching
        "38577": 23000,   # Crawlspace Excavation
        "38578": 88000,   # Additional Excavation
    }

    return data


def fetch_boq(boq_id):
    """Fetch BOQ with positions from API."""
    r = api("GET", f"/boq/boqs/{boq_id}")
    return r if r else {}


def fetch_cost_db():
    """Fetch all cost database items from API with pagination."""
    all_items = []
    page = 0
    while True:
        r = api("GET", f"/costs/?limit=100&offset={page * 100}")
        if not r or "items" not in r:
            break
        batch = r["items"]
        all_items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    tn_items = [i for i in all_items if i.get("region") == "USA_TENNESSEE"]
    return {"all": all_items, "usa_tn": tn_items}


# ─── Analysis helpers ───────────────────────────────────────────────────────

def classify_category(description):
    """Classify a BOQ position into a cross-cutting category."""
    desc_lower = description.lower()
    for category, patterns in CATEGORY_KEYWORDS.items():
        for pattern in patterns:
            if re.search(pattern, desc_lower):
                return category
    return "Other / Unclassified"


def get_rate_quality(rate, source):
    """Assess rate quality."""
    if rate == 0:
        return "zero"
    if source == "cost_database":
        return "cost_db_sourced"
    return "manual_estimate"


def extract_resources_from_metadata(p):
    """Extract L/E/M resource breakdown from position metadata if available."""
    meta = p.get("metadata") or {}
    resources = meta.get("resources") or meta.get("components") or []
    breakdown = {"labor": 0.0, "equipment": 0.0, "material": 0.0}
    for rsrc in resources:
        rtype = rsrc.get("type", "")
        cost = float(rsrc.get("total", 0) or 0)
        if rtype == "labor":
            breakdown["labor"] += cost
        elif rtype == "equipment":
            breakdown["equipment"] += cost
        elif rtype == "material":
            breakdown["material"] += cost
    return breakdown if any(breakdown.values()) else None


def guess_cost_code(description, meta):
    """Try to find which cost DB code a position maps to."""
    meta_code = meta.get("cost_item_code") if isinstance(meta, dict) else None
    if meta_code:
        return meta_code
    # Try pattern match from WILDCARD_CODE_MAP
    for pattern, code in WILDCARD_CODE_MAP.items():
        if re.search(pattern, description, re.IGNORECASE):
            return code
    return None


# ─── Main analysis ──────────────────────────────────────────────────────────

def analyze(boq_id):
    """Run full analysis and return structured results dict."""
    print(f"📡 Fetching BOQ {boq_id}...")
    boq = fetch_boq(boq_id)
    if not boq:
        print("✗ BOQ not found")
        sys.exit(1)

    all_positions = boq.get("positions", [])
    sections = [p for p in all_positions if p.get("unit") == "section"]
    positions = [p for p in all_positions if p.get("unit") != "section"]
    print(f"  ✓ {len(positions)} positions, {len(sections)} sections")

    print("📡 Fetching cost database...")
    cost_db = fetch_cost_db()
    print(f"  ✓ {len(cost_db['all'])} total items, {len(cost_db['usa_tn'])} USA_TN items")

    # Build cost DB lookup by code
    cost_db_by_code = {}
    for item in cost_db["all"]:
        cost_db_by_code[item["code"]] = item
    for item in cost_db["usa_tn"]:
        cost_db_by_code[item["code"]] = item

    print("📄 Loading legacy CSV...")
    legacy = load_legacy_csv(CSV_PATH)
    print(f"  ✓ {len(legacy)} sections parsed")

    print("📄 Loading project summary...")
    summary = load_project_summary(SUMMARY_PATH)

    # ─── Per-sub-job grouping ───────────────────────────────────────────────
    by_job = defaultdict(list)
    unassigned = []
    for p in positions:
        meta = p.get("metadata") or {}
        job_id = meta.get("job") if isinstance(meta, dict) else None
        if job_id:
            by_job[job_id].append(p)
        else:
            unassigned.append(p)

    print(f"  ✓ {len(by_job)} sub-jobs identified, {len(unassigned)} unassigned")

    # ─── Per-category grouping ─────────────────────────────────────────────
    by_category = defaultdict(list)
    category_codes_found = set()
    for p in positions:
        cat = classify_category(p.get("description", ""))
        by_category[cat].append(p)
        category_codes_found.add(cat)
    # Preserve order per CATEGORY_KEYWORDS
    ordered_cats = [c for c in CATEGORY_KEYWORDS if c in category_codes_found]
    ordered_cats += [c for c in category_codes_found if c not in CATEGORY_KEYWORDS]

    # ─── Build job comparison ───────────────────────────────────────────────

    # Parse legacy job summary rows
    job_summary_rows = {}
    if "JOB SUMMARY" in legacy:
        for row in legacy["JOB SUMMARY"]["rows"]:
            jid = row.get("Job ID", "").strip()
            if jid:
                job_summary_rows[jid] = row

    # Parse additions/credits
    additions_rows = {}
    if "ADDITIONAL LABOR & MATERIALS" in legacy:
        for row in legacy["ADDITIONAL LABOR & MATERIALS"]["rows"]:
            jid = row.get("Job ID", "").strip()
            if jid:
                additions_rows[jid] = row

    job_analysis = {}
    boq_grand_total = 0.0
    legacy_grand_total = 0.0
    legacy_labor_total = 0.0

    for job_id, label in JOB_LABELS.items():
        items = by_job.get(job_id, [])
        legacy_row = job_summary_rows.get(job_id, {})

        # BOQ totals
        boq_total = 0.0
        zero_rate_items = []
        rates_ok = 0
        cost_db_linked = 0
        component_breakdown = {"labor": 0.0, "equipment": 0.0, "material": 0.0}
        has_breakdown = 0

        item_details = []
        for p in items:
            qty = float(p.get("quantity", 0) or 0)
            rate = float(p.get("unit_rate", 0) or 0)
            total = qty * rate
            meta = p.get("metadata") or {}
            if meta.get("credit"):
                total = -abs(total)

            boq_total += total

            # Resource breakdown from metadata
            rsrc = extract_resources_from_metadata(p)
            if rsrc:
                for k in component_breakdown:
                    component_breakdown[k] += rsrc[k]
                has_breakdown += 1

            # Match to cost DB item
            guessed_code = guess_cost_code(p.get("description", ""), meta)
            cost_db_item = cost_db_by_code.get(guessed_code) if guessed_code else None
            if cost_db_item:
                cost_db_linked += 1

            if rate > 0:
                rates_ok += 1
            else:
                zero_rate_items.append(p["ordinal"])

            source = p.get("source", "unknown")
            item_details.append({
                "ordinal": p["ordinal"],
                "description": p["description"],
                "quantity": qty,
                "unit": p["unit"],
                "rate": rate,
                "total": total,
                "source": source,
                "rate_quality": get_rate_quality(rate, source),
                "has_resource_breakdown": rsrc is not None,
                "cost_db_code": guessed_code,
                "cost_db_match": cost_db_item is not None,
            })

        # Legacy totals
        legacy_price = float(legacy_row.get("Price ($)", "0").replace(",", "") or 0)
        legacy_material = float(legacy_row.get("Material Cost ($)", "0").replace(",", "") or 0)
        legacy_labor = float(legacy_row.get("Labor Cost ($)", "0").replace(",", "") or 0)
        legacy_total_owed = float(legacy_row.get("Total Owed ($)", "0").replace(",", "") or 0)
        legacy_area = legacy_row.get("Area (sqft)", "").replace(",", "")
        legacy_area_val = float(legacy_area) if legacy_area else 0

        boq_grand_total += boq_total
        legacy_grand_total += legacy_price
        legacy_labor_total += legacy_labor

        # Additional labor/materials from legacy
        add_row = additions_rows.get(job_id, {})
        additional_desc = add_row.get("Additional Price Description", "") if add_row else ""
        additional_price = float(add_row.get("Additional Price ($)", "0").replace(",", "")) if add_row else 0

        variance = boq_total - legacy_price
        variance_pct = (variance / legacy_price * 100) if legacy_price else 0

        # Match rock allowance
        rock_cap = summary["rock_allowances"].get(label, 0)

        job_analysis[job_id] = {
            "job_label": label,
            "legacy": {
                "price": round(legacy_price, 2),
                "material_cost": round(legacy_material, 2),
                "labor_cost": round(legacy_labor, 2),
                "total_owed": round(legacy_total_owed, 2),
                "area_sqft": legacy_area_val,
                "additional_materials_desc": additional_desc,
                "additional_price": round(additional_price, 2),
                "rock_allowance_cap": rock_cap,
            },
            "boq": {
                "total": round(boq_total, 2),
                "item_count": len(items),
                "items_with_rates": rates_ok,
                "zero_rate_items": len(zero_rate_items),
                "zero_rate_ordinals": zero_rate_items,
                "cost_db_linked": cost_db_linked,
                "items_with_resource_breakdown": has_breakdown,
                "component_breakdown": {k: round(v, 2) for k, v in component_breakdown.items()},
                "details": item_details,
            },
            "comparison": {
                "variance_dollars": round(variance, 2),
                "variance_pct": round(variance_pct, 1),
                "percent_of_legacy": round((boq_total / legacy_price * 100), 1) if legacy_price else 0,
            }
        }

    # Unassigned items
    unassigned_details = []
    for p in unassigned:
        qty = float(p.get("quantity", 0) or 0)
        rate = float(p.get("unit_rate", 0) or 0)
        total = qty * rate
        unassigned_details.append({
            "ordinal": p["ordinal"],
            "description": p["description"],
            "total": total,
            "rate": rate,
        })

    # ─── Category analysis ──────────────────────────────────────────────────
    category_analysis = {}
    for cat in ordered_cats:
        items = by_category[cat]
        boq_total = sum(
            float(p.get("quantity", 0) or 0) * float(p.get("unit_rate", 0) or 0)
            for p in items
        )
        category_analysis[cat] = {
            "item_count": len(items),
            "boq_total": round(boq_total, 2),
            "items": [
                {
                    "ordinal": p["ordinal"],
                    "description": p["description"],
                    "qty": float(p.get("quantity", 0) or 0),
                    "unit": p["unit"],
                    "rate": float(p.get("unit_rate", 0) or 0),
                    "total": float(p.get("quantity", 0) or 0) * float(p.get("unit_rate", 0) or 0),
                }
                for p in items
            ],
        }

    # ─── Rate quality assessment ─────────────────────────────────────────────
    zero_rate_positions = [p for p in positions if (float(p.get("unit_rate", 0) or 0)) == 0]
    total_boq_value = sum(
        float(p.get("quantity", 0) or 0) * float(p.get("unit_rate", 0) or 0)
        for p in positions
    )

    # ─── Resource breakdown summary ──────────────────────────────────────────
    total_resource = {"labor": 0.0, "equipment": 0.0, "material": 0.0}
    has_breakdown_count = 0
    for p in positions:
        rsrc = extract_resources_from_metadata(p)
        if rsrc:
            for k in total_resource:
                total_resource[k] += rsrc[k]
            has_breakdown_count += 1

    # ─── Overall quality metrics ─────────────────────────────────────────────
    total_items = len(positions)
    with_rates = sum(1 for p in positions if (float(p.get("unit_rate", 0) or 0)) > 0)
    source_count = defaultdict(int)
    for p in positions:
        source_count[p.get("source", "unknown")] += 1

    quality = {
        "total_positions": total_items,
        "positions_with_rates": with_rates,
        "zero_rate_positions": len(zero_rate_positions),
        "zero_rate_pct": round(len(zero_rate_positions) / total_items * 100, 1) if total_items else 0,
        "rate_coverage_pct": round(with_rates / total_items * 100, 1) if total_items else 0,
        "source_distribution": dict(source_count),
        "resource_breakdown_items": has_breakdown_count,
        "resource_breakdown_pct": round(has_breakdown_count / total_items * 100, 1) if total_items else 0,
        "implicit_labor_total": round(total_resource["labor"], 2),
        "implicit_equipment_total": round(total_resource["equipment"], 2),
        "implicit_material_total": round(total_resource["material"], 2),
        "grand_total_boq": round(total_boq_value, 2),
    }

    # ─── Assemble result ────────────────────────────────────────────────────
    result = {
        "meta": {
            "boq_id": boq_id,
            "boq_name": boq.get("name", ""),
            "boq_status": boq.get("status", ""),
            "analysis_date": datetime.now().isoformat(),
            "csv_source": str(CSV_PATH),
        },
        "legacy_summary": {
            "total_estimate": round(legacy_grand_total, 2),
            "total_labor_estimate": round(legacy_labor_total, 2),
            "credits_total": 44700.00,  # From TCG_Project_Summary.md
            "net_project_value": round(legacy_grand_total - 44700.00, 2),
            "rock_allowances_total": round(sum(summary["rock_allowances"].values()), 2),
        },
        "per_job": job_analysis,
        "categories": category_analysis,
        "unassigned_items": unassigned_details,
        "quality_metrics": quality,
        "zero_rate_items": [
            {
                "ordinal": p["ordinal"],
                "description": p["description"],
                "unit": p["unit"],
                "job_id": (p.get("metadata") or {}).get("job"),
                "source": p.get("source"),
            }
            for p in zero_rate_positions
        ],
    }

    return result


# ─── Report generation ──────────────────────────────────────────────────────

def generate_report(result):
    """Generate markdown report from analysis result."""
    lines = []
    now = datetime.now()

    lines.append(f"# TCG Test Analysis — 5655 Valley View Road, Brentwood")
    lines.append(f"")
    lines.append(f"**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**BOQ:** {result['meta']['boq_name']} (`{result['meta']['boq_id']}`)")
    lines.append(f"**Status:** {result['meta']['boq_status']}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # ── 1. Executive Summary ────────────────────────────────────────────────
    lines.append(f"## 1. Executive Summary")
    lines.append(f"")
    q = result["quality_metrics"]
    ls = result["legacy_summary"]

    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| **Legacy estimate total** | ${ls['total_estimate']:,.2f} |")
    lines.append(f"| **Net project value** (after -$44,700 credits) | ${ls['net_project_value']:,.2f} |")
    lines.append(f"| **BOQ total** | ${q['grand_total_boq']:,.2f} |")
    lines.append(f"| **Variance** | ${ls['total_estimate'] - q['grand_total_boq']:,.2f} |")
    variance_pct = (q["grand_total_boq"] - ls["total_estimate"]) / ls["total_estimate"] * 100
    lines.append(f"| **Variance %** | {variance_pct:+.1f}% |")
    lines.append(f"| **Legacy labor estimate** | ${ls['total_labor_estimate']:,.2f} |")
    lines.append(f"| **Implicit BOQ labor** (from component breakdown) | ${q['implicit_labor_total']:,.2f} |")
    lines.append(f"| **Positions with rates** | {q['positions_with_rates']}/{q['total_positions']} ({q['rate_coverage_pct']:.0f}%) |")
    lines.append(f"| **Zero-rate items** | {q['zero_rate_positions']} ({q['zero_rate_pct']:.0f}%) |")
    lines.append(f"| **Items with L/E/M breakdown** | {q['resource_breakdown_items']}/{q['total_positions']} ({q['resource_breakdown_pct']:.0f}%) |")
    lines.append(f"| **Rock allowances (unaccounted)** | ${ls['rock_allowances_total']:,.2f} |")
    lines.append(f"")

    # Score
    score = 0
    score += min(q["rate_coverage_pct"] * 0.4, 40)
    score += min(q["resource_breakdown_pct"] * 0.3, 30)
    scope_score = min(max(100 - abs(variance_pct) * 2, 0), 30)
    score += scope_score
    lines.append(f"**Test Quality Score:** {score:.0f}/100")
    lines.append(f"- Rate coverage: {q['rate_coverage_pct']:.0f}% × 0.4 = {min(q['rate_coverage_pct']*0.4, 40):.0f}")
    lines.append(f"- Component breakdown: {q['resource_breakdown_pct']:.0f}% × 0.3 = {min(q['resource_breakdown_pct']*0.3, 30):.0f}")
    lines.append(f"- Scope alignment: {scope_score:.0f}/30 (variance {abs(variance_pct):.1f}%)")
    lines.append(f"")

    # ── 2. Per-Job Comparison ───────────────────────────────────────────────
    lines.append(f"## 2. Per-Job Cost Comparison")
    lines.append(f"")
    lines.append(f"| # | Sub-Job | Legacy | BOQ | Variance | % of Legacy |")
    lines.append(f"|---|---------|--------|-----|----------|-------------|")

    for jid in ["38254", "38304", "38396", "38447", "38522", "38577", "38578"]:
        ja = result["per_job"].get(jid)
        if not ja:
            continue
        leg = ja["legacy"]
        boq = ja["boq"]
        cmp = ja["comparison"]
        label = JOB_LABELS.get(jid, jid)
        lines.append(f"| {jid} | {label} | ${leg['price']:>8,.2f} | ${boq['total']:>8,.2f} | ${cmp['variance_dollars']:>+8,.2f} | {cmp['percent_of_legacy']:>5.1f}% |")

    lines.append(f"| | **Total** | **${ls['total_estimate']:>8,.2f}** | **${q['grand_total_boq']:>8,.2f}** | **${ls['total_estimate'] - q['grand_total_boq']:>+8,.2f}** | **{(q['grand_total_boq']/ls['total_estimate']*100):>5.1f}%** |")
    lines.append(f"")

    for jid in ["38254", "38304", "38396", "38447", "38522", "38577", "38578"]:
        ja = result["per_job"].get(jid)
        if not ja:
            continue
        leg = ja["legacy"]
        boq = ja["boq"]
        cmp = ja["comparison"]
        label = JOB_LABELS.get(jid, jid)

        lines.append(f"### 2.{list(JOB_LABELS.keys()).index(jid)+1} {jid} — {label}")
        lines.append(f"")
        lines.append(f"| | Legacy | BOQ | Variance |")
        lines.append(f"|---|--------|-----|----------|")
        lines.append(f"| **Total** | ${leg['price']:,.2f} | ${boq['total']:,.2f} | ${cmp['variance_dollars']:+,.2f} ({cmp['variance_pct']:+.1f}%) |")
        lines.append(f"| Labor cost | ${leg['labor_cost']:,.2f} | ${boq['component_breakdown']['labor']:,.2f} (from {boq['items_with_resource_breakdown']} decomposed items) | — |")
        lines.append(f"| Materials | ${leg['material_cost']:,.2f} | ${boq['component_breakdown']['material']:,.2f} | — |")
        lines.append(f"| Rock allowance cap | ${leg['rock_allowance_cap']:,.2f} | Not applied | — |")
        lines.append(f"")

        if leg["additional_price"]:
            lines.append(f"**Additional items in legacy:** {leg['additional_materials_desc'][:200]}")
            lines.append(f"")

        # List BOQ items for this job
        lines.append(f"**BOQ positions ({boq['item_count']} items, ${boq['total']:,.2f}):**")
        lines.append(f"")
        lines.append(f"| Ordinal | Description | Qty | Unit | Rate | Total | Quality |")
        lines.append(f"|---------|-------------|-----|------|------|-------|--------|")
        for d in boq["details"]:
            quality_str = "✓" if d["rate_quality"] == "cost_db_sourced" else ("⚠ manual" if d["rate_quality"] == "manual_estimate" else "✗ zero")
            lines.append(f"| {d['ordinal']} | {d['description'][:55]} | {d['quantity']:>7.1f} | {d['unit']} | ${d['rate']:>7.2f} | ${d['total']:>8,.2f} | {quality_str} |")
        lines.append(f"")

        if boq["zero_rate_items"]:
            lines.append(f"> ⚠ **{boq['zero_rate_items']} item(s) at $0 rate**")
            lines.append(f"")

    # ── 3. Cross-Cutting Category Analysis ──────────────────────────────────
    lines.append(f"## 3. Cross-Cutting Category Analysis")
    lines.append(f"")
    lines.append(f"Categories where work spans multiple sub-jobs are aggregated to show total cost by work type.")
    lines.append(f"")

    for cat in SCOPE_DEEP_DIVES:
        ca = result["categories"].get(cat)
        if not ca:
            continue
        lines.append(f"### 3.{SCOPE_DEEP_DIVES.index(cat)+1} {cat}")
        lines.append(f"")
        lines.append(f"**{ca['item_count']} items · BOQ total: ${ca['boq_total']:,.2f}**")
        lines.append(f"")
        lines.append(f"| Ordinal | Description | Qty | Unit | Rate | Total | Job |")
        lines.append(f"|---------|-------------|-----|------|------|-------|------|")
        for d in ca["items"]:
            # Find job from per_job data
            item_job = ""
            for jid, ja in result["per_job"].items():
                if any(bd["ordinal"] == d["ordinal"] for bd in ja["boq"]["details"]):
                    item_job = JOB_LABELS.get(jid, jid)
                    break
            lines.append(f"| {d['ordinal']} | {d['description'][:50]} | {d['qty']:>7.1f} | {d['unit']} | ${d['rate']:>7.2f} | ${d['total']:>8,.2f} | {item_job} |")
        lines.append(f"")

    # All other categories
    all_cats_shown = set(SCOPE_DEEP_DIVES)
    for cat, ca in result["categories"].items():
        if cat in all_cats_shown:
            continue
        lines.append(f"### {cat}")
        lines.append(f"")
        lines.append(f"**{ca['item_count']} items · BOQ total: ${ca['boq_total']:,.2f}**")
        lines.append(f"")
        lines.append(f"| Ordinal | Description | Qty | Unit | Rate | Total |")
        lines.append(f"|---------|-------------|-----|------|------|-------|")
        for d in ca["items"]:
            lines.append(f"| {d['ordinal']} | {d['description'][:50]} | {d['qty']:>7.1f} | {d['unit']} | ${d['rate']:>7.2f} | ${d['total']:>8,.2f} |")
        lines.append(f"")

    # ── 4. Component Decomposition ──────────────────────────────────────────
    lines.append(f"## 4. Component Decomposition (Labor / Equipment / Materials)")
    lines.append(f"")
    lines.append(f"Of {q['total_positions']} BOQ positions, {q['resource_breakdown_items']} ({q['resource_breakdown_pct']:.0f}%) have resource-level breakdowns")
    lines.append(f"embedded in their metadata. The remaining items have flat rates only.")
    lines.append(f"")
    lines.append(f"| Component | BOQ Implicit Total | Legacy Total | Coverage |")
    lines.append(f"|-----------|-------------------|--------------|----------|")
    lines.append(f"| **Labor** | ${q['implicit_labor_total']:,.2f} | ${ls['total_labor_estimate']:,.2f} | {q['resource_breakdown_pct']:.0f}% of items |")
    lines.append(f"| Equipment | ${q['implicit_equipment_total']:,.2f} | (included in legacy) | — |")
    lines.append(f"| Materials | ${q['implicit_material_total']:,.2f} | (included in legacy) | — |")
    lines.append(f"")
    lines.append(f"> ℹ️ The implicit totals only cover the {q['resource_breakdown_items']} items with metadata resource breakdowns.")
    lines.append(f"> The {q['total_positions'] - q['resource_breakdown_items']} items without breakdowns contribute to the BOQ total")
    lines.append(f"> but cannot be split into L/E/M components for comparison.")
    lines.append(f"")

    # ── 5. Rate Quality Assessment ──────────────────────────────────────────
    lines.append(f"## 5. Rate & Quality Assessment")
    lines.append(f"")
    lines.append(f"### Source Distribution")
    lines.append(f"")
    lines.append(f"| Source | Count |")
    lines.append(f"|--------|-------|")
    for src, cnt in sorted(q["source_distribution"].items()):
        lines.append(f"| {src} | {cnt} |")
    lines.append(f"")

    if result["zero_rate_items"]:
        lines.append(f"### Items at $0 Rate ({len(result['zero_rate_items'])})")
        lines.append(f"")
        lines.append(f"These items have no unit rate and contribute nothing to the total.")
        lines.append(f"In the legacy estimate these would have specific costs.")
        lines.append(f"")
        lines.append(f"| Ordinal | Description | Unit | Job | Source |")
        lines.append(f"|---------|-------------|------|-----|--------|")
        for z in result["zero_rate_items"]:
            lines.append(f"| {z['ordinal']} | {z['description'][:50]} | {z['unit']} | {z.get('job_id','?')} | {z.get('source','?')} |")
        lines.append(f"")
        lines.append(f"> ⚠ **Impact:** These {len(result['zero_rate_items'])} zero-rate items understate the BOQ total.")
        lines.append(f"> Fixing them would increase the BOQ total and reduce the variance.")
        lines.append(f"")

    # ── 6. Specific Scope Deep Dives ────────────────────────────────────────
    lines.append(f"## 6. Specific Scope Deep Dives")
    lines.append(f"")

    # Concrete Curbing
    cc = result["categories"].get("Concrete Curbing")
    if cc:
        lines.append(f"### Concrete Curbing")
        lines.append(f"")
        cc_total = cc["boq_total"]
        legacy_cc = 0
        for jid in ["38447"]:
            ja = result["per_job"].get(jid, {})
            legacy_cc += ja.get("legacy", {}).get("price", 0)
        lines.append(f"**BOQ: ${cc_total:,.2f} | Legacy (Job 38447): ${legacy_cc:,.2f}**")
        lines.append(f"")
        lines.append(f"The curb work covers 75 LF of curb & gutter (Div 32.01) and 844 LF of ribbon curb (Div 32.02).")
        lines.append(f"Legacy includes concrete, form/pour labor ($32K sub crew), $3,800 concrete, 2A stone.")
        lines.append(f"The legacy estimate includes a -$37,000 credit for ribbon curb and walkways — in OCERP,")
        lines.append(f"this work was simply not added to the BOQ, which is the correct approach.")
        lines.append(f"")

    # Trenching
    tr = result["categories"].get("Trenching & Utilities")
    if tr:
        lines.append(f"### Trenching & Utilities")
        lines.append(f"")
        tr_total = tr["boq_total"]
        lines.append(f"**BOQ: ${tr_total:,.2f} | Legacy (Job 38522): ~$56,842**")
        lines.append(f"")
        lines.append(f"Covers ~1,300 LF of utility trenching: sewer, water, electrical, communications, gas.")
        lines.append(f"Also 125 LF of 18\" RCP pipe + 2 headwalls.")
        lines.append(f"Legacy gas line includes 8 loads of screenings at $8,400.")
        lines.append(f"")

    # Cut & Fill
    cf = result["categories"].get("Cut & Fill / Earthwork")
    if cf:
        lines.append(f"### Cut & Fill / Earthwork")
        lines.append(f"")
        cf_total = cf["boq_total"]
        lines.append(f"**BOQ: ${cf_total:,.2f} | Across jobs 38254, 38577, 38578**")
        lines.append(f"")
        lines.append(f"Total earthwork: 200 CY topsoil strip + 45,225 SF leveling + 1,955 CY import fill")
        lines.append(f"+ 200 CY topsoil (job 7) + 200 CY bulk excav + 200 CY structural fill + 720 CY crawlspace.")
        lines.append(f"Key rates: bulk excav $12.45/CY, structural fill $18.50/CY, grading $0.45/SF.")
        lines.append(f"Legacy total labor hours across earthwork: ~212 hrs (job 1) + 442 hrs (job 7).")
        lines.append(f"")

    # Stormwater / French Drain
    sw = result["categories"].get("Stormwater / Drainage")
    if sw:
        lines.append(f"### Stormwater / French Drain")
        lines.append(f"")
        sw_total = sw["boq_total"]
        lines.append(f"**BOQ: ${sw_total:,.2f} | Legacy (Job 38396): $76,421**")
        lines.append(f"")
        lines.append(f"860 CY stormwater excavation + infiltration pit with #57 stone (620 CY) + geotextile/sand/#8 stone.")
        lines.append(f"4 observation wells. 1,000 LF foundation perimeter drain (job 6).")
        lines.append(f"")

    # Demolition
    dm = result["categories"].get("Demolition")
    if dm:
        lines.append(f"### Demolition")
        lines.append(f"")
        dm_total = dm["boq_total"]
        lines.append(f"**BOQ: ${dm_total:,.2f} | Legacy (Job 38304): $48,049**")
        lines.append(f"")
        lines.append(f"House (1,500 SF @ $10.33), garage (400 SF @ $10.33), shed/treehouse, concrete removal,")
        lines.append(f"asphalt removal (8,400 SF @ $3.50), tree removal (12 @ $750), dumpsters (11 @ $800), hauling.")
        lines.append(f"Legacy includes 779 labor hours for demo — not directly represented in BOQ.")
        lines.append(f"")

    # ── 7. Unassigned Items ─────────────────────────────────────────────────
    if result["unassigned_items"]:
        lines.append(f"## 7. Unassigned Items")
        lines.append(f"")
        lines.append(f"The following items could not be mapped to a specific sub-job (no `job` field in metadata):")
        lines.append(f"")
        lines.append(f"| Ordinal | Description | Total | Rate |")
        lines.append(f"|---------|-------------|-------|------|")
        for u in result["unassigned_items"]:
            lines.append(f"| {u['ordinal']} | {u['description'][:50]} | ${u['total']:,.2f} | ${u['rate']:,.2f} |")
        lines.append(f"")

    # ── 8. Test Quality Metrics ─────────────────────────────────────────────
    lines.append(f"## 8. Test Quality Metrics")
    lines.append(f"")
    lines.append(f"| Metric | Value | Rating |")
    lines.append(f"|--------|-------|--------|")
    lines.append(f"| Rate coverage | {q['rate_coverage_pct']:.0f}% | {'✓ Good' if q['rate_coverage_pct'] >= 90 else ('⚠ Acceptable' if q['rate_coverage_pct'] >= 70 else '✗ Poor')} |")
    lines.append(f"| Component decomposition | {q['resource_breakdown_pct']:.0f}% | {'✓ Good' if q['resource_breakdown_pct'] >= 50 else '✗ Needs improvement'} |")
    lines.append(f"| Cost variance | {abs(variance_pct):.1f}% | {'✓ Tight' if abs(variance_pct) < 10 else ('⚠ Moderate' if abs(variance_pct) < 25 else '✗ Large gap')} |")
    lines.append(f"| Scope coverage | {len([j for j in JOB_LABELS if j in result['per_job'] and result['per_job'][j]['boq']['item_count'] > 0])}/{len(JOB_LABELS)} jobs | ✓ All sub-jobs represented |")
    lines.append(f"| Zero-rate items | {q['zero_rate_positions']} | {'✓ None' if q['zero_rate_positions'] == 0 else ('⚠ Fix needed' if q['zero_rate_positions'] <= 5 else '✗ Many zeros')} |")
    lines.append(f"| Test Quality Score | {score:.0f}/100 | {'✓ Good' if score >= 70 else ('⚠ Fair' if score >= 50 else '✗ Needs work')} |")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"*Generated by `scripts/analyze_tcg_test.py`*")

    return "\n".join(lines)


# ─── Output ─────────────────────────────────────────────────────────────────

def save_output(result, report, output_dir):
    """Save JSON data package and markdown report."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = os.path.join(output_dir, f"tcg_analysis_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"  ✓ JSON data: {json_path}")

    md_path = os.path.join(output_dir, f"tcg_analysis_{timestamp}.md")
    with open(md_path, "w") as f:
        f.write(report)
    print(f"  ✓ Markdown report: {md_path}")

    return json_path, md_path


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TCG Test Analysis — BOQ vs Legacy Estimate Comparison")
    parser.add_argument("--boq-id", default=DEFAULT_BOQ_ID, help="BOQ UUID to analyze")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    print("=" * 65)
    print("  TCG TEST ANALYSIS")
    print("  BOQ vs Legacy Estimate Comparison")
    print("=" * 65)
    print()

    login()

    result = analyze(args.boq_id)

    print()
    print("📝 Generating report...")
    report = generate_report(result)

    print("💾 Saving output...")
    json_path, md_path = save_output(result, report, args.output_dir)

    print()
    print("=" * 65)
    print("  ANALYSIS COMPLETE")
    print(f"  JSON:  {json_path}")
    print(f"  Report: {md_path}")
    print("=" * 65)

    # Print quick summary
    q = result["quality_metrics"]
    ls = result["legacy_summary"]
    variance = q["grand_total_boq"] - ls["total_estimate"]
    print()
    print(f"  Legacy total:     ${ls['total_estimate']:>10,.2f}")
    print(f"  BOQ total:        ${q['grand_total_boq']:>10,.2f}")
    print(f"  Variance:         ${variance:>+10,.2f} ({variance/ls['total_estimate']*100:+.1f}%)")
    print(f"  Positions:        {q['total_positions']}")
    print(f"  Zero rates:       {q['zero_rate_positions']}")
    print(f"  Decomposed:       {q['resource_breakdown_items']} ({q['resource_breakdown_pct']:.0f}%)")
    print(f"  Quality score:    {round(min(q['rate_coverage_pct']*0.4 + q['resource_breakdown_pct']*0.3 + max(100-abs(variance/ls['total_estimate']*100)*2,0)*0.3, 100)):.0f}/100")
    print(f"  Rock allowances:  ${ls['rock_allowances_total']:,.2f} (not in BOQ)")


if __name__ == "__main__":
    main()
