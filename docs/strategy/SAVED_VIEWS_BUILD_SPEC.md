# oe_saved_views - File-by-file Build Spec (Phase 1 keystone)

> STATUS: SPEC (founder green-lit to start now)
> OWNER: DataDrivenConstruction
> SCOPE: build the `oe_saved_views` module - a record-level, no-code saved-search
> engine any module can reuse. This is the keystone that unblocks the finance
> Chart of Accounts, financial statements, and `oe_revrec`. EXTEND not rebuild.

## How to read this spec

This is a concrete, file-by-file implementation contract. Every path is real,
every class and function is named, and the three safety primitives (scoper,
column whitelist, result budget) are pinned to the exact line they are enforced
on. Build the full vertical slice in this order: tests-first for the safe query
builder and the scoper, then models, schemas, repository, service, router,
permissions, manifest, migration. Nothing ships half-done.

A reviewer should be able to answer, from this doc alone: where is a cross-tenant
row prevented, where is an un-whitelisted column rejected, and where is an
oversized query refused. Those three answers are sections 4, 5, and 6.

## 0. What already exists (do not duplicate)

Read these before writing a line. The new module reuses their conventions and,
where the plan says "unify", will become the engine the older ones delegate to
later (that adaptation is a SEPARATE roadmap item, not this slice).

- `backend/app/modules/smart_views/` - a rule engine that re-evaluates filters
  over BIM elements ALREADY LOADED IN MEMORY (`evaluator.py` is pure, no SQL).
  It is NOT a record-level SQL query builder, so it does not solve the keystone
  problem. We copy its scope-predicate discipline (`_scope_predicate`,
  `created_by == user_id`) and its share-token caution, not its evaluator.
- `backend/app/modules/file_saved_views/` - saved filters for the file list.
  Same story: specialised, not a generic record engine.
- `backend/app/core/permissions.py` - `permission_registry`, `Role`,
  `role_has_permission`. RBAC tells you WHETHER you may use a feature.
- `backend/app/core/partner_pack/scope.py` - `active_pack_slug()` and
  `scope_project_query(stmt, Project)`. This is the real workspace ("tenant")
  isolation in this codebase: when a partner pack is active, only projects
  tagged `metadata_["partner_pack"] == slug` are visible. There is NO tenant
  table; "tenant" = partner-pack workspace + project ownership + team
  membership. The JWT carries `tenant_id` for audit only.
- `backend/app/dependencies.py` - `SessionDep`, `CurrentUserId`,
  `CurrentUserPayload`, `RequirePermission`, and crucially
  `verify_project_access(project_id, user_id, session)` which already encodes
  the owner-or-admin-or-team-member rule and returns 404 (not 403) to avoid an
  existence oracle. The saved-views scoper REUSES this, it does not reinvent it.
- `backend/app/database.py` - `Base` (gives `id`, `created_at`, `updated_at`),
  `GUID`. Money is decimal-string / `MoneyType`; JSON columns always carry a
  `server_default` because embedded PostgreSQL builds the schema via
  `create_all` and ignores Python-side defaults on existing dev DBs.
- `backend/app/modules/finance/models.py` - `LedgerEntry` (`oe_finance_ledger`):
  `project_id`, `account_code: String(100)`, append-only with
  `is_reversal`/`reversal_of_id`. This is the future COA backfill target
  (section 11).
- Current single alembic head: `v3174_pointcloud_init`. The new migration
  chains off it. Keep exactly one head (section 9).

## 1. Module purpose and the one-sentence contract

