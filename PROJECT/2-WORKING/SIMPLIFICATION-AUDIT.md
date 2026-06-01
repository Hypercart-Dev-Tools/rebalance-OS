# Simplification Audit — rebalance-OS Read/Display Layer

**Scope:** `scripts/dashboard.py`, `scripts/pulse_web.py`, `src/rebalance/ingest/dashboard.py`,
`src/rebalance/ingest/github_scan.py` (get_github_balance only), `src/rebalance/ingest/project_inference.py`,
`src/rebalance/ingest/registry.py`, `src/rebalance/ingest/project_classifier.py`

**Constraint:** Do not touch ingest scripts (DB writers). Do not break MCP server tools.

> **Line numbers:** Line numbers in this doc shift after every PR. Treat them as approximate search hints, not exact addresses. Always grep or search before executing a phase item.

---

## Maintainer instructions

This document is the living record of the simplification effort. Update it every time you complete a task:

1. **Tick the checkbox** next to the completed item.
2. **Update the Current Status table** — set "Last completed phase" and "Next action."
3. If you discover a new finding mid-phase, add it to the Findings Table and reference it in the appropriate phase checklist.
4. When an entire phase is done, move the phase header to read `### Phase N — [name] ✅` and update the status table.
5. When all phases are done, move this file to `PROJECT/3-DONE/`.

The rule: if you can tick a box and forget it, you're doing it right. If you need to think about whether something is done, write a note under the item.

---

## Current Status

| Column | Value |
|---|---|
| **Last completed phase** | _DECOUPLE-OBSIDIAN Phase 1_ complete (repos_json display gate removed, org-grouped view added) — this audit's Phase 1 not yet started |
| **What's next** | This audit's Phase 1 — zero-risk deletions listed below |

---

## Findings Table

Each row covers one unnecessary layer or duplicate. Risk is relative to the single-user read-only context.

