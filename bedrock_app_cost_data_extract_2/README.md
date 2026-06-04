# Bedrock App Cost Data Extract 2

Clean v2 import package generated from Bedrock evidence and attempt-1 outputs.

## Model

- `catalog_resources.json` imports atomic resources into `oe_catalog_resource`.
- `cost_items.json` imports estimator-facing work/conversion items into `oe_costs_item`.
- `assemblies.json` imports larger packages into `oe_assemblies_assembly` and `oe_assemblies_component`.
- Pure alias CostItems are excluded; use catalog resources directly.

## Import

Run from `OCERP/backend` with the app environment configured:

```bash
python ../scripts/import_bedrock_costs_v2.py --data-dir ../bedrock_app_cost_data_extract_2 --dry-run --verify
python ../scripts/import_bedrock_costs_v2.py --data-dir ../bedrock_app_cost_data_extract_2 --cleanup --verify
```

Do not use `--cleanup-attempt1` without a separate explicit approval and backup.
