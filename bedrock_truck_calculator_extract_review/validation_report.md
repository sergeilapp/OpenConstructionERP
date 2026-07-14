# Bedrock Truck Calculator Extract Review Validation Report

Status: standalone review-only package created from the truck calculator entries previously embedded in the TCG v4 review package.

## Package Counts

| Record Type | Count |
|---|---:|
| Catalog resources | 9 |
| CostItems | 3 |
| Assemblies | 0 |
| Assembly components | 0 |

## Namespace

| Field | Value |
|---|---|
| Source | `bedrock_truck_calculator_extract_review` |
| Region | `BEDROCK-REVIEW` |
| Review only | `true` |

## Included CostItems

| Code | Unit | Rate | Notes |
|---|---:|---:|---|
| `BEDROCK-TRUCK-OPERATING-LOCAL-MI` | MI | 4.375 | Fuel plus maintenance per local mile |
| `BEDROCK-TRUCK-OPERATING-LONG-MI` | MI | 4.875 | Fuel plus maintenance per longer-distance mile |
| `BEDROCK-TRUCK-LOCAL-2MAN-TRAVEL-MI` | MI | 8.3333 | Observed 84-mile round trip unitized to a mileage rate |

## Validation

- JSON syntax validation passed.
- CostItem component resource references resolve to catalog resources.
- CostItem `rate` values equal summed component costs within `0.01` tolerance.
- No assembly references are present because this package has no assemblies.
- No single-component CostItems remain. Driving labor rates are represented as atomic catalog resources and are used as components in the observed round-trip CostItem.
- Remaining CostItems include multiple component categories: operating-mile items use fuel material plus maintenance equipment, and the unitized two-man travel item uses fuel material, maintenance equipment, and driving labor.

## Import Blocker

No current importer blocker. `OCERP/scripts/import_tcg_package.py` has been restored from the Bedrock cost import branch and was used for this package.

## Import Result

Imported from `OCERP/backend` with:

```bash
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_truck_calculator_extract_review --cleanup
```

Result:
- Catalog resources imported: 9
- CostItems imported: 3
- Assemblies imported: 0
- Existing matching rows before import: 0 catalog resources, 0 CostItems, 0 assemblies
