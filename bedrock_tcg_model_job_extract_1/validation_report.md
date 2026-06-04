# TCG Draft Package — Validation Report

## Static Validation

### 1. Resource Rate Validity

✓ All 14 resources have positive rates.

### 2. CostItem Checklist Completeness

✓ All 33 CostItems have complete Phase 9 checklist.

### 3. BOQ Mapping Coverage

✓ All 71 costable BOQ items have mapping entries.

### 4. Subcontracting Model

✓ 3 subcontracted items modeled.

### 5. Assembly Membership

✓ 7 assemblies with 78 total member items.
  (Assembly-to-CostItem cross-reference is deferred — CostItems are not yet finalized.)

### 6. CostItem Component Assignment

✓ Component assignments are scoped: 46 total components, min 1, max 7.

## Summary

| Check | Result |
|---|---|
| Resource rate validity | PASS (14 resources) |
| CostItem checklist completeness | PASS (33 CostItems) |
| BOQ mapping coverage | PASS (71/71) |
| Subcontracting model | PASS |
| Assembly membership | PASS (cross-reference deferred) |
| CostItem component assignment | PASS (46 components, max 7) |

**Total: 6/6 checks passed**

## Open Review Flags

The following review flags from earlier phases remain open:

| ID | Flag | Status |
|---|---|---|
| TCG-P5-R1 | Zero price_override → $0 catalog price | Open |
| TCG-P5-R2 | Fill unit cents-vs-dollars risk | Open |
| TCG-P7-R1 | Site-prep pricing/unit issues | Open |
| TCG-P7-R2 | Site-prep pricing/unit issues | Open |
| TCG-P7-R3 | Site-prep pricing/unit issues | Open |

## Package Integrity

This package is review-only. No automatic import should be performed.
The importer must default to dry-run. Separate explicit approval is required before any OCERP data is created or modified.