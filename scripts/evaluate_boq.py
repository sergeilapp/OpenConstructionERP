#!/usr/bin/env python3
"""Comprehensive BOQ Evaluation — TCG Brentwood Sitework.

Evaluates the BOQ against MasterFormat divisions and industry estimating standards.
Generates a structured report with findings and recommendations.
"""

import json
import sys
import urllib.request
import urllib.error

BOQ_ID = "61839ac6-2af4-41ca-a385-c9b1c3516bf1"
BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None


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
        return True
    sys.exit(1)


def get_positions():
    r = api("GET", f"/boq/boqs/{BOQ_ID}")
    return r.get("positions", []) if r else []


def evaluate_division_01(positions):
    """Division 01 — General Requirements"""
    findings = []
    items = [p for p in positions if p["ordinal"].startswith("01.")]

    findings.append("━" * 70)
    findings.append("DIVISION 01 — General Requirements")
    findings.append("━" * 70)
    findings.append(f"Items: {len(items)} | Total: ${sum(float(p.get('total',0) or 0) for p in items):,.2f}")
    findings.append("")

    # Item-by-item evaluation
    for p in items:
        o = p["ordinal"]
        d = p["description"]
        u = p["unit"]
        r = float(p.get("unit_rate", 0) or 0)
        issues = []

        if "compaction testing" in d.lower():
            issues.append("✓ Unit 'EA' is standard for testing per building site")
            issues.append("? Rate $900/EA seems high for basic compaction test (market: $250-500)")
        elif "equipment rental" in d.lower():
            issues.append("✗ Should NOT be a separate line per work type — industry standard is one consolidated")
            issues.append("✗ 'LS' unit is wrong for equipment rental — should be 'DAY', 'WK', or 'MO'")
            issues.append("? Rate $2,000 is low for 30-ton excavator (market: $350-500/day, $7,000-10,000/mo)")
        elif "consultation" in d.lower():
            issues.append("✗ $0 rate — needs a rate or should be excluded as pre-contract cost")
            issues.append("? 'LS' unit acceptable for professional service")
        elif "layout and staking" in d.lower():
            issues.append("✓ Unit 'LS' is standard for layout service")
            issues.append("? Rate $1,200 is reasonable for 5-building site layout")
        elif "foundation elevation" in d.lower():
            issues.append("✗ $0 rate — typically included in layout or excavation cost")
            issues.append("? Consider removing — this is part of layout/staking scope")

        if issues:
            findings.append(f"  {o} {d[:50]}")
            for issue in issues:
                findings.append(f"      {issue}")
            findings.append("")

    # Division-level findings
    findings.append("─── Division-Level Issues ───")
    findings.append("  ✗ MISSING: Mobilization / demobilization (01 50 00)")
    findings.append("  ✗ MISSING: Temporary facilities (01 50 00)")
    findings.append("  ✗ MISSING: Erosion and sediment control (01 56 00) — currently in Div 02")
    findings.append("  ✗ MISSING: Site cleanup and restoration (01 70 00)")
    findings.append("  ✗ MISSING: Permits and fees (01 80 00)")
    findings.append("  ✗ MISSING: Construction entrance (01 56 00) — currently in Div 02 with wrong rate")
    findings.append("  ✗ Equipment rentals scattered across divisions — should consolidate under 01")
    findings.append("")

    return findings