`oe_saved_views` lets a user save a named filter spec ("Open RFIs over 14 days
old", "Ledger rows for cost group 330 this period") against any entity that a
module has REGISTERED as searchable, then run it as a paginated list, a count
for a reminder badge, a dashboard tile, or an export. The same saved view feeds
all of those. The engine compiles the saved spec into ONE parameterized
SQLAlchemy `select()` that is, without exception, bounded by three server-side
gates: the scoper (which rows you may see), the column whitelist (which columns
exist for filtering and output), and the result budget (how much work the query
may do). A registration without a scoper is rejected at import/startup, not at
query time.

## 2. Directory layout

All paths under `backend/app/modules/saved_views/`:

```
saved_views/
  __init__.py            # on_startup(): register permissions + built-in entities
  manifest.py            # ModuleManifest(name="oe_saved_views", ...)
  registry.py            # EntityRegistry, QueryableEntity, FieldSpec, register_queryable_entity()
  models.py              # SavedView, SavedViewRun (audit), table defs
  schemas.py             # FilterSpec DSL (Pydantic) + request/response models
  errors.py              # typed exceptions (ScopeError, WhitelistError, BudgetError, RegistrationError)
  scoper.py              # ScopeContext + the mandatory scoper protocol + builtins
  query_builder.py       # SafeQueryBuilder: FilterSpec -> bounded parameterized select()
  repository.py          # SavedViewRepository (CRUD on the SavedView rows only)
  service.py             # SavedViewService: save/run/count/export, ties builder+scoper+budget
  router.py              # FastAPI router, auto-mounted at /api/v1/saved_views/
  permissions.py         # register_saved_views_permissions()
  events.py              # saved_view.created / .run events (optional, thin)
  entities/              # built-in entity registrations (opt-in adapters)
    __init__.py
    projects_entity.py   # registers entity_type="project"
    boq_entity.py        # registers entity_type="boq_position"
    finance_entity.py    # registers entity_type="ledger_entry"
  tests/
    test_security_scoper.py        # WRITTEN FIRST - section 8
    test_security_whitelist.py     # WRITTEN FIRST
    test_security_budget.py        # WRITTEN FIRST
    test_registry.py
    test_query_builder.py
    test_service_crud.py
    test_router.py
```

The three safety primitives live in three dedicated files so they can be unit
tested in isolation and so a reviewer can audit each in one place:
`scoper.py` (primitive 1), `registry.py` + `query_builder.py` (primitive 2),
`query_builder.py` + `service.py` (primitive 3).

## 3. Data model - `models.py`

Two tables. Both inherit `Base` (so `id`, `created_at`, `updated_at` are free).
Money is not involved here, so no `MoneyType`. JSON columns carry
`server_default` per the create_all rule.

### `SavedView` (`oe_saved_views_view`)

- `owner_id: GUID NOT NULL, index` - FK to `oe_users_user.id`,
  `ondelete="CASCADE"`. The user who created the view. Scope anchor for
  `share_scope="private"`.
- `project_id: GUID | None, index` - FK to `oe_projects_project.id`,
  `ondelete="CASCADE"`. NULL only for entities that are not project-scoped
  (none in Phase 1; every built-in entity is project-scoped, so in practice
  this is NOT NULL for built-ins). The scoper ALWAYS pins this.
- `entity_type: String(64) NOT NULL, index` - registry key, e.g.
  `"ledger_entry"`. Validated against `EntityRegistry` on write; an unknown
  entity_type is a 422, never stored.
- `name: String(255) NOT NULL`.
- `description: Text | None`.
- `spec: JSON NOT NULL, server_default="{}"` - the serialized `FilterSpec`
  (section 7). Persisted as opaque JSON; re-validated by Pydantic on every
  read AND every write, never trusted as-is.
- `share_scope: String(16) NOT NULL, default="private", server_default="private"`
  - one of `private` (owner only), `project` (any member of `project_id`),
  `workspace` (any user in the active partner-pack workspace). NEVER "public".
  There is no unauthenticated share token in Phase 1 (smart_views has one; we do
  not, because record-level data is far more sensitive than a BIM colour preset).
- `is_pinned: Boolean NOT NULL, default=False, server_default="0"` - surfaces in
  the sidebar / dashboard tile picker.
- `metadata_: JSON NOT NULL, server_default="{}"` (mapped to column `metadata`)
  - module-extensible blob (e.g. a dashboard tile's chart hint).

Indexes (`__table_args__`):
- `Index("ix_saved_views_owner_entity", "owner_id", "entity_type")` - "my views
  for this entity", the sidebar read path.
- `Index("ix_saved_views_project_entity", "project_id", "entity_type")` - shared
  views in a project.
- `UniqueConstraint("owner_id", "project_id", "entity_type", "name",
  name="uq_saved_views_owner_scope_name")` - no two identically named views in
  the same scope for the same owner.

### `SavedViewRun` (`oe_saved_views_run`)

Lightweight audit/telemetry row written by the service AFTER a successful run, so
budget-overflow attempts and slow views are observable. Append-only by
convention.

- `saved_view_id: GUID | None, index` - FK `oe_saved_views_view.id`,
  `ondelete="SET NULL"`. NULL for ad-hoc runs (run-spec without saving).
- `owner_id: GUID NOT NULL, index` - who ran it.
- `entity_type: String(64) NOT NULL`.
- `row_count: Integer NOT NULL, default=0` - rows actually returned (post-cap).
- `truncated: Boolean NOT NULL, default=False, server_default="0"` - True when
  the budget cap clipped the result.
- `elapsed_ms: Integer NOT NULL, default=0`.
- `outcome: String(16) NOT NULL, default="ok"` - `ok` | `budget` | `scope` |
  `whitelist` | `error`.
- `metadata_: JSON NOT NULL, server_default="{}"`.

Index: `Index("ix_saved_views_run_view_created", "saved_view_id", "created_at")`.

## 4. SAFETY PRIMITIVE 1 - the mandatory scoper (`scoper.py`)

This is the whole point. Every executed query has scope predicates ANDed into it
server-side, derived from the request context, before any user filter is applied.
There is no code path that runs a saved view without the scoper, because the
service calls the scoper and the query builder requires the scoped base
statement as an argument - it cannot build a statement without one.

### `ScopeContext` (frozen dataclass)

Built once per request inside the service from `CurrentUserId` /
`CurrentUserPayload`, never from the saved view body:

```
@dataclass(frozen=True)
class ScopeContext:
    user_id: uuid.UUID          # from JWT sub, DB-rehydrated (see dependencies.py)
    role: str                   # from DB-rehydrated payload, not the raw JWT claim
    project_id: uuid.UUID | None
    workspace_slug: str | None  # = active_pack_slug() captured at request time
    is_admin: bool              # role == "admin"
```

### The scoper protocol (the thing registration MUST supply)

```
class EntityScoper(Protocol):
    async def scope(
        self,
        stmt: Select,
        model: type[Base],
        ctx: ScopeContext,
        session: AsyncSession,
    ) -> Select:
        """Return stmt with mandatory scope predicates ANDed in.
        MUST narrow, never widen. MUST raise ScopeDenied to refuse outright."""
```

A `QueryableEntity` registered without a `scoper` raises `RegistrationError` at
`register_queryable_entity()` call time, which runs at module startup, so a
misconfigured module fails the boot, never a request (mirrors the plan's
"registration without a scoper is rejected at startup").

### Built-in scoper: `ProjectMemberScoper`

The default scoper for every Phase 1 entity (`project`, `boq_position`,
`ledger_entry`). It enforces three independent narrowings, all ANDed:

1. PROJECT pin. `stmt = stmt.where(model.<project_fk> == ctx.project_id)`. The
   `<project_fk>` column name is declared per entity in its `FieldSpec` registry
   (`project_fk_column`), so the scoper does not guess. For `project` itself the
   pin is `Project.id == ctx.project_id`.
2. ACCESS check. Before returning, it `await`s
   `app.dependencies.verify_project_access(ctx.project_id, ctx.user_id, session)`.
   That helper raises 404 if the user is not owner/admin/team-member, so a user
   cannot even name a project they cannot see. This is the SAME guard every other
   module uses, so saved-views can never be a softer back door than the rest of
   the app.
3. WORKSPACE pin. When `ctx.workspace_slug` is not None, the entity's project
   relationship is constrained to that pack exactly as
   `scope_project_query` does. For entities that ARE projects, reuse
   `scope_project_query(stmt, Project)` verbatim. For child entities
   (`boq_position`, `ledger_entry`) the scoper adds
   `model.project_id.in_(select(Project.id).where(<pack predicate>))` as a
   correlated subquery so a child row whose project left the workspace is
   invisible too.

Admin note: admin bypasses the project ACCESS check (step 2) exactly as
`verify_project_access` already allows, but admin does NOT bypass the PROJECT pin
or the WORKSPACE pin. An admin still only sees the project and workspace they
asked for - admin is not "see every tenant at once". This is deliberate: it keeps
the workspace single-client illusion intact even for admins and removes the only
plausible cross-tenant leak.

### Why it cannot be bypassed

- `SafeQueryBuilder.build()` signature requires `base_stmt: Select` as its first
  argument and there is no overload that synthesizes its own `select(model)`.
  The ONLY producer of `base_stmt` is `SavedViewService._scoped_base()`, which
  calls the entity's scoper. So "compile a filter" and "apply the scope" are the
  same call graph - you cannot reach the former without the latter.
- The scoper runs FIRST. User filters from the `FilterSpec` are appended to the
  already-scoped statement, and SQLAlchemy ANDs `.where()` clauses, so no user
  predicate can OR its way past a scope predicate. There is no string SQL
  concatenation anywhere (section 7), so there is no injection path to a bare
  `OR 1=1`.
- The scope values come from `ScopeContext`, which is built from the
  DB-rehydrated JWT payload (`dependencies.get_current_user_payload` overwrites
  self-asserted `role`/`permissions` from the DB on every request), never from
  the saved view row or the request body. A user editing the stored `spec` JSON
  cannot move themselves into another project or workspace.
- `project_id` for the run is taken from the URL path / query, then the scoper's
  ACCESS check (`verify_project_access`) validates it. Passing a foreign
  `project_id` yields 404, not data.

## 5. SAFETY PRIMITIVE 2 - column whitelist per entity (`registry.py`)

Only explicitly whitelisted columns can be filtered, sorted, grouped, or
returned. Anything else is a 422 at validation time, before the query is built.

### `FieldSpec`

One per allowed column:

```
@dataclass(frozen=True)
class FieldSpec:
    name: str                      # the key the client uses in the FilterSpec
    column: str                    # the real ORM attribute name on the model
    kind: Literal["string","number","money","bool","date","uuid","enum"]
    filterable: bool = True
    sortable: bool = True
    selectable: bool = True        # may appear in the returned columns
    groupable: bool = False        # only set True on indexed/low-cardinality cols
    enum_values: tuple[str, ...] | None = None  # for kind == "enum"
    operators: tuple[str, ...] = ()  # allowed ops; () => kind default set
```

`groupable` defaults False and the registry refuses `groupable=True` on a column
that is not part of an index (we cross-check `model.__table_args__` indexes at
registration; if it cannot be proven indexed, registration raises
`RegistrationError`). This satisfies the plan's "no grouping on non-indexed
columns".

### `QueryableEntity`

```
@dataclass(frozen=True)
class QueryableEntity:
    entity_type: str
    model: type[Base]
    fields: dict[str, FieldSpec]    # keyed by FieldSpec.name
    project_fk_column: str          # the scoper's project pin target
    scoper: EntityScoper            # MANDATORY
    default_sort: tuple[str, str]   # (field_name, "asc"|"desc")
    max_rows: int = 500             # entity-level override of the global cap
    default_page_size: int = 50
```

### `EntityRegistry` and `register_queryable_entity()`

Module-global singleton `entity_registry: EntityRegistry`. The public API any
module calls (from its own `on_startup`) is:

```
def register_queryable_entity(entity: QueryableEntity) -> None:
    # validation, then store. Raises RegistrationError on:
    #  - missing scoper
    #  - duplicate entity_type
    #  - a FieldSpec.column that is not a real mapped column on entity.model
    #  - groupable=True on a non-indexed column
    #  - project_fk_column not present on the model (unless model IS Project)
```

This is the opt-in API in the plan's `register_queryable_entity(entity_type,
field_registry, scoper)` shape. Modules register WITHOUT modifying `saved_views`:
`boq` calls it from `app/modules/boq/__init__.py:on_startup()`, finance from its
own startup, etc. The built-in registrations under `entities/` are wired by
`saved_views.on_startup()` only as the reference adapters; a third-party module
registers the same way.

### The validation point

`schemas.FilterSpec.bind(entity: QueryableEntity)` (called by the service before
building the query) walks every referenced field name - in `filters`, `sort`,
`group_by`, and `columns` - and:

- rejects any name not in `entity.fields` -> `WhitelistError` -> HTTP 422 with
  the offending field name.
- rejects an operator not in the field's allowed set for its kind ->
  `WhitelistError`.
- rejects a `columns` entry whose `FieldSpec.selectable` is False; a `sort` on a
  non-`sortable`; a `group_by` on a non-`groupable`.

Because the query builder only ever reads `FieldSpec.column` from the bound,
validated entity to resolve a real ORM attribute (via `getattr(model, ...)` on
the whitelisted column name ONLY), there is no path for an arbitrary string to
reach `getattr` on the model. Relationship traversal (`foo.bar`) is rejected by
the FilterSpec field-name regex (`^[a-z][a-z0-9_]*$`, no dots), so no lazy join
or relationship attribute can be addressed at all.

## 6. SAFETY PRIMITIVE 3 - result budget (`query_builder.py` + `service.py`)

Enforced BEFORE execution, in two layers:

1. ROW CAP (hard). The builder always appends
   `.limit(min(requested_page_size, entity.max_rows, GLOBAL_MAX_ROWS) + 1)`.
   `GLOBAL_MAX_ROWS = 500` (module constant, env-overridable
   `SAVED_VIEWS_MAX_ROWS`). The `+ 1` is the sentinel: if the result has
   `cap + 1` rows the service trims to `cap`, sets `truncated=True`, and returns
   a "more rows exist, narrow your filter" flag. There is no "limit=0 means
   unlimited" branch anywhere - `0` clamps to `default_page_size`.
2. COMPLEXITY CEILING (pre-execution). `SafeQueryBuilder.estimate_cost(spec,
   entity)` computes a static complexity score from the spec shape BEFORE the
   DB is touched: `n_filters + 3*n_group_by + 2*(1 if distinct else 0)`, and
   rejects with `BudgetError` (HTTP 422) when it exceeds
   `MAX_COMPLEXITY = 12`. This caps pathological specs (20 ORed filters, group
   on three columns) without a round-trip. It is a STATIC guard, so it cannot be
   evaded by data volume.
3. OPTIONAL EXPLAIN GUARD (PostgreSQL, behind a flag). When
   `SAVED_VIEWS_EXPLAIN_GUARD=1`, the service runs `EXPLAIN (FORMAT JSON)` on the
   final scoped statement and refuses (`BudgetError`) if the planner's estimated
   total cost exceeds `SAVED_VIEWS_MAX_PLAN_COST` (default 500000) or the plan
   contains a `Seq Scan` over a table flagged `requires_index_scan` in the
   entity. Off by default (one extra round-trip), on for large external
   PostgreSQL. This is the plan's "or EXPLAIN-cost guard".
4. STATEMENT TIMEOUT. The service wraps execution in
   `SET LOCAL statement_timeout = <SAVED_VIEWS_TIMEOUT_MS, default 4000>` on the
   transaction so a query that somehow slips the static guards still cannot run
   the worker out. On timeout the service catches the DB error, writes a
   `SavedViewRun` with `outcome="budget"`, and returns 422, never a 500.

The budget is enforced for EVERY entry point: `run_view`, `count_for_reminder`
(which uses `select(func.count())` over the scoped+filtered subquery, itself
capped so a count cannot scan unboundedly), and `to_export` (which streams in
capped chunks, never one unbounded fetch).

## 7. The FilterSpec DSL - `schemas.py`

The client never sends SQL. It sends a small, typed JSON spec that the engine
compiles. No `eval`, no `exec`, no raw SQL string, no f-string interpolation of
identifiers - identifiers are resolved through the whitelist to real ORM
attributes only, values go through SQLAlchemy bind parameters.

```
class FilterCondition(BaseModel):
    field: str            # regex ^[a-z][a-z0-9_]*$  (no dots, no spaces)
    op: Literal["eq","neq","lt","lte","gt","gte","contains","startswith",
                "in","between","is_null","not_null"]
    value: Any = None     # validated against the field kind at bind time

class FilterGroup(BaseModel):
    join: Literal["and","or"] = "and"
    conditions: list[FilterCondition] = []     # max len 20 (mirrors complexity)
    groups: list["FilterGroup"] = []           # max nesting depth 3

class SortSpec(BaseModel):
    field: str
    direction: Literal["asc","desc"] = "asc"

class FilterSpec(BaseModel):
    where: FilterGroup = FilterGroup()
    sort: list[SortSpec] = []                   # max 3
    group_by: list[str] = []                    # max 2, each must be groupable
    columns: list[str] = []                     # [] => entity.default columns
    distinct: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1)    # clamped by the budget cap
