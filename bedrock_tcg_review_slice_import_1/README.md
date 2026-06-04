# TCG Review Slice Import 1

Status: review-only test package, not the final TCG import.

## Purpose

This package imports a small, reviewed slice of the TCG CostItem structure into OCERP so the team can inspect whether resources, CostItems, components, and an assembly roll up the way we expect.

## Included

- 16 catalog resources
- 5 CostItems
- 1 assembly

Included reviewed slices:

- Stormwater / French drain
- Utility trenching / conduit

## Validate

From `OCERP/`:

```bash
python -m json.tool bedrock_tcg_review_slice_import_1/catalog_resources.json >/tmp/tcg_catalog_resources.json
python -m json.tool bedrock_tcg_review_slice_import_1/cost_items.json >/tmp/tcg_cost_items.json
python -m json.tool bedrock_tcg_review_slice_import_1/assemblies.json >/tmp/tcg_assemblies.json
```

## Dry Run With Dedicated Review-Slice Importer

Activate the OCERP backend environment first, then run from `OCERP/backend`:

```bash
python ../scripts/import_tcg_review_slice.py \
  --data-dir ../bedrock_tcg_review_slice_import_1 \
  --dry-run
```

## Import For App Review

Run from `OCERP/backend` after dry-run succeeds:

```bash
python ../scripts/import_tcg_review_slice.py \
  --data-dir ../bedrock_tcg_review_slice_import_1 \
  --cleanup
```

`--cleanup` removes only prior rows with `source=bedrock_tcg_review_slice_import_1` and `region=BEDROCK-TCG-REVIEW`, then imports the package again. Use it when re-running this test package.

## Known Carried-Forward Review Items

- #57 stone rate uses the reviewed `$38/TON` draft proxy.
- Sand rate uses the reviewed `$25/CY` draft derivation.
- Stormwater labor split is draft: 89 HR aggregate placement, 20 HR stormwater-specific work.
- Utility trenching is LS for the draft; LF basis remains a Bedrock team review item.
- Utility `$6,500` material allowance and `$2,500` equipment allowance need team identification.

## Test BOQ

After importing the package, create the app-review BOQ with:

```bash
python scripts/create_tcg_review_boq.py --replace
```

Current generated BOQ:

- Project: `TCG Brentwood Sitework`
- Project ID: `8e5817aa-16b6-428f-bd2c-a340d1283d1f`
- BOQ name: `TCG Review Slice BOQ — Stormwater + Utilities`
- BOQ ID: `3e6acfc3-c095-4f3e-98b0-52ddbea8a1a2`
- Direct cost total: `$148,102.95`