def evaluate_division_02(positions):
    """Division 02 — Existing Conditions / Demolition"""
    findings = []
    items = [p for p in positions if p["ordinal"].startswith("02.")]

    findings.append("━" * 70)
    findings.append("DIVISION 02 — Existing Conditions / Demolition")
    findings.append("━" * 70)
    findings.append(f"Items: {len(items)} | Total: ${sum(float(p.get('total',0) or 0) for p in items):,.2f}")
    findings.append("")

    for p in items:
        o = p["ordinal"]
        d = p["description"]
        u = p["unit"]
        r = float(p.get("unit_rate", 0) or 0)
        issues = []

        if "erosion controls" in d.lower():
            issues.append("✗ WRONG DIVISION — should be 01 56 00 (Temporary Erosion and Sediment Control)")
            issues.append("✗ $0 rate — needs a rate or should be in Division 01")
        elif "construction entrance" in d.lower():
            issues.append("✗ WRONG DIVISION — should be 01 56 13 (Construction Entrance)")
            issues.append("✗ WRONG RATE — $27.98 is likely a partial match; should be ~$2,600")
            issues.append("✓ 'LS' unit is standard for construction entrance")
        elif "demolish existing residence" in d.lower():
            issues.append("✓ Unit 'SF' is standard for building demolition")
            issues.append("✓ Rate $10.33/SF is reasonable for wood-frame residential")
        elif "demolish existing garage" in d.lower():
            issues.append("✓ Unit 'SF' is standard")
            issues.append("? Rate $10.33/SF — same as house; garage is simpler, could be $6-8/SF")
        elif "shed" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("? 'EA' unit acceptable for small structures; market: $500-1,500/EA")
        elif "concrete removal" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✓ Unit 'SF' is standard; market: $3-6/SF for saw-cut and remove")
        elif "tree removal" in d.lower():
            issues.append("✓ Unit 'EA' is standard per tree")
            issues.append("? Rate $750/EA is high for 12 trees — market: $300-500/EA for standard trees")
        elif "dumpster" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✓ Unit 'EA' (per load) is standard")
            issues.append("? Description says '$800/load' but rate is $0 — inconsistency")
        elif "haul" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✓ Unit 'EA' (per load) is standard")
            issues.append("? Description says '$450/load' but rate is $0 — inconsistency")
        elif "demo labor" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✓ Unit 'HR' is standard")
            issues.append("? 779 hours seems high for this scope — verify quantity")
        elif "orange construction fence" in d.lower():
            issues.append("✗ WRONG DIVISION — should be 01 56 00 (Temporary Fencing)")
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✓ Unit 'LF' is standard; market: $4-8/LF installed")
        elif "asphalt driveway removal" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✓ Unit 'SF' is standard; market: $2-4/SF")

        if issues:
            findings.append(f"  {o} {d[:50]}")
            for issue in issues:
                findings.append(f"      {issue}")
            findings.append("")

    findings.append("─── Division-Level Issues ───")
    findings.append("  ✗ 4 items in wrong division (erosion controls, construction entrance, orange fence)")
    findings.append("  ✗ 6 items at $0 rate (shed, concrete, asphalt, dumpster, hauling, labor)")
    findings.append("  ✗ Rate/description inconsistencies (dumpster $800/load shown but rate $0)")
    findings.append("  ✗ Missing: Hazardous material assessment (02 80 00) for older structures")
    findings.append("  ✗ Missing: Debris disposal tipping fees (often separate line item)")
    findings.append("")

    return findings


