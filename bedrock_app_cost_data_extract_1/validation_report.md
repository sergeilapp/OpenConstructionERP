# Validation Report — Bedrock CostItem Extraction

## Summary

| Phase | File | Items | Validation |
|---|---|---|---|
| Phase 1 | `resources.json` | 648 | All pass (empty components, rate == unit_rate) |
| Phase 2 | `cost_items.json` | 17 | All pass (rate == sum(components.cost)) |
| Phase 2 | `cost_items_rock_pad.json` | 10 | All pass |
| Phase 2 | `cost_items_site_prep.json` | 11 | All pass |
| Phase 2 | `cost_items_adhoc.json` | 5 | All pass |
| **Total** | | **691** | **0 failures** |

## Validation Rule

For every composite CostItem: `abs(item.rate - sum(c.cost for c in item.components)) <= 0.01`

All 43 Phase 2 items pass this gate. The 648 leaf resources trivially pass (empty components, rate == unit_rate).

## Phase 2 Concrete — Sampling Coverage

| Code | Unit | Rate | Components | Sample Count | Factor Source |
|---|---|---|---|---|---|
| BED-CONC-SLAB-4IN | sf | $14.88 | 5 | 25 jobs | Median: concrete (0.017042 cy/sf), rebar (1.266 lf/sf), wire (0.03125 sheets/sf), vapor (0.000278 rolls/sf), labor (0.088 hr/sf) |
| BED-CONC-SLAB-6IN | sf | $13.76 | 5 | 25 jobs | Median: concrete (0.021605 cy/sf), rebar (1.191 lf/sf), labor (0.068 hr/sf) |
| BED-CONC-SLAB-8IN | sf | $15.91 | 5 | 1 job | Formula fallback (0.027778 cy/sf, 1.2 rebar) — insufficient samples |
| BED-CONC-FOOTER | lf | $19.06 | 3 | 200 jobs | Median: concrete (0.0686 cy/lf), rebar (2.0 lf/lf), wire (0.0579 pieces/lf) |
| BED-CONC-BLOCK-6IN | lf | $2.63 | 1 | 0 jobs | Geometry fallback (0.75 blocks/lf) — no jobs found |
| BED-CONC-BLOCK-8IN | lf | $2.63 | 1 | 289 jobs | 0.75 blocks/lf (universal; all 289 samples return exactly 0.75) |
| BED-CONC-BLOCK-10IN | lf | $3.19 | 1 | 7 jobs | 0.75 blocks/lf |
| BED-CONC-BLOCK-12IN | lf | $3.38 | 1 | 4 jobs | 0.75 blocks/lf (below 5-job threshold, geometry fallback) |
| BED-CONC-PIER | ea | $65.17 | 2 | 200 jobs | Median: concrete (0.2778 cy/pier), rebar (3.33 lf/pier) |
| BED-CONC-APRON | sf | $3.58 | 2 | 147 jobs | Median: concrete (0.0123 cy/sf), rebar (1.0 lf/sf) |
| BED-CONC-EDGE | lf | $11.11 | 1 | 200 jobs | Median: concrete (0.0494 cy/lf) |
| BED-CONC-CORE-FILL | lf | $19.32 | 2 | 200 jobs | Median: core fill (0.0764 cy/lf), rebar (2.667 lf/lf) |
| BED-CONC-TOP-BLOCK | lf | $2.63 | 1 | 200 jobs | Median: 0.75 blocks/lf (same as block wall) |
| BED-CONC-DRIVING | trip | $214.50 | 3 | — | Pass-through (laborer + dual-axle truck time + mileage) |
| BED-CONC-LABOR | hr | $100.00 | 1 | — | Pass-through (laborer rate) |
| BED-CONC-ACCESS | lf | $2.00 | 1 | — | Pass-through (pipe/board cost per lf) |
| BED-CONC-MAT-GATHER | hr | $100.00 | 1 | — | Pass-through (laborer rate) |

### Notes on concrete sampling

- **8-in slab** (1 job): Rate is from the sampled job's concrete/rebar; wire/vapor used formula fallback. Tag this for re-sampling as more 8in jobs come in.
- **6-in block** (0 jobs): No historical jobs use 6in block. Geometry fallback (0.75 blocks/lf) used. Flag for review — if Bedrock doesn't actually use 6in block, this CostItem may be unnecessary.
- **12-in block** (4 jobs): Below the 5-job threshold; geometry fallback used. Revisit when more jobs exist.
- **Pass-through items** (driving, labor, access, mat gather): No sampling needed — they directly reference leaf resource rates.

## Phase 2 Rock Pad — Formula-Based

