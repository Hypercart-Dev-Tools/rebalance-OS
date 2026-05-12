# Goal Layer Plan

> Rebalance grows a first-class goal/KPI/task data model — sourced from vault frontmatter — and ports the coaching detector rules that operate over it. Goaly the repo stays useful standalone; rebalance the repo stays useful without goaly. They share a frontmatter contract, not a runtime. Supersedes the deleted `P3-GOALY-COACHING.md` (an integration plan whose contradictions argued for absorption instead).

## TOC

- Goals
- Assumptions
- Non-Goals
- Current State
- Architecture Direction
- Schema
- Phase 0 — Frontmatter Contract Spike
- Phase 1 — Data Model + Ingestor
- Phase 2 — Detectors As MCP Tools
- Contracts And Ownership
- Risks And Guardrails
- Success Criteria
- Open Questions

## Goals

- Add `goals`, `kpis`, `tasks` tables to rebalance, projected from goaly-shaped vault frontmatter. Vault stays source of truth; tables are derived.
- Extend `project_registry` with the fields goaly's "Projects" layer needs (`goal_slug`, `horizon`, `definition_of_done`) so projects don't fragment across two stores.
- Port goaly's coaching detector rules (frog status, killed-mammoth, spear-sharpening, ikigai, unmeasured-goal, SMART validation) as pure MCP tools over the unified store.
- Eliminate the fuzzy-match join problem by making rebalance the owner of project slugs; goaly markdown references `project_slug:` directly.
- Keep skill layer out of scope: goaly's `.claude/skills/` continue to call rebalance MCP tools instead of `qmd`/grep, but no skill files move into rebalance.

## Assumptions

- Goaly's frontmatter shape (`title`, `status`, `project`, `goal`, `impact`, `energy`, `priority`, `timeframe` for tasks; SMART fields for KPIs) is stable and worth adopting as-is.
- Operators are willing to move their goaly `notion-mirror/` content into the rebalance vault (or symlink it). Phase 1 ships a `rebalance goal-layer import` helper for the one-time migration.
- The vault is the canonical store. Rebalance never writes goal/KPI/task markdown — ingest is read-only.
- Single operator, ~30 active projects, bi-weekly coaching cadence — no concurrency or multi-tenant concerns.
- `project_registry.slug` is the load-bearing identifier across all linked tables. Tasks/goals/KPIs reference projects by slug, never by display name.
- Detector logic is cheap (SQLite reads + small in-memory joins). No LLM calls inside detectors.

## Non-Goals

- Porting goaly's `.claude/skills/` into rebalance. Skills are presentation; they stay in goaly (or a future thinner copy in rebalance is additive, not blocking).
- Two-way sync. Vault → SQLite only.
- Real-time enforcement of goaly's creation rules (SMART KPIs, goal-link required, etc.). Rebalance can flag invalid records on ingest; it can't reject a markdown file that's already on disk.
- Multi-vault support. One vault, configured via the existing `vault_path` mechanism.
- Notion sync. That's still goaly's `tools/notion-sync/` problem and remains independent of rebalance.

## Current State

Rebalance already walks the vault via [../../src/rebalance/ingest/note_ingester.py](../../src/rebalance/ingest/note_ingester.py), parses frontmatter, chunks, and embeds. A KPI note today is just another markdown file in `chunks` + `embeddings` — semantically searchable, but the system doesn't *understand* its fields.

`project_registry` is in place with project slugs as natural keys ([../../src/rebalance/ingest/registry.py](../../src/rebalance/ingest/registry.py)), and downstream tables (`github_activity`, `calendar_events` classification, `sleuth_reminders`) already key off it. Coaching detectors today live in goaly as skill logic, keyed off file mtimes — the proxy this plan replaces.

The deleted predecessor (`P3-GOALY-COACHING.md`) tried to bridge the gap with MCP tools across two systems. The three architectural tensions it surfaced (fuzzy match brittleness, embedding abstraction mismatch, one-way contract violations in its own later phases) were all symptoms of bridging two systems that conceptually want to be one. This plan absorbs instead of bridging.

## Architecture Direction

