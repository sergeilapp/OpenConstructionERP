# TCG Model Job Extract v4 Review

Status: review-only import package for OCERP app inspection.

Current import status: revised package validates and dry-runs under region `BEDROCK-TCG-V4-REVIEW` with source `bedrock_tcg_model_job_extract_v4_review`. The database still contains the previous imported v4 counts until `--cleanup` is run again.

Included records:
- 37 catalog resources
- 12 CostItems
- 5 assemblies
- 10 assembly components

French drain reassessment:
- `TCG-V5-ASM-STORMWATER-INFILTRATION-PIT-SF` supersedes `TCG-V4-ASM-STORMWATER-FRENCH-DRAIN-DRAFT`.
- Quarry `truck_cost_per_load` rows for job `38396` are modeled as delivered material load prices, not separate hauling stacked on proxy material rates.
- Known subtotal is `$69,640` before unresolved #8 top course, construction entrance stone removal/offhaul, conditional check dams, rock excavation allowance treatment, and ambiguous driving labor/equipment treatment.
- The prior `7 HR @ $95` driving labor and `168 MI` driving equipment evidence is excluded from base because delivered material load prices should already include supplier delivery. Keep it as a review item unless Bedrock confirms it is crew mobilization or spoil-haul support.

Validate/import from `OCERP/backend`:

```bash
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_v4_review --validate-only
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_v4_review --dry-run
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_v4_review --cleanup
```

This package is not final-approved. It is intended to get the reviewed CostItems and assemblies into OCERP for visual/app review.

See `validation_report.md` for imported scope and carried review flags.