| # | File : Line(s) | Name | What this layer does | Replace with | Risk | Phase |
|---|---|---|---|---|---|---|
| F1 | `src/rebalance/ingest/dashboard.py:326,381` | Stale commented-out code | Two comment lines (`# PHASE 1: removed Obsidian gate`) left over from a previous pass | Delete the comment lines | **Zero** | 1 |
| F2 | `scripts/dashboard.py:896-898` | `_interleave()` no-op | Returns its input unchanged; named like a utility but does nothing. **Verified: body is `return items`.** | Delete function + its single call site on line 885 | **Zero** | 1 |
| F3 | `scripts/pulse_web.py:378-381` | `_repo_label()` identity function | Returns `full` unchanged after a falsy check. **Verified: body is `if not full: return ""; return full`.** 3 call sites confirmed. | Delete + inline at 3 call sites | **Zero** | 1 |
| F4 | `scripts/pulse_web.py:384-386` + `scripts/dashboard.py:684-688` | Duplicate `_truncate()` | Identical 3-line helper defined independently in both files | `pulse_web.py` already imports from `dashboard.py` on line 53; import `_truncate` from there and remove the local copy | **Low (unverified)** — verify both bodies are identical before executing; any difference in max-length default, ellipsis char, or `None` handling changes rendered output in both TUI and web simultaneously | 1 |
| F5 | `scripts/dashboard.py:439-490` + `src/rebalance/ingest/dashboard.py:29-78` | `fetch_org_activity()` / `get_all_repo_activity_by_org()` near-duplicate | Same query (`github_activity GROUP BY repo_full_name`), same return shape, same org-split logic. Only difference: `fetch_org_activity` applies the ignored-repos filter; `get_all_repo_activity_by_org` uses `ensure_github_schema` and no filter | One function in `scripts/dashboard.py` with optional `ignored` param; remove from `src/rebalance/ingest/dashboard.py` and update its one import site in `build_dashboard_payload()` | **Low** — one consumer; unit tests don't cover it by name | 2 |
| F6/F7 | `src/rebalance/ingest/dashboard.py:299-304` + `github_scan.py:557-641` | Remove `get_github_balance()` from Obsidian note build | `build_dashboard_payload()` builds a `{project_name: [repos]}` map from project_registry and passes it to `get_github_balance()` — the old registry-gated path — in parallel with the already-working `get_all_repo_activity_by_org()` call. These are the same code location: F6 is the call site, F7 is the function being called. One Phase 3A task removes both. `get_github_balance()` is preserved in `mcp_server.py:40` where per-project aggregation is genuinely useful for agents. | Remove `repo_map` construction and `get_github_balance()` call from `build_dashboard_payload()`; choose Option A or B for verdict section (see Phase 3A). | **Medium** — verdict labels lose project granularity; MCP tool `github_balance` is unaffected (separate call site) | 3 |
| F8 | `scripts/dashboard.py:400-436` | `fetch_repo_activity_counts()` union query | Counts events by unioning `github_items + github_commits + github_comments` to drive the repo pie chart. Same totals could come from `github_activity` aggregate columns | Replace with: `SELECT repo_full_name, SUM(commits+prs_opened+prs_merged+issues_opened) FROM github_activity WHERE scan_date >= ? GROUP BY repo_full_name ORDER BY total DESC LIMIT ?` | **Low** — semantics shift slightly (no comment counts) but pie chart purpose unchanged | 3 |
| F9 | `src/rebalance/ingest/registry.py:27-36` | 6-list `Registry` model | `Registry` has `active_projects`, `most_likely_active_projects`, `semi_active_projects`, `dormant_projects`, `potential_projects`, `archived_projects`. The display layer only ever calls `get_projects(db, status="active")` — a flat SQLite query that ignores this model entirely | The model is only needed for the Obsidian markdown ↔ YAML sync path. If that path is removed in Phase 4, the entire `Registry`/`load_registry`/`save_registry`/`sync_registry` stack collapses to a no-op | **Medium** — MCP `confirm_projects` writes via `save_registry`; until Phase 4 is decided, leave the model alone | 4 |
| F10 | `src/rebalance/ingest/registry.py:195-223` | `sync_registry()` 3-way pull/push/check | Provides a pull/push/check sync between Obsidian markdown and SQLite. In the decoupled architecture, the Obsidian note is the *output*, not the source of truth | After Phase 3 confirms nothing breaks, the `pull` mode (Obsidian → SQLite) can be removed; `push` mode (SQLite → Obsidian) is the future direction | **Medium** — CLI and MCP use it today | 4 |
| F11 | `src/rebalance/ingest/project_classifier.py:183-195` | `repos_json` alias-building for calendar matching | Loads `repos_json` from `project_registry` and converts repo names into text aliases (e.g. `acmecorp/shopify-theme` → `shopify theme` → alias for "AcmeCorp") used to tag calendar events. **This is the only remaining functional load-bearing use of `repos_json` once the display gate is removed.** | If `project_inference.py` is running and auto-populating `repos_json` from activity, this works correctly already. If repos are all empty, calendar events still match by project name — graceful degradation, not a hard failure. Lowest-risk path: leave it alone; it costs nothing | **Low** — graceful degradation; does not gate display | flag only |
| F12 | `src/rebalance/ingest/dashboard.py` (entire file name) | Name collision between two `dashboard.py` files | `scripts/dashboard.py` is the TUI renderer + shared data fetchers (imported by `pulse_web.py`). `src/rebalance/ingest/dashboard.py` is the Obsidian note generator. Same name, different stacks — any new contributor will be confused | Rename `src/rebalance/ingest/dashboard.py` → `src/rebalance/ingest/note_builder.py`; update all import sites | **Low** — pure rename; no logic change | 2 |
| F13 | `tests/test_project_priority.py:122-145` + `tests/test_dashboard_cli.py` | Tests covering registry-gated path | Both test files exercise `build_dashboard_payload()` with `repos_json` populated (repos registered to projects) and verify per-project verdict generation via `get_github_balance()`. If Phase 3 removes that path, these tests cover machinery being deleted | After Phase 3: update `test_project_priority.py` to verify org-based activity instead; `test_dashboard_cli.py` can remain as an integration smoke test | **n/a** — test impact only | 3 |

