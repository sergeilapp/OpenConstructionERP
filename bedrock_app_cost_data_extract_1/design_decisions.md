# Design Decisions — Bedrock CostItem Extraction

## Data Model

**Unified CostItem table (`oe_costs_item`).** Leaf resources and composite recipes live in one table with embedded `components[]` arrays — same model as CWICR (55K+ items) and the Tennessee pilot. This keeps search, BOQ apply-rate, and `/costs/match` working out of the box. Rejected `oe_assemblies_assembly` + FK components (0 rows, separate feature for templated recipes).

## Naming Convention

All Bedrock items use the `BED-` prefix to avoid collisions with CWICR. Sub-prefixes by calculator:

| Prefix | Calculator | Items |
|---|---|---|
| `BED-CONC-` | Concrete | 17 |
| `BED-ROCK-` | Rock pad | 10 |
| `BED-PREP-` | Site prep | 11 |
| `BED-ADHOC-` | Adhoc | 5 |

## Unit Selection

Each CostItem's unit matches the BOQ takeoff unit, not the calculator's internal unit:

| Item(s) | Unit | Rationale |
|---|---|---|
| Slabs, apron | `sf` | BOQ applies per sq ft of slab surface |
| Footers, block wall, edge, core fill, access | `lf` | BOQ applies per linear ft of perimeter |
| Pier | `ea` | BOQ applies per pier |
| Driving | `trip` | BOQ quotes per truck trip |
| Labor, mat gather | `hr` | Direct labor hour costs |
| Stone, fill dirt | `ton` | Material priced by weight |
| Board | `lf` | Lumber priced by linear ft |
| Rebar (rock pad) | `ea` | Individual rebar pieces |
| Rebar (site prep) | `lf` | Rebar priced by length |
| Excavation | `sf` | Area-based excavation pricing |
| Erosion control, vapor, fabric, wire | `sf` | Coverage-area materials |

## Variant Strategy

Concrete PSI — the only variant dimension with real data. CostItems reference `MAT-CONCRETE-PRICE-PER-YARD` (a single leaf resource) and use `available_variants` in `metadata` to surface PSI pricing from the Phase 1 resource table. No separate CostItem per PSI grade.

Block size variants (6/8/10/12 in) ARE separate CostItems because the block width changes both material and labor factors.

Foundation type variants NOT modeled — footer size is the dominant variable, not the slab thickness.

## Factor Derivation — Three Tiers

### Tier 1: Sampled (concrete calculator items)

Used for all concrete CostItems except pass-throughs. The `rake estimating:extraction:concrete_sampling_report` task pulls real job data, computes per-factor rates, picks median-factor samples, and writes `sampled_factor_source` into metadata.

| Item | Sample count | Factor source |
|---|---|---|
| Slab 4/6/8in | 25 / 25 / 1 | Median of job samples; 8in fallback to formula (1 job only) |
| Footer | 200 | Median of job samples |
| Block 8in | 289 | Median of job samples (factor = 0.75 blocks/lf universal) |
| Block 10in | 7 | Median of job samples |
| Block 12in | 4 | Median of job samples (below 5-job threshold, geometry fallback) |
| Block 6in | 0 | No jobs found — geometry fallback (0.75 blocks/lf) |
| Pier | 200 | Median of job samples |
| Apron | 147 | Median of job samples |
| Edge | 200 | Median of job samples |
| Core fill | 200 | Median of job samples |
| Top block | 200 | Median of job samples |

Block factor is 0.75 blocks/lf across all sizes — consistent with standard 16" block geometry. All 289 samples for 8in block show exactly 0.75.

### Tier 2: Formula-based, tagged for future sampling (rock pad, site prep, adhoc calculators)

These calculators use geometric formulas rather than material-takeoff from job history. Factors derived from calculator source code with hardcoded defaults (e.g. 0.08 hrs/sf excavation labor). Items tagged `needs_sampling` so OCERP can flag them for validation after import.

### Tier 3: Pass-through (driving, labor, access, mat gather — all calculators)

Simple pass-through CostItems that reference a single leaf resource with qty=1. Their rate matches the leaf resource rate exactly. Used in BOQ directly; no decomposition needed.

## Single-Component Items (by design)

Block wall CostItems per course (BED-CONC-BLOCK-*), edge, top block, and all pass-throughs have exactly one component. This is intentional:

- **Block wall:** The CostItem per course represents block cost per lf only. Core fill, rebar, and labor are handled by separate CostItems (BED-CONC-CORE-FILL, BED-CONC-FOOTER, etc.). BOQ multiplies courses × perimeter × $/lf.
- **Edge:** Concrete cost per lf only. No rebar/core-fill needed for edge beams.
- **Rock pad stone/board/rebar/erosion-control:** One leaf resource per CostItem. They are composed at BOQ time, not in the CostItem.
- **Labor, driving, access, mat gather:** Utility CostItems that reference the relevant labor/equipment leaf resource. Same pattern across all calculators.

## Roll-Based Material Conversion

Weed fabric and vapor barrier CostItems assume standard roll dimensions (12 ft × 300 ft = 3600 sf). The calculator stores roll cost; the CostItem divides by 3600 sf for per-sf pricing. This is noted because roll dimensions are NOT yet available as Phase 1 resources — they exist only as calculator constants.

## Fill Dirt CostItem Structure

Fill dirt CostItems are 2-component composites: material (MAT-PREP-FILL-DIRT-AGGREGATE) plus equipment (EQP-TRUCK-COST-PER-MILE). The fill dirt material is discovered by a regex lookup against Phase 1 resources (`MAT-PREP-.*FILL.*DIRT`) with $15.00/ton fallback if no match.

## Exclusion Decisions

55 variables excluded from Phase 1 extraction:
- **17 phase2**: Composite cost variables (e.g. total block cost per lf, total footer cost per lf) — calculated by the CostItem itself, not a leaf resource.
- **31 exclude**: Markup percentages, config constants, company-specific adjustments, formulas — not importable as resources.
- **7 variant**: PSI-specific concrete pricing — handled through `available_variants` on the component, not separate leaf resources.

## Import Order

1. Phase 1: `resources.json` (648 leaf items) via `/costs/bulk/`
2. Phase 2: `cost_items.json`, `cost_items_rock_pad.json`, `cost_items_site_prep.json`, `cost_items_adhoc.json` (43 composite items) via `/costs/bulk/`
3. Catalog extraction via `/catalog/extract/`

Phase 1 must complete before Phase 2 because component references must resolve to existing leaf resources.

## Rate Composition

All composite CostItems satisfy `rate == sum(components[].cost)` within ±0.01 tolerance. The rate field represents base cost only — all markup is applied at the BOQ/tendering layer, not inside the CostItem.
