#!/usr/bin/env python3
"""Import a review-only JSON cost package into OCERP.

Run from OCERP/backend, for example:

    uv run python ../scripts/import_tcg_package.py \
      --data-dir ../bedrock_truck_calculator_extract_review --dry-run

The package manifest must define `source` and `region`. Cleanup only deletes
records matching that package source/region.
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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def dec(value: object) -> Decimal:
    return Decimal(str(value or 0))


def component_total(factor: object, quantity: object, unit_cost: object) -> str:
    return str(dec(factor) * dec(quantity) * dec(unit_cost))


def load_manifest(data_dir: Path) -> dict[str, Any]:
    manifest = load_json(data_dir / "import_manifest.json")
    if not manifest.get("source") or not manifest.get("region"):
        raise RuntimeError("import_manifest.json must define source and region")
    if not manifest.get("review_only"):
        raise RuntimeError("Refusing to import package without review_only=true")
    return manifest


def validate_files(
    data_dir: Path,
    source: str,
    region: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    catalog = load_json(data_dir / "catalog_resources.json")
    costs = load_json(data_dir / "cost_items.json")
    assemblies = load_json(data_dir / "assemblies.json")
    resource_codes = {r["resource_code"] for r in catalog}
    cost_codes = {c["code"] for c in costs}
    errors = []
    for row in [*catalog, *costs]:
        if row.get("source") not in (None, source):
            errors.append(f"{row.get('resource_code') or row.get('code')} has source {row.get('source')} expected {source}")
        if row.get("region") not in (None, region):
            errors.append(f"{row.get('resource_code') or row.get('code')} has region {row.get('region')} expected {region}")
    for item in costs:
        total = sum(float(c.get("cost") or 0) for c in item.get("components") or [])
        if abs(total - float(item["rate"])) > 0.01:
            errors.append(f"{item['code']} rate mismatch: {item['rate']} != {total:.2f}")
        for comp in item.get("components") or []:
            if comp["code"] not in resource_codes:
                errors.append(f"{item['code']} unresolved resource {comp['code']}")
    for asm in assemblies:
        total = sum(float(c.get("total") or 0) for c in asm.get("components") or [])
        if abs(total - float(asm.get("total_rate") or 0)) > 0.01:
            errors.append(f"{asm['code']} total mismatch: {asm.get('total_rate')} != {total:.2f}")
        for comp in asm.get("components") or []:
            code = comp.get("cost_item_code")
            if code and code not in cost_codes:
                errors.append(f"{asm['code']} unresolved cost item {code}")
    if errors:
        raise RuntimeError("Validation failed:\n" + "\n".join(errors))
    return catalog, costs, assemblies


async def count_existing(session, source: str, region: str) -> dict[str, int]:
    catalog = await session.scalar(
        select(func.count())
        .select_from(CatalogResource)
        .where(CatalogResource.region == region, CatalogResource.source == source)
    )
    costs = await session.scalar(
        select(func.count())
        .select_from(CostItem)
        .where(CostItem.region == region, CostItem.source == source)
    )
    assemblies = await session.scalar(
        select(func.count()).select_from(Assembly).where(Assembly.metadata_["source"].as_string() == source)
    )
    components = await session.scalar(
        select(func.count())
        .select_from(Component)
        .join(Assembly, Component.assembly_id == Assembly.id)
        .where(Assembly.metadata_["source"].as_string() == source)
    )
    return {
        "catalog_resources": int(catalog or 0),
        "cost_items": int(costs or 0),
        "assemblies": int(assemblies or 0),
        "assembly_components": int(components or 0),
    }


async def cleanup(session, source: str, region: str) -> dict[str, int]:
    assembly_ids = [
        row[0]
        for row in (await session.execute(select(Assembly.id).where(Assembly.metadata_["source"].as_string() == source))).all()
    ]
    deleted_components = 0
    deleted_assemblies = 0
    if assembly_ids:
        result = await session.execute(delete(Component).where(Component.assembly_id.in_(assembly_ids)))
        deleted_components = int(result.rowcount or 0)
        result = await session.execute(delete(Assembly).where(Assembly.id.in_(assembly_ids)))
        deleted_assemblies = int(result.rowcount or 0)
    result = await session.execute(delete(CostItem).where(CostItem.region == region, CostItem.source == source))
    deleted_costs = int(result.rowcount or 0)
    result = await session.execute(delete(CatalogResource).where(CatalogResource.region == region, CatalogResource.source == source))
    deleted_catalog = int(result.rowcount or 0)
    return {
        "components": deleted_components,
        "assemblies": deleted_assemblies,
        "cost_items": deleted_costs,
        "catalog_resources": deleted_catalog,
    }


async def import_catalog(session, rows: list[dict[str, Any]], source: str, region: str) -> int:
    session.add_all(
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
            source=source,
            region=region,
            specifications=row.get("specifications") or {},
            metadata_=row.get("metadata") or {},
        )
        for row in rows
    )
    await session.flush()
    return len(rows)


async def import_cost_items(session, rows: list[dict[str, Any]], source: str, region: str) -> int:
    session.add_all(
        CostItem(
            code=row["code"],
            description=row.get("description") or row["code"],
            descriptions=row.get("descriptions") or {},
            unit=row["unit"],
            rate=str(row["rate"]),
            currency=row.get("currency") or "USD",
            source=source,
            classification=row.get("classification") or {},
            components=row.get("components") or [],
            tags=row.get("tags") or [],
            region=region,
            metadata_=row.get("metadata") or {},
        )
        for row in rows
    )
    await session.flush()
    return len(rows)


async def load_lookup_maps(session, source: str, region: str) -> tuple[dict[str, Any], dict[str, Any]]:
    cost_rows = (
        await session.execute(select(CostItem.code, CostItem.id).where(CostItem.region == region, CostItem.source == source))
    ).all()
    resource_rows = (
        await session.execute(
            select(CatalogResource.resource_code, CatalogResource.id).where(
                CatalogResource.region == region,
                CatalogResource.source == source,
            )
        )
    ).all()
    return ({code: item_id for code, item_id in cost_rows}, {code: resource_id for code, resource_id in resource_rows})


async def import_assemblies(session, rows: list[dict[str, Any]], source: str, region: str) -> int:
    cost_map, resource_map = await load_lookup_maps(session, source, region)
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
            metadata_={**(row.get("metadata") or {}), "tags": row.get("tags") or [], "source": source, "region": region},
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


from app.modules.costs.router import _invalidate_cost_cache


async def async_main(args: argparse.Namespace) -> None:
    manifest = load_manifest(args.data_dir)
    source = manifest["source"]
    region = manifest["region"]
    catalog, costs, assemblies = validate_files(args.data_dir, source, region)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "valid": True,
                    "source": source,
                    "region": region,
                    "catalog_resources": len(catalog),
                    "cost_items": len(costs),
                    "assemblies": len(assemblies),
                },
                indent=2,
            )
        )
        return
    async with async_session_factory() as session:
        before = await count_existing(session, source, region)
        plan = {
            "source": source,
            "region": region,
            "before": before,
            "package_counts": {"catalog_resources": len(catalog), "cost_items": len(costs), "assemblies": len(assemblies)},
            "cleanup": bool(args.cleanup),
        }
        if args.dry_run:
            print(json.dumps({"dry_run": True, "plan": plan}, indent=2, default=str))
            return
        result: dict[str, Any] = {"source": source, "region": region, "before": before}
        try:
            if args.cleanup:
                result["cleanup"] = await cleanup(session, source, region)
            result["catalog_imported"] = await import_catalog(session, catalog, source, region)
            result["cost_items_imported"] = await import_cost_items(session, costs, source, region)
            result["assemblies_imported"] = await import_assemblies(session, assemblies, source, region)
            result["after"] = await count_existing(session, source, region)
            await session.commit()
            _invalidate_cost_cache()
        except Exception:
            await session.rollback()
            raise
        print(json.dumps(result, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("../bedrock_tcg_model_job_extract_v4_review"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
