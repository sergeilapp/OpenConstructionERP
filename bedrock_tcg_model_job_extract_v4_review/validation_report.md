# TCG Model Job Extract v4 Review Validation Report

Status: review-only package imported into OCERP for app inspection.

## Import Result

Imported with:

```bash
cd /home/sergei/dev/bedrock-siteworks/OCERP/backend
uv run python ../scripts/import_tcg_package.py \
  --data-dir ../bedrock_tcg_model_job_extract_v4_review \
  --cleanup
```

Result:

| Record Type | Imported |
|---|---:|
| Catalog resources | 36 |
| CostItems | 15 |
| Assemblies | 5 |
| Assembly components | 13 |

Package namespace:

| Field | Value |
|---|---|
| Source | `bedrock_tcg_model_job_extract_v4_review` |
| Region | `BEDROCK-TCG-V4-REVIEW` |
| Review only | `true` |

## Included Reviewed Scopes

| Scope | Included As |
|---|---|
| Stormwater / French drain | 4 CostItems + `TCG-V4-ASM-STORMWATER-FRENCH-DRAIN-DRAFT` |
| Utility trenching / conduit | 1 LS CostItem |
| Concrete curb / paving / asphalt repair | Split CostItems + `TCG-V4-ASM-CONCRETE-CURB-PAVING-DRAFT` |
| Crawlspace/footer drainage | Delivered stone + LS scope + `TCG-V4-ASM-CRAWLSPACE-FOOTER-DRAINAGE-DRAFT` |
| Site prep / erosion / demo-disposal | Delivered drain stone + erosion scope + demo/disposal scope + `TCG-V4-ASM-SITE-PREP-DEMO-EROSION-DRAFT` |
| Fill placement review | Delivered fill review + placement review + `TCG-V4-ASM-FILL-PLACEMENT-REVIEW` |

## Carried Review Flags

- `TCG-P7-R2`: drain stone quarry rate versus calculator pricing source.
- `TCG-P7-R3`: fill material/hauling unit semantics.
- `TCG-P7-R5`: #57 stone uses drain-stone quarry rate as proxy.
- `TCG-P7-R6`: sand rate is a draft derivation.
- `TCG-P7-R7`: job 38447 uses `$125/hr` adhoc labor.
- `TCG-RS-R1`: demo/disposal candidate assembly mismatch, `$14,650` versus `$17,450` equipment addons.

## Validation

- JSON schema/reference validation passed via `import_tcg_package.py --validate-only`.
- Dry-run passed before import and showed no existing records for the v4 source/region.
- Assembly codes use a `TCG-V4-ASM-*` namespace to avoid collisions with the prior review slice.