---

## Phased Plan

### Phase 1 — Zero-risk deletions (dead code, duplicate helpers)

No logic changes. No tests need updating. Safe to do in one commit.

- [ ] **F1** — `src/rebalance/ingest/dashboard.py:326,381`: delete the two comment lines tagged `# PHASE 1: removed Obsidian gate` (lines 326-327 and 381-382 as of last read). The surrounding live code stays.
- [ ] **F2** — `scripts/dashboard.py:884-898`: delete `_interleave()` (lines 896-898) and replace the call on line 885 with just `sections` directly.
  ```python
  # Before:
  body = Group(*[Group(s, Text("")) for s in _interleave(sections)])
  # After:
  body = Group(*[Group(s, Text("")) for s in sections])
  ```
- [ ] **F3** — `scripts/pulse_web.py:378-381`: delete `_repo_label()`. Inline the null check at its 3 call sites:
  - `pulse_web.py:785` `repo = _repo_label(r.get("repo_full_name"))` → `repo = r.get("repo_full_name") or ""`
  - `pulse_web.py:853` `repo_label = _repo_label(repo["repo_full_name"])` → `repo_label = repo["repo_full_name"] or ""`
  - `pulse_web.py:894` `repo_label = _repo_label(repo["repo_full_name"])` → same
- [ ] **F4** — Before touching anything: read both `_truncate()` bodies and confirm they are identical (max-length default, ellipsis character, `None` handling). If they differ, note the difference and leave both in place. If identical, mark as **Zero** and proceed: delete the local definition in `scripts/pulse_web.py:384-386` and add `_truncate` to the import from `dashboard` (already in that import block). Verify no other local shadow.
- [ ] Run tests to confirm green: `uv run pytest tests/test_dashboard_terminal_theme.py tests/test_pulse_web_goals.py -x -q`

---

### Phase 2 — Consolidate the two dashboard.py files

One data layer per output format. Rename the collision.

- [ ] **F12** — Rename `src/rebalance/ingest/dashboard.py` → `src/rebalance/ingest/note_builder.py`. Update all import sites:
  - `src/rebalance/cli.py` (search: `from rebalance.ingest.dashboard import`)
  - `tests/test_dashboard_cli.py:14` (`from rebalance.ingest.dashboard import build_dashboard_payload`)
  - `tests/test_project_priority.py:14` (same)
  - Any other grep hit: `grep -r "from rebalance.ingest.dashboard" src/ tests/`
  - Entry points and re-exports (often missed): `grep -r "ingest.dashboard\|ingest/dashboard" pyproject.toml src/rebalance/__init__.py`
- [ ] **F5** — Add the ignored-repos filter to `get_all_repo_activity_by_org()` in `note_builder.py` (a 2-line change, same pattern as `fetch_org_activity`). Leave both functions in place for now. Defer full extraction to Phase 4, after the "retire the Obsidian note?" decision is made — if the note is retired, `note_builder.py` disappears and there is nothing to consolidate. If it stays, extract then with confidence both consumers will coexist long-term. _Note on import direction: `scripts/ → src/rebalance/` (the existing direction `pulse_web.py` already uses) is fine. The forbidden direction is `src/ → scripts/` — package code must not import from the scripts layer._
- [ ] Run tests: `uv run pytest tests/test_dashboard_cli.py tests/test_project_priority.py -x -q`

---

### Phase 3 — Eliminate get_github_balance() from the Obsidian note build; reassess github_items/github_commits tables

This is the highest-value phase but has the most moving parts.

**3A — Remove the parallel registry-gated path from `build_dashboard_payload()`**