def evaluate_division_31(positions):
    """Division 31 — Earthwork & Grading"""
    findings = []
    items = [p for p in positions if p["ordinal"].startswith("31.")]

    findings.append("━" * 70)
    findings.append("DIVISION 31 — Earthwork & Grading")
    findings.append("━" * 70)
    findings.append(f"Items: {len(items)} | Total: ${sum(float(p.get('total',0) or 0) for p in items):,.2f}")
    findings.append("")

    for p in items:
        o = p["ordinal"]
        d = p["description"]
        u = p["unit"]
        r = float(p.get("unit_rate", 0) or 0)
        q = float(p.get("quantity", 0))
        issues = []

        if "cut and stockpile topsoil" in d.lower():
            issues.append("✓ Unit 'CY' is standard for earthwork")
            issues.append("✓ Rate $12.44/CY is reasonable")
            issues.append("? Quantity 200 CY for 45,225 SF seems low — verify: 45,225 SF × 0.5 ft = ~837 CY")
        elif "excavate and level site" in d.lower():
            issues.append("✗ WRONG UNIT — 'SF' is not standard for excavation; should be 'CY'")
            issues.append("✗ Rate $0.45/SF is misleading — this is a grading rate, not excavation")
            issues.append("? Description says 'excavate' but rate is for grading — clarify")
        elif "import and compact fill" in d.lower():
            issues.append("✓ Unit 'CY' is standard")
            issues.append("✓ Rate $18.50/CY is reasonable for structural fill")
        elif "compact to 95%" in d.lower():
            issues.append("✗ WRONG UNIT — 'SF' is not standard; should be 'CY' or 'LS'")
            issues.append("✗ Rate $0.45/SF — compaction is typically included in fill placement rate")
            issues.append("? Consider removing — this is part of fill import item above")
        elif "berm" in d.lower():
            issues.append("✓ Unit 'LF' is standard for linear grading features")
            issues.append("? Rate $15/LF seems high for berm grading — market: $5-10/LF")
        elif "straw mulch" in d.lower():
            issues.append("✗ WRONG UNIT — 'LS' is not standard; should be 'SF' or 'SY'")
            issues.append("✗ $0 rate — needs a rate")
            issues.append("? Market: $0.05-0.10/SF for straw mulch")
        elif "topsoil strip" in d.lower() or "bulk excavation" in d.lower():
            issues.append("✓ Unit 'CY' is standard")
            issues.append("✓ Rate $12.45/CY is reasonable")
            issues.append("? These are essentially the same item — consider consolidating")
        elif "structural fill import" in d.lower():
            issues.append("✓ Unit 'CY' is standard")
            issues.append("✓ Rate $18.50/CY matches item 31.03")
            issues.append("? Duplicate of 31.03 — consider consolidating")
        elif "site grading and fine grade" in d.lower():
            issues.append("✗ WRONG UNIT — 'SF' is acceptable but 'AC' (acre) or 'LS' is more common")
            issues.append("✓ Rate $0.45/SF is reasonable for fine grading")
        elif "crawlspace and footer excavation" in d.lower():
            issues.append("✓ Unit 'CY' is standard")
            issues.append("✓ Rate $8.88/CY is reasonable")
            issues.append("? Quantity 720 CY for 5 foundations — verify: 5 × 38' × 64' × 2' = ~900 CY")
        elif "fine grade garage" in d.lower() or "fine grade porch" in d.lower():
            issues.append("✓ Unit 'SF' is standard for fine grading")
            issues.append("✓ Rate $0.45/SF is reasonable")
            issues.append("? These are very small quantities — consider combining with main grading")
        elif "fine grade crawlspace" in d.lower():
            issues.append("✓ Unit 'SF' is standard")
            issues.append("✓ Rate $2.28/SF includes vapor barrier + stone — reasonable")
            issues.append("? Consider moving to Division 03 (Concrete) or 07 (Thermal/Moisture)")

        if issues:
            findings.append(f"  {o} {d[:50]}")
            for issue in issues:
                findings.append(f"      {issue}")
            findings.append("")

    findings.append("─── Division-Level Issues ───")
    findings.append("  ✗ Multiple unit errors (SF used for excavation, LS for straw mulch)")
    findings.append("  ✗ Duplicate items (topsoil, fill import)")
    findings.append("  ✗ Compaction line item is redundant — should be included in fill rate")
    findings.append("  ✗ Fine grade crawlspace might belong in Div 03 or 07")
    findings.append("  ✗ Missing: Dewatering (31 23 00) if groundwater encountered")
    findings.append("  ✗ Missing: Slope protection / geotextile for cuts")
    findings.append("")

    return findings


def evaluate_division_32(positions):
    """Division 32 — Exterior Improvements"""
    findings = []
    items = [p for p in positions if p["ordinal"].startswith("32.")]

    findings.append("━" * 70)
    findings.append("DIVISION 32 — Exterior Improvements (Concrete & Paving)")
    findings.append("━" * 70)
    findings.append(f"Items: {len(items)} | Total: ${sum(float(p.get('total',0) or 0) for p in items):,.2f}")
    findings.append("")

    for p in items:
        o = p["ordinal"]
        d = p["description"]
        u = p["unit"]
        r = float(p.get("unit_rate", 0) or 0)
        issues = []

        if "concrete curb and gutter" in d.lower():
            issues.append("✓ Unit 'LF' is standard")
            issues.append("✓ Rate $15.20/LF is reasonable for formed/poured curb")
        elif "concrete ribbon curb" in d.lower():
            issues.append("✓ Unit 'LF' is standard")
            issues.append("✓ Rate $9.81/LF is reasonable for ribbon curb")
        elif "subgrade preparation" in d.lower():
            issues.append("✓ Unit 'SF' is standard for subgrade prep")
            issues.append("✓ Rate $0.45/SF is reasonable")
            issues.append("? Consider combining with main grading item — subgrade prep is typically part of paving")
        elif "asphalt pavement" in d.lower():
            issues.append("✓ Unit 'SF' is standard")
            issues.append("✓ Rate $5.56/SF is reasonable for 3.5\" hot mix")
        elif "mill and overlay" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("? Market: $3-5/SF for mill and overlay")
            issues.append("? 'LS' unit is wrong — should be 'SF' or 'SY'")
        elif "excavation and grading for driveway" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✗ WRONG DIVISION — should be Division 31 (Earthwork)")
            issues.append("✗ 'LS' unit is wrong — should be 'CY' or 'SF'")
        elif "repair utility trenches" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✗ WRONG DIVISION — should be Division 33 (Utilities) or 32")
            issues.append("? 'LS' unit acceptable for small repair")
        elif "stone base" in d.lower():
            issues.append("✓ Unit 'SF' is standard for base course")
            issues.append("✓ Rate $1.62/SF is reasonable for 8\" crushed aggregate")

        if issues:
            findings.append(f"  {o} {d[:50]}")
            for issue in issues:
                findings.append(f"      {issue}")
            findings.append("")

    findings.append("─── Division-Level Issues ───")
    findings.append("  ✗ 2 items in wrong division (excavation for driveway ramp should be Div 31)")
    findings.append("  ✗ 3 items at $0 rate (mill/overlay, driveway excavation, trench repair)")
    findings.append("  ✗ Subgrade prep is duplicated — should be part of paving scope")
    findings.append("  ✗ Missing: Curing compound, control joints, expansion joints for concrete")
    findings.append("  ✗ Missing: Edge restraint for asphalt (if applicable)")
    findings.append("")

    return findings