```

Request/response models:

- `SavedViewCreate` (entity_type, name, description, spec, share_scope,
  is_pinned).
- `SavedViewUpdate` (all optional).
- `SavedViewResponse` (row fields; `share_token` does NOT exist).
- `RunRequest` (an inline `spec` for ad-hoc runs without saving; same DSL).
- `RunResponse` (`rows: list[dict]`, `columns: list[str]`, `total_estimate: int |
  None`, `truncated: bool`, `page`, `page_size`).
- `CountResponse` (`count: int`, `truncated: bool`).

`max nesting depth 3` and `max conditions 20` are enforced by Pydantic
validators so an abusive spec is rejected at deserialization, before the
complexity ceiling even runs.

## 8. The safe query builder - `query_builder.py`

`SafeQueryBuilder` is the compiler. Pure-ish: it takes the already-scoped base
statement and the bound entity and returns a `Select`. It NEVER opens a session
and NEVER applies scope itself (that is the service's job via the scoper) - this
separation is what makes "you cannot build without scoping" structurally true.

```
class SafeQueryBuilder:
    def __init__(self, entity: QueryableEntity) -> None: ...

    def estimate_cost(self, spec: FilterSpec) -> int: ...          # primitive 3, static

    def build(self, base_stmt: Select, spec: FilterSpec) -> Select:
        # 1. resolve each whitelisted field -> getattr(model, FieldSpec.column)
        # 2. compile FilterGroup -> sqlalchemy and_/or_ of bind-param comparisons
        # 3. apply sort (whitelisted, sortable only)
        # 4. apply group_by (whitelisted, groupable only) + select count aggregate
        # 5. apply distinct if requested
        # 6. ALWAYS .limit(cap + 1)   <- primitive 3, hard row cap
        # never touches scope; base_stmt arrives already scoped

    def build_count(self, base_stmt: Select, spec: FilterSpec) -> Select: ...