| Code | Unit | Rate | Components | Note |
|---|---|---|---|---|
| BED-ROCK-STONE | ton | $52.00 | 1 | Leaf resource pass-through |
| BED-ROCK-BOARD | lf | $5.00 | 1 | Leaf resource pass-through |
| BED-ROCK-REBAR | ea | $2.00 | 1 | Leaf resource pass-through |
| BED-ROCK-EROSION-CONTROL | lf | $2.50 | 1 | Leaf resource pass-through |
| BED-ROCK-EXCAVATION | sf | $8.00 | 1 | Formula: 0.08 hrs/sf × $100/hr laborer. **needs_sampling** |
| BED-ROCK-FILL-DIRT | ton | $23.25 | 2 | Material ($15.00/ton) + equip ($8.25/trip mileage). **needs_sampling** |
| BED-ROCK-DRIVING | trip | $214.50 | 3 | Same driving composite as concrete |
| BED-ROCK-LABOR | hr | $100.00 | 1 | Same laborer rate as concrete |
| BED-ROCK-ACCESS | lf | $2.00 | 1 | Same access cost as concrete |
| BED-ROCK-MAT-GATHER | hr | $100.00 | 1 | Same laborer rate as concrete |

## Phase 2 Site Prep — Formula-Based

| Code | Unit | Rate | Components | Note |
|---|---|---|---|---|
| BED-PREP-EXCAVATION | sf | $11.60 | 1 | Formula: 0.08 hrs/sf × $145/hr operator labor. **needs_sampling** |
| BED-PREP-BOARD | lf | $5.50 | 1 | Leaf resource pass-through |
| BED-PREP-REBAR | lf | $0.55 | 1 | Leaf resource pass-through |
| BED-PREP-WIRE | sf | $0.63 | 1 | Roll-based; assumes standard roll dims. **needs_sampling** |
| BED-PREP-VAPOR | sf | $0.11 | 1 | Roll-based; assumes 12ft × 300ft roll. **needs_sampling** |
| BED-PREP-FABRIC | sf | $0.17 | 1 | Roll-based; assumes 12ft × 300ft roll. **needs_sampling** |
| BED-PREP-FILL-DIRT | ton | $23.25 | 2 | Same fill dirt composite as rock pad. **needs_sampling** |
| BED-PREP-DRIVING | trip | $214.50 | 3 | Same driving composite |
| BED-PREP-LABOR | hr | $145.00 | 1 | Operator rate (higher than concrete laborer) |
| BED-PREP-ACCESS | lf | $2.00 | 1 | Same access cost |
| BED-PREP-MAT-GATHER | hr | $145.00 | 1 | Operator rate |

## Phase 2 Adhoc — Formula-Based

| Code | Unit | Rate | Components | Note |
|---|---|---|---|---|
| BED-ADHOC-LABOR | hr | $130.00 | 1 | Laborer rate (between concrete $100 and operator $145) |
| BED-ADHOC-DRIVING | trip | $214.50 | 3 | Same driving composite |
| BED-ADHOC-MAT-GATHER | hr | $130.00 | 1 | Same rate as adhoc labor |
| BED-ADHOC-FILL-DIRT | ton | $23.25 | 2 | Same fill dirt composite. **needs_sampling** |
| BED-ADHOC-ACCESS | lf | $2.00 | 1 | Same access cost |

## Items Flagged for Future Sampling

Items tagged `needs_sampling` — rates are formula-based (not job-sampled) and should be validated against real job data:

- Rock pad: excavation, fill dirt
- Site prep: excavation, wire, vapor, fabric, fill dirt
- Adhoc: fill dirt

## Items Below 5-Job Threshold

Items with <5 job samples — used geometry/formula fallback; may refine with more data:

- Slab 8in: 1 job
- Block 6in: 0 jobs
- Block 12in: 4 jobs

## Known Gaps

- **No excavator equipment resource.** Footer and edge CostItems assume concrete/rebar/wire only. If excavator time should be included, a new Phase 1 resource (EQP-EXC-*) needs to be added.
- **Roll dimensions not in Phase 1.** Vapor barrier and weed fabric CostItems assume standard 12×300 ft rolls (3600 sf). Roll dimensions exist only as calculator constants, not as extractable leaf resources.
- **All formwork/pour labor is implicit.** Concrete labor hours are sampled from job data (median 0.067–0.088 hrs/sf for slabs) but the concrete calculator does not distinguish between form, pour, and finish labor separately. They're rolled into the single LAB-CONCRETE-LABORER-RATE.
- **No markup in CostItems.** Rates are base cost only. Markup is applied at BOQ/tendering layer.
