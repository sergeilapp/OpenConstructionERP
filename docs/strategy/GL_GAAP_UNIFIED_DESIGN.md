# Configurable GAAP General Ledger + Financial Reporting - Unified Design

> STATUS: DESIGN LOCKED (single architecture, ten lenses reconciled, critique resolved)
> OWNER: DataDrivenConstruction
> SCOPE: a full GAAP general ledger, financial statements, and construction-industry
> revenue recognition, built AROUND the existing append-only `oe_finance_ledger`
> primitive. US GAAP primary, pluggable for IFRS and local frameworks.
> PRINCIPLE: extend, do not rebuild. AI suggests, human confirms. PostgreSQL only.

This document is the single contract. Where the ten draft lenses disagreed, this
resolves the disagreement once and every section below references the same names,
the same columns, and the same writer. No lens invents its own ledger column,
journal header, period table, or scoper. The three decisions that unblock
everything are settled up front in Part 1 and never reopened.

---

## Part 1 - Executive summary and design goals

### 1.1 What we are building

A configurable double-entry general ledger that turns the existing two-row,
single-currency, project-scoped `LedgerEntry` primitive into an airtight,
multi-book, multi-entity, multi-framework GAAP ledger - without rewriting the
primitive and without breaking a single existing consumer (the accounting
connector, the cost spine, the EVM snapshots, the invoice/payment flow). On top
of the ledger we add a journal-entry document layer, a chart of accounts, fiscal
periods with close locks, a posting-rule engine, financial statements with
drill-down, analytic dimensions, FX and consolidation, construction revenue
recognition (ASC 606 over-time POC, WIP, retention, over/under-billing), and a
first-class audit and validation surface.

### 1.2 The three foundational decisions (locked, resolve critique TIER 1)

Every contradiction in the critique traces back to three unresolved forks. They
are decided here and are non-negotiable for the rest of the design.

