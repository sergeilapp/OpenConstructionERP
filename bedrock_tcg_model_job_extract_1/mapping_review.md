# TCG OCERP Mapping Review

## Package Overview

This package demonstrates how the TCG model job's 71 costable BOQ items
map into OCERP resources, CostItems, assemblies, notes, and allowances.

## Summary Counts

| Item | Count |
|---|---:|
| Total costable BOQ items | 71 |
| Proposed catalog resources | 14 |
| Proposed CostItems | 33 |
| Proposed assemblies | 7 |
| Manual allowances / adjustments | 5 |
| Resource gaps | 24 |
| Notes and assumptions | 37 |
| BOQ items: needs_new_cost_item | 43 |
| BOQ items: track_as_labor_component | 13 |
| BOQ items: needs_cost_item_refinement | 7 |
| BOQ items: track_as_pricing_adjustment | 5 |
| BOQ items: track_as_subcontractor_component | 3 |

## MasterFormat Coverage

| **00 00 00** Project Evidence And Reconciliation | 4 recommendations |
| **02 00 00** Existing Conditions | 10 recommendations |
| **03 00 00** Concrete | 4 recommendations |
| **31 00 00** Earthwork | 27 recommendations |
| **32 00 00** Exterior Improvements | 3 recommendations |
| **33 00 00** Utilities | 23 recommendations |

## Key Mapping Decisions

1. **No direct matches** to existing Extract 2 CostItems — the catalog covers concrete/masonry/insulation; TCG is site-prep only.
2. **43 items need new CostItems** — material supply, hauling, driving, and addon groups.
3. **16 items tracked as components** — labor and subcontractor components attach to parent CostItems.
4. **5 items excluded as pricing adjustments** — markup, discounts, and opaque adjustments stay in pricing layer.
5. **7 items need refinement** — scheduled truck entries without rate evidence.
6. **Addon decomposition** reduced 30 opaque adjustments to 5 true adjustments by classifying atomic meanings.

## Review Guidance

- Review proposed CostItems for scope accuracy and unit prices.
- Confirm labor component assignment to parent CostItems.
- Resolve scheduled truck/resource gaps before import.
- Resolve TCG-P5-R1, TCG-P5-R2, and TCG-P7-R1/2/3 review flags.
- Before import, finalize CostItem codes and verify all component math.