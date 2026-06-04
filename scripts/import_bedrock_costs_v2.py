#!/usr/bin/env python3
"""Import Bedrock v2 cost package into OCERP.

Run from OCERP/backend so `app.*` imports resolve, for example:

    python ../scripts/import_bedrock_costs_v2.py \
      --data-dir ../bedrock_app_cost_data_extract_2 --dry-run --verify

The script uses the backend DB session directly for catalog resources and
assemblies because v2 needs CatalogResource-first import and stable component
resolution. It does not run attempt-1 cleanup unless `--cleanup-attempt1` is
explicitly passed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select

from app.database import async_session_factory
from app.modules.assemblies.models import Assembly, Component
from app.modules.catalog.models import CatalogResource
from app.modules.costs.models import CostItem
from app.modules.projects import models as _project_models  # noqa: F401  # load FK metadata


REGION = "BEDROCK-MAIN"
SOURCE = "bedrock_extraction_v2"
ATTEMPT1_SOURCE = "bedrock_extraction"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def dec(value: object) -> Decimal:
    return Decimal(str(value or 0))


def component_total(factor: object, quantity: object, unit_cost: object) -> str:
    return str(dec(factor) * dec(quantity) * dec(unit_cost))


async def count_existing(session) -> dict[str, int]:
    catalog = await session.scalar(
        select(func.count()).select_from(CatalogResource).where(CatalogResource.region == REGION, CatalogResource.source == SOURCE)
    )
    costs = await session.scalar(
        select(func.count()).select_from(CostItem).where(CostItem.region == REGION, CostItem.source == SOURCE)
    )
    assemblies = await session.scalar(
        select(func.count()).select_from(Assembly).where(Assembly.metadata_["source"].as_string() == SOURCE)
    )
    attempt1_costs = await session.scalar(
        select(func.count()).select_from(CostItem).where(CostItem.region == REGION, CostItem.source == ATTEMPT1_SOURCE)
    )
    return {
        "catalog_resources_v2": int(catalog or 0),
        "cost_items_v2": int(costs or 0),
        "assemblies_v2": int(assemblies or 0),
        "cost_items_attempt1": int(attempt1_costs or 0),
    }


async def cleanup_v2(session) -> dict[str, int]:
    assembly_ids = [
        row[0]
        for row in (
            await session.execute(select(Assembly.id).where(Assembly.metadata_["source"].as_string() == SOURCE))
        ).all()
    ]
    deleted_components = 0
    if assembly_ids:
        result = await session.execute(delete(Component).where(Component.assembly_id.in_(assembly_ids)))
        deleted_components = int(result.rowcount or 0)
        result = await session.execute(delete(Assembly).where(Assembly.id.in_(assembly_ids)))
        deleted_assemblies = int(result.rowcount or 0)
    else:
        deleted_assemblies = 0
    result = await session.execute(delete(CostItem).where(CostItem.region == REGION, CostItem.source == SOURCE))
    deleted_costs = int(result.rowcount or 0)
    result = await session.execute(delete(CatalogResource).where(CatalogResource.region == REGION, CatalogResource.source == SOURCE))
    deleted_catalog = int(result.rowcount or 0)
    return {
        "components": deleted_components,
        "assemblies": deleted_assemblies,
        "cost_items": deleted_costs,
        "catalog_resources": deleted_catalog,
    }


async def cleanup_attempt1(session) -> dict[str, int]:
    result = await session.execute(delete(CostItem).where(CostItem.region == REGION, CostItem.source == ATTEMPT1_SOURCE))
    return {"cost_items_attempt1": int(result.rowcount or 0)}


async def import_catalog(session, rows: list[dict[str, Any]]) -> int:
    resources = []
    for row in rows:
        resources.append(
            CatalogResource(
                resource_code=row["resource_code"],
                name=row["name"],
                resource_type=row["resource_type"],
                category=row["category"],
                unit=row["unit"],
                base_price=str(row["base_price"]),
                min_price=str(row.get("min_price", 0)),
                max_price=str(row.get("max_price", 0)),
                currency=row.get("currency") or "USD",
                usage_count=0,
                source=row.get("source") or SOURCE,
                region=row.get("region") or REGION,
                specifications=row.get("specifications") or {},
                metadata_=row.get("metadata") or {},
            )
        )
    session.add_all(resources)
    await session.flush()
    return len(resources)


async def import_cost_items(session, rows: list[dict[str, Any]]) -> int:
    items = []
    for row in rows:
        items.append(
            CostItem(
                code=row["code"],
                description=row.get("description") or row["code"],
                descriptions=row.get("descriptions") or {},
                unit=row["unit"],
                rate=str(row["rate"]),
                currency=row.get("currency") or "USD",
                source=row.get("source") or SOURCE,
                classification=row.get("classification") or {},
                components=row.get("components") or [],
                tags=row.get("tags") or [],
                region=row.get("region") or REGION,
                metadata_=row.get("metadata") or {},
            )
        )
    session.add_all(items)
    await session.flush()
    return len(items)


async def load_lookup_maps(session) -> tuple[dict[str, Any], dict[str, Any]]:
    cost_rows = (
        await session.execute(select(CostItem.code, CostItem.id).where(CostItem.region == REGION, CostItem.source == SOURCE))
    ).all()
    resource_rows = (
        await session.execute(
            select(CatalogResource.resource_code, CatalogResource.id).where(
                CatalogResource.region == REGION, CatalogResource.source == SOURCE
            )
        )
    ).all()
    return ({code: item_id for code, item_id in cost_rows}, {code: resource_id for code, resource_id in resource_rows})


async def import_assemblies(session, rows: list[dict[str, Any]]) -> int:
    cost_map, resource_map = await load_lookup_maps(session)
    imported = 0
    for row in rows:
        assembly = Assembly(
            code=row["code"],
            name=row["name"],
            description=row.get("description") or "",
            unit=row["unit"],
            category=row.get("category") or "",
            classification=row.get("classification") or {},
            total_rate=str(row.get("total_rate") or 0),
            currency=row.get("currency") or "USD",
            bid_factor=str(row.get("bid_factor") or 1.0),
            regional_factors=row.get("regional_factors") or {},
            is_template=bool(row.get("is_template", True)),
            project_id=None,
            owner_id=None,
            metadata_={**(row.get("metadata") or {}), "tags": row.get("tags") or []},
        )
        session.add(assembly)
        await session.flush()
        components = []
        for index, comp in enumerate(row.get("components") or []):
            cost_item_code = comp.get("cost_item_code")
            resource_code = comp.get("catalog_resource_code") or comp.get("resource_code")
            cost_item_id = cost_map.get(cost_item_code) if cost_item_code else None
            catalog_resource_id = resource_map.get(resource_code) if resource_code else None
            if cost_item_code and cost_item_id is None:
                raise RuntimeError(f"Assembly {row['code']} unresolved cost_item_code {cost_item_code}")
            if resource_code and catalog_resource_id is None:
                raise RuntimeError(f"Assembly {row['code']} unresolved catalog_resource_code {resource_code}")
            factor = comp.get("factor", 1.0)
            quantity = comp.get("quantity", 1.0)
            unit_cost = comp.get("unit_cost", 0.0)
            total = comp.get("total") if comp.get("total") is not None else component_total(factor, quantity, unit_cost)
            components.append(
                Component(
                    assembly_id=assembly.id,
                    cost_item_id=cost_item_id,
                    catalog_resource_id=catalog_resource_id,
                    description=comp.get("description") or cost_item_code or resource_code or "",
                    resource_type=comp.get("resource_type"),
                    factor=str(factor),
                    quantity=str(quantity),
                    unit=comp.get("unit") or row["unit"],
                    unit_cost=str(unit_cost),
                    total=str(total),
                    sort_order=index,
                    metadata_=comp.get("metadata") or {},
                )
            )
        session.add_all(components)
        imported += 1
    await session.flush()
    return imported


def validate_files(data_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    catalog = load_json(data_dir / "catalog_resources.json")
    costs = load_json(data_dir / "cost_items.json")
    assemblies = load_json(data_dir / "assemblies.json")
    resource_codes = {r["resource_code"] for r in catalog}
    cost_codes = {c["code"] for c in costs}
    errors = []
    for item in costs:
        total = sum(float(c.get("cost") or 0) for c in item.get("components") or [])
        if abs(total - float(item["rate"])) > 0.01:
            errors.append(f"{item['code']} rate mismatch")
        for comp in item.get("components") or []:
            if comp["code"] not in resource_codes:
                errors.append(f"{item['code']} unresolved resource {comp['code']}")
    for asm in assemblies:
        for comp in asm.get("components") or []:
            if comp.get("cost_item_code") and comp["cost_item_code"] not in cost_codes:
                errors.append(f"{asm['code']} unresolved cost item {comp['cost_item_code']}")
            if comp.get("catalog_resource_code") and comp["catalog_resource_code"] not in resource_codes:
                errors.append(f"{asm['code']} unresolved catalog resource {comp['catalog_resource_code']}")
    if errors:
        raise RuntimeError("Validation failed:\n" + "\n".join(errors))
    return catalog, costs, assemblies


async def verify_import(session) -> dict[str, int]:
    counts = await count_existing(session)
    components = await session.scalar(
        select(func.count())
        .select_from(Component)
        .join(Assembly, Component.assembly_id == Assembly.id)
        .where(Assembly.metadata_["source"].as_string() == SOURCE)
    )
    counts["assembly_components_v2"] = int(components or 0)
    return counts


async def async_main(args: argparse.Namespace) -> None:
    catalog, costs, assemblies = validate_files(args.data_dir)
    async with async_session_factory() as session:
        before = await count_existing(session)
        plan = {
            "before": before,
            "package_counts": {
                "catalog_resources": len(catalog),
                "cost_items": len(costs),
                "assemblies": len(assemblies),
            },
            "cleanup_v2": bool(args.cleanup),
            "cleanup_attempt1": bool(args.cleanup_attempt1),
            "modes": {
                "catalog_only": args.catalog_only,
                "costs_only": args.costs_only,
                "assemblies_only": args.assemblies_only,
            },
        }
        if args.dry_run:
            print(json.dumps({"dry_run": True, "plan": plan}, indent=2, default=str))
            return

        result: dict[str, Any] = {"before": before}
        try:
            if args.cleanup:
                result["cleanup_v2"] = await cleanup_v2(session)
            if args.cleanup_attempt1:
                result["cleanup_attempt1"] = await cleanup_attempt1(session)

            if not args.costs_only and not args.assemblies_only:
                result["catalog_imported"] = await import_catalog(session, catalog)
            if not args.catalog_only and not args.assemblies_only:
                result["cost_items_imported"] = await import_cost_items(session, costs)
            if not args.catalog_only and not args.costs_only:
                result["assemblies_imported"] = await import_assemblies(session, assemblies)

            if args.verify:
                result["verify"] = await verify_import(session)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        print(json.dumps(result, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--cleanup-attempt1", action="store_true")
    parser.add_argument("--catalog-only", action="store_true")
    parser.add_argument("--costs-only", action="store_true")
    parser.add_argument("--assemblies-only", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    selected_only = sum([args.catalog_only, args.costs_only, args.assemblies_only])
    if selected_only > 1:
        raise SystemExit("Use at most one of --catalog-only, --costs-only, --assemblies-only")
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