```
VAULT (canonical)                  SQLITE (projection)           MCP TOOLS (detectors)
─────────────────                  ──────────────────            ──────────────────────
Goals/*.md   ─────┐                goals          ─┐
KPIs/*.md    ─────┼─▶ goal_layer.py ─▶ kpis        ┼─▶ querier ──▶ unmeasured_goals
Tasks/*.md   ─────┘                tasks           │              frog_status
                                                   │              spear_sharpening_check
existing (unchanged or +fields):                   │              ikigai_score
  project_registry (+ goal_slug,                   │              coaching_signals
                     horizon,                      │
                     definition_of_done,           │
                     love/good_at/needs/paid_for) ─┤
  github_activity   ────────────────────────────────┤
  github_items      ────────────────────────────────┤
  calendar_events   ────────────────────────────────┤
  sleuth_reminders  ────────────────────────────────┘
```

The new ingestor (`goal_layer.py`) is shaped exactly like [../../src/rebalance/ingest/sleuth_reminders.py](../../src/rebalance/ingest/sleuth_reminders.py): a dataclass per record, `sync_*()` function, module-local `ensure_goal_layer_schema(conn)`. Detector MCP tools are pure functions over the joined state. No embeddings in this layer — detectors are deterministic SQL + small Python; if you want semantic search over goaly notes, that's the existing vault embedding doing its job.

## Schema

```sql
CREATE TABLE goals (
    slug            TEXT PRIMARY KEY,         -- from filename, kebab-case
    title           TEXT NOT NULL,
    status          TEXT NOT NULL,            -- 'active' | 'archived'
    horizon         TEXT,                     -- '1yr' | '5yr' | 'lifetime'
    source_file     TEXT NOT NULL,            -- vault-relative path
    content_hash    TEXT NOT NULL,
    first_seen_at   TEXT NOT NULL,
    last_synced_at  TEXT NOT NULL
);

CREATE TABLE kpis (
    slug            TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    goal_slug       TEXT NOT NULL REFERENCES goals(slug) ON DELETE CASCADE,
    current_value   TEXT,                     -- TEXT so we can store '$8.5k MRR' alongside '23'
    target_value    TEXT,
    unit            TEXT,                     -- 'MRR' | 'count' | 'pct' | ...
    tracking_freq   TEXT,                     -- 'weekly' | 'biweekly' | 'monthly'
    last_updated_at TEXT,                     -- when current_value last changed (not file mtime)
    source_file     TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    first_seen_at   TEXT NOT NULL,
    last_synced_at  TEXT NOT NULL
);

CREATE TABLE tasks (
    slug            TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL,            -- 'Not started' | 'Planned this week' | 'In progress' | 'Done' | 'Deprioritized'
    project_slug    TEXT,                     -- soft FK to project_registry.slug; may not exist yet
    goal_slug       TEXT REFERENCES goals(slug),
    kpi_slug        TEXT REFERENCES kpis(slug),  -- optional direct link
    impact          TEXT,                     -- 'Needle Mover' | 'Supporting' | 'Maintenance'
    energy          TEXT,                     -- 'Deep Work' | 'Admin' | 'Meeting'
    priority        TEXT,                     -- 'High' | 'Medium' | 'Low'
    timeframe       TEXT,                     -- 'This Week' | 'Next Week' | 'Someday'
    has_coaching_accountability INTEGER NOT NULL DEFAULT 0,
    pr_link         TEXT,                     -- parsed from body: GitHub URL or 'closes #N'
    source_file     TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    first_seen_at   TEXT NOT NULL,
    last_synced_at  TEXT NOT NULL
);

CREATE INDEX idx_tasks_project ON tasks(project_slug);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_frog ON tasks(slug) WHERE has_coaching_accountability = 1;

CREATE TABLE goal_layer_validation_errors (
    id              INTEGER PRIMARY KEY,
    source_file     TEXT NOT NULL,
    record_type     TEXT NOT NULL,            -- 'goal' | 'kpi' | 'task'
    field           TEXT,                     -- offending field, or NULL for whole-record
    error           TEXT NOT NULL,
    seen_at         TEXT NOT NULL
);
```

**Additive fields on `project_registry`** (one migration in `db.py`):

