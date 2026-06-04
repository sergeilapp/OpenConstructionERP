# Bedrock V2 Item Design Review

Human approvals applied before generation:

- D1: backend/direct DB import script first; no new API bulk route.
- D2: keep only useful conversion wrappers; no pure aliases.
- D3: prefer ton-mi for hauling where data supports it; preserve review tag otherwise.
- D4: defer subcontractor labor modeling.
- D5: finish/fiber/insulation modeled as separate optional CostItems/components.
- D6: natural dominant takeoff units; avoid vague lump sum.
- D7: defer rare non-deterministic scopes under 5 samples.
- D8: cleanup support included; attempt-1 cleanup requires separate approval.

| Decision | Count |
|---|---:|
| assembly | 3 |
| cost_item_conversion | 11 |
| cost_item_installed_work | 14 |
| delete_alias | 18 |

## Deleted Pure Aliases

- `BED-CONC-LABOR`: Rejected pure alias; use CatalogResource LAB-CONCRETE-LABORER-RATE directly.
- `BED-CONC-ACCESS`: Rejected pure alias; use CatalogResource MAT-DISTANCE-FROM-ACCESS-COST-PER-FOOT directly.
- `BED-CONC-MAT-GATHER`: Rejected pure alias; use CatalogResource LAB-CONCRETE-LABORER-RATE directly.
- `BED-ROCK-STONE`: Rejected pure alias; use CatalogResource MAT-CONCRETE-ROCK-PER-TON directly.
- `BED-ROCK-BOARD`: Rejected pure alias; use CatalogResource MAT-ROCKPAD-BOARD-COST-PER-FOOT directly.
- `BED-ROCK-REBAR`: Rejected pure alias; use CatalogResource MAT-ROCKPAD-REBAR-PIECE directly.
- `BED-ROCK-EROSION-CONTROL`: Rejected pure alias; use CatalogResource MAT-ROCKPAD-EROSION-CONTROL-WIRE-PRICE directly.
- `BED-ROCK-LABOR`: Rejected pure alias; use CatalogResource LAB-ROCKPAD-LABORER-RATE directly.
- `BED-ROCK-ACCESS`: Rejected pure alias; use CatalogResource MAT-DISTANCE-FROM-ACCESS-COST-PER-FOOT directly.
- `BED-ROCK-MAT-GATHER`: Rejected pure alias; use CatalogResource LAB-ROCKPAD-LABORER-RATE directly.
- `BED-PREP-BOARD`: Rejected pure alias; use CatalogResource MAT-PREPARATION-BOARD-COST-PER-FOOT-6X6 directly.
- `BED-PREP-REBAR`: Rejected pure alias; use CatalogResource MAT-PREPARATION-REBAR-PRICE-PER-FOOT directly.
- `BED-PREP-LABOR`: Rejected pure alias; use CatalogResource LAB-PREPARATION-LABORER-RATE directly.
- `BED-PREP-ACCESS`: Rejected pure alias; use CatalogResource MAT-DISTANCE-FROM-ACCESS-COST-PER-FOOT directly.
- `BED-PREP-MAT-GATHER`: Rejected pure alias; use CatalogResource LAB-PREPARATION-LABORER-RATE directly.
- `BED-ADHOC-LABOR`: Rejected pure alias; use CatalogResource LAB-ADHOC-LABORER-RATE directly.
- `BED-ADHOC-MAT-GATHER`: Rejected pure alias; use CatalogResource LAB-ADHOC-LABORER-RATE directly.
- `BED-ADHOC-ACCESS`: Rejected pure alias; use CatalogResource MAT-DISTANCE-FROM-ACCESS-COST-PER-FOOT directly.