```

Each `op` maps to a SQLAlchemy column expression: `eq -> col == bindparam`,
`contains -> col.ilike("%" + escaped + "%")` (LIKE wildcards in the value are
escaped so a user value cannot inject a wildcard pattern), `in -> col.in_(values)`
with a hard cap of 200 elements, `between -> col.between(lo, hi)`,
`is_null -> col.is_(None)`. Value coercion is driven by `FieldSpec.kind`
(`money`/`number` -> Decimal/float, `date` -> validated ISO, `uuid` -> UUID,
`enum` -> membership in `enum_values`); a coercion failure is a 422, not a 500.

## 9. Service, repository, router

### `repository.py` - `SavedViewRepository`

Pure data access on the `SavedView` / `SavedViewRun` rows ONLY (it never runs a
user view; that is the builder's job). Methods: `get_by_id`,
`list_for_owner(owner_id, entity_type, project_id)`,
`list_shared_in_project(project_id, entity_type)`, `create`, `update_fields`,
`delete`, `record_run(SavedViewRun)`. Mirrors `ProjectRepository` style. Every
list method is itself scoped (owner/project) so the CRUD surface cannot leak
other users' saved-view DEFINITIONS either.

### `service.py` - `SavedViewService`

The orchestrator. Key methods (names are the public contract):

- `_scoped_base(entity, ctx, session) -> Select` - builds `select(entity.model)`
  and hands it to `entity.scoper.scope(...)`. The ONLY producer of a base
  statement. Private, but it is the choke point the whole safety story rests on.
- `run_view(view_id, ctx, page, page_size) -> RunResponse` - load view, bind +
  validate spec against the entity (whitelist), `estimate_cost` (budget),
  `_scoped_base` (scope), `builder.build`, execute under statement_timeout,
  trim sentinel, `record_run`.
- `run_adhoc(entity_type, spec, ctx) -> RunResponse` - same pipeline without a
  stored row (powers the "preview before save" UX).
- `save_view(ctx, payload) -> SavedView` - validates `entity_type` is registered
  and `spec` binds cleanly before persisting; rejects a `share_scope` the user
  is not allowed to grant (only a project owner/admin may create a `workspace`
  view).
- `count_for_reminder(view_id, ctx) -> CountResponse` - capped count path for
  reminder badges and dashboard tiles.
- `to_export(view_id, ctx, fmt) -> Iterator[bytes]` - chunked CSV/Parquet using
  pandas/openpyxl (already base deps), each chunk re-applies the cap; never one
  unbounded fetch (honours the 2GB-core rule).

All five paths go through scope + whitelist + budget. There is no sixth path.

### `router.py` - endpoints (auto-mounted at `/api/v1/saved_views/`)

`ScopeContext` is assembled in a small dependency `get_scope_ctx(project_id,
user_id, payload, session)` that every data endpoint depends on; it captures
`active_pack_slug()` at request time.

- `POST   /` -> `save_view` (perm `saved_views.create`).
- `GET    /` -> list my views + shared, filter by `entity_type`, `project_id`
  (perm `saved_views.read`).
- `GET    /{view_id}` -> get one definition (perm `saved_views.read`, scoped).
- `PATCH  /{view_id}` -> update (perm `saved_views.update`, owner/admin only).
- `DELETE /{view_id}` -> delete (perm `saved_views.delete`, owner/admin only).
- `POST   /{view_id}/run` -> `run_view` (perm `saved_views.read`).
- `POST   /run` -> `run_adhoc` (perm `saved_views.read`).
- `GET    /{view_id}/count` -> `count_for_reminder` (perm `saved_views.read`).
- `GET    /{view_id}/export?fmt=csv|parquet` -> streamed `to_export`
  (perm `saved_views.export`).
- `GET    /entities` -> list registered `entity_type`s + their whitelisted fields
  (so the frontend filter builder is data-driven; perm `saved_views.read`).

Every endpoint takes `project_id` (path or required query) so the scoper always
has its pin. A run without a resolvable project is a 422 ("a saved view runs
inside a project"), never an unscoped query.

### `permissions.py`

```
def register_saved_views_permissions() -> None:
    permission_registry.register_module_permissions("saved_views", {
        "saved_views.read":   Role.VIEWER,
        "saved_views.create": Role.EDITOR,
        "saved_views.update": Role.EDITOR,
        "saved_views.delete": Role.EDITOR,
        "saved_views.export": Role.VIEWER,
    })
