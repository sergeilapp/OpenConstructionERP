# TOP-30 competitive roadmap - execution program

Resumable control file. Read this first on any resume.

## What this is

Implement the 30 ranked competitive-gap features from the June 2026 deep research
(`01_sections_competitive_top30.json`, `result.top_30_missing`) plus the
companion coordination fixes and critical stubs, to high quality with simple,
clear, beautiful UI, and deep browser testing (real Playwright clicks +
screenshots + screenshot analysis) before each wave is committed.

Started: 2026-06-04. Base: branch `feat/postgres-only` == remote `main` at `d1ede2f90`.
Local backend for testing: `http://localhost:8080` (v6.7.0, 117 modules).
Frontend e2e: Playwright is wired (`frontend/playwright.config.ts`, `frontend/e2e/`).

## Hard rules (do not violate)

- The research findings are dated 2026-06-02 and are PARTLY STALE; v6.5-v6.7
  already fixed some. Always triage against current code before implementing.
  Confirmed already done so far: #13 LTIFR/TRIR (`safety/service.py:488-503`);
  #1 clash->notifications high-severity path (`notifications/events.py`
  `_on_clash_high_severity`).
- One change touches one file at a time. Within a wave, lanes must be
  file-disjoint so parallel agents never collide. Shared files
  (`core/events.py`, `notifications/events.py`, `costmodel/service.py`,
  dashboard rollup) get a single owner lane.
- No DB migration without checking `python -m alembic heads` == one head after.
  Current single head: `v3152_ai_agents_custom`.
- Heavy backend work (pytest that boots embedded PG, Playwright) is throttled:
  never more than 3 concurrent. Implementation agents only py_compile + ruff
  their own files; the full test + browser pass runs centrally afterward.
- Commits/PRs/releases: human prose, DDC voice, no em-dashes, no AI attribution.
  Push to main via `git push origin $(git rev-parse HEAD):refs/heads/main`.
- Do not delete other sessions' untracked scratch files.

## Execution protocol per wave

1. Triage (read-only, parallel) - confirm what is really missing.
2. Implement in file-disjoint lanes (parallel). Each lane: confirm finding ->
   implement backend + frontend -> py_compile + ruff its own files. Write tests,
   do not run pytest in-lane.
3. Verify centrally: targeted pytest for touched modules, `tsc --noEmit`,
   `tsc TS1117` locale dup check, `npm run build`, single alembic head.
4. Browser-test the user-facing surfaces: restart backend, run Playwright,
   capture screenshots, read + analyze them, fix what looks wrong, re-shoot.
5. Commit the wave, push to main, update this file's status table, then next wave.

## Waves (research dependency order)

- Wave 1 - event-bus gaps + data-integrity footguns (cheap, high leverage):
  items 1, 8, 13, 24 + coordination fixes (inspection.completed.failed
  subscriber, supplier-rating publish, variation-to-contract hardening,
  plugin_manager manifest/check_updates).
- Wave 2 - planning + financial truth: items 3, 5, 6 + cost-model roll-up,
  validation->NCR escalation.
- Wave 3 - commercial depth + money flow: items 4, 9, 10, 11, 20.
- Wave 4 - field operations first-class: items 2, 7, 14, 26, 28.
- Wave 5 - AI estimating + coordination differentiators: items 12, 16, 17, 18,
  19, 23.
- Wave 6 - compliance, lifecycle, platform reach: items 15, 21, 22, 25, 27, 29,
  30.

## Triage result (2026-06-04)

Authoritative per-item status + files + remaining work + test plans live in
`_triage_digest.json` (this folder). Totals: 0 done, 26 partial, 4 missing.
The 4 fully missing: #4 ERP connectors, #17 drawing-revision compare, #24
risk<->task auto, #30 takt/line-of-balance. "partial" means a foundation exists
but the competitive feature is not complete (e.g. #13 LTIFR/TRIR is computed but
trend analytics is missing; #1 clash high-severity notify exists but
punchlist/NCR/validation subscribers do not). Wave/lane plan: `plan` key in the
digest. This is a genuine multi-wave build; each wave ships as a tested
increment, not a fake "done" on the XL items.

## Status table (initial estimate; digest is source of truth)

