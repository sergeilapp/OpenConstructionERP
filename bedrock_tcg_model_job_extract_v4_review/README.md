# TCG Model Job Extract v4 Review

Status: review-only import package for OCERP app inspection.

Current import status: imported into OCERP under region `BEDROCK-TCG-V4-REVIEW` with source `bedrock_tcg_model_job_extract_v4_review`.

Included records:
- 36 catalog resources
- 15 CostItems
- 5 assemblies
- 13 assembly components

Validate/import from `OCERP/backend`:

```bash
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_v4_review --validate-only
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_v4_review --dry-run
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_v4_review --cleanup
```

This package is not final-approved. It is intended to get the reviewed CostItems and assemblies into OCERP for visual/app review.

See `validation_report.md` for imported scope and carried review flags.
