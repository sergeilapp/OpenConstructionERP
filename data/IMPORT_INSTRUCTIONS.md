# Import Instructions: US Tennessee Sitework Cost Database

## Prerequisites

1. OCERP backend running at http://localhost:8082
2. Logged in as estimator or admin account
3. Data file: `data/us_tn_sitework_costs.json`

## Quick Import

```bash
cd /home/sergei/dev/bedrock-siteworks/OCERP
python scripts/import_cost_database.py
```

## Manual Import (via API)

### 1. Login
```bash
TOKEN=$(curl -s -X POST http://localhost:8082/api/v1/users/auth/demo-login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"estimator@openestimator.io"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### 2. Bulk import
```bash
curl -X POST http://localhost:8082/api/v1/costs/bulk/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @data/us_tn_sitework_costs.json
```

### 3. Verify
```bash
# Search for Tennessee region items
curl -s "http://localhost:8082/api/v1/costs/?region=USA_TENNESSEE&limit=20" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Or search by code prefix
curl -s "http://localhost:8082/api/v1/costs/?search=DEM-&limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

## File Import (CSV/Excel alternative)

```bash
curl -X POST http://localhost:8082/api/v1/costs/import/file/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data/us_tn_sitework_costs.csv"
```

## Current Data: 12 Pilot Items

| Code | Description | Unit | Rate | Components |
|------|-------------|------|------|------------|
| DEM-HSE-01 | House demolition (wood-frame) | SF | $10.33 | Labor + Equipment + 2 Materials |
| DEM-GRG-01 | Garage demolition (detached) | SF | $7.50 | Labor + Equipment + 2 Materials |
| DEM-CON-01 | Concrete removal (slabs) | SF | $4.25 | Labor + Equipment + Disposal |
| DEM-ASP-01 | Asphalt removal (pavement) | SF | $3.50 | Labor + Equipment + Disposal |
| EXC-BLK-01 | Bulk excavation, common earth | CY | $12.45 | 2 Labor + 5 Equipment |
| EXC-TRN-01 | Trench excavation (utility, up to 3ft) | LF | $15.00 | 2 Labor + 2 Equipment + 3 Materials |
| GRD-SIT-01 | Site grading and leveling | SF | $0.45 | 2 Labor + 3 Equipment + 1 Material |
| FILL-CMP-01 | Fill import, placement, compaction | CY | $18.50 | 2 Labor + 3 Equipment + 2 Materials |
| SW-FRN-01 | French drain installation | LF | $28.00 | 3 Labor + 2 Equipment + 5 Materials |
| SW-INF-01 | Stormwater infiltration pit | EA | $850.00 | 3 Labor + 2 Equipment + 4 Materials |
| UT-WTR-01 | Water service line (4" PVC) | LF | $22.00 | 3 Labor + 2 Equipment + 4 Materials |
| UT-SWR-01 | Sewer service line (6" PVC) | LF | $28.00 | 3 Labor + 2 Equipment + 4 Materials |

## Data Sources

- **Equipment rates**: USACE EP 1110-1-8 (Dec 2022, Region 3 Southeast) — `data/usace_equipment_rates.json`
- **Labor wages**: BLS OEWS May 2024 Nashville-Davidson-Murfreesboro-Franklin, TN MSA — `data/bls_labor_wages.json`
- **Material rates**: Nashville market estimates (Home Depot, Lowe's, local suppliers) — `data/material_rates.json`
- **TDOT validation**: 2024 Average Unit Bid Prices — `data/tdot_bid_prices.json`

## Notes

- All items use `region: USA_TENNESSEE`
- All items have `currency: USD`
- All items have `source: manual` (derived from USACE + BLS + market estimates)
- Component validation: `rate == sum(components.cost)` within $0.01 tolerance
- Tags include: demolition, excavation, stormwater, utilities, sitework, nashville, tn
- Each item includes `metadata.data_sources` and `metadata.validation_status`
- TDOT comparison notes are in `metadata.tdot_comparison` where applicable

## Validation Report

See `docs/validation_report.md` for detailed comparison against TDOT bid prices.