| # | Feature | Status | Wave | Notes |
|---|---------|--------|------|-------|
| 1 | Clash + validation events into notifications/punchlist/NCR | partial (high-sev done) | 1 | |
| 2 | Mobile time/attendance -> job cost | triaging | 4 | |
| 3 | Event-driven live EVM/KPI | triaging | 2 | |
| 4 | Bi-directional ERP/accounting connectors | triaging | 3 | |
| 5 | Cross-project resource leveling | triaging | 2 | |
| 6 | Unify schedule dependency graph + guards | triaging | 2 | |
| 7 | AI photo intelligence | triaging | 4 | |
| 8 | Tendering vs Bid award reconciliation | triaging | 1 | |
| 9 | Lien waiver automation + pay enforcement | triaging | 3 | |
| 10 | Commitment management + budget sync | triaging | 3 | |
| 11 | Change Order AI draft + impact simulator | triaging | 3 | |
| 12 | ITP workflow with hold points | triaging | 5 | |
| 13 | LTIFR/TRIR computation | DONE | - | safety/service.py:488-503 |
| 14 | Native offline-first mobile app | triaging | 4 | FieldShellPage stub |
| 15 | Auto client/owner progress report | triaging | 6 | |
| 16 | Semantic AI assistant over docs | triaging | 5 | |
| 17 | Auto drawing/BIM revision compare + cost | triaging | 5 | |
| 18 | ML quantity extraction / symbol recog | triaging | 5 | |
| 19 | Predictive schedule/cost risk analytics | triaging | 5 | |
| 20 | Vendor/sub scorecards + prequal gating | triaging | 3 | |
| 21 | ISO 19650 CDE suitability propagation | triaging | 6 | |
| 22 | Subcontractor portal invoice submission | triaging | 6 | |
| 23 | Persistent clash profiles + grouping | triaging | 5 | |
| 24 | Risk<->task + schedule-slip<->risk auto | triaging | 1 | |
| 25 | Digital handover / closeout package | triaging | 6 | |
| 26 | Equipment predictive maintenance | triaging | 4 | |
| 27 | Compliance rule engine enforced at gates | triaging | 6 | |
| 28 | Model-based progress overlay in 3D | triaging | 4 | |
| 29 | No-code agent builder | triaging | 6 | |
| 30 | Takt / line-of-balance scheduling | triaging | 6 | |

## Log

- 2026-06-04: Program created. Triage workflow launched over all 30 items.
- 2026-06-04: Triage done (31 agents). 0 done / 26 partial / 4 missing. Digest
  saved to `_triage_digest.json`. Desktop installers v6.7.0: Win + macOS
  attached; Linux Tauri build hung in CI (no .deb/.AppImage yet); download page
  made honest about it (commit 1f5252edf).
- 2026-06-04: Wave 1 BACKEND launched (run wf_a40ca164-d22), 4 file-disjoint
  lanes, backend-only, no migrations (reported for one consolidated migration),
  no frontend yet. Lane A clash/validation/inspection -> notifications + auto
  punch/NCR; Lane B schedule dependency single-source + completion guard; Lane C
  bid-award -> PO idempotent reconciliation; Lane D plugin_manager install/update.
  Next: central verify (py_compile, ruff, one consolidated migration, single
  alembic head, targeted pytest), then frontend lanes, then Playwright browser
  test with screenshots, then commit Wave 1.
- 2026-06-04: Wave 1 BACKEND verified + committed. All 4 lanes clean
  (py_compile + ruff). One consolidated migration v3153_clash_source_links
  (oe_punchlist_item.clash_result_id, oe_ncr_ncr.clash_result_id, both nullable
  indexed); single alembic head. Fixed a flagged follow-up: schedule/service_4d
  CSV import now reconciles its JSON edges into the canonical store. Fixed one
  test-harness bug (fake session column-projection detection) found by pytest;
  51/51 Wave 1 unit tests pass. Backend restarted on :8080: 117 modules,
  database ok, embedded PG auto-added both columns, no SQLite fallback. Items
  #1, #6, #8 backend done + plugin_manager stub. STILL TODO for Wave 1: frontend
  (clash/inspection origin badges on punch + NCR, validation deep-link, schedule
  "blocked by predecessor" hint, bid-award PO toast) + Playwright browser test
  with screenshots, then a frontend commit. Then Wave 2.
- 2026-06-04: Wave 1 FRONTEND done + browser-tested + 2 bugs fixed.
  Frontend: punchlist "From clash" badge (red) added next to existing
  inspection/ncr chips (kanban + table); NCR "From clash" badge + metadata on
  the type; schedule progress mutation maps HTTP 409 -> a warning toast titled
  "Blocked by predecessor" carrying the backend detail; tendering award success
  toast now names the auto-created draft PO and offers a "View purchase orders"
  action to /procurement; en.ts keys for all of the above + the validation and
  clash notification bodies. tsc clean (0 errors, 0 TS1117).
  Browser test (Playwright vs vite :5174 -> backend :8080, real demo login,
  injected clash/inspection rows on the Toronto project): punch "From clash" +
  "From inspection" and NCR "From clash" render correctly with zero console
  errors on all six surfaces (punchlist, ncr, validation, schedule, tendering,
  procurement). Two real bugs caught by the deep test and fixed:
    1. Validation ?report= deep link did nothing until a BOQ was picked, so a
       notification link landed on an empty page. ValidationPage now fires the
       report-by-id fetch on the param alone and auto-aligns project + BOQ to
       the linked report. Re-tested cold (no preselected project): the report
       (score 97) renders.
    2. POST schedule relationships returned 500 (MissingGreenlet): the Lane B
       JSON-mirror rebuild calls session.expire_all() and the handler then
       serialised the expired ScheduleRelationship, triggering an implicit
       async refresh from Pydantic's sync attribute access. Fixed by snapshotting
       RelationshipResponse before the mirror rebuild. End-to-end re-test: create
       relationship 201, complete successor while predecessor open -> 409 with
       the named-blocker message, unblocked sequence -> 200. Added integration
       regression test backend/tests/integration/test_schedule_relationship_guard.py
       (real async DB; a fake session cannot reproduce the greenlet error).
    Also fixed a pre-existing red unit test (test_schedule_relationships_limit:
    date object into a VARCHAR start_date, rejected by asyncpg since the SQLite
    removal). NEXT: commit Wave 1 frontend + these fixes, push, then Wave 2.
