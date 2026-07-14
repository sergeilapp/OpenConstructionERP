# TCG Model Job Extract v4 Review Validation Report

Status: review-only package revised and validated for OCERP app inspection. The database still has the prior v4 import counts until `--cleanup` is run again.

## Import Result

Previously imported with:

```bash
cd /home/sergei/dev/bedrock-siteworks/OCERP/backend
uv run python ../scripts/import_tcg_package.py \
  --data-dir ../bedrock_tcg_model_job_extract_v4_review \
  --cleanup
```

Revised package validation result:

| Record Type | Imported |
|---|---:|
| Catalog resources | 45 |
| CostItems | 17 |
| Assemblies | 5 |
| Assembly components | 10 |

Package namespace:

| Field | Value |
|---|---|
| Source | `bedrock_tcg_model_job_extract_v4_review` |
| Region | `BEDROCK-TCG-V4-REVIEW` |
| Review only | `true` |

## Included Reviewed Scopes

| Scope | Included As |
|---|---|
| Stormwater / French drain | `TCG-INSTALL-STORMWATER-INFILTRATION-PIT-SF` + `TCG-V5-ASM-STORMWATER-INFILTRATION-PIT-SF` |
| Utility trenching / conduit | 1 LS CostItem |
| Concrete curb / paving / asphalt repair | Split CostItems + `TCG-V4-ASM-CONCRETE-CURB-PAVING-DRAFT` |
| Crawlspace/footer drainage | Delivered stone + LS scope + `TCG-V4-ASM-CRAWLSPACE-FOOTER-DRAINAGE-DRAFT` |
| Site prep / erosion / demo-disposal | Delivered drain stone + erosion scope + demo/disposal scope + `TCG-V4-ASM-SITE-PREP-DEMO-EROSION-DRAFT` |
| Fill placement review | Delivered fill review + placement review + `TCG-V4-ASM-FILL-PLACEMENT-REVIEW` |
| BedRock truck travel | Atomic fuel/maintenance/labor resources + local, long-distance, and 84-mile round-trip CostItems |

## Carried Review Flags

- `TCG-P7-R2`: drain stone quarry rate versus calculator pricing source.
- `TCG-P7-R3`: fill material/hauling unit semantics.
- `TCG-P7-R5`: #57 stone uses drain-stone quarry rate as proxy.
- `TCG-P7-R6`: sand rate is a draft derivation.
- `TCG-P7-R7`: job 38447 uses `$125/hr` adhoc labor.
- `TCG-RS-R1`: demo/disposal candidate assembly mismatch, `$14,650` versus `$17,450` equipment addons.
- `TCG-MAT-R1`: `truck_cost_per_load` is interpreted as delivered material load price, not hauling-only. Bedrock should confirm.
- `TCG-FD-R1`: #8 stone appears in scope, but job addition says credit to remove #8 stone `$4,500`; base inclusion unresolved.
- `TCG-FD-R2`: existing construction entrance stone removal/offhaul quantity and rate not independently isolated.
- `TCG-FD-R3`: excavation/offhaul row `43 LOAD @ $245` likely belongs to infiltration pit excess material, but exact semantics need confirmation.
- `TCG-FD-R4`: fabric quantity `12 ROLL` may or may not cover all fabric layers/wraps described in scope.
- `TCG-FD-R5`: check dams are conditional and should be optional, not base scope.

## French Drain Delivered-Material Reassessment

`TCG-V5-ASM-STORMWATER-INFILTRATION-PIT-SF` supersedes the prior French drain assembly because the old shape combined proxy material rates with `truck_cost_per_load` values. For job `38396`, the package now treats `38 LOAD @ $945` as delivered #57 stone and `4 LOAD @ $745` as delivered coarse sand.

Known revised subtotal before unresolved #8/top-course/removal/check-dam treatment and ambiguous driving treatment is `$69,640` against source job price `$76,421.25`, leaving `$6,781.25` for reconciliation against unresolved credits/additions, markup, export/version differences, non-base allowances, and any confirmed Bedrock crew mobilization or spoil-haul support.

The prior `7 HR @ $95` driving labor and `168 MI` driving equipment evidence is excluded from the French drain base model because delivered material load pricing should already include supplier delivery. Carry it as a review item unless Bedrock confirms it is not supplier delivery.

## BedRock Truck Travel Additions

Added standalone, reusable truck resources and CostItems without adding calculator code. The package now carries local mileage at `$4.375/mi` split into `$1.375/mi` fuel and `$3.00/mi` maintenance, and longer-distance mileage at `$4.875/mi` split into `$1.625/mi` fuel and `$3.25/mi` maintenance. Driving labor is available at `$95/hr` local/default and `$85/hr` longer-distance observed rate. A reusable observed local round-trip item models `84 MI + 2 men x 1.75 HR = $700/roundtrip`.

The anomalous example with `$6.00/mi` maintenance is intentionally excluded from the default truck maintenance basis.

## Validation

- JSON syntax validation passed after truck travel additions.
- JSON schema/reference validation previously passed via `import_tcg_package.py --validate-only`; `OCERP/scripts/import_tcg_package.py` has since been restored in this checkout.
- Validate-only passed after the French drain reassessment.
- Dry-run passed and showed existing prior v4 records in the database: 36 catalog resources, 15 CostItems, 5 assemblies, and 13 assembly components. A cleanup import would replace them with the revised package counts above.
- The French drain assembly now uses a `TCG-V5-ASM-*` code to make the reassessment explicit; unrelated assemblies keep their `TCG-V4-ASM-*` namespace.
- Static package audit against `BEDROCK_TO_OCERP_EXTRACTION_GUIDE.md` passed for JSON counts, CostItem resource references, CostItem `rate == sum(components.cost)`, assembly CostItem references, and assembly rollups.
- Four single-component CostItems remain by design: fill placement is a review-only labor scope with missing equipment rate, topsoil placement is a review-only placeholder, and the two driving labor CostItems are unit-conversion items from observed labor dollars to hourly rates.
- Import is no longer blocked by a missing helper; `OCERP/scripts/import_tcg_package.py` is present. `OCERP/scripts/import_tcg_job.py` remains a separate BOQ-position importer and is not the package importer.