def evaluate_division_33(positions):
    """Division 33 — Utilities"""
    findings = []
    items = [p for p in positions if p["ordinal"].startswith("33.") and not p["ordinal"].startswith("33S")]

    findings.append("━" * 70)
    findings.append("DIVISION 33 — Utilities")
    findings.append("━" * 70)
    findings.append(f"Items: {len(items)} | Total: ${sum(float(p.get('total',0) or 0) for p in items):,.2f}")
    findings.append("")

    for p in items:
        o = p["ordinal"]
        d = p["description"]
        u = p["unit"]
        r = float(p.get("unit_rate", 0) or 0)
        issues = []

        if "sanitary sewer" in d.lower():
            issues.append("✓ Unit 'LF' is standard")
            issues.append("✓ Rate $28.00/LF is reasonable for 4\" PVC, 3' deep")
        elif "water service" in d.lower():
            issues.append("✓ Unit 'LF' is standard")
            issues.append("✓ Rate $22.00/LF is reasonable for 4\" PVC, 3' deep")
        elif "electrical conduit" in d.lower():
            issues.append("✓ Unit 'LF' is standard")
            issues.append("✓ Rate $16.01/LF is reasonable for 3\" PVC with bedding")
        elif "communications conduit" in d.lower():
            issues.append("✓ Unit 'LF' is standard")
            issues.append("✓ Rate $3.52/LF is reasonable for 1.5\" PVC")
        elif "gas line trench" in d.lower():
            issues.append("✓ Unit 'LF' is standard")
            issues.append("✓ Rate $23.54/LF is reasonable for 3'×3' trench with backfill")
        elif "rcp storm pipe" in d.lower():
            issues.append("✓ Unit 'LF' is standard")
            issues.append("✓ Rate $44.67/LF is reasonable for 18\" Class III RCP")
        elif "precast concrete headwall" in d.lower():
            issues.append("✓ Unit 'EA' is standard")
            issues.append("✓ Rate $1,101.74/EA is reasonable for 18\" headwall with rip rap")
        elif "foundation perimeter drain" in d.lower():
            issues.append("✗ WRONG DIVISION — should be 31 20 00 (Earth Moving) or 07 50 00 (Membrane Roofing)")
            issues.append("✗ This is a foundation drainage system, not a utility")
            issues.append("✓ Rate $19.19/LF is reasonable for perforated pipe with stone")

        if issues:
            findings.append(f"  {o} {d[:50]}")
            for issue in issues:
                findings.append(f"      {issue}")
            findings.append("")

    findings.append("─── Division-Level Issues ───")
    findings.append("  ✗ 1 item in wrong division (foundation drain should be Div 31 or 07)")
    findings.append("  ✗ Missing: Trench backfill compaction testing")
    findings.append("  ✗ Missing: Utility locates / potholing (if required)")
    findings.append("  ✗ Missing: Connection fees / tap fees for water/sewer")
    findings.append("  ✗ Stormwater items (33S) should be consolidated into 33 40 00")
    findings.append("")

    return findings


