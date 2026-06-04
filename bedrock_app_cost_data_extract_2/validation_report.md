# Bedrock V2 Validation Report

Generated: 2026-05-28T19:50:25+00:00
Status: **pass**

## Counts

| Entity | Count |
|---|---:|
| catalog_resources | 648 |
| cost_items | 30 |
| assemblies | 6 |
| conversion_wrappers | 11 |
| needs_design_review | 6 |

## Static Validation

- CatalogResource codes are unique in the generated file.
- CostItem rates equal summed component costs within $0.01.
- CostItem components resolve to generated catalog resources.
- Assembly totals equal summed components times bid_factor.
- Pure alias CostItems are rejected before output.

## Job-Based Validation Notes

Recent job frequency drove priority, but v2 does not treat Bedrock job/calculator buckets as import structures. High-frequency site prep, rock pads, weed fabric, borders, fill dirt, concrete slabs, Gibraltar components, apron, and core-fill scopes are represented or explicitly deferred.

Hauling remains tagged `needs_design_review` where attempt-1 trip components could not be honestly converted to ton-mi without job-level load and distance sampling.

## Errors

- None

## Warnings

- CostItem BED-CONC-CMU-BLOCK-10IN-PER-LF is a permitted conversion wrapper
- CostItem BED-CONC-CMU-BLOCK-12IN-PER-LF is a permitted conversion wrapper
- CostItem BED-CONC-CMU-BLOCK-6IN-PER-LF is a permitted conversion wrapper
- CostItem BED-CONC-CMU-BLOCK-8IN-PER-LF is a permitted conversion wrapper
- CostItem BED-CONC-CMU-TOP-BLOCK-PER-LF is a permitted conversion wrapper
- CostItem BED-CONC-EDGE-INSTALLED is a permitted conversion wrapper
- CostItem BED-PREP-EXCAVATION-INSTALLED is a permitted conversion wrapper
- CostItem BED-ROCK-EXCAVATION-INSTALLED is a permitted conversion wrapper
- CostItem BED-VAPOR-BARRIER-INSTALLED is a permitted conversion wrapper
- CostItem BED-WEED-FABRIC-INSTALLED is a permitted conversion wrapper
- CostItem BED-WIRE-MESH-INSTALLED is a permitted conversion wrapper
