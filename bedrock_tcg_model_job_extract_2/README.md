# TCG Model Job Extract 2 — Unitized CostItems

Status: review-only import package for OCERP app inspection.

Extends the v4 POC (15 CostItems) with 7 new unit-priced CostItems
derived from LS-to-unitized decomposition review.

Validate/import from `OCERP/backend`:

```bash
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_2 --validate-only
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_2 --dry-run
uv run python ../scripts/import_tcg_package.py --data-dir ../bedrock_tcg_model_job_extract_2 --cleanup
```

This package is not final-approved. It is intended to get the unitized CostItems
into OCERP for visual/app review and Bedrock team demo.