- `goal_slug TEXT REFERENCES goals(slug)` — primary goal this project advances
- `horizon TEXT` — '1yr' | '5yr' etc.
- `definition_of_done TEXT` — the "what does shipped look like" statement
- `love INTEGER`, `good_at INTEGER`, `needs INTEGER`, `paid_for INTEGER` — ikigai booleans (0/1; NULL = unscored)

All new fields nullable. Existing projects keep working unchanged.

**Slug derivation contract.** Filenames map to slugs: `Goals/build-portfolio.md` → `build-portfolio`. Frontmatter can override with explicit `slug:` field. Goaly's existing notion-mirror uses human-readable filenames (e.g. `goals/build-portfolio-of-internet-companies.md`), which kebab-case cleanly. This is the join key everywhere; there is no display-name matching in this plan.

## Phase 0 — Frontmatter Contract Spike

Timebox: half-day. Read-only investigation, output is a written contract.

### Checklist

- [ ] Walk goaly's `notion-mirror/{goals,kpis,projects,tasks}/*.md` and produce a definitive field inventory per record type — required vs. optional, observed types, observed value ranges.
- [ ] Verify project linkage in goaly tasks: do they use a slug or a display name in the `project:` field? If display name, document the translation rule (kebab-case the display name? require explicit slug?).
- [ ] Confirm KPI files carry enough fields to derive `last_updated_at` for the `current_value` (vs. file mtime, which is a proxy for "any edit"). May need to read body for "Updated: YYYY-MM-DD" markers; if absent, document the limitation.
- [ ] Spot-check that "Coaching Accountability" body sections are detectable with a single regex pattern across all current frog tasks.
- [ ] Identify ambiguous or breaking cases (one task linked to multiple projects, KPI with no goal, goal with no KPI) and define how the ingestor will handle each — soft validation error + still ingest vs. hard reject.

### What Phase 0 Must Prove

- The frontmatter contract is regular enough that a small YAML-frontmatter parser plus a handful of validators covers everything.
- The slug naming convention works without per-record exceptions.
- The volume of validation errors on the current goaly corpus is small enough that the operator will actually fix them (single digits, not dozens).

### Deliverables

- [ ] `docs/GOAL_LAYER_CONTRACT.md` checked in. Documents required/optional fields per record type, slug derivation rules, the "Coaching Accountability" regex, and the validation policy (soft vs. hard).
- [ ] Findings block appended to this plan: inventory counts, ambiguous cases found, any contract concessions needed.

## Phase 1 — Data Model + Ingestor

Objective: ship the schema, ingestor, validation, and CLI. No detectors yet. ~1 week focused.

### Checklist

- [ ] Add `src/rebalance/ingest/goal_layer.py` shaped like [../../src/rebalance/ingest/sleuth_reminders.py](../../src/rebalance/ingest/sleuth_reminders.py): record dataclasses (`Goal`, `Kpi`, `Task`), `sync_goal_layer(vault_path, conn)`, module-local `ensure_goal_layer_schema(conn)`.
- [ ] Migrate `project_registry` to add the additive fields (`goal_slug`, `horizon`, `definition_of_done`, ikigai booleans). All nullable, existing projects unaffected.
- [ ] Reuse the YAML frontmatter parser from [../../src/rebalance/ingest/md_parser.py](../../src/rebalance/ingest/md_parser.py). No new markdown engine.
- [ ] Validators per record type, returning `list[ValidationError]` (record, field, message). Errors go to `goal_layer_validation_errors`, not exceptions. Record still ingests unless it's so broken it can't be persisted (e.g. no slug derivable).
- [ ] Validators implement:
  - Goal: requires `title`, `status ∈ {active, archived}`. Active goals with zero linked KPIs flagged (not rejected).
  - KPI: requires `title`, `goal_slug` resolvable, `target_value`, `tracking_freq`. Missing `current_value` flagged.
  - Task: requires `title`, `status` in the enum. Missing `project_slug` or `goal_slug` flagged. Missing `impact` flagged.
