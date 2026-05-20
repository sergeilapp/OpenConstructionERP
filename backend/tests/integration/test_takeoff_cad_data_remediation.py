"""HTTP-level regression for the takeoff CAD-data remediation fixes.

Seeds an in-memory CAD session (standalone → uploader-only gate is a
no-op for an empty owner) and drives the real endpoints so the fixes
are pinned at the API boundary:

* D-TKC-009 — mixed-type column sort no longer 500s.
* D-TKC-018 — numeric-aware element filter ("3" matches stored 3.0).
* D-TKC-011 — aggregate response labels totals additive vs global stat.
* D-TKC-025 — describe surfaces excluded non-numeric count.
* D-TKC-026 — value-counts exposes non-null percentage base.
* D-TKC-030 — cad-group element totals require predominantly numeric.
* D-TKC-012 — create-boq emits real UoM and keeps every dimension.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest_asyncio.fixture(scope="module")
async def client():
    app = create_app()

    @asynccontextmanager
    async def lifespan_ctx():
        async with app.router.lifespan_context(app):
            yield

    async with lifespan_ctx():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture(scope="module")
async def auth(client: AsyncClient) -> dict[str, str]:
    unique = uuid.uuid4().hex[:8]
    email = f"cadrem-{unique}@test.io"
    password = f"CadRem{unique}9!"
    reg = await client.post(
        "/api/v1/users/auth/register",
        json={"email": email, "password": password, "full_name": "Cad Rem"},
    )
    assert reg.status_code == 201, reg.text

    from sqlalchemy import update as sa_update

    from app.database import async_session_factory
    from app.modules.users.models import User

    async with async_session_factory() as s:
        await s.execute(sa_update(User).where(User.email == email.lower()).values(role="admin", is_active=True))
        await s.commit()

    login = await client.post(
        "/api/v1/users/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _seed_session(elements: list[dict], columns_metadata=None) -> str:
    """Push a standalone CAD session into the in-memory store.

    Empty ``user_id`` → the uploader-only access gate is a no-op.
    """
    import time

    from app.modules.takeoff import router as tk

    sid = f"test-{uuid.uuid4().hex}"
    tk._cad_sessions[sid] = {
        "elements": elements,
        "filename": "t.ifc",
        "format": "ifc",
        "created": time.time(),  # fresh — not evicted by TTL cleanup
        "columns_metadata": columns_metadata or {},
        "user_id": "",
        "project_id": None,
    }
    return sid


# ── D-TKC-009 — mixed-type sort must not 500 ─────────────────────────────


@pytest.mark.asyncio
async def test_dtkc009_mixed_type_sort_no_500(client: AsyncClient, auth: dict[str, str]) -> None:
    sid = _seed_session([{"mark": 12}, {"mark": "A-3"}, {"mark": 7}, {"mark": None}])
    r = await client.get(
        f"/api/v1/takeoff/cad-data/elements/?session_id={sid}&sort_by=mark",
        headers=auth,
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 4


# ── D-TKC-018 — numeric-aware filter ─────────────────────────────────────


@pytest.mark.asyncio
async def test_dtkc018_numeric_filter_matches(client: AsyncClient, auth: dict[str, str]) -> None:
    sid = _seed_session([{"length": 3.0}, {"length": 3.10}, {"length": 9}])
    r = await client.get(
        f"/api/v1/takeoff/cad-data/elements/?session_id={sid}&filter_column=length&filter_value=3",
        headers=auth,
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1  # "3" matches stored 3.0


# ── D-TKC-025 — describe excluded-count ──────────────────────────────────


@pytest.mark.asyncio
async def test_dtkc025_describe_reports_excluded(client: AsyncClient, auth: dict[str, str]) -> None:
    sid = _seed_session([{"v": 10}, {"v": 20}, {"v": "N/A"}, {"v": 30}, {"v": "TBD"}, {"v": 40}])
    r = await client.post(
        "/api/v1/takeoff/cad-data/describe/",
        json={"session_id": sid},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    col = next(c for c in r.json()["columns"] if c["name"] == "v")
    assert col["dtype"] == "number"
    assert col["excluded_non_numeric"] == 2
    assert col["sum"] == 100


# ── D-TKC-026 — value-counts non-null base ───────────────────────────────


@pytest.mark.asyncio
async def test_dtkc026_value_counts_non_null(client: AsyncClient, auth: dict[str, str]) -> None:
    sid = _seed_session([{"cat": "A"}, {"cat": "A"}, {"cat": None}, {"cat": None}, {"cat": None}])
    r = await client.post(
        "/api/v1/takeoff/cad-data/value-counts/",
        json={"session_id": sid, "column": "cat", "limit": 10},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["null_count"] == 3
    assert body["non_null_total"] == 2
    a_row = next(v for v in body["values"] if v["value"] == "A")
    assert a_row["percentage"] == 40.0  # 2 / 5
    assert a_row["percentage_of_non_null"] == 100.0  # 2 / 2


# ── D-TKC-011 — aggregate totals semantics ───────────────────────────────


@pytest.mark.asyncio
async def test_dtkc011_aggregate_totals_semantics(client: AsyncClient, auth: dict[str, str]) -> None:
    sid = _seed_session([{"cat": "A", "v": 10}, {"cat": "A", "v": 30}, {"cat": "B", "v": 50}])
    r = await client.post(
        "/api/v1/takeoff/cad-data/aggregate/",
        json={
            "session_id": sid,
            "group_by": ["cat"],
            "aggregations": {"v": "avg"},
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["totals_semantics"]["v"] == "global_statistic"


# ── D-TKC-030 — cad-group element totals predominantly-numeric ───────────


@pytest.mark.asyncio
async def test_dtkc030_group_totals_require_majority_numeric(client: AsyncClient, auth: dict[str, str]) -> None:
    # thickness column: 2/3 numeric → still totalled, 1 excluded reported.
    sid = _seed_session(
        [
            {"category": "Wall", "thickness": "200"},
            {"category": "Wall", "thickness": "300mm"},
            {"category": "Wall", "thickness": "250"},
        ]
    )
    r = await client.post(
        "/api/v1/takeoff/cad-group/elements/",
        json={"session_id": sid, "group_key": {"category": "Wall"}},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["totals"].get("thickness") == 450.0
    assert body["totals_excluded_non_numeric"].get("thickness") == 1


@pytest.mark.asyncio
async def test_dtkc030_mostly_string_column_not_totalled(client: AsyncClient, auth: dict[str, str]) -> None:
    # code column: only 1/3 parses → must NOT be totalled.
    sid = _seed_session(
        [
            {"category": "W", "code": "A-1"},
            {"category": "W", "code": "B-2"},
            {"category": "W", "code": "7"},
        ]
    )
    r = await client.post(
        "/api/v1/takeoff/cad-group/elements/",
        json={"session_id": sid, "group_key": {"category": "W"}},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    assert "code" not in r.json()["totals"]


# ── D-TKC-012 — create-boq real UoM + all dimensions ─────────────────────


@pytest.mark.asyncio
async def test_dtkc012_create_boq_real_uom_all_dimensions(client: AsyncClient, auth: dict[str, str]) -> None:
    proj = await client.post("/api/v1/projects/", json={"name": "CAD QTO"}, headers=auth)
    assert proj.status_code in (200, 201), proj.text
    project_id = proj.json()["id"]

    # One group with BOTH volume and area sums.
    sid = _seed_session(
        [
            {"category": "Wall", "volume": 9.0, "area": 37.5},
            {"category": "Wall", "volume": 1.0, "area": 2.5},
        ],
        columns_metadata={
            "suggested_grouping": ["category"],
            "suggested_quantities": ["volume", "area"],
        },
    )
    r = await client.post(
        "/api/v1/takeoff/cad-group/create-boq/",
        json={
            "session_id": sid,
            "project_id": project_id,
            "boq_name": "CAD",
            "group_by": ["category"],
            "sum_columns": ["volume", "area"],
        },
        headers=auth,
    )
    assert r.status_code == 201, r.text
    boq_id = r.json()["boq_id"]
    # Two positions: one m3 (volume), one m2 (area) — area NOT dropped.
    structured = await client.get(f"/api/v1/boq/boqs/{boq_id}/structured/", headers=auth)
    assert structured.status_code == 200, structured.text
    positions = structured.json().get("positions", [])
    units = sorted(p["unit"] for p in positions)
    assert units == ["m2", "m3"], units
    # Literal column name must NEVER leak as a unit.
    assert "volume" not in units
    assert "area" not in units
