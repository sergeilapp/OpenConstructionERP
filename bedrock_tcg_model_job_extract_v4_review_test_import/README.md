# TCG Model Job Extract v4 Review

Status: review-only import package for OCERP app inspection.

Current test import status: revised package validates and dry-runs under region `BEDROCK-TCG-V4-FD-TEST` with source `bedrock_tcg_v4_fd_test_import`. The database still contains the previous imported v4 counts until `--cleanup` is run again.

Included records:
- 45 catalog resources
- 17 CostItems
- 5 assemblies
- 10 assembly components

French drain reassessment:
- `TCG-V5-ASM-STORMWATER-INFILTRATION-PIT-SF` supersedes `TCG-V4-ASM-STORMWATER-FRENCH-DRAIN-DRAFT`.
- Quarry `truck_cost_per_load` rows for job `38396` are modeled as delivered material load prices, not separate hauling stacked on proxy material rates.
- Known subtotal is `$69,640` before unresolved #8 top course, construction entrance stone removal/offhaul, conditional check dams, rock excavation allowance treatment, and ambiguous driving labor/equipment treatment.
- The prior `7 HR @ $95` driving labor and `168 MI` driving equipment evidence is excluded from base because delivered material load prices should already include supplier delivery. Keep it as a review item unless Bedrock confirms it is crew mobilization or spoil-haul support.

Truck travel additions:
- Added atomic truck fuel and maintenance resources for local mileage (`$1.375/mi` fuel + `$3.00/mi` maintenance) and longer-distance mileage (`$1.625/mi` fuel + `$3.25/mi` maintenance).
- Added driving labor CostItems at `$95/hr` local/default and `$85/hr` longer-distance observed rate.
- Added a reusable observed 84-mile, two-man round-trip CostItem at `$700/roundtrip` with fuel, maintenance, and labor components.
- Added single/dual/tri axle truck resource metadata using the known calculator capacities (`3 CY`, `13 CY`, `20 CY`) without introducing calculator code.

Validate/import from `OCERP/backend`:

```bash
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_v4_fd_test_import --validate-only
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_v4_fd_test_import --dry-run
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_v4_fd_test_import --cleanup
```

This package is not final-approved. It is intended to get the reviewed CostItems and assemblies into OCERP for visual/app review.

See `validation_report.md` for imported scope and carried review flags.
