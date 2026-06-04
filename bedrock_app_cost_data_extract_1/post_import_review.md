# Post-Import Review — Bedrock Cost Database

## Summary

Import completed: **691 items** landed in the CostItem table (`oe_costs_item`). Of those:

| Category | Count | % |
|---|---|---|
| Leaf resources extracted from Bedrock | 648 | 94% |
| Composite cost items (43 extracted) | 43 | 6% |
| **Total** | **691** | **100%** |

## Problem 1: 635 resources are unreachable by the catalog

The `POST /catalog/extract/` endpoint scans `CostItem.components[]` and creates `CatalogResource` records only for items that appear as components. Since our 648 leaf resources have empty `components[]`, only ~13 are referenced by the 43 composites. Result:

- **/costs page**: 691 items (648 leaf + 43 composites) — cluttered, hard to navigate
- **/catalog page**: 27 resources — nearly empty, despite having rich data

**Fix needed**: The 648 leaf resources should be imported into the `oe_catalog_resource` table directly, then deleted from `oe_costs_item`. The catalog populates from components, but we need a separate path for base-price data that isn't (yet) referenced by composites.

## Problem 2: 29 of 43 cost items are single-component wrappers

| Tier | Count | What they are | Verdict |
|---|---|---|---|
| **Pure aliases** (qty=1, rate matches resource) | 18 | `*-LABOR`, `*-ACCESS`, `*-MAT-GATHER`, `*-STONE`, `*-BOARD`, `*-REBAR`, `*-EROSION-CONTROL` | ❌ Delete — reference the resource directly in the BOQ |
| **Fixed-conversion wrappers** (qty=0.75, block items) | 6 | Blocks and top block — 0.75 blocks/lf universal factor | ⚠️ Keep for now — converting blocks/ea → blocks/lf is a legitimate takeoff convenience |
| **Unit-conversion wrappers** (formula factor, qty≠1) | 5 | Edge (cy→lf), excavation (hr→sf), wire/vapor/fabric (roll→sf) | ⚠️ Keep for now — they serve a real unit-conversion purpose |
| **Legitimate composites** (2+ components) | 14 | Slabs (5), footer (3), pier (2), apron (2), core fill (2), driving (3), fill dirt (2) | ✅ Keep — these are the only items doing real work composition |

## Problem 3: The import architecture flows the wrong direction

Current flow:

```
resources.json ──▶ /costs/bulk/ ──▶ CostItem table  ← wrong
                    ↓
                 /catalog/extract/  ──▶ CatalogResource table
                    (misses 635 items with empty components[])
```

Should be:

```
resources.json ──▶ CatalogResource table (direct bulk insert, region=BEDROCK-MAIN)
cost_items*.json ──▶ /costs/bulk/ ──▶ CostItem table (components reference catalog codes)
```

## Problem 4: No component editing in the UI

Components inside cost items are **read-only** in the `/costs` page. There is no form, modal, or inline editor to add/remove/modify components. All component data must be populated via import scripts. This means:

- Building new composites from our 648 resources must happen via script (or a new UI feature)
- The 14 legitimate composites are locked to whatever components they were imported with
- The block/edge/excavation items can't be refined without re-importing

---

## Comprehensive Recommendation: Option C — Revisit the Modeling

### Core thesis

Stop treating our data as two parallel datasets (648 resources + 43 cost items) and restructure it as a **proper regional cost database** where:

- **Catalog** = atomic building blocks (materials, labor, equipment — the 648 base prices)
- **Cost Items** = work items an estimator puts in a BOQ (genuine composites with real breakdowns)

The 18 pass-through aliases exist because the original extraction modeled cost items at the wrong level of abstraction. They should vanish entirely — the BOQ can reference catalog resources directly.

### Step 1: Load resources into the catalog properly

Write a script (or extend the import) to bulk-insert the 648 resources into `oe_catalog_resource` with `region='BEDROCK-MAIN'`, `source='cost_import'`. These become the building blocks.

Then delete the 648 leaf entries from `oe_costs_item`. The 43 composites stay.

Result: `/catalog` shows 648 resources (under a BEDROCK-MAIN tab), `/costs` shows 43 items (clean).

### Step 2: Delete the 18 pure-alias cost items

Remove these — they add nothing:

```
BED-CONC-LABOR           BED-ROCK-STONE            BED-PREP-BOARD
BED-CONC-ACCESS          BED-ROCK-BOARD            BED-PREP-REBAR
BED-CONC-MAT-GATHER      BED-ROCK-REBAR            BED-PREP-LABOR
                         BED-ROCK-EROSION-CONTROL   BED-PREP-ACCESS
                         BED-ROCK-LABOR             BED-PREP-MAT-GATHER
                         BED-ROCK-ACCESS
                         BED-ROCK-MAT-GATHER
BED-ADHOC-LABOR
BED-ADHOC-ACCESS
BED-ADHOC-MAT-GATHER
```

In the BOQ, reference the underlying resources directly (e.g. `LAB-CONCRETE-LABORER-RATE` instead of `BED-CONC-LABOR`).

### Step 3: Keep the conversion-wrapper items (for now)

The 11 items that transform units serve a real purpose for estimators doing takeoff:

