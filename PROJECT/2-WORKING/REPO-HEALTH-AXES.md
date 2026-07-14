---
title: "Project Health Axes — Concrete Spec"
owner: Noel
gh_issue: TBA
source: "TBA"
status: "Active (2-WORKING)"
created: 2026-07-07
updated: 2026-07-07
doc_type: project
goal: >
  Add a local project-health report that scores a repository on 4-5 high-level axes such as UX, stability, security, performance, and maintainability.
related: []
effort: 3
complexity: 3
risk: 2
phases: 3
---

# PROJECT HEALTH AXES — CONCRETE SPEC

## Status

| What was just completed | What's next |
|---|---|
| Project initialized 2026-07-07 (spec drafted; no phase fired). Not yet issue-tracked — `gh_issue: TBA`. | **Open the GitHub issue** to satisfy the issue-first SOP, then Phase 1 (Spec, Schema, and Collector). Sequencing question to settle first: a per-repo health score is a candidate *signal*, so it should register against the `candidates=` collector provider built in [GH-125 HiQS](GH-125-HIQS-PIPELINE.md) Phase 3 rather than opening a parallel path into the ranking. |

## Table of Contents
- [Purpose](#purpose)
- [Design constraints](#design-constraints)
- [Feature name](#feature-name)
- [Non-goals for v1](#non-goals-for-v1)
- [Source inputs](#source-inputs)
- [Required GitHub label taxonomy](#required-github-label-taxonomy)
- [Repository scope](#repository-scope)
- [Time windows](#time-windows)
- [Storage model](#storage-model)
- [Write ownership](#write-ownership)
- [Collector registration](#collector-registration)
- [Module layout](#module-layout)
- [CLI surface](#cli-surface)
- [Data extraction rules](#data-extraction-rules)
- [Derived issue facts](#derived-issue-facts)
- [Axis scoring model](#axis-scoring-model)
- [Delta scoring](#delta-scoring)
- [JSON payload in `inputs_json`](#json-payload-in-inputs_json)
- [Dashboard contract](#dashboard-contract)
- [SQL read helpers](#sql-read-helpers)
- [Python module spec](#python-module-spec)
- [CLI module spec](#cli-module-spec)
- [Collector integration spec](#collector-integration-spec)
- [Error handling](#error-handling)
- [Test plan](#test-plan)
- [Documentation updates required in same PR](#documentation-updates-required-in-same-pr)
- [Implementation Phases](#implementation-phases)
- [Open questions](#open-questions)
- [Recommended v1 answers](#recommended-v1-answers)
- [Example operator workflow](#example-operator-workflow)
- [Definition of done](#definition-of-done)

> Status: proposed v1
> Scope: local-only derived stage for rebalance OS
> Primary input: labeled GitHub issues already synced into the local SQLite corpus
> Primary output: persisted per-repo axis snapshots for dashboard consumption

## Purpose

Add a local project-health report that scores a repository on 4-5 high-level axes such as UX, stability, security, performance, and maintainability. The implementation must fit rebalance OS's existing architecture: local-first, SQLite-backed, orchestrated writes through `refresh_index()`, and read-only dashboard surfaces over persisted state.

This feature is intentionally a **derived local scan / projection stage**, not a new raw upstream source. It reads existing GitHub artifact tables, computes transparent axis scores, persists them to dedicated tables, and lets the dashboard render a quick radar-style overview plus drilldown metrics.

## Design constraints

- Local-only by default; no required live GitHub API reads during score generation.
- Writes must go through the orchestrator via a registered collector scope.
- One writer per new table.
- Dashboard remains read-only and consumes persisted output.
- v1 uses GitHub issue labels and issue lifecycle metadata only.
- v2 may blend other local signals later without breaking storage or surface contracts.

## Feature name

Internal feature name: `project_health`

Why this name:
- It fits future non-GitHub expansion.
- It matches the repo's signal-agnostic direction.
- It is broader than a chart widget and narrower than a full prioritization engine.

## Non-goals for v1

- No MCP tool in v1.
- No live GitHub writes from rebalance OS.
- No automatic issue relabeling.
- No LLM synthesis in the scoring pass.
- No claim that the score is objective "truth" about product quality.

## Source inputs

The v1 scoring pass reads from local SQLite only.

Primary source tables:
- `github_items`
- `github_labels`
- `project_registry` (optional repo filtering / watched-repo scoping)

Optional future enrichments:
- `github_comments`
- `github_links`
- `github_check_runs`
- `calendar_events`
- `email_messages`

## Required GitHub label taxonomy

Axis labels are the canonical inclusion signal.

Required axis labels:
- `axis:ux`
- `axis:stability`
- `axis:security`
- `axis:performance`
- `axis:maintainability`

Optional type labels:
- `type:bug`
- `type:improvement`
- `type:debt`
- `type:incident`

Optional severity labels:
- `severity:low`
- `severity:medium`
- `severity:high`
- `severity:critical`

Optional source labels:
- `source:customer`
- `source:internal`
- `source:automated`

Rules:
- An issue may carry multiple labels but should carry exactly one `axis:*` label in v1.
- Issues without an `axis:*` label are ignored by the v1 scoring pass.
- If an issue has multiple axis labels, mark it as ambiguous and exclude it from score math while surfacing it in run warnings.

## Backfill Strategy (Cold Start)

Existing repositories will not have `axis:*` labels out of the box, resulting in empty dashboard charts. While automatic full-corpus relabeling is a non-goal for the `rebalance` ingest pipeline itself, an opt-in "jumpstart" mechanism is required.

**Proposed Approach (Opt-in Manual Enrichment):**
1. **Enrichment Script**: A manual script (e.g., `scripts/backfill_health_labels.py`) that evaluates the most recent N issues (default: 25) for a specified repository and applies the correct `axis:*`, `type:*`, and `severity:*` labels directly via the GitHub API.
2. **Agent Skill**: A dedicated LLM skill (e.g., `github-health-labeler`) that an agent can invoke when an operator asks to "enable project health for `owner/repo`". 

This ensures that the `project_health` local collector remains purely read-only, while providing operators with a precise tool to retroactively fix the upstream data source when needed.

## Repository scope

The generator must support three scope modes:

1. Explicit repo: `--repo owner/name`
2. Watched repos: `--all-watched`
3. All locally present repos with GitHub artifacts: `--all-local`

Default behavior for CLI v1:
- If `--repo` is supplied, use that repo only.
- Else if `--all-watched` is supplied, read repos from `project_registry`.
- Else default to `--all-watched`.

## Time windows

The scoring pass computes snapshots over an explicit period.

Required CLI options:
- `--days 30` default
- `--days 7`
- `--days 90`
- `--start YYYY-MM-DD --end YYYY-MM-DD` optional explicit window

Window semantics:
- Closed/resolved metrics use issues closed within the window.
- Backlog metrics use issues still open as of `period_end`.
- Delta compares the current window to the immediately preceding window of equal length.

## Storage model

Create three dedicated tables owned only by `src/rebalance/ingest/project_health.py`.

### 1) `project_health_snapshots`

One row per repo, period, and axis.

Suggested schema:

```sql
CREATE TABLE IF NOT EXISTS project_health_snapshots (
  id INTEGER PRIMARY KEY,
  repo_full_name TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  axis TEXT NOT NULL,
  score REAL NOT NULL,
  score_delta REAL,
  closed_count INTEGER NOT NULL DEFAULT 0,
  open_backlog_count INTEGER NOT NULL DEFAULT 0,
  median_close_hours REAL,
  high_severity_closed_count INTEGER NOT NULL DEFAULT 0,
  reopened_count INTEGER NOT NULL DEFAULT 0,
  stale_open_count INTEGER NOT NULL DEFAULT 0,
  ambiguous_labeled_count INTEGER NOT NULL DEFAULT 0,
  unlabeled_closed_count INTEGER NOT NULL DEFAULT 0,
  inputs_json TEXT,
  source_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  run_id TEXT NOT NULL,
  UNIQUE(repo_full_name, period_start, period_end, axis)
);
```

### 2) `project_health_runs`

One row per generator run.

```sql
CREATE TABLE IF NOT EXISTS project_health_runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  repo_count INTEGER NOT NULL DEFAULT 0,
  snapshot_count INTEGER NOT NULL DEFAULT 0,
  warnings_json TEXT,
  status TEXT NOT NULL,
  source_version TEXT NOT NULL
);
```

### 3) `project_health_issue_facts`

Optional but recommended debugging/provenance table for deterministic inspection.

```sql
CREATE TABLE IF NOT EXISTS project_health_issue_facts (
  repo_full_name TEXT NOT NULL,
  issue_number INTEGER NOT NULL,
  issue_node_id TEXT,
  axis TEXT,
  issue_type TEXT,
  severity TEXT,
  issue_state TEXT,
  created_at TEXT,
  closed_at TEXT,
  close_hours REAL,
  is_reopened INTEGER NOT NULL DEFAULT 0,
  is_stale_open INTEGER NOT NULL DEFAULT 0,
  source_labels_json TEXT,
  run_id TEXT NOT NULL,
  PRIMARY KEY (repo_full_name, issue_number, run_id)
);
```

## Write ownership

Writer ownership must be documented explicitly.

- Writer: `src/rebalance/ingest/project_health.py`
- Writes: `project_health_snapshots`, `project_health_runs`, `project_health_issue_facts`
- Reads: `github_items`, `github_labels`, optional `project_registry`

No other module may write to the three `project_health_*` tables.

## Collector registration

Register a new derived collector scope in `src/rebalance/ingest/index_ops.py`.

Proposed scope name:
- `project_health`

Collector characteristics:
- kind: derived local scan / projection stage
- included_in_all: `False` for v1
- requires: GitHub artifact corpus present locally
- side effects: writes only to `project_health_*` tables

Proposed behavior:
- Can be triggered manually via CLI.
- Can later be added to a scheduled flow if it proves cheap and useful.
- Must not fail the entire refresh if a single repo produces a warning; per-repo warnings accumulate into `project_health_runs.warnings_json`.

## Module layout

Planned files:

- `src/rebalance/ingest/project_health.py`
- `src/rebalance/cli/project_health.py`
- `tests/test_project_health.py`
- `tests/test_project_health_cli.py`
- Dashboard read integration in existing web/dashboard codepaths
- `PROJECT/` spec doc entry or equivalent plan-doc index reference
- `ARCHITECTURE.md` update in the same PR

## CLI surface

Add a new Typer command group:

```bash
rebalance project-health generate --repo owner/name --days 30
rebalance project-health generate --all-watched --days 30
rebalance project-health show --repo owner/name --days 30
rebalance project-health export --repo owner/name --days 30 --format json
```

### Command behavior

#### `generate`

Computes and persists snapshots.

Options:
- `--repo TEXT`
- `--all-watched`
- `--all-local`
- `--days INTEGER`
- `--start TEXT`
- `--end TEXT`
- `--database TEXT`
- `--json` optional machine-readable summary

Returns:
- run id
- repo count
- snapshot count
- warnings count

#### `show`

Read-only summary from persisted rows.

Options:
- same repo/window selectors
- `--latest` default

Returns:
- plain-text axis table with score, delta, and supporting metrics

#### `export`

Read-only structured output.

Options:
- `--format json` only in v1
- optional future `csv`

## Data extraction rules

The scoring pass uses issues only in v1.

Required item filter assumptions:
- `github_items.item_type = 'issue'`
- Pull requests must be excluded.
- Closed issues are included in resolved metrics if `closed_at` is within the active window.
- Open issues are included in backlog metrics if `created_at <= period_end` and state is open at evaluation time.

Label extraction rules:
- Read labels from the normalized GitHub artifact store.
- Map labels into `axis`, `issue_type`, `severity`, and `source` buckets.
- Store original labels as JSON in `project_health_issue_facts` for debugging.

Ambiguity rules:
- 0 axis labels -> ignored for score, counted as `unlabeled_closed_count` if closed in window
- 1 axis label -> include normally
- 2+ axis labels -> exclude from score, counted as `ambiguous_labeled_count`

## Derived issue facts

For each candidate issue, compute:
- `axis`
- `issue_type`
- `severity`
- `created_at`
- `closed_at`
- `close_hours`
- `is_reopened`
- `is_stale_open`

Definitions:
- `close_hours = closed_at - created_at` in hours for closed issues
- `is_stale_open = 1` when issue is still open and age > stale threshold
- stale threshold default: 30 days
- `is_reopened` is best-effort in v1; if no reliable reopen signal exists in local data, default to 0 and document limitation

## Axis scoring model

Scores are 0-100 floats rounded to one decimal place.

Each axis score is composed from weighted sub-scores.

### v1 weights

- 35% resolved volume
- 25% resolution speed
- 20% backlog health
- 10% severity handling
- 10% reopen penalty

### Sub-score definitions

#### 1) Resolved volume sub-score

Purpose: reward sustained completed work within the axis.

Inputs:
- `closed_count`

Normalization:
- Repo-local saturation function, not a global hard maximum.
- Suggested v1 formula:
  - `resolved_volume_score = min(100, 25 * sqrt(closed_count))`

Reason:
- Avoid linear reward explosions on large repos.

#### 2) Resolution speed sub-score

Purpose: reward faster closure.

Inputs:
- `median_close_hours`

Suggested v1 bands:
- <= 24h => 100
- <= 72h => 85
- <= 168h => 70
- <= 336h => 50
- > 336h => 30
- no closed issues => 50 neutral

#### 3) Backlog health sub-score

Purpose: penalize unresolved open work in the same axis.

Inputs:
- `open_backlog_count`
- `stale_open_count`

Suggested v1 formula:
- start at 100
- subtract `5 * open_backlog_count`, capped at 40
- subtract `10 * stale_open_count`, capped at 40
- floor at 0

#### 4) Severity handling sub-score

Purpose: reward closure of high-severity work.

Inputs:
- `high_severity_closed_count`

Suggested v1:
- 0 high-severity issues closed => 60 neutral
- 1 => 75
- 2 => 85
- 3+ => 100

Reason:
- Absence of high-severity closures may simply mean no such issues existed.

#### 5) Reopen penalty sub-score

Purpose: penalize churn.

Inputs:
- `reopened_count`

Suggested v1:
- 0 => 100
- 1 => 80
- 2 => 60
- 3+ => 40
- if reopen signal unavailable => 100 with warning note in run metadata

### Final score

```text
score =
  0.35 * resolved_volume_score +
  0.25 * resolution_speed_score +
  0.20 * backlog_health_score +
  0.10 * severity_handling_score +
  0.10 * reopen_penalty_score
```

Round to one decimal place before persistence.

## Delta scoring

For each snapshot, compute `score_delta` by comparing the current axis score to the immediately previous adjacent window of equal length.

Rules:
- If previous window data exists, `score_delta = current_score - previous_score`
- Else `score_delta = NULL`

This is a persisted value, not computed live by the dashboard.

## JSON payload in `inputs_json`

Persist a compact explanation payload for dashboard drilldown and debugging.

Suggested shape:

```json
{
  "weights": {
    "resolved_volume": 0.35,
    "resolution_speed": 0.25,
    "backlog_health": 0.20,
    "severity_handling": 0.10,
    "reopen_penalty": 0.10
  },
  "subscores": {
    "resolved_volume": 70.7,
    "resolution_speed": 85.0,
    "backlog_health": 80.0,
    "severity_handling": 75.0,
    "reopen_penalty": 100.0
  },
  "thresholds": {
    "stale_open_days": 30
  },
  "counts": {
    "closed_count": 8,
    "open_backlog_count": 3,
    "stale_open_count": 1,
    "high_severity_closed_count": 1,
    "reopened_count": 0,
    "ambiguous_labeled_count": 2,
    "unlabeled_closed_count": 5
  }
}
```

## Dashboard contract

The dashboard is read-only and reads latest snapshots.

Required dashboard behavior:
- Query the most recent `project_health_snapshots` rows for a repo and period.
- Render 4-5 axes in a radar/spider chart.
- Show score delta next to each axis.
- Provide drilldown metrics per axis from `inputs_json`.

Suggested dashboard API shape:

```json
{
  "repo": "owner/name",
  "period": {
    "start": "2026-06-01",
    "end": "2026-06-30"
  },
  "axes": [
    {
      "axis": "ux",
      "score": 76.5,
      "score_delta": 4.2,
      "closed_count": 6,
      "open_backlog_count": 2,
      "median_close_hours": 48.0
    }
  ],
  "run_id": "ph_20260707_183900_abcd1234",
  "generated_at": "2026-07-07T18:39:00Z"
}
```

The dashboard must not calculate scores itself.

## SQL read helpers

Suggested helper queries:

### Latest snapshot per axis for one repo

```sql
SELECT *
FROM project_health_snapshots
WHERE repo_full_name = ?
  AND period_start = ?
  AND period_end = ?
ORDER BY axis;
```

### Latest available run for one repo

```sql
SELECT run_id, MAX(generated_at) AS generated_at
FROM project_health_snapshots
WHERE repo_full_name = ?;
```

## Python module spec

File: `src/rebalance/ingest/project_health.py`

### Public functions

```python
def ensure_project_health_schema(conn) -> None: ...

def sync_project_health(
    database_path: str | None = None,
    repo_names: list[str] | None = None,
    all_watched: bool = False,
    all_local: bool = False,
    period_start: str | None = None,
    period_end: str | None = None,
    days: int | None = 30,
) -> dict: ...
```

### Internal helpers

```python
def _resolve_repo_scope(conn, repo_names, all_watched, all_local) -> list[str]: ...
def _compute_period(days, period_start, period_end) -> tuple[str, str]: ...
def _load_repo_issues(conn, repo_full_name, period_start, period_end) -> list[dict]: ...
def _classify_labels(labels: list[str]) -> dict: ...
def _derive_issue_fact(row: dict, period_end: str) -> dict: ...
def _compute_axis_snapshot(issue_facts: list[dict], axis: str, period_start: str, period_end: str) -> dict: ...
def _persist_run(conn, run_meta: dict) -> None: ...
def _persist_issue_facts(conn, facts: list[dict], run_id: str) -> None: ...
def _persist_snapshots(conn, snapshots: list[dict], run_id: str) -> None: ...
```

### Return shape from `sync_project_health()`

```json
{
  "run_id": "ph_20260707_183900_abcd1234",
  "status": "ok",
  "period_start": "2026-06-07",
  "period_end": "2026-07-07",
  "repo_count": 3,
  "snapshot_count": 15,
  "warnings": [
    "owner/repo: 2 issues had multiple axis labels",
    "owner/repo: reopen signal unavailable; reopen penalty treated as neutral"
  ]
}
```

## CLI module spec

File: `src/rebalance/cli/project_health.py`

Typer group name:
- `project-health`

Required commands:
- `generate`
- `show`
- `export`

Pseudo-signatures:

```python
@app.command("generate")
def generate(...): ...

@app.command("show")
def show(...): ...

@app.command("export")
def export(...): ...
```

Register the command group in the root CLI package consistent with existing command layout.

## Collector integration spec

In `src/rebalance/ingest/index_ops.py`:

- Register `project_health` as a collector.
- `included_in_all = False` in v1.
- Use the standard collector wrapper pattern used by other derived scopes.
- Require local GitHub artifacts to exist; if absent, return a structured warning rather than crashing obscurely.

Expected operator flows:

```bash
rebalance project-health generate --all-watched --days 30
rebalance refresh-index --scope project_health
```

If the codebase uses `refresh_index(scope=[...])` naming rather than a shell subcommand equivalent, align to the existing implementation style.

## Error handling

Warnings should not be fatal when:
- a repo has zero labeled issues in the window
- some issues are ambiguously labeled
- reopen signal is unavailable
- some axes have no qualifying issues

Fatal errors should include:
- database unavailable
- schema creation failure
- malformed date options
- repo scope resolves to zero repos when an explicit repo was requested

Persist run status:
- `ok`
- `warning`
- `error`

## Test plan

Add `tests/test_project_health.py` with coverage for:

1. Schema creation succeeds.
2. Repo scope resolution works for explicit repo, watched repos, and all-local.
3. Unlabeled issues are ignored but counted in warnings.
4. Multi-axis issues are excluded and counted as ambiguous.
5. Closed issues inside the window affect resolved metrics.
6. Open issues affect backlog metrics.
7. Stale open issues affect backlog penalty.
8. Score is deterministic for a fixed synthetic issue set.
9. Delta scoring compares to the prior adjacent window correctly.
10. Re-running the same repo/window upserts rather than duplicates.

Add `tests/test_project_health_cli.py` with coverage for:
- `generate` exits 0 and prints run summary
- `show` returns persisted rows
- `export --format json` returns valid JSON

## Documentation updates required in same PR

Because the architecture doc is load-bearing, the implementing PR must update architecture documentation in the same change.

Required doc updates:
- Add `project_health` to the list of registered derived scopes.
- Add `project_health_*` tables to Storage Layer -> Tables by Domain.
- Add the CLI entrypoints to Invocation points if they are user-facing.
- Add a short note to README roadmap or dashboard docs if the feature ships visibly.

## Implementation Phases

### Phase 1: Spec, Schema, and Collector

- [ ] Add spec doc (`PROJECT/2-WORKING/REPO-HEALTH-AXES.md` cleanup and finalization)
- [ ] Add schema definitions for `project_health_snapshots`, `project_health_runs`, `project_health_issue_facts`
- [ ] Create ingest module skeleton (`src/rebalance/ingest/project_health.py`)
- [ ] Register `project_health` collector scope in `src/rebalance/ingest/index_ops.py`
- [ ] Add tests for schema creation and pure scoring helpers in `tests/test_project_health.py`

**Phase 1 QA Checklist (PDDA Verification):**
- [ ] `pytest tests/test_project_health.py` passes
- [ ] Schema is correctly generated when running tests or manually testing the ingest script
- [ ] Collector scope is successfully listed in registered scopes without errors
- [ ] `utils/pdda/pdda.sh run` clean for all touched files

### Phase 2: Persistence and CLI Surface

- [ ] Implement data extraction and derivation logic (`_load_repo_issues`, `_classify_labels`, `_derive_issue_fact`)
- [ ] Implement scoring logic (`_compute_axis_snapshot`)
- [ ] Persist run and snapshot rows (`_persist_run`, `_persist_snapshots`, `_persist_issue_facts`)
- [ ] Add CLI command group (`project-health`) in `src/rebalance/cli/project_health.py`
- [ ] Implement `generate`, `show`, and `export` CLI commands
- [ ] Add CLI tests in `tests/test_project_health_cli.py`
- [ ] Write `scripts/backfill_health_labels.py` for manual retroactive labeling (N=25 issues) and document the related LLM agent skill.

**Phase 2 QA Checklist (PDDA Verification):**
- [ ] `rebalance project-health generate --all-watched --days 30` completes successfully
- [ ] DB contains expected rows in `project_health_snapshots`
- [ ] `rebalance project-health show --latest` outputs plain-text axis table correctly
- [ ] `pytest tests/` passes successfully
- [ ] `rebalance doctor` is clean
- [ ] `utils/pdda/pdda.sh run` clean for all touched files

### Phase 3: Dashboard Integration and Documentation

- [ ] Build SQL read helpers for the dashboard to fetch latest snapshots
- [ ] Add radar chart rendering and drilldown metrics to the dashboard UI
- [ ] Update `ARCHITECTURE.md` (add derived scope, table details)
- [ ] Update README and DASHBOARD docs with the new feature
- [ ] Validate end-to-end flow with a real repository and labels

**Phase 3 QA Checklist (PDDA Verification):**
- [ ] Dashboard correctly visualizes data from `project_health_snapshots`
- [ ] No live GitHub requests occur when loading the dashboard health views
- [ ] `ARCHITECTURE.md` accurately reflects new tables and scope
- [ ] `utils/pdda/pdda.sh run` clean for all touched files

## Open questions

1. Does the current `github_items` projection already expose labels in a directly queryable form, or is a label join/JSON parse needed?
2. Is reopen state derivable from local GitHub artifact history, or should v1 explicitly treat reopen penalty as neutral?
3. Should watched repos be filtered to only those present in `project_registry`, or should GitHub-local repos still appear in `--all-watched` fallback mode if registry is sparse?
4. Does the existing dashboard prefer reading from SQLite directly or via a small read helper/API layer for chart payloads?
5. Should `project_health` remain manual-only in v1, or should an opt-in scheduled job be added after the scoring cost is measured?

## Recommended v1 answers

- Assume labels may require normalization/parsing; design helper functions accordingly.
- Treat reopen penalty as neutral if a trustworthy local signal is absent.
- Default `--all-watched` to registry repos only; require `--all-local` for broader scan.
- Keep dashboard scoring read-only and preferably route through a small read helper rather than embedding SQL in templates.
- Keep generation manual in v1; revisit scheduling after operator feedback.

## Example operator workflow

```bash
rebalance github-sync-artifacts --repo owner/name --database rebalance.db
rebalance project-health generate --repo owner/name --days 30 --database rebalance.db
rebalance project-health show --repo owner/name --days 30 --database rebalance.db
rebalance project-health export --repo owner/name --days 30 --format json --database rebalance.db
```

## Definition of done

The feature is done for v1 when:

- A maintainer can label GitHub issues with one `axis:*` label and run a local command to generate persisted health snapshots.
- Snapshots are stored in dedicated `project_health_*` tables with a single writer.
- The dashboard can render the latest per-repo axis overview from persisted rows without live GitHub reads.
- Scores are explainable through persisted sub-score inputs.
- Tests cover schema, classification, scoring, upsert behavior, and CLI basics.
- `ARCHITECTURE.md` is updated in the same PR.
