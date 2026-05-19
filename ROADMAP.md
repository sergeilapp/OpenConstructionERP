# OpenConstructionERP — Product Roadmap

> **Living document.** Update this file when themes shift; keep granular
> tracking in GitHub Issues and the versioned roadmap
> (`docs/ROADMAP_v1.9.md`).

---

## Now (Current Sprint)

> Actively being built. Every item here has an owner and a GitHub Issue.

| Theme | Issue | Description |
|-------|-------|-------------|
| | | |

---

## Next (Validated & Ready)

> Accepted by the team, estimated, waiting for capacity or dependencies.

| Theme | Issue | Description | Blocker |
|-------|-------|-------------|---------|
| | | | |

---

## Later (Ideas & Exploration)

> Not yet validated. Open a GitHub Discussion or an Issue with `status: idea`
> to move these forward.

| Theme | Description | Notes |
|-------|-------------|-------|
| Mobile field app | Native / PWA app for daily diaries, photos, sign-offs | Needs UX research |
| Procore integration | Bidirectional sync for projects, RFIs, submittals | Needs API scoping |
| AI takeoff from drone imagery | Auto-quantify earthworks from orthophotos | Needs POC dataset |
| Multi-tenant SaaS mode | True tenant isolation for hosted version | Needs infra ADR |
| Schedule ↔ Cost live link | EVM auto-update when schedule shifts | Needs CPM engine v2 |

---

## Done (Recently Shipped)

> Reference only. Link to the release notes or changelog.

| Release | Date | Highlights |
|---------|------|------------|
| | | |

---

## How to add an idea

1. **Raw thought?** Open a [GitHub Discussion](../discussions) in the `Ideas` category.
2. **Validated problem?** Create a GitHub Issue, label it `type: feature` + `status: idea`.
3. **Ready to build?** Move the Issue to `status: accepted`, assign a milestone, link it here.
4. **Big architectural choice?** Write an ADR in `docs/adr/` before coding.

---

## Legend

| Label | Meaning |
|-------|---------|
| `type: feature` | New capability |
| `type: enhancement` | Improvement to existing feature |
| `type: bug` | Broken behavior |
| `type: tech-debt` | Refactor / cleanup |
| `status: idea` | Not yet validated |
| `status: accepted` | Ready to build |
| `status: blocked` | Waiting on something else |
| `priority: p0` | Drop everything |
| `priority: p1` | Next sprint |
| `priority: p2` | This quarter |
| `priority: p3` | Nice to have |
