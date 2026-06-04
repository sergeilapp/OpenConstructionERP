# Bedrock App Cost Data Extract 1 — Import Summary

## What this is

A cost database extraction from the Bedrock Siteworks estimating app for import into OCERP. Contains 691 items across two phases:

| Phase | File | Items | Description |
|---|---|---|---|
| 1 | `resources.json` | 648 | Leaf resources (materials, labor, equipment rates) |
| 2 | `cost_items.json` | 17 | Concrete composite CostItems (slabs, footers, block wall, piers, etc.) |
| 2 | `cost_items_rock_pad.json` | 10 | Rock pad composites (stone, excavation, fill dirt) |
| 2 | `cost_items_site_prep.json` | 11 | Site prep composites (excavation, board, rebar, vapor barrier) |
| 2 | `cost_items_adhoc.json` | 5 | Adhoc composites (labor, driving, access) |

## Key details

- **Region:** `BEDROCK-MAIN` (all items)
- **Prefix:** `BED-` (BED-CONC-, BED-ROCK-, BED-PREP-, BED-ADHOC-) — avoids collision with existing CWICR items
- **Model:** Unified `oe_costs_item` table — same as CWICR (55K+) and Tennessee pilot
- **Validation:** All 43 composites pass `rate == sum(components.cost)` within ±0.01

## Import order matters

Phase 1 resources must be imported **before** Phase 2 cost items, because each cost item's `components` array references leaf resource `code` values. If Phase 1 fails, Phase 2 items will still import but their component references won't resolve.

## The script: `import_bedrock_costs.py`

The script:
1. Logs in via `POST /api/v1/users/auth/login/`
2. Validates each item's rate matches sum of component costs
3. Bulk-imports each file via `POST /api/v1/costs/bulk/`
4. Verifies a sample of items exist in DB
5. Triggers catalog extraction via `POST /api/v1/catalog/extract/`
6. Reports catalog stats

## What went wrong (and the fix)

### 1. Phase 1 timeout

The original 30s timeout on `urllib.request.urlopen()` was too short for the 648-item bulk insert. The `except Exception` handler caught the timeout silently (printing to stderr only) and returned `None`, so Phase 1 was skipped without the user noticing. Phase 2's 43 items (a fast import) succeeded, giving a misleading "43 total."

**Fix:** Timeout increased from 30s → 120s. Added `WARNING: only X/Y items imported` message.

### 2. Region tab not visible on Costs page

The frontend's `RegionTabBar` looks up each region in `REGION_MAP` (defined in `frontend/src/stores/useCostDatabaseStore.ts`). If the region key is missing, the tab returns `null` (hidden). `BEDROCK-MAIN` wasn't in the map — only CWICR regions and `CUSTOM` were.

**Fix:** Added `"BEDROCK-MAIN"` entry to `REGION_MAP` with label "Bedrock Siteworks".

### 3. Catalog tab not visible

The generic `POST /api/v1/catalog/extract/` endpoint calls `extract_from_cost_items()`, which creates `CatalogResource` entries **without setting `region`** (`region = NULL`). The region stats query (`stats_by_region()`) filters `WHERE region IS NOT NULL`, so extracted resources contributed to no tab. The "My Catalog" tab is hardcoded to `region = "CUSTOM"`.

Tennessee data works because `extract_tennessee_catalog.py` uses `service.import_region_from_costs("USA_TENNESSEE")` instead, which **does** set `region`.

**Fix:** Ran `service.import_region_from_costs("BEDROCK-MAIN")` directly, extracting 27 catalog resources (19 material, 5 labor, 3 equipment) with proper region assignment.

### 4. Frontend/backend port mismatch

The Vite dev server (`frontend/vite.config.ts`) proxied `/api` to `http://127.0.0.1:9090`, but the backend runs on port 8000. This was introduced by an upstream change that updated the default from 8000 → 9090 for v4.1.0+. The `start-dev.sh` script always starts the backend on 8000.

**Fix:** Reverted proxy target to `http://127.0.0.1:8000`. Added a sanity check in `start-dev.sh` that compares the vite proxy port against the backend port and exits early on mismatch.

## Post-import steps

After running the import script, two additional steps are needed for full visibility:

### Add region to REGION_MAP

Add an entry for `"BEDROCK-MAIN"` in `frontend/src/stores/useCostDatabaseStore.ts`:
```ts
"BEDROCK-MAIN": {
  label: "Bedrock Siteworks (USD)",
  name: "Bedrock Siteworks",
  flag: "us",
  currency: "USD",
},
```

### Run region-aware catalog extraction

Use the backend service directly (not the generic `/api/v1/catalog/extract/` endpoint):
```bash
source venv/bin/activate
cd backend && python -c "
import asyncio
from app.database import async_session_factory
from app.modules.catalog.service import CatalogResourceService

async def main():
    async with async_session_factory() as session:
        service = CatalogResourceService(session)
        counts = await service.import_region_from_costs('BEDROCK-MAIN')
        await session.commit()
        print(f'Extracted {sum(counts.values())} resources')

asyncio.run(main())
"
```

## How to run

```bash
python3 bedrock_app_cost_data_extract_1/import_bedrock_costs.py \
  --data-dir bedrock_app_cost_data_extract_1
```

## Supporting files

| File | Purpose |
|---|---|
| `design_decisions.md` | Design rationale (data model, naming, factor derivation tiers, exclusions) |
| `validation_report.md` | Full validation results per item, sampling coverage, flagged items |
| `concrete_sampling_report.json` | Job sampling statistics for concrete factors (median, count per factor) |
| `resource_exclusions.json` | 55 variables excluded from extraction with rationale |