**Decision A - Tenant/entity owns the chart and the calendar; project becomes a
posting dimension (resolves gaps #4, #5, #27).** A legal/reporting entity
(`oe_gl_entity`) owns the chart of accounts and the fiscal calendar. This is
GAAP-correct: a trial balance, a consolidation journal, an intercompany
elimination, a year-end close to retained earnings, and an opening-balance
journal have a legal entity but no single project. `project_id` stays on every
ledger row as a **posting dimension** (the most common and always-present
dimension), but it becomes **nullable** so entity-level journals can carry
`project_id = NULL`. This forces one migration the drafts never planned: drop the
`NOT NULL` on `oe_finance_ledger.project_id`. Single-entity installs pay nothing -
one implicit default entity is auto-seeded per tenant, and `entity_id` defaults to
it.

**Decision B - One ledger-extension migration, one journal header table, one
period table, each with a single owner and a single canonical column set
(resolves gaps #1, #2, #3).** The five conflicting ledger-column proposals
collapse to ONE additive migration owned by the `gl_core` module. The journal
header is ONE table, `oe_gl_journal`, with ONE superset status machine. The
period is ONE table, `oe_gl_period`, owned by the calendar module. The join from
header to ledger is a real FK column (`oe_finance_ledger.journal_id`), never a
fragile `journal_no == transaction_ref` string match.

**Decision C - One N-line, FX-aware, balanced post primitive replaces the 2-row
writer for all GL posting (resolves gaps #6, #7).** A new
`create_journal(lines[])` primitive writes N ledger rows under one
`transaction_ref` / `journal_id`, asserts `sum(debits) == sum(credits)` in
**book currency** (after FX conversion, never on raw transaction amounts), and
coerces every computed amount to `Decimal` through `MoneyType` before the balance
check. The existing two-row `create_ledger_transaction` becomes a thin wrapper
over `create_journal` (a 2-line journal) so every current caller keeps working
unchanged. Year-end close, WIP allocations, consolidation, and multi-currency
journals all go through `create_journal`.

### 1.3 Design goals, foregrounding configurability

1. **Maximally configurable, no code changes for normal accounting work.** Chart
   structure, account types and normal balances, posting rules (event to
   journal), statement layouts, dimensions, fiscal calendars, books, currencies,
   numbering, rounding, and the accounting framework itself are all DATA in
   `oe_gl_*` tables. A new framework (IFRS, local GAAP) ships as a framework row
   plus seed JSON, never Python. This is the founder's primary requirement and it
   drives every modelling choice below.
2. **Airtight GAAP correctness.** Double-entry balance, period locks,
   subledger-ties-to-control-account, immutability (corrections are reversing
   journals, never edits or deletes), and a derived-but-guarded normal-balance are
   hard invariants enforced by the single writer and surfaced as first-class
   validation rules.
3. **Construction accounting is core, not a bolt-on.** ASC 606 over-time POC, WIP,
   contract assets/liabilities (under/over-billing), retention (dual-sided), and
   change-order cumulative-catch-up live in the core, posted through the same one
   writer and the same one posting-rule engine.
4. **Extend, never rebuild.** Every new table is `oe_gl_*` and additive; the
   existing `LedgerEntry`, `Invoice`, `Payment`, `ControlAccount`, `CostLine`,
   `EVMSnapshot`, and the connector keep their contracts. The only schema change
   to an existing table is additive nullable columns with `server_default` plus
   the one deliberate `NOT NULL` drop on `project_id` (Decision A).
5. **AI suggests, human confirms.** Cost-to-complete forecasts, mapping
   suggestions, and posting-rule previews are confidence-scored proposals; nothing
   posts without an explicit human action.
6. **Lightweight.** No new datastore, no non-AGPL dependency. The expression
   engine is the `simpleeval` already in base deps. Money is `Decimal` via
   `MoneyType`. Single-entity, single-book, single-currency installs leave every
   advanced column NULL and pay zero complexity.

### 1.4 Module layout (one set of modules, no overlap)

The ten lenses become a small set of co-operating modules under
`backend/app/modules/`, each a standard self-contained package
(models/schemas/repository/service/router/manifest), auto-mounted at
`/api/v1/<module>/`. To keep the GL coherent (one writer, one header, one ledger
migration), the GL ships as ONE module, `gl`, with internal sub-areas, rather than
ten modules fighting over shared tables. `gl_revrec` (the construction flagship,
build-plan `oe_revrec`) is a separate module that depends on `gl`.

| Module | Owns | Routes |
|---|---|---|
| `gl` | the ledger extension migration, `oe_gl_entity`, `oe_gl_book`, `oe_gl_coa`/`oe_gl_account`, `oe_gl_journal`/`oe_gl_journal_line`, `oe_gl_period`/`oe_gl_fiscal_year`, the `create_journal` writer, posting-rule engine, dimensions, FX, statements engine, audit/controls, config bundles | `/api/v1/gl/*` |
| `gl_revrec` | `oe_gl_revrec_contract`, `oe_gl_revrec_run`, `oe_gl_retention_ledger`; emits values, posts through `gl` | `/api/v1/gl/revrec/*` |

The `gl` module is large but internally partitioned by file
(`coa.py`, `journal.py`, `periods.py`, `posting_rules.py`, `dimensions.py`,
`fx.py`, `statements.py`, `audit.py`, `config_bundle.py`) so the team can still
work the ten lenses in parallel without colliding on table ownership.

---

## Part 2 - The unified data model

Legend: **[NEW]** = new `oe_gl_*` table. **[EXT]** = additive change to an
existing table. **[MIG]** = data migration over existing rows. All new tables
inherit `Base` (`id` GUID PK, `created_at`, `updated_at`). Money is `MoneyType`
(NUMERIC(18,2) default; `scale=6` for rates/percentages/factors). Dates that take
part in period or aging math use `SafeDate`/`AwareDateTime`, NEVER `String(40)`
(resolves gap #24).

### 2.1 The one ledger extension (Decision B) - `oe_finance_ledger` [EXT][MIG]

This is the single, frozen, additive migration owned by `gl`. No other area adds a
column to the ledger. Canonical column set (every lens references exactly these
names):

| Column | Type | Notes |
|---|---|---|
| `project_id` | GUID **nullable** | **[MIG]** drop `NOT NULL` (Decision A). Now a posting dimension; entity-level journals carry NULL. |
| `entity_id` | GUID nullable, FK `oe_gl_entity.id` | NULL = tenant default entity. Backfilled to default entity. |
| `book_id` | GUID nullable, FK `oe_gl_book.id` | NULL = primary book. |
| `journal_id` | GUID nullable, FK `oe_gl_journal.id` ON DELETE SET NULL | the header join key. NULL on legacy rows (journal-less postings still sum into the trial balance). |
| `account_id` | GUID nullable, FK `oe_gl_account.id` | resolved account. Legacy `account_code` string stays the durable natural key; `account_id` is the typed link. |
| `period_id` | GUID nullable, FK `oe_gl_period.id` | denormalised period for fast period-scoped trial balances without a date join. |
| `txn_amount` | MoneyType nullable | original amount in `currency_code` (the transaction currency). NULL = single-currency legacy row where `debit/credit_amount` already is the book amount. |
| `fx_rate` | MoneyType(scale=8) nullable | rate used to convert `txn_amount` to the book accounting currency at post time. |
| `dimensions` | JSON, server_default `'{}'` | denormalised snapshot of analytic-dimension members for fast pivots (the normalized carrier is `oe_gl_journal_line_dim`, below). |

Unchanged and still authoritative: `debit_amount` / `credit_amount` hold the
**book (accounting) currency** figure the trial balance sums; exactly one is `> 0`
per row; `is_reversal` / `reversal_of_id`; `transaction_ref`; `posted_at`;
`source_type` / `source_id`; `created_by`. New index
`ix_ledger_entity_book_period (entity_id, book_id, period_id)` powers per-book,
per-period trial balance.

Resolves gap #6: for a single-currency journal, `txn_amount` is NULL and
`debit_amount`/`credit_amount` are the amount, exactly as today, so the connector
and every existing reader are byte-for-byte unaffected. For a multi-currency
journal, the writer converts to book currency BEFORE writing, puts the book amount
in `debit_amount`/`credit_amount` (so the cent-balance check is in book currency),
and preserves the original in `txn_amount` + `fx_rate` + `currency_code`. The
connector contract is versioned (see 7.4) so it knows `debit_amount` is always book
currency.

**[MIG] backfill (one alembic head, satisfies build-plan hard condition #6 and
resolves gap #8):**
1. Create all `oe_gl_*` tables. Seed one default `oe_gl_entity` per tenant
   (functional currency = the tenant's existing project currency mode), one
   primary `oe_gl_book`, and the active config bundle from the `us_gaap_standard`
   + `us_construction_contractor` templates.
2. For every distinct existing `account_code`, create an `oe_gl_account` leaf
   (matched template codes link to the seeded account; unmatched codes are created
   active and postable under a single shared `9999 Unmapped` suspense parent -
   one shared account, see Decision in Part 10; resolves the `9999` vs per-code
   disagreement).
3. Backfill `account_id`, `entity_id` (default entity), `book_id` (primary), and
   `period_id` (resolved from `posted_at` against generated periods; rows outside
   any period land in a synthetic `unassigned` period flagged for review).
4. **Opening-balance integrity (resolves gap #8):** before and after remap,
   assert `sum(debit_amount) == sum(credit_amount)` per legacy `transaction_ref`.
   Remapping a leg's account to suspense preserves the per-`transaction_ref`
   balance because we never change amounts, only the account link. If a legacy
   `transaction_ref` is itself unbalanced (pre-existing corruption), it is listed
   in an **opening-balance reconciliation report** and the suspense absorption is
   recorded explicitly, never silently. The migration emits this report as a
   `ValidationReport` artifact.

### 2.2 Entity and book - `oe_gl_entity` [NEW], `oe_gl_book` [NEW]

`oe_gl_entity` (resolves gap #5; the deferred `oe_consolidation` seam, present now
only as nullable columns):
`tenant_id GUID`, `parent_id GUID nullable` (ownership tree),
`code String(40)` (unique per tenant), `name String(255)`,
`entity_type String(20)` (`operating|holding|jv|elimination|consolidation`),
`functional_currency String(3)` (ASC 830 functional currency, immutable once
posted-against), `reporting_currency String(3)`,
`ownership_pct MoneyType(scale=6)`,
`consolidation_method String(20)` (`full|equity|proportional|none`),
`is_eliminating Boolean`, `status String(20)`. A project belongs to one entity via
a new nullable `entity_id` on `oe_projects_project` [EXT] (NULL = tenant default
entity), so existing project-scoped rollups keep working.

`oe_gl_book` (the parallel-book seam):
`tenant_id`, `entity_id FK`, `code String(40)`, `name`,
`framework_code String(20)` (`us_gaap|ifrs|tax|management|local_*`),
`is_primary Boolean` (exactly one primary per entity, partial unique index),
`accounting_currency String(3)` (the book's measurement currency, usually = entity
functional), `parent_book_id GUID nullable` (a delta/adjustment book layers on a
base book). One entity has N books; the same economic event posts once per book
with different recognition rules (resolves gap #18: `book_id` is part of the
idempotency key everywhere, see 4.4).

### 2.3 Chart of accounts - `oe_gl_coa` [NEW], `oe_gl_account` [NEW], templates [NEW]

`oe_gl_coa` (the chart container, so multiple frameworks/books coexist):
`entity_id FK`, `tenant_id`, `name`, `framework_code String(20)`,
`is_default Boolean`, `template_slug String(60)`.

`oe_gl_account` (the master account; single owner, supersedes all three draft
versions; resolves gaps #13, #14, #25):
- `coa_id FK -> oe_gl_coa`, `entity_id FK` (denormalised), `tenant_id`.
- `code String(40)`, `name String(255)`, `description Text`.
- `account_type String(20)` - validated against the framework profile's type set,
  NOT a Python enum (resolves gap #14). The five GAAP roots
  (`asset|liability|equity|revenue|expense`) are the seed vocabulary for
  `us_gaap`, but the allowed set is data in `oe_gl_framework.account_type_vocab`,
  so IFRS/OCI roots are additive without code.
- `account_subtype String(40)` nullable - framework-defined refinement
  (`current_asset|fixed_asset|cogs|contra_revenue|retention_payable|cie|bie|...`),
  drives statement classification and POC/WIP target resolution by subtype, never
  by literal code.
- `normal_balance String(6)` (`debit|credit`) - **derived-but-stored and guarded**:
  the single service computes it from `account_type` (asset/expense = debit, else
  credit), flips for `is_contra`, and a validation rule `gl.normal_balance_consistent`
  (ERROR) plus recompute-on-write forbid the two columns drifting (resolves gap #13).
- `is_contra Boolean`, `contra_of_account_id GUID nullable` (self-FK).
- `is_postable Boolean` (only leaves post; header/control accounts never carry a
  direct balance), `is_control Boolean`, `subledger_type String(30)` nullable
  (`ar|ap|wip|retention|job_cost|...`).
- `parent_id GUID nullable` (self-FK, RESTRICT), `path String(512)` (materialized
  ancestor path for O(1) subtree rollups), `depth Integer`.
- `requires_project Boolean`, `requires_cost_line Boolean` (dimension rules
  enforced at post time; a WIP/job-cost account demands its dimension).
- `currency_mode String(10)` (`entity` = functional only; `any` = multi-currency
  account like a foreign bank), `fixed_currency String(3)` nullable.
- `tax_code_default String(20)` nullable - **see Decision in Part 10: tax is
  scoped OUT of v1; this column is reserved but inert, documented as such, not a
  half-implemented feature** (resolves gap #17).
- `external_aliases JSON` (`{connector_type: external_code}`) - supersedes the
  connector's loose `settings_.account_map` (resolves gap #30).
- `status String(20)` (`active|inactive|retired`; retirement is soft, history
  immutable).
- Unique `(coa_id, code)`; indexes `(coa_id, account_type)`, `(coa_id, parent_id)`,
  `(coa_id, status)`.

`oe_gl_account_template` + `oe_gl_account_template_line` [NEW] - shipped CoA seeds
(`us_gaap_standard`, `us_construction_contractor`, `ifrs_skeleton`). Template lines
carry `code`, `parent_code`, `account_type`, `account_subtype`, `is_contra`,
`is_control`, `subledger_type`, `name_key` (i18n key). All construction account
codes (WIP, CIE, BIE, retention receivable/payable, contract revenue, cost of
revenue) live ONLY here as rows, never as constants in Python.

`oe_gl_numbering_scheme` [NEW] - per-entity code policy: `entity_id FK`,
`scope String(20)` (`account|journal|invoice`), `mask String(60)`,
`segment_defs JSON`, `validation_regex String(200)`, `reset_cycle String(12)`,
`current_seq BigInteger`. **Journal numbering is gapless and synchronous** (see
Decision in Part 10, resolves gap #15): the number is allocated INSIDE the
successful post transaction under the period lock, scope = legal entity, because
gapless and detached-best-effort are mutually exclusive - so GL posting numbering
is synchronous even though the posting-rule trigger is detached (the rule writes a
`pending` log row first, then the synchronous post allocates the number; a failed
post allocates nothing).

### 2.4 Journal header and lines (Decision B) - `oe_gl_journal` [NEW], `oe_gl_journal_line` [NEW]

`oe_gl_journal` - ONE header table, ONE name, ONE superset status machine
(resolves gaps #2, #11):
- `tenant_id`, `entity_id FK`, `project_id GUID nullable` (posting dimension),
  `book_id FK`, `period_id FK -> oe_gl_period`,
  `journal_no String(40)` (gapless per entity, allocated at post),
  `transaction_ref String(100)` (stamped onto every child ledger row; the legacy
  balance-per-ref check still works),
  `journal_type String(30)`
  (`standard|adjusting|accrual|deferral|recurring|reversing|opening|closing|reclass|revrec|depreciation|prior_period_adjustment`),
  `currency_code String(10)` (one per journal - enforces FX-never-blend at the
  document level; cross-currency settlement is two journals plus an FX gain/loss
  line),
  `source_module String(40)`, `source_type String(50)`, `source_id String(36)`,
  `idempotency_key String(64)` (the SINGLE idempotency contract, see below;
  UNIQUE),
  `reverses_journal_id GUID nullable` (self-FK), `reversed_by_journal_id GUID nullable`,
  `auto_reverse Boolean`, `reversal_period_id GUID nullable`,
  `total_debit MoneyType`, `total_credit MoneyType` (stored, asserted equal in
  book currency), `memo Text`,
  `status String(20)` - superset machine
  `draft -> pending_approval -> approved -> posted -> reversed | void`
  (`void` reachable only from `draft`/`rejected`; a posted journal is corrected by
  reversal, never voided),
  `control_hash String(64)` (SHA-256 over ordered line tuples, written at post -
  tamper evidence),
  `created_by`, `submitted_by`, `approved_by`, `approved_at`, `posted_by`,
  `posted_at`.
- Indexes `(entity_id, book_id, period_id, status)`, `(source_type, source_id)`.
- **Single idempotency contract (resolves gap #11):** the canonical key is
  `idempotency_key = sha256(f"{event_name}:{source_type}:{source_id}:{rule_id}:{book_id}")`.
  It is stored on BOTH `oe_gl_journal.idempotency_key` and
  `oe_gl_posting_log.idempotency_key` (same string), so the header unique
  constraint and the posting-log unique constraint agree. `book_id` is in the key
  so two books = two journals, never a collision (resolves gap #18). The existing
  `Payment.idempotency_key` is independent (it dedupes the payment, not the GL
  posting) and is unaffected.

`oe_gl_journal_line` - the balanced detail:
- `journal_id FK CASCADE`, `line_no Integer`,
  `account_id GUID FK -> oe_gl_account`, `account_code String(40)` (denormalised
  snapshot; **single resolution point in the post service validates
  `journal_line.account_code == account.code == ledger.account_code` at post**,
  resolves gap #25),
  `debit_amount` / `credit_amount` MoneyType (exactly one `> 0`, book currency),
  `txn_amount MoneyType nullable`, `fx_rate MoneyType(scale=8) nullable`,
  `currency_code String(10)`,
  `description Text`,
  `project_id` / `cost_line_id` / `control_account_id` / `wbs_id` GUID nullable
  (cost-spine dimensions, link straight to `oe_costmodel_cost_line.id` /
  `oe_costmodel_control_account.id`),
  `subledger_ref String(64)` nullable (the AR/AP doc, e.g.
  `oe_finance_invoice.id`),
  `tax_code String(20)` nullable (reserved, inert in v1),
  `memo Text`.

`oe_gl_journal_line_dim` [NEW] - the normalized dimension carrier (resolves the
dimensions lens cleanly): `journal_line_id FK CASCADE`, `dimension_id FK`,
`member_id GUID nullable`, `entity_ref_id GUID nullable`, `entity_ref_kind String(40)`,
`member_path String(512)` (snapshotted at post so a later re-parent cannot rewrite
history). The `oe_finance_ledger.dimensions` JSON is the denormalised fast-pivot
copy of these rows.

### 2.5 Fiscal calendar and periods (Decision B) - `oe_gl_fiscal_year` [NEW], `oe_gl_period` [NEW]

Single owner of period and fiscal-year (resolves gap #3). Scoped by
**entity + book** (Decision A: entity owns the calendar), not by project and not by
project-or-fiscal-year-or-entity depending on the reader.

`oe_gl_fiscal_year`: `entity_id FK`, `book_id GUID nullable` (NULL = applies to all
books of the entity), `code String(20)` (`FY2026`),
`start_date SafeDate`, `end_date SafeDate`, `period_count Integer`,
`calendar_type String(20)` (`calendar_month|four_four_five|thirteen_period|custom`),
`status String(20)` (`open|closing|closed|permanently_closed`),
`retained_earnings_account_id GUID FK -> oe_gl_account`,
`current_earnings_account_id GUID FK -> oe_gl_account`.
Unique `(entity_id, book_id, code)`; no two years overlap on date (service-enforced
`assert_no_overlap`, not a DB trigger).

`oe_gl_period`: `fiscal_year_id FK CASCADE`, `entity_id` / `book_id`
(denormalised), `period_no Integer` (`0` = opening/BBF, `1..period_count` regular,
`period_count+1` = year-end adjustment period),
`period_type String(20)` (`opening|regular|adjustment`),
`name String(40)` (`2026-07`, `P13-ADJ`),
`start_date SafeDate`, `end_date SafeDate`,
`status String(20)` - ONE vocabulary
(`open|soft_closed|closed|locked|permanently_closed`), where `soft_closed` allows
only `adjusting`/`accrual`-type journals, `closed` blocks all new postings,
`locked`/`permanently_closed` additionally block reopen except by admin with
reason,
`adjustments_allowed Boolean`,
`closed_by`, `closed_at AwareDateTime`, `reopened_count Integer`.
Unique `(fiscal_year_id, period_no)`; indexes `(entity_id, status)`,
`(entity_id, start_date, end_date)`.

`oe_gl_period_lock` [NEW] - per-subsystem staged close: one row per
`(period_id, module)` where module in `ap|ar|gl|payroll|revrec|all`, with
`status` (`soft_closed|hard_closed`). Lets a controller lock AP while GL stays open
for adjustments.

### 2.6 Posting-rule engine - `oe_gl_posting_rule` [NEW], `oe_gl_posting_rule_leg` [NEW], `oe_gl_account_map` [NEW], `oe_gl_subledger_link` [NEW], `oe_gl_posting_log` [NEW]

The single place operational events become journals (resolves gap #9: exactly one
event-to-journal owner). No operational module ever names a GL account or writes a
ledger row directly.

`oe_gl_posting_rule`: `tenant_id`, `project_id GUID nullable` (NULL = all projects;
non-NULL overrides), `entity_id`, `book_id`,
`event_name String(120)` (the event-bus dot name, e.g. `finance.invoice.posted`,
`contracts.claim.certified`, `gl_revrec.run.confirmed`),
`framework_code String(20)`,
`condition String` nullable (a `simpleeval` predicate over the event payload),
`currency_source String(20)` (`event|project|fixed`),
`priority Integer`, `is_active Boolean`,
`description_template String`. Unique
`(tenant_id, project_id, event_name, framework_code, book_id, priority)`.

`oe_gl_posting_rule_leg`: `rule_id FK CASCADE`, `side String(6)` (`debit|credit`),
`account_selector JSON` (`{kind: "fixed"|"event_field"|"map"|"subledger_control"|"by_subtype", ...}`),
`amount_expr String` (a `simpleeval` expression over the payload),
`dimension_map JSON` (which event fields populate which dimension), `sort_order`.

`oe_gl_account_map`: named lookup tables (`map_name`, `key`, `account_code`,
`framework_code`) for data-driven account routing (e.g. `cost_category=labor ->
5100`).

`oe_gl_subledger_link`: binds a subledger to its GL control account and recon
config: `subledger String(20)` (`ar|ap|job_cost|fixed_assets|retention`),
`control_account_code String(100)`, `clearing_account_code String(100)` nullable,
`recon_tolerance MoneyType`.

`oe_gl_posting_log`: idempotency + replay + reconciliation ledger:
`tenant_id`, `project_id`, `entity_id`, `book_id`, `event_name`, `event_id String(36)`,
`idempotency_key String(160)` (UNIQUE - the same string stored on the journal),
`rule_id GUID`, `journal_id GUID nullable`, `transaction_ref String(100)`,
`status String(20)` (`pending|posted|skipped|failed|reversed`),
`error Text` nullable, `payload_hash String(64)`,
`posted_at AwareDateTime nullable`, `reversal_log_id GUID nullable`.
Index `(tenant_id, event_name, posted_at)`.

### 2.7 Dimensions - `oe_gl_dimension` [NEW], `oe_gl_dimension_member` [NEW], `oe_gl_account_dimension_rule` [NEW], `oe_gl_allocation_rule` [NEW], `oe_gl_allocation_basis` [NEW]

The analytic axes (project, job, cost center, department, class, phase, fund, plus
custom). `project_id` is the always-present system dimension; it lives directly on
the ledger row and the journal line, the rest are carried via
`oe_gl_journal_line_dim` (2.4).

`oe_gl_dimension`: `tenant_id GUID nullable` (NULL = system/global),
`code String(40)`, `name String(120)`, `kind String(20)` (`system|custom`),
`binding String(20)` (`freeform|entity_ref`), `binding_entity String(80)` (from a
server allowlist; e.g. `project`, `costmodel.control_account`,
`costmodel.cost_line`), `is_balancing Boolean` (participates in dimensional
trial-balance: every `transaction_ref` nets to zero per member of this dimension -
the GAAP mechanism for fund accounting and inter-job due-to/due-from),
`requirement_default String(10)` (`required|optional|forbidden`),
`is_active Boolean`. Unique `(tenant_id, code)`.

`oe_gl_dimension_member`: `dimension_id FK CASCADE`, `parent_id GUID nullable`,
`code String(80)`, `name String(255)`, `path String(512)`, `is_active Boolean`,
`is_postable Boolean`, `valid_from SafeDate nullable`, `valid_to SafeDate nullable`
(effective-dating). Unique `(dimension_id, code)`.

`oe_gl_account_dimension_rule`: `account_id FK`, `dimension_id FK`,
`requirement String(10)`, `default_member_id GUID nullable`,
`allowed_member_subtree_path String(512) nullable`. Unique
`(account_id, dimension_id)`.

`oe_gl_allocation_rule` + `oe_gl_allocation_basis`: declarative distribution
(source filter, method `fixed_pct|headcount|cost_driver|even`, clearing account so
the allocation is itself a balanced journal posted through `create_journal`; bases
carry `factor MoneyType(scale=6)`, normalised to 100% at run, currency never
blended).

### 2.8 FX and consolidation - `oe_gl_fx_rate` [NEW], `oe_gl_revaluation_run`/`_line` [NEW], `oe_gl_intercompany_txn` [NEW], `oe_gl_cta` [NEW]

`oe_gl_fx_rate`: `tenant_id`, `from_currency String(3)`, `to_currency String(3)`,
`rate MoneyType(scale=8)`, `rate_type String(12)` (`spot|average|historical|closing`),
`rate_date SafeDate`, `source String(40)` (`manual|ecb|...`), `inverse_rate MoneyType(scale=8)`.
Unique `(tenant_id, from_currency, to_currency, rate_type, rate_date, source)`.

`oe_gl_revaluation_run` + `oe_gl_revaluation_line`: ASC 830-20 period-end
remeasurement of monetary balances; computes unrealized FX gain/loss and posts a
balanced journal through `create_journal` that auto-reverses next period.

`oe_gl_intercompany_txn`: links two postings across entities for matching and
elimination (`from_entity_id`, `to_entity_id`, `from_txn_ref`, `to_txn_ref`,
`match_status`, `elimination_txn_ref`). Eliminations are balanced journals in the
dedicated `entity_type='elimination'` entity with `project_id = NULL` (works
because Decision A made `project_id` nullable; resolves gap #27).

`oe_gl_cta`: cumulative translation adjustment per `(entity_id, reporting_currency,
period_id)` - an equity/OCI component kept separate from P&L FX.

### 2.9 Construction revenue recognition (module `gl_revrec`) - `oe_gl_revrec_contract` [NEW], `oe_gl_revrec_run` [NEW], `oe_gl_retention_ledger` [NEW]

`oe_gl_revrec_contract` - the recognition policy wrapper over an existing
`oe_contracts_contract` (modelled at the **performance-obligation grain**, resolves
gap #20): `project_id`, `contract_id GUID` (plain, no cross-module FK),
`performance_obligation_no Integer` (default 1; one row per distinct PO so a
contract with both an asset PO and a liability PO is representable),
`method String(40)`
(`cost_to_cost|efforts_input|units_output|completed_contract|point_in_time|fixed_amount`),
`framework_code String(20)`, `transaction_price MoneyType` (ASC 606 step 3,
independently revisable; see change orders), `currency String(3)` (pinned at
creation, must equal the contract currency, recognition refuses mixed currency),
`est_total_cost MoneyType`, `loss_provision_required Boolean`, the posting account
map (`revenue_account_id`, `cogs_account_id`, `contract_asset_account_id`,
`contract_liability_account_id`, `retention_recv_account_id`,
`retention_pay_account_id` FKs to `oe_gl_account`, defaulted from the framework
posting rules, overridable), `status String(40)` (`active|closed|loss_recognized`).

`oe_gl_revrec_run` - one immutable recognition computation per PO per period
(append-only like the ledger): `revrec_contract_id FK`, `period_id FK`,
`as_of_date SafeDate`, snapshotted inputs
(`cost_incurred_to_date`, `est_total_cost`, `transaction_price`, `billed_to_date`,
`claims_certified_to_date`), computed
(`percent_complete MoneyType(scale=6)`, `earned_revenue_to_date`,
`earned_this_period`, `cost_recognized_this_period`, `gross_profit_to_date`),
position (`contract_asset` = under-billing, `contract_liability` = over-billing;
the mutually-exclusive invariant is relaxed to **per-PO**, resolves gap #20),
`provision_for_loss MoneyType` (full estimated loss recognized immediately),
`journal_id GUID nullable` (set when posted), `confidence Float nullable` (only
when `est_total_cost` came from an AI forecast). Unique
`(revrec_contract_id, period_id, kind)` where `kind` separates a draft preview from
the posted run.

`oe_gl_retention_ledger` - retention as the **projection of the GL retention
control account** (resolves gap #22: it is NOT an independent third source of
truth). It mirrors the posted retention journals and reconciles to
`Payment.withholding_amount`; its `outstanding` is recomputed from the GL, never
maintained as an independent decoupled scalar: `project_id`, `contract_id`,
`direction String(10)` (`receivable|payable`), `source_claim_id GUID`,
`source_payment_id GUID`, `held_amount`, `released_amount`, `outstanding`
(derived), `account_id FK`, `expected_release_date SafeDate`, `status`
(`held|partially_released|released`).

Change orders need no new table: they anchor on the contracts module's existing
dated change-order rows (resolves gap #21). Each change order writes a dated
`transaction_price` revision that `oe_gl_revrec_contract` reads, so the
cumulative-catch-up math has both the prior period price and the new price and is
never lost when `Contract.total_value` is edited twice between runs.

### 2.10 Statements and config bundles - report and config tables [NEW]

`oe_gl_report_def` + `oe_gl_report_line` + `oe_gl_report_run` + `oe_gl_aging_bucket`
(Part 6). `oe_gl_config_bundle` + `oe_gl_framework` + `oe_gl_statement_layout` +
`oe_gl_rounding_policy` (Part 3). `oe_gl_audit_event` + `oe_gl_recon` /
`oe_gl_recon_item` + `oe_gl_approval_rule` + `oe_gl_sequence` (Part 8). All listed
in their respective parts to avoid repetition.

### 2.11 What is new vs extended vs migrated (summary)

- **[EXT] existing tables:** `oe_finance_ledger` (the one additive migration +
  `project_id` NOT NULL drop), `oe_projects_project` (nullable `entity_id`),
  `oe_costmodel_control_account` (nullable `gl_account_id` so job cost rolls into
  the GL without merging the CBS and CoA trees).
- **[MIG] data migrations:** account-code backfill into `oe_gl_account`,
  entity/book/period stamping, opening-balance reconciliation report.
- **[NEW]:** every `oe_gl_*` table above.
- **Untouched:** `Invoice`, `InvoiceLineItem`, `Payment`, `ProjectBudget`,
  `EVMSnapshot`, `CostLine`, `BudgetLine`, `crm.Account` (explicitly distinct from
  `oe_gl_account` - confirmed by prefix, resolves gap #29), the connector tables
  (read contract versioned, not broken).

---

## Part 3 - The configurability model (no code changes)

Everything an accountant configures is DATA in `oe_gl_*` tables, versioned and
exportable as one bundle.

### 3.1 Config bundle (versioned, copy-on-write)

`oe_gl_config_bundle`: `tenant_id`, `framework_id FK -> oe_gl_framework`,
`version Integer`, `status String(12)` (`draft|active|archived`),
`parent_version_id GUID nullable`, `checksum String(64)` (sha256 of the serialized
bundle), `activated_at`, `created_by`. Exactly one `active` per
`(tenant_id, framework_id)`, enforced in the single-writer service. A bundle is the
unit of export/import (`GET/POST /gl/bundles/{id}/export|import`), so a whole GL
config moves between installs as one signed JSON file.

### 3.2 Framework registry (multi-framework pluggability - one table, resolves gap #14)

`oe_gl_framework` is the SINGLE framework registry (the draft `FrameworkProfile`
plugin-registry concept is deleted; resolves gap #14): `code String(20)`
(`us_gaap|ifrs|local_de_hgb|...`), `display_name`, `is_builtin Boolean`,
`account_type_vocab JSON` (the allowed `account_type` set - this is what makes
account types pluggable, not a Python enum), `statement_taxonomy JSON` (ordered
statement-line keys), `normal_balance_convention JSON`,
`default_rounding_policy JSON`, `loss_provision_policy String(20)`
(immediate vs relaxed, per-framework), `revrec_modification_policy String(20)`
(cumulative vs prospective). A new framework = one row + a seed bundle JSON. No
Python.

### 3.3 What is configurable, by area

- **CoA:** templates (`apply-template`), account create/rename/re-parent,
  contra-flagging, control/subledger flags, `requires_project`/`requires_cost_line`
  dimension rules, `currency_mode`, `external_aliases`, soft retirement.
- **Numbering:** `oe_gl_numbering_scheme` mask/segments/reset per entity per scope.
- **Posting rules:** the entire `oe_gl_posting_rule` + leg set (event, condition,
  account selector per leg, amount expression, dimension map), account maps,
  subledger links - all via `simpleeval`, all with a mandatory dry-run before
  activation.
- **Statement layouts:** `oe_gl_statement_layout` / `oe_gl_report_def` +
  `oe_gl_report_line` (grouping selectors, subtotals, formula lines, sign, sort,
  i18n labels, comparatives, rounding).
- **Dimensions:** create custom dimensions and member trees, per-account
  requirement matrix, balancing flag, allocation rules.
- **Fiscal calendars:** `calendar_type`, `period_count`, custom boundaries, close
  policy block (which `journal_type`s pass in soft vs hard close, P13 auto-open,
  reopen permission tier).
- **Multi-book / multi-currency:** books per entity with framework + accounting
  currency, FX rate sources/types per book, FX gain-loss and CTA account mapping,
  per-book posting-rule overrides (a tax book defers what GAAP recognizes via a
  book-scoped rule).
- **Rounding/precision:** `oe_gl_rounding_policy` is the SINGLE owner (resolves
  gap #16): `precision` (matches `MoneyType` scale), `mode` (`half_even|half_up`),
  `rounding_account_code` (the ONE residual sink). Statements and posting both read
  it; the three competing rounding mechanisms collapse to this one. Aging buckets
  are also data (`oe_gl_aging_bucket`), so retention aging is a configured bucket
  set, not a hardcoded column.

### 3.4 Expression-engine safety contract (one place, resolves gap #12)

All user-authored expressions (`condition`, `amount_expr`, statement
`formula.expr`, allocation factors) use the existing `simpleeval` with a SINGLE
documented function whitelist (arithmetic + `sum|abs|min|max|round`, no attribute
access, no comprehensions, no imports). Hard rules:
1. Every expression result is coerced to `Decimal` through the `MoneyType` bind
   path; a non-Decimal/float/None result hard-fails the post.
2. A division-by-zero, a missing payload field, or any expression error
   **hard-fails the entire journal** - never posts a partial or unbalanced
   journal.
3. The dry-run/`test` endpoint is REQUIRED before a rule or layout can be
   activated; activation of an untested rule is refused.

---

## Part 4 - GAAP correctness guarantees and hard invariants

### 4.1 The one writer (Decision C) - `create_journal(lines[])`

All GL posting goes through ONE service method:
`create_journal(entity_id, book_id, period_id, lines[], *, journal_type,
idempotency_key, source, currency_code)`. In one transaction it:
1. Resolves each line's `account_id`, asserts `is_postable`, `status='active'`, the
   account's `currency_mode` permits the line currency, and dimension rules are
   met.
2. Converts each line to **book currency** if `currency_code != book.accounting_currency`
   (looks up `oe_gl_fx_rate`, stamps `txn_amount`+`fx_rate`, puts the book amount in
   `debit_amount`/`credit_amount`).
3. Coerces every amount to `Decimal` via `MoneyType`, then asserts
   `sum(debits) == sum(credits)` **in book currency** to the cent (resolves gaps
   #6, #7 - N lines, book-currency balance).
4. Asserts the target period is postable for this `journal_type` (period lock).
5. Honours `idempotency_key` (second call returns the existing journal).
6. Allocates `journal_no` from the gapless per-entity sequence (synchronous,
   inside this transaction).
7. Writes the `oe_gl_journal` header + N `oe_gl_journal_line` + N
   `oe_finance_ledger` rows (sharing one `transaction_ref`/`journal_id`) +
   `oe_gl_journal_line_dim` rows + the denormalised `dimensions` JSON.
8. Writes the `control_hash` and flips status to `posted`.

`create_ledger_transaction` (the legacy 2-row writer) becomes a thin wrapper that
calls `create_journal` with two lines, so every existing caller keeps its exact
contract. Year-end close, allocations, revaluation, consolidation, and
multi-currency journals all use `create_journal` directly.

### 4.2 Hard invariants (enforced by the writer AND as first-class validation rules)

Registered in `app/core/validation/rules/__init__.py` under a new `gl` rule set,
run on every post and on demand:

- `gl.journal_balanced` (ERROR) - each journal balances in book currency before
  post.
- `gl.trial_balance_zero` (ERROR) - per period+book, `sum(debit) == sum(credit)`.
- `gl.period_open` (ERROR) - no posting/reversal into a `closed`/`locked`/
  `permanently_closed` period (except the documented reversal/PPA path, 4.3).
- `gl.posts_to_leaf` (ERROR) - account `is_postable` and active.
- `gl.normal_balance_consistent` (ERROR) - `normal_balance` matches
  `account_type`/`is_contra` (resolves gap #13).
- `gl.subledger_ties` (ERROR) - each control account balance equals its subledger
  (AR/AP/retention/WIP/job-cost) for the period.
- `gl.required_dimensions` (ERROR) - per-account `requires_*` and dimension rules
  satisfied.
- `gl.no_currency_blend` (ERROR) - reuses costmodel FX-never-blend; a journal is
  single transaction-currency, conversion is explicit through the writer.
- `gl.sod_satisfied` (ERROR) - approver distinct from preparer per approval rule.
- `gl.wip_ties_to_ledger` (ERROR) - the WIP schedule CIE/BIE totals equal the GL
  contract-asset/liability control-account balances (resolves gap #19).
- `gl.close_ties_to_income` (ERROR) - the year-end close journal's RE delta equals
  the income-statement net income for the year (resolves gap #28).
- `gl.poc_evm_variance` (WARNING) - revrec percent-complete vs EVM
  percent-complete variance surfaced, not just prose (resolves gap #23).
- `gl.audit_chain_intact` (ERROR) - the audit hash chain verifies.

### 4.3 Immutability and the single reversal/PPA rule (resolves gap #10)

Posted journals and ledger rows are NEVER updated or deleted. Corrections are a
reversing journal (`reverses_journal_id`, reusing the ledger `:rev`/swapped-account
convention). ONE documented rule for reversing into a closed period (the four
contradictory drafts collapse to this):

> A reversal of a posted journal whose original period is now closed posts to the
> earliest currently-open period AND is tagged `journal_type='prior_period_adjustment'`
> with a `prior_period_adjustment` marker linking the original. Money is never
> silently moved between periods; the PPA trail makes the restatement visible in
> both periods.

Accrual auto-reversals are generated when the target period OPENS (inheriting that
period's status), not at post time; if the target period is permanently closed the
reversal is redirected to the next open period as a flagged PPA.

### 4.4 Idempotency under the detached bus (resolves gap #11)

The single `idempotency_key` (2.4) is stored on both the journal header and the
posting log. The posting-rule trigger is detached/best-effort, but:
1. It first writes a `pending` `oe_gl_posting_log` row (idempotent on the key).
2. The synchronous `create_journal` then posts and flips the log to `posted` with
   `journal_id`.
3. A mandatory reconciliation sweep `POST /gl/reconcile` flags every source
   document whose expected posting has no `posted` log row (a `pending`/`failed`
   that never completed), so "best-effort" can never silently leave the GL missing
   a posting. Gapless numbering stays correct because the number is allocated only
   inside the successful synchronous post (4.1 step 6).

---

## Part 5 - Construction GAAP coverage

### 5.1 ASC 606 over-time POC

`gl_revrec` computes percentage-of-completion per performance obligation
(cost-to-cost default; efforts-input, units-output, completed-contract,
point-in-time, fixed-amount selectable per PO). Inputs roll up from the cost spine
(`CostLine`/`BudgetLine` actual/forecast grouped by `control_account_id`), the
contract (`transaction_price` seeded from `Contract.total_value`, dated change-order
revisions for catch-up), and certified `ProgressClaim`s (billed-to-date). Currency
is pinned per PO; a run refuses on mixed currency (FX-never-blend).

### 5.2 WIP, contract assets/liabilities (under/over-billing)

`build_wip_schedule(project_id, period)` produces the industry-standard WIP row
(contract value, est cost, % complete, earned revenue, billed to date, over/under,
backlog, gross profit). The position is billed-vs-earned (not billed-vs-cost), so
mobilization/advance payments correctly drive a contract liability even at 0%
complete. **Over/under-billing is a posted GL position, and the WIP schedule
reconciles to it** via `gl.wip_ties_to_ledger` (ERROR) - the balance sheet CIE/BIE
line (from posted journals) and the WIP schedule (from `oe_gl_revrec_run`) can
never disagree (resolves gap #19). Statements read both and the validation rule
ties them.

### 5.3 Retention (dual-sided), resolves gap #22

Retention receivable (we are owed held-back cash) and retention payable (we hold
subs' retention) are posted at certification through the posting-rule engine ONLY
(resolves gap #9: one owner). `gl_revrec` and the FX lens EMIT values and events;
they never post retention journals directly. `oe_gl_retention_ledger` is a
projection of the GL retention control account, reconciled to
`Payment.withholding_amount`, with `outstanding` derived from the GL - not an
independent third source of truth. Retention has its own aging (a configured bucket
set) and its own balance-sheet line, never folded into trade AR/AP.

### 5.4 Change orders (cumulative catch-up), resolves gap #21

Change orders anchor on the contracts module's dated change-order rows. Each writes
a dated `transaction_price` revision; the next revrec run picks up the new price
and computes the cumulative-catch-up adjustment (ASC 606 for modifications not
distinct) landing in the period the price changed. Prior posted runs are never
restated. Per-framework `revrec_modification_policy` can switch to prospective for
distinct-good modifications.

### 5.5 Loss provisions

Full estimated loss on an onerous contract is recognized immediately
(`provision_for_loss`, ASC 606/605-35), per-framework toggle via
`loss_provision_policy`. Modelled per PO so a contract can have an under-billing on
one PO and a loss provision on another simultaneously (resolves gap #20).

---

## Part 6 - The financial-statements engine and drill-down

### 6.1 Configurable report definitions

`oe_gl_report_def` (`report_kind`:
`balance_sheet|income_statement|cash_flow_direct|cash_flow_indirect|equity_changes|trial_balance|gl_detail|ar_aging|ap_aging|wip|job_pnl`,
`framework_code`, `currency_mode` `transaction|functional|presentation`,
`settings_` JSON for rounding/comparatives/zero-row suppression) +
`oe_gl_report_line` (ordered line tree: `line_type`
`header|account_group|subtotal|formula|spacer|total`, `selector_` JSON for account
gathering by type/subtype/code-range/prefix/tag/explicit, `formula_` JSON evaluated
via the safe `simpleeval`, `sign` `natural|invert`, i18n `label_key`) +
`oe_gl_report_run` (immutable snapshot with `result_` JSON, `totals_check`,
`fx_rate_set_id` pinned for reproducibility) + `oe_gl_aging_bucket` (configurable
AR/AP buckets).

### 6.2 Reading the GL

Selectors resolve `account_code` to a set of codes through `oe_gl_account` (joining
in `account_type`/`subtype`/`normal_balance`/`path`/`tags`); an `account_code`
present in the ledger but absent from the CoA surfaces as an `unmapped` warning row
(never silently dropped) so the balance sheet still balances and the gap is
visible. Period scoping uses `period_id` (denormalised on the ledger) or
`posted_at` against `oe_gl_period`. Reversal honesty is automatic: values are
`sum(debit_amount - credit_amount)`, so `is_reversal` rows net out, never filtered.
Cost lines feed job P&L and the WIP cost-incurred column.

### 6.3 GAAP-correct statement math

- Balance sheet computes `Assets - (Liabilities + Equity)` and writes
  `totals_check.balanced`; non-zero beyond the rounding tolerance from
  `oe_gl_rounding_policy` raises a blocking `unbalanced` row.
- Indirect cash flow starts from IS net income, adds back `noncash`-tagged lines,
  adjusts working-capital deltas as period-over-period balance changes; the
  reconciliation `CFO + CFI + CFF == ending_cash - beginning_cash` is itself a
  checked formula line.
- Sign discipline comes from `normal_balance`; contra lines use `sign=invert`.
- Comparatives pull prior-period runs; each run pins `fx_rate_set_id` so an old
  period re-renders to the exact historical numbers (auditor reproducibility).

### 6.4 Drill-down

`GET /gl/reports/runs/{run_id}/lines/{line_id}/drill` returns the underlying
`oe_finance_ledger` rows (or invoices for aging, cost lines for job P&L) that summed
into the line, scoped and capped, each with a `journal_id` link back to the source
document. Every number on every statement is drillable to journal lines.

### 6.5 Saved report views (resolves gap #4) - the EntityScoper prerequisite

The critique's ground truth holds: `ProjectMemberScoper` raises `ScopeDenied` on a
null `project_id`, and `register_queryable_entity` requires a `project_fk_column` or
`project_subquery`. So "reuse saved_views for entity-level statements" is NOT free.
Resolution, split by scope, treated as a real dependency not a footnote:

- **Project-scoped reports (job P&L, project trial balance, project WIP)** register
  as queryable entities with the existing `ProjectMemberScoper` and a real
  `project_id` column - these ride saved_views in v1 with zero new infrastructure.
- **Entity/tenant-scoped reports (consolidated statements, CoA inquiry,
  dimensions, periods)** require a NEW `EntityMemberScoper` (and a `TenantScoper`),
  built as an explicit Phase-2 prerequisite deliverable. It satisfies the
  `EntityScoper` Protocol but pins on `entity_id` via entity membership instead of
  `verify_project_access`. Because the registry's `_validate_entity` currently
  demands a project pin, the registry gains a small additive change: an entity may
  register with an `entity_fk_column` + `EntityMemberScoper` instead of a project
  pin (the validation is widened to "must declare a project pin OR an entity pin
  with an entity scoper"). Until that ships, entity-level statements use a
  dedicated read path (a scoped service method, not saved_views), and only
  project-scoped reports are saveable. This is called out as a hard Phase-2
  dependency in Part 9.

---

## Part 7 - Integration and posting flows

### 7.1 Event to journal (the only path)

Operational modules publish events on the existing `event_bus`; they never name a
GL account. A single detached handler filters to events with an active
`oe_gl_posting_rule`, writes a `pending` posting-log row, selects the
highest-priority rule whose `condition` passes, evaluates each leg's
`account_selector` and `amount_expr` (safe `simpleeval`, Decimal-coerced), asserts
balance, and posts through `create_journal`. Posting is downstream of the business
event; a failure writes `status='failed'` and does NOT roll back the source
operation, but the reconciliation sweep (4.4) guarantees it is never silently lost.

### 7.2 Subledger control postings

`finance` invoice/payment events post AR/AP through the subledger control accounts
resolved from `oe_gl_subledger_link`. `gl.subledger_ties` reconciles control to
subledger every period. Job cost (`costmodel.cost.incurred`) posts to the WIP/control
account derived from `CostLine.control_account_id`, carried as a dimension.

### 7.3 Construction events

Seed rules (editable data): `contracts.claim.certified` -> AR + retention split
(reads `Payment.withholding_amount`); `gl_revrec.run.confirmed` -> contract
asset/liability + revenue/COGS; `contracts.retention.released` -> reverse retention
into AR. Exactly one rule owns each event (resolves gap #9).

### 7.4 Connector (resolves gap #30)

The accounting connector keeps reading `oe_finance_ledger`, but the read contract is
VERSIONED, not claimed-unchanged: `debit_amount`/`credit_amount` are documented as
always book currency, and the account mapping source is `oe_gl_account.external_aliases`
(superseding `settings_.account_map`). A posted journal emits `gl.journal.posted`,
which the connector's `auto_push_events` subscribes to, so the GL FEEDS the
connector. The export carries `entity_id`, `book_id`, and both currencies so
external systems receive transaction-currency truth.

---

## Part 8 - Audit, controls, and first-class validation

### 8.1 Audit trail (hash-chained, immutable)

`oe_gl_audit_event`: append-only, never updated/deleted, with
`hash_prev`/`hash_self` so a deleted or mutated row breaks the chain
(`gl.audit_chain_intact`). Records every `create|submit|approve|reject|post|reverse|void|period_close|period_reopen|coa_edit`
with `before`/`after` field diffs, `actor_id`, `actor_role`, and a required `reason`
on reject/reopen/void. `GET /gl/audit/verify-chain` recomputes the chain.

### 8.2 Segregation of duties and approval

`oe_gl_approval_rule` per entity: `applies_to`, `match_value`,
`amount_threshold MoneyType`, `min_approvers`, `require_distinct_preparer`,
`allowed_approver_roles`. Evaluated at submit; post refused until satisfied
(`gl.sod_satisfied`). SoD is configurable down to WARNING for single-user installs
(see Part 10 open questions).

### 8.3 Reconciliation

`oe_gl_recon` + `oe_gl_recon_item`: bank, control-to-subledger, and intercompany
reconciliation surfaces. Control-to-subledger materializes the GAAP requirement
that each subledger ties to its control account (AR to open invoices net of
payments, retention to `Payment.withholding_amount` outstanding, WIP to the costed-
vs-billed position). The `POST /gl/reconcile` sweep (4.4) also flags source
documents with no posted journal.

### 8.4 Numbering and sequences

`oe_gl_sequence` backs the gapless per-entity journal numbering; the number is
allocated synchronously inside the successful post transaction under the period
lock (resolves gap #15).

---

## Part 9 - Phased, tests-first build plan

Money math is tests-FIRST throughout (build-plan hard condition #7). Each phase is
shippable and independently valuable. Module layout, table names, and routes are as
defined above; routes mount at `/api/v1/gl/`.

### Phase 0 - The writer and the migration spine (the unblock)
Tests-first for: balance-in-book-currency, N-line balance, Decimal coercion,
period-lock rejection, idempotency, the `project_id` NOT NULL drop.
- Build `create_journal(lines[])` (Decision C); make `create_ledger_transaction` a
  2-line wrapper. Tests prove every existing caller is unchanged.
- The ONE additive `oe_finance_ledger` migration (Decision B): add `entity_id`,
  `book_id`, `journal_id`, `account_id`, `period_id`, `txn_amount`, `fx_rate`,
  `dimensions`; drop `project_id` NOT NULL (Decision A). `server_default` on all.
- Seed default entity + primary book + active bundle. Single alembic head.
- Routes: none user-facing yet; internal writer + migration only.
Shippable value: the ledger can carry entity/book/journal/period without behaviour
change; multi-currency-safe writer in place.

### Phase 1 - CoA + periods + journals + trial balance (the GL core)
Tests-first for: trial-balance = 0, normal-balance consistency, leaf-only posting,
backfill opening-balance reconciliation.
- Build `oe_gl_entity`, `oe_gl_book`, `oe_gl_coa`/`oe_gl_account` + templates +
  numbering; `oe_gl_journal`/`oe_gl_journal_line`; `oe_gl_fiscal_year`/`oe_gl_period`/
  `oe_gl_period_lock`. Account-code backfill [MIG] with the reconciliation report.
- Routes: `/gl/entities`, `/gl/books`, `/gl/accounts` (+ `apply-template`,
  `validate-code`, `retire`), `/gl/coa/seed`, `/gl/fiscal-years`,
  `/gl/periods` (+ `soft-close|close|reopen|permanently-close`),
  `/gl/journals` (+ `post|reverse|void|batch-post`), `/gl/trial-balance`
  (+ `/{account_code}/entries` drill).
- Period-close lock in the writer (single writer, not a DB trigger).
- Project-scoped saved report views ride the existing `ProjectMemberScoper`.
Shippable value: a real, balanced, period-locked GL with a chart of accounts and a
trial balance, drillable to ledger rows.

### Phase 2 - Posting-rule engine + dimensions + statements + EntityScoper
Tests-first for: rule balance assertion, expression Decimal coercion/hard-fail,
allocation factor normalization, statement balance check.
- Build `oe_gl_posting_rule`/`_leg`, `oe_gl_account_map`, `oe_gl_subledger_link`,
  `oe_gl_posting_log` (single idempotency contract, `/test` dry-run required,
  `/replay`, `/reconcile`). Wire finance invoice/payment events.
- Build dimensions (`oe_gl_dimension`/`_member`/`_account_dimension_rule`/
  `_allocation_rule`/`_basis`) + `oe_gl_journal_line_dim`.
- Build the statements engine (`oe_gl_report_def`/`_line`/`_run`/`_aging_bucket`)
  + drill-down; balance-sheet/TB validation rules.
- Build the **`EntityMemberScoper`/`TenantScoper` prerequisite** and the registry
  widening (Part 6.5) so entity-level statements are saveable.
- Routes: `/gl/posting-rules` (+ `/test`), `/gl/account-maps`,
  `/gl/subledger-links`, `/gl/replay`, `/gl/reconcile`, `/gl/dimensions`
  (+ members tree, `validate-dimensions`), `/gl/allocation-rules` (+ `preview|run`),
  `/gl/reports/defs` (+ `clone|lines|run`), `/gl/reports/runs/{id}` (+ drill,
  export), `/gl/aging`, `/gl/wip`, `/gl/job-pnl`.
Shippable value: events auto-post balanced journals by config; full financial
statements with drill-down and saved views.

### Phase 3 - Construction revenue recognition (`gl_revrec`, the flagship)
Tests-FIRST for money math: percent-complete, earned revenue, over/under, loss
provision, retention split, WIP-ties-to-ledger, change-order catch-up.
- Build module `gl_revrec`: `oe_gl_revrec_contract` (PO grain),
  `oe_gl_revrec_run`, `oe_gl_retention_ledger` (GL projection). Posts ONLY through
  the posting-rule engine + `create_journal`; emits `gl_revrec.run.confirmed`.
- Routes: `/gl/revrec/contracts`, `/gl/revrec/runs:preview`, `/gl/revrec/runs:post`
  (explicit confirm, no silent auto-post), `/gl/revrec/wip-schedule`,
  `/gl/retention/aging`, `/gl/retention/{id}:release`,
  `/gl/revrec/cost-to-complete:suggest` (AI, confidence-scored).
- `gl.wip_ties_to_ledger`, `gl.poc_evm_variance` rules.
Shippable value: ASC 606 over-time POC, WIP schedule, dual-sided retention - the
asymmetric construction edge.

### Phase 4 - Audit, controls, period close mechanics, year-end roll-forward
Tests-first for: SoD block, period-reopen restatement flag, close-ties-to-income,
PPA routing, audit chain.
- Build `oe_gl_audit_event` (hash chain), `oe_gl_approval_rule`,
  `oe_gl_recon`/`_item`, `oe_gl_sequence`, `oe_gl_config_bundle`/`_framework`/
  `_statement_layout`/`_rounding_policy`.
- Year-end close (N-line P&L-to-RE through `create_journal`), accrual
  auto-reversal, the single reversal/PPA rule (4.3), bundle export/import.
- Routes: `/gl/journals/{id}/submit|approve|reject`, `/gl/recon` (+ match/close),
  `/gl/audit` (+ `verify-chain`), `/gl/fiscal-years/{id}/close|preview-close`,
  `/gl/bundles` (+ activate|clone|import|export), `/gl/frameworks`,
  `/gl/statement-layouts`, `/gl/rounding-policies`, `/gl/numbering-schemes`.
Shippable value: audit-defensible, SOX-shaped controls; configurable frameworks;
year-end close.

### Phase 5 - Multi-currency, multi-entity, consolidation (demand-gated)
Tests-first for: revaluation, translation/CTA, intercompany elimination balance.
- Build `oe_gl_fx_rate`, `oe_gl_revaluation_run`/`_line`,
  `oe_gl_intercompany_txn`, `oe_gl_cta`. Elimination entity journals with
  `project_id = NULL` (works because of Decision A).
- Routes: `/gl/fx-rates` (+ import|lookup), `/gl/revaluation/preview|post`,
  `/gl/intercompany` (+ match|eliminate), `/gl/translate`, `/gl/consolidation`,
  `/gl/fx-exposure`.
Shippable value: ASC 830 remeasurement/translation and consolidated statements.
Aligned with the build plan's deferred `oe_consolidation`; the nullable
entity/book/currency columns shipped in Phase 0-1 mean no retrofit.

---

## Part 10 - Decisions register and open questions

### 10.1 Decisions made (and why)

1. **Tenant/entity owns the chart and calendar; `project_id` becomes a nullable
   posting dimension.** GAAP-correct (consolidation/close/opening/intercompany
   journals have no single project), and it is the only way a trial balance can
   balance once entity-level journals exist. Forces the `project_id` NOT NULL drop.
   (Resolves #4, #5, #27.)
2. **One additive ledger migration, one journal header (`oe_gl_journal`), one
   period table (`oe_gl_period`), FK joins not string matches.** Eliminates the
   five-way column collision and the three-way header/period collisions; a real FK
   is robust where `journal_no == transaction_ref` breaks on `:rev`. (Resolves #1,
   #2, #3.)
3. **One N-line, FX-aware `create_journal` writer; legacy 2-row writer becomes a
   wrapper.** Year-end close and allocations need N lines; multi-currency needs the
   balance check in book currency. (Resolves #6, #7.)
4. **Single idempotency key `sha256(event:source_type:source_id:rule_id:book_id)`
   on both header and posting log; mandatory `/reconcile` sweep.** Makes detached
   best-effort posting airtight. (Resolves #11, #18.)
5. **Posting-rule engine is the SINGLE event-to-journal owner; `gl_revrec` and FX
   emit values/events only.** Prevents double-posting retention and revenue.
   (Resolves #9.)
6. **One reversal/PPA rule: reversals into a closed period land in the earliest
   open period as a tagged prior-period adjustment.** (Resolves #10.)
7. **`account_type` vocabulary lives in `oe_gl_framework.account_type_vocab`
   (data), one framework registry table; the parallel `FrameworkProfile` plugin
   registry is deleted.** True multi-framework pluggability. (Resolves #14.)
8. **Gapless journal numbering is synchronous, per legal entity, allocated inside
   the successful post.** Gapless and detached-best-effort are mutually exclusive;
   numbering wins. (Resolves #15.)
9. **One rounding-policy owner (`oe_gl_rounding_policy`), one residual sink
   account.** Collapses the three competing rounding mechanisms. (Resolves #16.)
10. **Tax is scoped OUT of v1, explicitly.** `tax_code`/`tax_code_default` columns
    are reserved but documented inert; no tax engine ships in v1. Deferred to a
    dedicated tax phase (post Phase 5). This avoids shipping dangling half-features.
    (Resolves #17.)
11. **All expressions use the existing `simpleeval` with one documented whitelist;
    results Decimal-coerced; dry-run required before activation; any expression
    error hard-fails the journal.** (Resolves #12.)
12. **`normal_balance` is derived-but-stored, recomputed on write, guarded by
    `gl.normal_balance_consistent`.** (Resolves #13.)
13. **Single account-resolution point validates
    `journal_line.account_code == account.code == ledger.account_code` at post.**
    (Resolves #25.)
14. **Quarantine policy: ONE shared `9999 Unmapped` suspense account.** Simpler to
    reconcile than per-code accounts; the opening-balance reconciliation report
    lists every code that landed there. (Resolves the #8 disagreement.)
15. **Revrec is modelled at the performance-obligation grain; the
    asset-xor-liability invariant is per-PO.** (Resolves #20.)
16. **Change orders anchor on dated contract change-order rows, not the mutable
    `Contract.total_value` scalar.** (Resolves #21.)
17. **`oe_gl_retention_ledger` is a projection of the GL retention control account,
    `outstanding` derived, reconciled to `Payment.withholding_amount`.** (Resolves
    #22.)
18. **WIP schedule reconciles to GL CIE/BIE control balances via
    `gl.wip_ties_to_ledger` (ERROR); POC-vs-EVM variance surfaced via
    `gl.poc_evm_variance` (WARNING); close-to-RE checked via `gl.close_ties_to_income`
    (ERROR).** (Resolves #19, #23, #28.)
19. **New date columns participating in period/aging math use `SafeDate`/
    `AwareDateTime`, never `String(40)`.** (Resolves #24.)
20. **Re-parenting an account/member with descendants is forbidden inline (done as
    a maintenance job outside the posting path); the lock cost is documented.**
    (Resolves #26.)
21. **EntityMemberScoper/TenantScoper is a real Phase-2 prerequisite, with a small
    additive registry widening; only project-scoped reports ride saved_views until
    it ships.** (Resolves #4 properly, not as a footnote.)
22. **Connector read contract is versioned: `debit_amount`/`credit_amount` always
    book currency; account mapping from `external_aliases`.** (Resolves #30.)
23. **`crm.Account` and `oe_gl_account` stay disjoint by prefix.** (Confirms #29.)
24. **The GL ships as ONE module (`gl`) plus `gl_revrec`,** so table ownership
    (one ledger migration, one writer, one header) is unambiguous; the ten lenses
    are internal files, not competing modules.

### 10.2 Open questions for the founder

1. **Default install shape:** auto-seed one implicit entity + primary book +
   12-month calendar on first GL post (recommended, zero setup friction), or force
   an explicit setup step? Recommendation: silent default, expose entity/book UI
   only when a second entity is created.
2. **SoD hardness for single-user/small contractor installs:** hard ERROR block on
   preparer==approver everywhere, or configurable to WARNING below a threshold for
   one-person firms? Recommendation: configurable to WARNING, default ERROR.
3. **Seed frameworks at launch:** US GAAP complete + IFRS skeleton (marked beta), or
   US GAAP only first? Recommendation: US GAAP complete + IFRS skeleton.
4. **Adjustment period (P13):** always auto-create at hard-close, or opt-in per
   framework profile? Recommendation: opt-in per framework profile, default on for
   `us_gaap`.
5. **Tax phase priority:** tax is deferred out of v1 (Decision 10); confirm the
   phase ordering - after consolidation (Phase 5+) or pulled earlier given US
   sales-and-use tax on materials is common in construction?
6. **Allocation rules tier:** community AGPL or enterprise-gated? (Affects the
   `oe_gl_allocation_rule` exposure.)
7. **Statement snapshots vs always-live:** snapshot the four primary statements +
   WIP (audit-grade, reproducible), keep aging/GL-detail/trial-balance live?
   Recommendation: yes.
8. **Audit immutability hardness:** is the hash-chained `oe_gl_audit_event`
   sufficient, or also enforce append-only at the DB layer
   (`REVOKE UPDATE/DELETE`) for a stronger claim?

### 10.3 Founder decisions (locked 2026-06-10)

These answer the open questions and adjust the build order. Build agents follow
these over any conflicting default above.

1. **Build scope now:** build straight through Phase 3 (revenue recognition),
   reporting per phase. Phases stay sequential (each builds on the prior).
2. **Tax pulled earlier:** insert a dedicated tax phase BETWEEN Phase 3 and
   Phase 4 (US sales/use tax on materials is common in construction). The
   reserved `tax_code`/`tax_code_default` columns are activated there, not
   post-Phase-5. v1 core (Phase 0-3) still ships tax-inert.
3. **Allocation rules tier:** `oe_gl_allocation_rule` ships in the Community /
   AGPL open core, not enterprise-gated.
4. **Frameworks at launch:** seed US GAAP complete + an IFRS skeleton marked
   beta (proves multi-framework pluggability and opens the non-US market).
5. **Remaining open questions proceed on the recommended defaults:** silent
   auto-seed of one entity + primary book + 12-month calendar (Q1); SoD
   configurable, default ERROR (Q2); P13 adjustment period opt-in per framework,
   default on for `us_gaap` (Q4); snapshot the four primary statements + WIP,
   keep aging/GL-detail/trial-balance live (Q7); hash-chained audit is
   sufficient for v1, DB-level `REVOKE UPDATE/DELETE` is a later hardening (Q8).