- [ ] In `src/rebalance/ingest/note_builder.py:build_dashboard_payload()` (currently lines 299-304):
  Delete the `repo_map` construction and the `github_rows` dict built from `get_github_balance()`.
  The `org_activity` dict (from `get_all_repo_activity_by_org` / unified function) already covers all repos.
- [ ] **Record decision before writing any code** (owner must confirm): Option A is recommended — delete `_determine_verdict()` and the per-project verdict section entirely. The note was last generated May 12 (19 days stale). No one is reading verdict labels from a stale note. Option B's org-prefix heuristic fails silently for cross-org projects and would be retired two phases later anyway. Simpler replacement: a last-sync timestamp line + the org-activity table already in the payload. If owner prefers Option B, document why here before proceeding.
  > **Owner decision recorded:** _______________ (Option A / Option B)
- [ ] Delete `_determine_verdict()` and its call site in `build_dashboard_payload()`. Replace the verdict block in the rendered note with a brief last-sync timestamp and the org-activity table (data already in `org_activity`).
- [ ] Update evidence strings (currently near lines 338-346) — remove `github_rows` references entirely.
- [ ] Update `tests/test_project_priority.py` — **scope is smaller than "rewrite":** delete the verdict-assertion block (lines 122–145 per current numbering), add one assertion that `payload.org_activity` is a non-empty dict keyed by org name. Fixture setup, DB scaffolding, and `build_dashboard_payload()` call structure are unchanged.
- [ ] Update `tests/test_dashboard_cli.py` — verify the note still renders without error; verdict assertions can be removed if verdict section is gone.

**3B — Assess `fetch_repo_activity_counts()` (F8)**

- [ ] Replace the union query in `scripts/dashboard.py:400-436` with a direct `github_activity` query:
  ```sql
  SELECT repo_full_name,
         SUM(commits + prs_opened + prs_merged + issues_opened) AS events
  FROM github_activity
  WHERE scan_date >= date('now', ?)
  GROUP BY repo_full_name
  ORDER BY events DESC
  LIMIT ?
  ```
  Apply the ignored-repos filter the same way as the rest of the function.
- [ ] Confirm the pie chart in `pulse_web.py` renders correctly with the new data shape (same dict keys, different counts — visual comparison only). **Expected: per-repo event counts will be lower than before because comment events are no longer counted. This is intentional — the chart shows commit/PR/issue activity, not comment volume.**

**3C — Assess `github_commits` / `github_items` table necessity (context, not action)**

These tables are NOT redundant with `github_activity`. Keep them. The reasons:

| Consumer | Table | Purpose | Replaceable by `github_activity`? |
|---|---|---|---|
| `fetch_recent_github()` (TUI + web activity feed) | `github_items` + `github_commits` + `github_comments` | Detailed per-item view: PR titles, commit messages, issue titles | No — `github_activity` has counts only |
| `fetch_open_prs()` (web PR panel) | `github_items WHERE item_type='pull_request'` | PR state, title, review decision, draft flag | No — `github_activity` has no per-PR detail |
| `fetch_watched_summary()` (TUI watched panel) | `github_items` + `github_commits` + `github_repo_meta` | Last-sync timestamp per repo | Partially — `github_activity.last_active_at` is close but not identical to `fetched_at` |
| `fetch_repo_activity_counts()` (pie chart) | union of all three | Event count per repo | **Yes** — replace with `github_activity` in 3B above |

Verdict: `github_items` and `github_commits` earn their keep. The only query that should migrate to `github_activity` is the pie chart counter.

---

### Phase 4 — Evaluate project_registry, priority tiers, and onboarding flow

This phase is an architectural decision, not a refactor. It should be treated as an owner decision, not a code cleanup.