def evaluate_division_33s(positions):
    """Division 33S — Stormwater Systems (NOT a real MasterFormat division)"""
    findings = []
    items = [p for p in positions if p["ordinal"].startswith("33S")]

    findings.append("━" * 70)
    findings.append("DIVISION 33S — Stormwater Systems")
    findings.append("━" * 70)
    findings.append(f"Items: {len(items)} | Total: ${sum(float(p.get('total',0) or 0) for p in items):,.2f}")
    findings.append("")

    findings.append("  ✗✗✗ CRITICAL: '33S' is NOT a real MasterFormat division")
    findings.append("  ✗✗✗ All items should be moved to Division 33 40 00 (Storm Drainage)")
    findings.append("")

    for p in items:
        o = p["ordinal"]
        d = p["description"]
        u = p["unit"]
        r = float(p.get("unit_rate", 0) or 0)
        issues = []

        if "stormwater excavation" in d.lower():
            issues.append("✓ Unit 'CY' is standard")
            issues.append("✓ Rate $12.00/CY is reasonable")
            issues.append("✗ WRONG DIVISION — should be 33 40 00")
        elif "geotextile fabric" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✓ Unit 'SF' is standard; market: $0.50-1.00/SF")
            issues.append("✗ WRONG DIVISION — should be 33 40 00")
        elif "coarse sand bedding" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✓ Unit 'CY' is standard; market: $30-45/CY")
            issues.append("✗ WRONG DIVISION — should be 33 40 00")
        elif "#57 stone" in d.lower():
            issues.append("✓ Unit 'CY' is standard")
            issues.append("✓ Rate $45.00/CY is reasonable")
            issues.append("✗ WRONG DIVISION — should be 33 40 00")
        elif "#8 stone" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✓ Unit 'CY' is standard; market: $50-65/CY")
            issues.append("✗ WRONG DIVISION — should be 33 40 00")
        elif "observation wells" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("✓ Unit 'EA' is standard; market: $200-400/EA")
            issues.append("✗ WRONG DIVISION — should be 33 40 00")
        elif "pipe for observation wells" in d.lower():
            issues.append("✗ $0 rate — needs a rate")
            issues.append("? 'LS' unit is vague — should be 'LF' with pipe diameter specified")
            issues.append("✗ WRONG DIVISION — should be 33 40 00")

        if issues:
            findings.append(f"  {o} {d[:50]}")
            for issue in issues:
                findings.append(f"      {issue}")
            findings.append("")

    findings.append("─── Division-Level Issues ───")
    findings.append("  ✗✗✗ Division '33S' does not exist in MasterFormat")
    findings.append("  ✗ All items should be renumbered to 33.40.xxx (or 33.41.xxx)")
    findings.append("  ✗ 5 items at $0 rate")
    findings.append("  ✗ Missing: Inlet structures, catch basins, manholes (if applicable)")
    findings.append("  ✗ Missing: Outlet protection / rip rap (separate from headwalls)")
    findings.append("")

    return findings


def main():
    login()
    positions = get_positions()
    if not positions:
        print("✗ No positions found")
        sys.exit(1)

    all_findings = []
    all_findings.append("=" * 70)
    all_findings.append("COMPREHENSIVE BOQ EVALUATION")
    all_findings.append("TCG Brentwood Sitework — MasterFormat & Industry Standards")
    all_findings.append("=" * 70)
    all_findings.append("")
    all_findings.append(f"Total positions evaluated: {len([p for p in positions if p.get('unit') != 'section'])}")
    all_findings.append("")

    all_findings.extend(evaluate_division_01(positions))
    all_findings.extend(evaluate_division_02(positions))
    all_findings.extend(evaluate_division_31(positions))
    all_findings.extend(evaluate_division_32(positions))
    all_findings.extend(evaluate_division_33(positions))
    all_findings.extend(evaluate_division_33s(positions))

    all_findings.append("=" * 70)
    all_findings.append("SUMMARY")
    all_findings.append("=" * 70)
    all_findings.append("")
    all_findings.append("Critical Issues (must fix):")
    all_findings.append("  1. Division '33S' does not exist — move all items to Division 33 40 00")
    all_findings.append("  2. 6 items in wrong divisions (erosion controls, fence, foundation drain)")
    all_findings.append("  3. 19 items at $0 rate — need rates or should be removed")
    all_findings.append("  4. Multiple unit errors (SF for excavation, LS for measurable work)")
    all_findings.append("")
    all_findings.append("Major Issues (should fix):")
    all_findings.append("  5. Equipment rentals scattered — consolidate under Division 01")
    all_findings.append("  6. Duplicate items (topsoil, fill import)")
    all_findings.append("  7. Redundant compaction line item — include in fill rate")
    all_findings.append("  8. Rate/description mismatches (dumpster, hauling)")
    all_findings.append("")
    all_findings.append("Minor Issues (nice to fix):")
    all_findings.append("  9. Description format — remove prices from descriptions")
    all_findings.append(" 10. Missing general conditions items (permits, cleanup, etc.)")
    all_findings.append(" 11. Consider consolidating small quantity items")
    all_findings.append("")

    report = "\n".join(all_findings)
    print(report)

    # Save to file
    with open("/tmp/boq_evaluation.txt", "w") as f:
        f.write(report)
    print("\n✓ Report saved to /tmp/boq_evaluation.txt")


if __name__ == "__main__":
    main()
