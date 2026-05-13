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

| Code | Description | Unit | Rate |
|------|-------------|------|------|
| DEM-HSE-01 | House demolition (wood-frame) | SF | $10.38 |
| DEM-GRG-01 | Garage demolition | SF | $7.50 |
| DEM-CON-01 | Concrete removal | SF | $4.25 |
| DEM-ASP-01 | Asphalt removal | SF | $3.50 |
| EXC-BLK-01 | Bulk excavation | CY | $12.75 |
| EXC-TRN-01 | Trench excavation | LF | $15.00 |
| GRD-SIT-01 | Site grading | SF | $0.45 |
| FILL-CMP-01 | Fill and compaction | CY | $18.50 |
| SW-FRN-01 | French drain | LF | $28.00 |
| SW-INF-01 | Stormwater infiltration pit | EA | $850.00 |
| UT-WTR-01 | Water service line | LF | $22.00 |
| UT-SWR-01 | Sewer service line | LF | $28.00 |

## Notes

- All items use `region: USA_TENNESSEE`
- All items have `currency: USD`
- All items have `source: manual` (derived from USACE + BLS + market estimates)
- Component validation: `rate == sum(components.cost)`
- Tags include: demolition, excavation, stormwater, utilities, sitework, nashville, tn