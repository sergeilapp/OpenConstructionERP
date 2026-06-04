#!/usr/bin/env python3
"""Create a BOQ for BEDROCK-TCG-V4-REVIEW cost items, grouped by MasterFormat.

Run from OCERP/backend:

    python ../scripts/create_tcg_boq.py
"""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from sqlalchemy import select, update

from app.database import async_session_factory
from app.modules.boq.schemas import BOQCreate, PositionCreate, SectionCreate
from app.modules.boq.service import BOQService
from app.modules.costs.models import CostItem
from app.modules.projects.models import Project

# ── Project ─────────────────────────────────────────────────────────────
PROJECT_ID = UUID("548c9bfd-0409-4638-ae35-f55d1d47c0ab")

# ── Cost items keyed by MasterFormat code ──────────────────────────────
# (ordinal_suffix, code, description, unit, quantity, rate, cost_item_id)
ITEMS_BY_MF: dict[str, list[tuple]] = {
    "02 00 00": [
        ("01", "TCG-DELIVER-DRAIN-STONE-CE", "Deliver drain stone for construction entrance", "t", 1.0, 80.83, UUID("e2348dc9-16e6-4656-a99a-06a0b68ca176")),
        ("02", "TCG-SITE-PREP-DEMO-DISPOSAL-SCOPE", "Site prep demolition, tree removal, and disposal review scope", "LS", 1.0, 24665.00, UUID("d470acf9-9152-4cb2-ad44-a22fa3ebdee2")),
    ],
    "03 00 00": [
        ("01", "TCG-CONCRETE-CURB-GUTTER-SCOPE", "Concrete curb and gutter internal work", "LS", 1.0, 12572.75, UUID("a1cf0aa6-f8d3-4de7-b545-912a4f4226d4")),
    ],
    "31 00 00": [
        ("01", "TCG-EROSION-STABILIZATION-SCOPE", "Erosion control and site stabilization scope", "LS", 1.0, 23550.00, UUID("8a1bd668-6619-4a88-9eda-044b53aec998")),
        ("02", "TCG-DELIVER-57-STONE-CF", "Deliver #57 stone for crawlspace/footer drainage", "t", 1.0, 83.96, UUID("e5502d38-d5e2-4233-a6f7-498f4ad8b831")),
        ("03", "TCG-CRAWLSPACE-FOOTER-EXCAVATION-SCOPE", "Crawlspace/footer excavation and drainage scope", "LS", 1.0, 20386.73, UUID("182572c0-2102-417f-825e-36b20cc42705")),
        ("04", "TCG-DELIVER-FILL-REVIEW", "Delivered fill material and hauling review item", "CY", 1.0, 26.30, UUID("1bbd158a-fb66-4ed6-8fc0-6cd59f12a320")),
        ("05", "TCG-PLACE-COMPACT-FILL-REVIEW", "Place and compact imported fill review item", "LS", 1.0, 25380.00, UUID("aa8fab44-9739-4311-a048-f465d6707e28")),
        ("06", "TCG-PLACE-TOPSOIL-REVIEW", "Place stockpiled topsoil review item", "LS", 1.0, 135.00, UUID("6b6ad3c6-e182-44d0-90f0-6fa68e665500")),
    ],
    "32 00 00": [
        ("01", "TCG-PAVING-ASPHALT-REPAIR-SUBCONTRACT-SCOPE", "Subcontracted paving and asphalt utility trench repair", "LS", 1.0, 11300.00, UUID("b8b0152b-9132-4e3d-87df-f1be1c07a0aa")),
    ],
    "33 00 00": [
        ("01", "TCG-DELIVER-57-STONE-FD", "Deliver #57 stone for French drain", "t", 1.0, 79.57, UUID("6c608b5b-5b58-43de-ad01-f2a18109a369")),
        ("02", "TCG-DELIVER-SAND-FD", "Deliver sand for French drain", "CY", 1.0, 63.20, UUID("8e2618c9-73ec-421b-8099-748e03a5417c")),
        ("03", "TCG-PLACE-AGGREGATE-FD", "Place aggregate layers for French drain", "LS", 1.0, 12015.00, UUID("706b45fa-dacf-442d-ada3-555273bf3b0b")),
        ("04", "TCG-STORMWATER-DRAINAGE-FILTRATION-SCOPE", "Stormwater filtration fabric, observation pipe, equipment, and specialty labor", "LS", 1.0, 8200.00, UUID("68506a15-8931-4de2-83ef-be86748328af")),
        ("05", "TCG-UTILITY-TRENCHING-CONDUIT-SCOPE", "Utility trenching, conduit/pipe installation, and backfill", "LS", 1.0, 54225.00, UUID("184301c8-76d2-4a59-8029-263881390b04")),
    ],
}

SECTION_META: dict[str, tuple[str, str]] = {
    "02 00 00": ("02", "Division 02 — Existing Conditions"),
    "03 00 00": ("03", "Division 03 — Concrete"),
    "31 00 00": ("31", "Division 31 — Earthwork"),
    "32 00 00": ("32", "Division 32 — Exterior Improvements"),
    "33 00 00": ("33", "Division 33 — Utilities"),
}


async def main() -> None:
    async with async_session_factory() as session:
        svc = BOQService(session)
        boq_id = None

        # 1. Set project classification_standard
        await session.execute(
            update(Project)
            .where(Project.id == PROJECT_ID)
            .values(classification_standard="masterformat")
        )
        await session.commit()
        print("✓ Updated project classification_standard → masterformat")

        # 2. Create BOQ
        boq = await svc.create_boq(
            BOQCreate(
                project_id=PROJECT_ID,
                name="TCG Brentwood Sitework — Sitework Estimate",
                description="Sitework estimate based on BEDROCK-TCG-V4-REVIEW cost database, organised by MasterFormat divisions 02, 03, 31, 32, and 33.",
                estimate_type="detailed",
                base_date="2026-Q2",
            )
        )
        boq_id = boq.id
        print(f"✓ Created BOQ: {boq.name} ({boq.id})")

        # 3. Create sections + positions per MasterFormat division
        for mf_code, items in ITEMS_BY_MF.items():
            section_ordinal, section_desc = SECTION_META[mf_code]

            sec = await svc.create_section(
                boq_id,
                SectionCreate(
                    ordinal=section_ordinal,
                    description=section_desc,
                ),
            )
            section_id = sec.id
            print(f"  ✓ Section: {section_desc} ({section_id})")

            for suffix, code, desc, unit, qty, rate, cost_item_id in items:
                ordinal = f"{mf_code}.{suffix}"
                pos = await svc.add_position(
                    PositionCreate(
                        boq_id=boq_id,
                        parent_id=section_id,
                        ordinal=ordinal,
                        description=desc,
                        unit=unit,
                        quantity=qty,
                        unit_rate=rate,
                        classification={"masterformat": mf_code},
                        source="cwicr",
                        cost_item_id=cost_item_id,
                    )
                )
                print(f"    ✓ {ordinal} — {code}: {desc[:50]}... ${rate}")

        # 4. Commit
        await session.commit()
        print()
        print("=" * 60)
        print("BOQ created successfully!")
        print(f"  Project: {PROJECT_ID}")
        print(f"  BOQ ID:  {boq_id}")
        print(f"  Sections: {len(ITEMS_BY_MF)}")
        total_items = sum(len(v) for v in ITEMS_BY_MF.values())
        print(f"  Positions: {total_items}")
        print("=" * 60)


asyncio.run(main())
