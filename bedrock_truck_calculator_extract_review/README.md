# Bedrock Truck Calculator Extract Review

Status: standalone review-only import package for Bedrock truck calculator rates and observed truck travel CostItems.

This package separates the truck calculator data that was originally added inside `OCERP/bedrock_tcg_model_job_extract_v4_review/`. The TCG v4 package is left intact as a historical/current review snapshot; this package provides a truck-specific namespace for independent review and future import.

Included records:
- 9 catalog resources
- 3 CostItems
- 0 assemblies

Namespace:
- Source: `bedrock_truck_calculator_extract_review`
- Region: `BEDROCK-REVIEW`
- Review only: `true`

Scope:
- local truck operating cost at `$4.375/mi`, split into `$1.375/mi` fuel and `$3.00/mi` maintenance
- longer-distance truck operating cost at `$4.875/mi`, split into `$1.625/mi` fuel and `$3.25/mi` maintenance
- local/default driving labor at `$95/hr` as an atomic catalog resource
- longer-distance driving labor at `$85/hr` as an atomic catalog resource
- observed 84-mile, two-man local round trip unitized to `$8.3333/mi` so an estimate line can use mileage quantity
- single, dual, and tri-axle dump truck capacity metadata from the calculator spec

Import from `OCERP/backend`:

```bash
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_truck_calculator_extract_review --validate-only
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_truck_calculator_extract_review --dry-run
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_truck_calculator_extract_review --cleanup
```

Future approval path:
- Keep this package in the shared `BEDROCK-REVIEW` region while review-only unless side-by-side comparison requires a dedicated region.
- Once approved, import into a stable operational region such as `USA_TENNESSEE` with source/provenance preserving `bedrock_truck_calculator_extract`.
- Do not create a new region for every extraction batch unless side-by-side review requires it.