- [ ] **Inventory load-bearing uses of `project_registry`** after Phase 3 completes:
  - MCP `list_projects` — returns project names, summaries, priorities. Still useful for agents.
  - MCP `github_balance` — uses `{project: [repos]}` map from registry. After Phase 3, the Obsidian note no longer needs this, but the MCP tool still calls it. Decision: keep for agents, or replace with org-grouped view?
  - MCP `confirm_projects` / `onboarding_status` — write to registry via `save_registry()`. Load-bearing for onboarding flow.
  - Calendar classifier (`project_classifier.py`) — uses `repos_json` for alias building (F11). Low-risk if empty.
  - `apply_project_priorities()` — reads priority tiers from registry rows to sort projects in the Obsidian note. If the Obsidian note is removed in a future phase, this becomes dead code.

- [ ] **Decision point: does the Obsidian note (`rebalanceOS Dashboard.md`) still serve a purpose?**
  - As of the last known state (May 12), it was stale.
  - The web dashboard (`pulse_web.py`) and TUI (`scripts/dashboard.py`) are the live views.
  - If the Obsidian note is retired: `src/rebalance/ingest/note_builder.py` (Phase 2 renamed) and all its supporting machinery (`read_current_goals`, `read_recent_changelog_highlights`, `build_dashboard_note_content`, `synthesize_dashboard_narrative`, `DashboardProjectRow`, `DashboardPayload`) can be archived.
  - If it stays: keep everything, but eliminate the `get_github_balance()` call from it (Phase 3A).

- [ ] **Decision point: replace `get_github_balance()` MCP semantics with org-grouped view?**
  - Current: returns `[{project_name, total_commits, repos_linked, repos_touched, is_idle}]` — per manually-registered project.
  - Alternative: `[{org, repo, commits, prs_opened, prs_merged, last_active_at}]` — per discovered repo, no registration required.
  - The agent-facing use case may genuinely prefer per-project names ("how is the LTVera project doing?") over per-org grouping. If project names matter to agents, keep `get_github_balance()` as-is.

- [ ] **`Registry` model and `sync_registry()` audit (F9, F10)**
  - After Phase 3, determine whether `sync_registry(mode='pull')` (Obsidian → SQLite) is still called.
  - If not: remove `pull` mode from `sync_registry()`; keep `push` mode (or replace with a simpler writer).
  - `_default_registry_markdown()`, `_extract_yaml_block()`, `YAML_BLOCK_PATTERN` are only needed by `load_registry()` / `save_registry()`. If those are removed, these helpers go too.

---

## Test coverage map — machinery under review

| Test file | What it covers | Survives Phase 3? |
|---|---|---|
| `tests/test_project_priority.py` | `build_dashboard_payload()` + `get_github_balance()` via `repos_json` | Phase 3A: delete verdict-assertion block (lines 122–145), add one `org_activity` assertion. Fixture and call structure unchanged — smaller than "rewrite." |
| `tests/test_dashboard_cli.py` | CLI `dashboard-render` command end-to-end | Update assertions; structure stays |
| `tests/test_github_scan.py` | `scan_github()`, `upsert_github_activity()`, `discover_repos_from_activity()` | Unchanged — ingest only |
| `tests/test_project_inference.py` | `infer_project_registry()` auto-inference | Unchanged — ingest only |
| `tests/test_watched_repos.py` | `fetch_watched_summary()` + repo registry fixture | Unchanged — display only, uses `github_items` not `get_github_balance` |
| `tests/test_pulse_web_goals.py` | Goal parse + completion flow in `pulse_web.py` | Unchanged — not related to GitHub data path |

---

## How the symptom map connects to findings

| Original symptom | Root cause finding(s) | Phase that fixes it |
|---|---|---|
| SYMPTOM 1 — `repos_json` gate silently hides repos from dashboards | F6/F7 (parallel `repo_map` + `get_github_balance()` path), F5 (duplicate org-activity functions) | Phase 3A removes the call; Phase 1+2 reduce noise |
| SYMPTOM 2 — Two `dashboard.py` files with overlapping concerns | F5 (duplicate query function), F12 (name collision) | Phase 2 |
| Downstream: `fetch_repo_activity_counts()` hitting wrong tables | F8 | Phase 3B |
| calendar classifier's last dependency on `repos_json` | F11 | flag only — graceful degradation, no action needed |