```

RBAC gates WHETHER you may use the feature; the scoper gates WHICH rows. Both
always run. Note: holding `saved_views.read` does NOT let a viewer read an entity
they have no project access to, because the scoper still calls
`verify_project_access`.

### `__init__.py`

```
async def on_startup() -> None:
    from app.modules.saved_views.permissions import register_saved_views_permissions
    from app.modules.saved_views.entities import register_builtin_entities
    register_saved_views_permissions()
    register_builtin_entities()   # project / boq_position / ledger_entry
```

### `manifest.py`

```
manifest = ModuleManifest(
    name="oe_saved_views",
    version="0.1.0",
    display_name="Saved Views",
    description="Record-level saved-search engine: save a filter spec against any "
                "registered entity and reuse it as a list, count, tile, or export.",
    author="OpenEstimate Core Team",
    category="core",
    depends=["oe_users", "oe_projects"],
    auto_install=True,
    enabled=True,
)
```

## 10. The migration - `alembic/versions/v3175_saved_views_init.py`

- `revision = "v3175_saved_views_init"`, `down_revision = "v3174_pointcloud_init"`
  (the current single head). This KEEPS exactly one head. After writing it, run
  `python -m alembic heads` and confirm a single line; if an agent added another
  migration meanwhile, re-point `down_revision` so the chain stays linear (see
  the "single head" rule in the team notes).
- Mirror `v3174_project_gross_floor_area.py` exactly: `from __future__ import
  annotations`, `_has_table`/`_has_column` guards via `sa.inspect(op.get_bind())`,
  idempotent `upgrade()` that no-ops when the embedded runtime already built the
  tables through `create_all`. PostgreSQL-only, no SQLite shim.
- `upgrade()` creates `oe_saved_views_view` and `oe_saved_views_run` with the
  columns, server_defaults, indexes, and unique constraint from section 3,
  guarded so a re-run or an auto-created DB is a no-op. `downgrade()` drops both
  in reverse FK order.
- After the model lands, also run `python scripts/check_version_sync.py` if any
  version-bearing file changes; the migration itself does not bump app version.

## 11. SECURITY tests FIRST, then functional - `tests/`

Per the plan ("tests-first for the safe query builder and the scoper"), write
and commit the three security test files BEFORE the service implementation. They
must fail (import error / not-implemented) first, then go green as the builder
and scoper land. Use the `tests._pg.transactional_session` helper (the Windows
loop-artifact note) and gate the real assertions on Linux CI.

### `test_security_scoper.py` (written first)

- `test_cross_tenant_rows_never_returned`: seed project A in workspace pack
  "alpha" and project B in pack "beta", each with ledger rows. With
  `ScopeContext` pinned to A/alpha, `run_view` over `ledger_entry` returns ONLY
  A's rows. Then mutate the stored `spec` JSON to reference B's `project_id` in a
  filter value - assert it STILL returns only A's rows (the scoper pin wins; a
  spec value cannot move scope).
- `test_foreign_project_id_in_url_is_404`: a user who is not a member of project
  B passes `project_id=B`. Assert 404 (from `verify_project_access`), no rows.
- `test_admin_does_not_see_other_workspace`: an admin pinned to workspace alpha
  cannot list project B's rows from workspace beta - admin bypasses the access
  check but NOT the workspace/project pin.
- `test_share_scope_workspace_requires_owner`: a plain editor cannot create a
  `workspace`-shared view; a project owner can.
- `test_registration_without_scoper_rejected`: calling
  `register_queryable_entity` with `scoper=None` raises `RegistrationError`
  (and would fail module startup).

### `test_security_whitelist.py` (written first)

- `test_filter_on_unwhitelisted_column_rejected`: a spec filtering on
  `created_by` when that field is not in the entity's `fields` -> 422
  `WhitelistError`, naming the field.
- `test_relationship_traversal_rejected`: field `"project.owner_id"` (a dotted
  path) -> 422 at Pydantic validation (regex), never reaches the builder.
- `test_sort_on_non_sortable_rejected`, `test_group_on_non_groupable_rejected`,
  `test_select_non_selectable_column_rejected`.
- `test_unknown_operator_rejected`: `op="regex"` on a string field whose
  `operators` set excludes it -> 422.
- `test_like_wildcard_in_value_is_escaped`: a `contains` value of `"%"` matches
  the literal percent, not every row (proves wildcard escaping).
- `test_in_list_over_cap_rejected`: an `in` list of 201 elements -> 422.

### `test_security_budget.py` (written first)

- `test_row_cap_enforced_and_truncated_flag`: seed 600 rows, default cap 500,
  assert exactly 500 returned and `truncated is True`.
- `test_page_size_zero_clamps_not_unlimited`: `page_size` clamped to the entity
  default, never unbounded.
- `test_complexity_ceiling_rejects_pathological_spec`: 20 ORed filters + 2
  group_bys exceeds `MAX_COMPLEXITY` -> 422 `BudgetError`, BEFORE any DB hit
  (assert no query ran, e.g. via a session spy).
- `test_count_path_is_capped`: `count_for_reminder` over a huge table does not
  scan unboundedly (count subquery is itself limited).
- `test_statement_timeout_yields_422_not_500`: a deliberately slow stub raises
  the DB timeout; the service returns 422 with `outcome="budget"`, records a
  `SavedViewRun`, and does not 500.
- (explain-guard variant, skipped unless `SAVED_VIEWS_EXPLAIN_GUARD=1`)
  `test_explain_seq_scan_refused`.

### Functional tests (after the slice builds)

- `test_registry.py`: register/dedupe/validate `QueryableEntity`; reject a
  `FieldSpec.column` that is not a real mapped column; reject `groupable=True` on
  a non-indexed column.
- `test_query_builder.py`: each operator compiles to the right predicate; sort,
  group_by+count, distinct; bind parameters used (no literal interpolation).
- `test_service_crud.py`: save -> get -> update -> delete; duplicate-name in the
  same scope rejected by the unique constraint; `run_adhoc` round-trips.
- `test_router.py`: the ten endpoints, permission gates (viewer can read/run/
  export, editor can create/update/delete), `/entities` returns the whitelist.

## 12. How COA / statements / oe_revrec reuse this keystone (and the LedgerEntry backfill)

This module is the keystone because finance reads stop being one-off endpoints
and become registered entities the moment COA lands.

- `finance` registers `entity_type="ledger_entry"` (the built-in adapter in
  `entities/finance_entity.py` is the starting point; finance owns the final
  field list). Whitelisted fields: `account_code`, `currency_code`, `posted_at`,
  `debit_amount` (money), `credit_amount` (money), `transaction_ref`,
  `source_type`, `is_reversal`. `project_fk_column="project_id"`, scoper =
  `ProjectMemberScoper`. The moment that lands, "trial balance for cost group
  330 this period", "all reversals last month", and a reminder badge "unposted
  source rows" are all SAVED VIEWS, not bespoke queries.
- The COA itself (`ChartOfAccount`, the next Phase 1 item) registers
  `entity_type="coa_account"` so the account tree is searchable/filterable the
  same way (by `account_type`, parent, active flag).
- Financial statement lines (trial balance, P&L, balance sheet) drill DOWN to
  source by running a saved `ledger_entry` view filtered to one `account_code`
  and period - the statement service builds the `FilterSpec` and calls
  `SavedViewService.run_view`, so the drill-through inherits scope + budget for
  free and can never over-fetch.
- `oe_revrec` (Phase 2) reuses the same `ledger_entry` entity to read certified
  billings and posted revenue rows when it builds the WIP schedule, and to list
  the journals it posted - again as saved views, single-currency filtered.

### Backfilling `LedgerEntry.account_code` into the future COA

`LedgerEntry.account_code` is a free `String(100)` today with no FK. When the COA
arrives, the backfill (a finance migration, NOT a saved_views one) runs in this
order, and saved_views is what makes the orphan triage observable:

1. Create `oe_finance_coa_account` and `oe_finance_accounting_period`, add a new
   nullable `account_id: GUID` FK column to `oe_finance_ledger` with a
   `server_default` of NULL (create_all ignores Python defaults on existing dev
   DBs, so the column MUST carry a server_default per the standing rule).
2. Data-migration pass: for each DISTINCT `account_code` in `oe_finance_ledger`,
   if it maps to a COA account (seed the standard chart first), set
   `account_id`; if it does NOT map, leave `account_id` NULL and tag the row's
   account as a quarantined "unmapped" account so trial balance still balances
   (quarantine, not drop).
3. Register a built-in saved view "Unmapped ledger accounts" (a `ledger_entry`
   view filtered `account_id is_null`) so an operator can SEE and resolve the
   orphans through the normal UI instead of a SQL console. This is the concrete
   payoff of building the keystone first: the cleanup tool is just a saved view.
4. Only once the orphan count is zero (or every orphan is deliberately
   quarantined) does finance consider promoting `account_id` to NOT NULL - a
   later, separate migration, never in the same step as the backfill.

`account_code` stays on the row (denormalized, human-readable, GAEB/export
friendly); the FK is additive. Nothing about the append-only ledger invariants
(`is_reversal` / `reversal_of_id`) changes.

## 13. Definition of done for this slice

models -> schemas (FilterSpec DSL) -> registry -> scoper -> query_builder ->
repository -> service -> router -> permissions -> manifest -> migration (single
head) -> the three security test files green FIRST, then the functional tests ->
the three built-in entity adapters registered -> ruff clean. The frontend filter
builder, i18n of its strings into all 27 locales, in-product guidance, and the
visual acceptance gate are required by the platform build plan and tracked as the
frontend half of this feature; this doc is the backend file-by-file contract.
