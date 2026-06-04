# TCG Review Slice Import 1 Validation Report

Status: review-only draft import package.

## Scope

This package intentionally includes only the most complete reviewed slices:

- `TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE`
- `TCG-UTILITY-TRENCHING-CONDUIT-SCOPE`
- stormwater delivery/place CostItems needed to test an assembly rollup

## Package Counts

| File | Count |
|---|---:|
| `catalog_resources.json` | 16 |
| `cost_items.json` | 5 |
| `assemblies.json` | 1 |

## Known Review Items Carried Forward

- #57 stone material rate uses `$38/TON` draft proxy.
- Sand material rate uses `$25/CY` draft derivation.
- Stormwater labor split is draft: 89 HR aggregate placement, 20 HR stormwater-specific scope.
- Utility trenching is `LS` for draft; LF basis remains a Bedrock team review item.
- Utility `$6,500` material allowance and `$2,500` equipment allowance need team identification.

## Import Safety

- Package is `review_only: true`.
- Region is `BEDROCK-TCG-REVIEW`.
- Source is `bedrock_tcg_review_slice_import_1`.
- This package is not the final TCG import package.

## Component Factor Requirement

Every CostItem component quantity must be interpreted as the amount of that component required for `1` unit of the parent CostItem.

Examples in this package:

| CostItem | Parent unit | Component | Component quantity meaning |
|---|---|---|---|
| `TCG-DELIVER-57-STONE-FD` | `t` | `TCG-RES-57-STONE-TON` | `1.0 t` of material per `1 t` delivered stone CostItem |
| `TCG-DELIVER-57-STONE-FD` | `t` | `TCG-RES-HAUL-57-STONE-LOAD` | `0.04399 LOAD` per `1 t` delivered stone CostItem |
| `TCG-DELIVER-SAND-FD` | `CY` | `TCG-RES-HAUL-SAND-LOAD` | `0.05129 LOAD` per `1 CY` delivered sand CostItem |

BOQ positions that use these CostItems must scale the component factors by the BOQ position quantity during review or when components are manually linked in the app.