- [ ] Body parsing: detect `## Coaching Accountability` heading (case-insensitive) to set `has_coaching_accountability`. Extract first GitHub URL or `closes #\d+` into `pr_link`.
- [ ] Delta strategy mirrors note_ingester: SHA-256 of frontmatter + body in `content_hash`. Unchanged content + advanced mtime = touch refresh (`last_synced_at` only). Changed content = full re-parse + re-insert.
- [ ] Wire into `refresh_index(scope=["goal-layer"])` and append a step to [../../scripts/daily_sync.sh](../../scripts/daily_sync.sh) (guarded by `&& OK || FAILED`).
- [ ] CLI: `rebalance ingest goal-layer [--dry-run] [--vault PATH]`.
- [ ] Migration helper: `rebalance goal-layer import-from-goaly --goaly-path PATH [--vault PATH]` copies markdown into the vault `Goals/`, `KPIs/`, `Tasks/` folders without rewriting frontmatter. One-time op; idempotent (won't clobber if target file has different content).
- [ ] Tests in `tests/test_goal_layer.py`: parse fixture files for each record type, validation error coverage, content-hash delta, touch-only refresh, hard-reject (missing slug).

### Phase 1 Acceptance

- All goaly-shaped notes in the current vault parse and persist cleanly. Validation errors are listed by `rebalance goal-layer validation-errors` and the operator agrees the list is small + actionable.
- Re-running `rebalance ingest goal-layer` on an unchanged vault produces zero inserts/updates (idempotent).
- Hand-spot-check: pick 5 tasks, 3 KPIs, 2 goals at random — every field in SQLite matches the source markdown.
- Daily sync runs the new step and the run-log shows it under the same `&& OK || FAILED` pattern as the existing scopes.

## Phase 2 — Detectors As MCP Tools

Objective: ship 5 detector MCP tools that consume the new tables + existing rebalance tables, plus dashboard surfaces. ~1 week focused.

### Tool surface

Each is a pure function — SQLite reads, in-memory joins, no LLM, no embeddings, no network.

| Tool | Input | Output |
|---|---|---|
| `unmeasured_goals()` | none | `[{goal_slug, title, days_active, kpi_count}]` for active goals with zero KPIs |
| `frog_status(task_slug=None)` | optional task slug; default = all `has_coaching_accountability=1` not Done | `[{task_slug, title, status, days_since_status_change, project_slug, project_activity_signals, pr_link_match}]` |
| `coaching_signals(project_slug, since_days=14)` | hard project slug | `{commits, prs_opened, prs_merged, issues_opened, issues_closed, calendar_touches, last_*_at, verdict}` |
| `spear_sharpening_check(window_days=7)` | window | `{prs_merged, kpi_deltas, fired: bool, message}` — fires when 3+ PRs merged but zero KPI `current_value` changes in window |
| `ikigai_score(project_slug)` | hard project slug | `{love, good_at, needs, paid_for, score, verdict}` where verdict ∈ {core, acceptable, misaligned, red_flag} |

### Verdict decision tables (explicit, testable)

`coaching_signals.verdict`:
- `unknown_project` — `project_slug` not in `project_registry`
- `killed_mammoth` — 0 commits + 0 calendar touches in window AND project status = active
- `stalled` — 0 commits but ≥1 calendar touch (talking, not shipping)
- `active` — ≥1 commit OR ≥1 PR in window

`frog_status.pr_link_match`:
- `linked_shipped` — `tasks.pr_link` resolves to a merged PR / closed issue in `github_items`
- `linked_pending` — `tasks.pr_link` resolves to an open PR / issue
- `linked_missing` — `tasks.pr_link` set but no matching row in `github_items` (PAT can't see it, or it's external)
- `unlinked` — no `pr_link`

The deterministic `linked_shipped` path is the high-precision answer to "did the operator ship this." No embeddings; the operator already pasted the URL. Tasks with `unlinked` status remain a goaly skill problem (e.g. operator forgot to link) — out of scope for this plan, by design.

`ikigai_score.verdict`:
- 4/4 or 3/4 → `core`
- 2/4 → `acceptable`
- 1/4 → `misaligned`
- 0/4 → `red_flag`

### Checklist

- [ ] `src/rebalance/coaching/__init__.py` and one module per detector (`unmeasured.py`, `frog.py`, `coaching_signals.py`, `spear.py`, `ikigai.py`). Coaching primitives get their own subpackage — they read the ingest layer, never write it.
- [ ] Register all 5 tools in [../../src/rebalance/mcp_server.py](../../src/rebalance/mcp_server.py) under a new "Coaching" category.
- [ ] Document all 5 tools in [../../MCP.md](../../MCP.md).
- [ ] CLI mirrors: `rebalance coaching {unmeasured-goals,frog-status,signals,spear-check,ikigai-score}` for offline smoke-testing.
- [ ] Tests in `tests/test_coaching_*.py` per detector: each verdict branch, empty-result cases, window boundary conditions.
- [ ] Dashboard panel ([../../scripts/dashboard.py](../../scripts/dashboard.py)): add a "Goal Layer" section showing (a) stale KPIs sorted by days-since-update, (b) frog streak count + top 3 stalled frogs. KPI/task tables are small; the 2-second poll loop stays cheap.
- [ ] Pulse markdown ([../../scripts/pulse_web.py](../../scripts/pulse_web.py) and the pulse-publish path): add a "Coaching pulse" section that renders the same content as the dashboard panel, but only if there are non-zero results (no empty headers in pulse).

### Phase 2 Acceptance

- Every detector returns correct results on the current dataset, verified by hand against the most recent coaching session output from goaly.
- `coaching_signals` returns in <500ms on the local DB (no network).
- `spear_sharpening_check` fires correctly on a historical week where it should have (manual verification against memory or `data/run-log.jsonl` from goaly if available).
- Goaly's `/goaly-coaching-prep` skill, switched to call rebalance MCP tools, no longer uses `_notion_edited` mtime proxies anywhere. The skill is shorter post-switch — net deletion in goaly's repo when this lands.
- Rebalance remains useful for operators who don't run goaly: every detector tool returns `{ok: false, reason: 'goal layer empty'}` (or equivalent) when the relevant tables are empty, never an exception.

## Contracts And Ownership

- **Vault is source of truth.** Rebalance reads goal/KPI/task markdown. It never writes those files. Even validation errors are surfaced via a tool, not by editing the markdown.
- **Project slug is the universal join key.** Tasks reference `project_slug`. Coaching detectors take `project_slug` as input. No fuzzy matching, no display-name translation in code paths.
- **One module owns the schema** (`goal_layer.py`). Schema changes go through `ensure_goal_layer_schema(conn)` with migration notes in [../../CHANGELOG.md](../../CHANGELOG.md).
- **Detectors are pure.** No LLM calls, no embeddings, no network. They're cheap functions over SQLite. If a detector ever needs to embed something, it's a sign we're rebuilding goaly's skills in the wrong place — push that work back into the skill layer.
- **Frontmatter contract is versioned.** [docs/GOAL_LAYER_CONTRACT.md](../../docs/GOAL_LAYER_CONTRACT.md) (produced in Phase 0) is authoritative. Breaking changes get a version bump and a migration note. Goaly the external repo is welcome to evolve faster than us, but the contract in our repo is what our ingestor parses against.
- **No skill files cross the boundary.** Goaly's `.claude/skills/` stay there. If we want a thinner rebalance-side skill set later, it's net-new work, not a port-then-divergence.

## Risks And Guardrails

- **Scope expansion.** Rebalance was "signal ingestion + query + dashboard." This adds a goal data model and detector logic — pushing it toward "personal OS." This is the intended direction (a single operator should run fewer systems, not more), but it does mean ongoing maintenance of a model that doesn't perfectly belong to ingest or to query. Mitigation: keep the new code in two clearly-scoped places (`ingest/goal_layer.py`, `coaching/`); resist temptation to mix coaching logic into existing modules.
- **Goaly drift.** Goaly's frontmatter shape may evolve in its own repo. Our ingestor will silently start producing validation errors. Mitigation: Phase 0 produces a versioned contract; Phase 1 surfaces validation errors clearly; tests fixture-check against a snapshot of goaly's `example-*.md` files so regressions break CI, not coaching.
- **Soft FK on `tasks.project_slug`.** Operators create tasks before formalizing projects. If we hard-reject tasks with an unknown `project_slug`, ingest breaks for legitimate workflows. We accept and flag instead. Risk: a typo'd `project_slug` silently joins to nothing. Mitigation: `goal_layer_validation_errors` lists every soft-FK miss; the operator sees it next sync.
- **`last_updated_at` for KPI values.** File mtime tells us *some* edit happened, not that `current_value` changed. Without parsing change-history out of the body, we may overstate freshness. Mitigation: Phase 0 verifies whether the markdown convention encodes this somewhere. If not, document the limitation and propose a frontmatter convention (`last_value_change: YYYY-MM-DD`) for operators to adopt over time.
- **Detector logic drift between rebalance and goaly.** If we port the rules and goaly evolves its rules independently, the two diverge. Mitigation: by Phase 2 acceptance, goaly's prep skill should *call* rebalance tools rather than re-implement them. There's one source of truth for "what does killed-mammoth mean" — and it's the MCP tool, documented in MCP.md.
- **Vault becomes overloaded.** Goaly's notion-mirror is hundreds of files. Dumping all of it into the rebalance vault means every embed pass walks more notes, every search returns more candidates. Mitigation: scope the goaly content to a top-level subfolder (`Goaly/` or similar) that the operator can choose to include/exclude from semantic search via a config glob.
- **Effort honesty.** Phase 0: half-day. Phase 1: ~1 week — most of the time is in the ingestor's parser + validation + idempotency + the project_registry migration, not the schema. Phase 2: ~1 week — 5 detectors at ~1 day each, plus dashboard + pulse plumbing. Total: 2–3 weeks of elapsed work given context switches. This is meaningfully bigger than the deleted plan's "one day for Phase 1"; the upside is no follow-on cross-system integration tax.

## Success Criteria

- [ ] All goaly-shaped notes in the vault are present in `goals`, `kpis`, `tasks` with content hashes that match the source files. Validation errors are surfaced via `rebalance coaching validation-errors`.
- [ ] The 5 detector MCP tools return correct results on the current dataset for the most recent coaching session (manual verification).
- [ ] Goaly's `/goaly-coaching-prep` skill, post-switch, contains zero references to `_notion_edited` mtime proxies. The skill is shorter than today.
- [ ] The dashboard surfaces stale KPIs and frog streaks. The pulse markdown surfaces them too, but only when non-empty.
- [ ] Rebalance remains useful for operators who don't run goaly: empty goal layer = detector tools return structured "empty" responses, dashboard panel hides, pulse section omits. No exceptions, no warnings.
- [ ] Frontmatter contract is documented in `docs/GOAL_LAYER_CONTRACT.md` and snapshotted as a test fixture. Future goaly changes that break the contract break CI, not coaching prep.
- [ ] Detectors never call LLMs or embeddings. Verified by reading the `coaching/` subpackage — no imports of `embedder`, `mlx`, or `subprocess` for LLM calls.

## Open Questions

- [ ] Should the goal layer be its own ingest scope (`refresh_index(scope=["goal-layer"])`) or rolled into vault ingest? Probably separate — vault ingest is mostly free, goal-layer parsing + validation is more expensive and worth scheduling independently if we ever want sub-daily KPI refresh.
- [ ] Verdict thresholds (days_stalled, frog_streak cutoffs, etc.) — hardcoded constants in detectors vs. config file vs. project_registry frontmatter? Start hardcoded; promote to a config when we have a second consumer that wants different values.
- [ ] Coaching session history: should rebalance track sessions (date, what was committed, what was claimed Done)? Probably yes eventually — adds a `coaching_sessions` table, makes the "RECURRING STALL — sessions=3+" detector possible without consulting goaly's MEMORY.md. Defer to a Phase 3 if useful.
- [ ] Goaly's `clients/` folder (CRM-shaped) — is it in scope here? Probably no for v1; clients ≈ projects with extra metadata, and the project_registry can absorb the relevant fields if needed. Revisit if Phase 2 detectors want client-level signals beyond project-level.
- [ ] Should `tasks.pr_link` accept multiple links (a task that closes 2 PRs)? Schema is single-TEXT today; promote to a separate `task_links` table only if real operator data shows >5% of tasks need it.
- [ ] Migration UX: do we provide a `rebalance goal-layer doctor` CLI that diffs the current vault state against the contract and proposes fixes? Probably yes in Phase 1, but as a thin wrapper over `validation-errors` — not a separate workflow.