| Item | Conversion | Purpose |
|---|---|---|
| `BED-CONC-BLOCK-*` (4 items) | 0.75 blocks/lf | Takeoff by linear foot of wall |
| `BED-CONC-TOP-BLOCK` | 0.75 blocks/lf | Same — top course |
| `BED-CONC-EDGE` | 0.0494 cy/sf → $11.11/lf | Concrete volume → edge beam length |
| `BED-ROCK-EXCAVATION` | 0.08 hr/sf → $8.00/sf | Labor time → area |
| `BED-PREP-EXCAVATION` | 0.08 hr/sf → $11.60/sf | Labor time → area (operator rate) |
| `BED-PREP-WIRE` | 0.0312 sheets/sf → $0.63/sf | Roll → coverage area |
| `BED-PREP-VAPOR` | 0.0003 rolls/sf → $0.11/sf | Roll → coverage area |
| `BED-PREP-FABRIC` | 0.0003 rolls/sf → $0.17/sf | Roll → coverage area |

These are legitimate thin composites — they package a conversion factor so estimators don't have to. If they were folded into the resource itself (e.g. storing `MAT-WEED-FABRIC-PER-SF` instead of `MAT-WEED-FABRIC-PER-ROLL`), these cost items wouldn't be needed.

**Future**: decide whether to keep these or pre-convert the resource units so they vanish.

### Step 4: Preserve the 14 genuine composites

These are the foundation of the cost database:

| Code | Components | Notes |
|---|---|---|
| `BED-CONC-SLAB-4IN` | 5 | concrete + rebar + wire + vapor + labor |
| `BED-CONC-SLAB-6IN` | 5 | same pattern |
| `BED-CONC-SLAB-8IN` | 5 | same pattern |
| `BED-CONC-FOOTER` | 3 | concrete + rebar + wire |
| `BED-CONC-PIER` | 2 | concrete + rebar |
| `BED-CONC-APRON` | 2 | concrete + rebar |
| `BED-CONC-CORE-FILL` | 2 | core fill + rebar |
| `BED-CONC-DRIVING` | 3 | labor + truck time + truck mileage |
| `BED-ROCK-FILL-DIRT` | 2 | aggregate + truck |
| `BED-ROCK-DRIVING` | 3 | same as concrete driving |
| `BED-PREP-FILL-DIRT` | 2 | same as rock fill dirt |
| `BED-PREP-DRIVING` | 3 | same as concrete driving |
| `BED-ADHOC-DRIVING` | 3 | same as concrete driving |
| `BED-ADHOC-FILL-DIRT` | 2 | same as rock fill dirt |

### Step 5: Build richer composites (next iteration)

Now that the catalog holds 648 real material prices, compose them into fuller work items. This is where the framework expects you to be — proper cost items with meaningful breakdowns:

**Concrete wall assemblies** (currently blocks + core fill + labor are separate):
- `BED-CONC-WALL-8IN` → block + core fill + rebar + labor (all-in cost per lf)
- `BED-CONC-WALL-10IN` → same pattern
- `BED-CONC-WALL-12IN` → same pattern

**Rock pad assemblies** (currently stone + excavation + rebar are separate):
- `BED-ROCK-PAD-ASSEMBLY` → stone + excavation + rebar + erosion control + labor

**Site prep assemblies** (currently board + rebar + wire + vapor + fabric + excavation are separate):
- `BED-PREP-AREA-ASSEMBLY` → excavation + board + rebar + wire + vapor + fabric

**Concrete footing + wall combo:**
- `BED-CONC-FOOTING-WALL-8IN` → footer + block wall + core fill + rebar + labor

### How the final architecture looks

```
┌─────────────────────────────────────────────┐
│              CatalogResource                 │
│              (oe_catalog_resource)           │
│                                              │
│   648 entries, region=BEDROCK-MAIN           │
│      MAT-QUARRY-*    (520 quarry products)   │
│      MAT-PREP-*      (52 site prep mats)     │
│      MAT-CONCRETE-*  (12 concrete mats)      │
│      MAT-ROCKPAD-*   (6 rock pad mats)       │
│      MAT-CAT-*       (32 catalog mats)       │
│      MAT-OTHER-*     (12 other mats)         │
│      EQP-*           (8 equipment)           │
│      LAB-*           (6 labor rates)         │
└──────────────────┬──────────────────────────┘
                   │ components[].code references
                   ▼
┌─────────────────────────────────────────────┐
│              CostItem                        │
│              (oe_costs_item)                 │
│                                              │
│   ~25-35 entries, region=BEDROCK-MAIN        │
│      (14 preserved + 0-11 conversion         │
│       + ~10-20 new richer composites)        │
│                                              │
│   Each has real components[] referencing     │
│   catalog resources with quantities & rates  │
└─────────────────────────────────────────────┘
```

The `/costs` page shows only work items an estimator would put in a BOQ. The `/catalog` page shows the full palette of materials, labor, and equipment at their base prices. The derivation chain is clean: cost items are composed from catalog resources, not duplicated alongside them.

### Concrete action items

1. **[High] Write a catalog import script** — bulk-insert 648 resources into `oe_catalog_resource` with `region='BEDROCK-MAIN'`, then delete the 648 orphans from `oe_costs_item`
2. **[High] Delete 18 pure-alias cost items** — they're noise in the cost database
3. **[Medium] Rebuild the import pipeline** so future extractions go resources→catalog → cost items, not everything→cost items
4. **[Medium] Decide fate of 11 conversion-wrapper items** — keep as convenience wrappers or fold conversions into resource units
5. **[Low] Build richer composites** (wall assemblies, rock pad assemblies, site prep assemblies) once the catalog is populated
