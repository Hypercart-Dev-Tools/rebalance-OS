---
title: Focus 5 Dashboard View
status: proposed
doc_type: project-plan
owner: Noel Saw
last_updated: 2026-06-05
surfaces:
  - web
  - dashboard
---

| Most recently completed phase | What's next |
|---|---|
| Phases 1–3 shipped and tested (PR #54). Phase 3 adds: 24h roster TTL with lazy recompute on visit, a manual refresh control (post/redirect/get), live top-5 tree-health re-probe on every load (separate from the snapshot, with `health_probed_at`), explicit freshness/stale markers, and the off-roster hidden-attention warning strip from the cached signals. The view is wired into the always-on pulse server (`:8767`) with a sidebar link. | Phase 4: collector/route test hardening (largely done — 52 tests), structured timing logs around the collector path, and final rollout notes. |

## Table of Contents

1. [Phase 0 - Technical Spike](#phase-0---technical-spike)
2. [Phase 1 - Data Contract and Collector](#phase-1---data-contract-and-collector)
3. [Phase 2 - Web View and Interaction Model](#phase-2---web-view-and-interaction-model)
4. [Phase 3 - Refresh Behavior and Safety Signals](#phase-3---refresh-behavior-and-safety-signals)
5. [Phase 4 - Testing, Observability, and Rollout](#phase-4---testing-observability-and-rollout)
6. [Working Model](#working-model)
7. [Risks and Open Decisions](#risks-and-open-decisions)
8. [Definition of Done](#definition-of-done)

Decision lock-ins for this plan:
- Local repo activity is the ranking signal, not remote GitHub activity.
- Local git state and local git history are the primary activity sources; GitHub corpus data is enrichment only.
- Repo scope must be zero-config for the operator.
- There is no server-side session model in the first implementation; the view should use a persisted roster snapshot with timestamps and refresh rules.

## Working Model

- Roster model:
  the page reads from a persisted `Focus 5` roster snapshot with `computed_at` metadata and a 24-hour freshness window.
- Refresh trigger model:
  "automatic 24-hour refresh" means lazy recompute on page load when the persisted roster is stale, unless a background scheduler is later added explicitly.
- Manual refresh model:
  the refresh button forces roster recompute immediately and can admit newly active repos at that moment.
- Persistence split:
  roster membership, ranking inputs, off-roster warning inputs, and recent activity summaries may be persisted; top-5 working tree health should be treated as a live probe with visible freshness markers.
- Off-roster warning model:
  the hidden-attention strip should read cached or persisted health summaries for non-visible repos rather than probing the entire discovered set live on every request.
- GitHub enrichment fallback:
  a locally active repo remains eligible even when no GitHub mapping exists; in that case the PR section should render an explicit empty or unavailable state rather than dropping the repo.
- Discovery model:
  zero-config discovery should reuse the repo's existing bounded local-scan pattern rather than introducing whole-disk search or brittle editor-state scraping.
- Activity signal model:
  the first pass should use local git signals, such as local commit history, working tree state, and repository timestamps, rather than undocumented VS Code workspace internals.
- UI implementation scope:
  the first pass may stay inside the existing single-file FastAPI surface, but the plan should allow a small rendering split if the page becomes unwieldy in one file.

## Risks and Open Decisions

- Stateless server constraint:
  the current FastAPI surface is stateless, so the plan must not imply cookies, per-browser session memory, or page-load identity without explicitly adding storage.
- Live-probe budget:
  top-5 live probes are acceptable; full-set live probes for off-roster warnings are not. Non-visible repos need cached summaries, caps, or time budgets.
- Automatic refresh semantics:
  if no scheduler is added, "automatic" means "recompute on next visit after TTL expiry," not "refresh in the background while nobody is looking."
- Discovery reuse:
  the repo already has a bounded local-discovery pattern; Phase 0 should bias toward adapting that pattern instead of inventing a second unrelated discovery mechanism.
- Local-first rendering:
  cards must still feel populated for active repos that have no GitHub corpus coverage yet, especially personal or side-project repos.
- Ranking signal (OPEN — blocks Phase 1, raised by the Phase 0 spike):
  `.git/index` mtime is polluted by clone/fetch/checkout and surfaces dormant third-party clones over the operator's own dirty WIP. The activity signal must be operator-authored (commits by the operator's git email) and/or dirty-tree based, not raw index mtime. The exact eligibility/ranking policy is pending an explicit decision before the collector is written.

## Phase 0 - Technical Spike

Goal: Prove the critical assumptions in 1-2 hours before committing to the full build.

### Phase 0 spike results (executed 2026-06-05, read-only, real device)

Validated empirically with a throwaway script reusing the ask_self scan-root + pruned-walk pattern (`.git` marker instead of the ask_self harness):

- **Discovery — PASS.** 21 git repos found under the existing zero-config scan roots in **95 ms**, bounded by the existing prune list + max-depth and stopping at each repo boundary (no submodule fan-out). No operator config needed.
- **Live git-health reads — PASS.** A single `git status --porcelain=v2 --branch` per repo yields branch, upstream, ahead/behind, modified count, untracked count, and clean/dirty verdict in **~51 ms/repo**. Big drift reads correctly (e.g. one clone at `+0/-1484`).
- **Live-vs-cached split — PASS / confirms the plan.** Full 21-repo health sweep = **~1.2 s**; top-5-only probe ≈ **256 ms**. Confirms off-roster warnings must read **cached** summaries (a full live sweep per request is too slow), while top-5 live probing per request is fine.
- **Activity ranking — FAIL / CONTRADICTION (escalated).** Ranking by "most recent local activity" using `.git/index` mtime is **invalid**: index mtime is bumped by `git clone`/`fetch`/`checkout`, not just by the operator's edits. The spike's top 5 were dormant third-party clones the operator has **never committed to** (e.g. `shopify_python_api` — index touched 0h ago but last commit 39d ago, zero operator commits; `hermes-agent` — `+0/-1484` behind, never touched), while the operator's actual dirty WIP (`rebalance-OS`: 5 modified / 4 untracked) was pushed to rank #7, *out* of the top 5. The signal must be **operator-authored activity** (commits by the operator's email) and/or **dirty working tree**, explicitly excluding raw index/fetch mtime. Final ranking policy is the open decision blocking Phase 1 — see [Risks and Open Decisions](#risks-and-open-decisions).

Secondary observation: repo display names can collide across scan roots (two `sleuth-app` paths seen). Phase 1 must key the roster by resolved path / repo identity, not bare name.

- [ ] Confirm the additive surface will live as a new route in [src/rebalance/web.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/web.py:1) without replacing any existing page.
- [ ] Validate reuse of the existing bounded local-scan pattern for repo discovery:
  observable result: documented zero-config discovery path for active local repos that adapts the current bounded filesystem-walk approach instead of requiring operator-maintained repo lists or whole-disk search.
- [ ] Define the authoritative local activity signals:
  observable result: documented source-of-truth for "active on this device" using local git signals and related local repo metadata, without depending on undocumented editor-state internals.
- [ ] Replace the loose session idea with a persisted roster contract:
  observable result: documented roster row shape, `computed_at` semantics, TTL behavior, and recompute rules for page load and manual refresh.
- [ ] Validate local git health reads for candidate repos:
  observable result: per-repo sample output for branch, ahead/behind, modified count, untracked count, and clean/dirty verdict.
- [ ] Validate ranking logic for "most recently active on this device":
  observable result: documented ranking by local repo activity using local git-first signals, with GitHub data excluded from primary rank decisions.
- [ ] Define the live-versus-persisted split:
  observable result: documented separation between persisted roster data and live working-tree probes so freshness and storage behavior are explicit.
- [ ] Define the off-roster warning strategy:
  observable result: documented decision that hidden-attention warnings for non-visible repos use cached or persisted health summaries, caps, or a time budget rather than full-set live probes on every request.
- [ ] Define fallback behavior for repos without a clean GitHub identity:
  observable result: documented card behavior for local-only repos, non-GitHub remotes, or repos not yet present in the GitHub corpus.
- [ ] Define the 24-hour refresh trigger precisely:
  observable result: documented choice between lazy-on-visit refresh and an explicit scheduler-backed refresh path, with the first implementation selected intentionally.
- [ ] Validate performance for the top-5 read path:
  observable result: one-page load can discover active repos, probe top-5 live health, and render the page without operator setup or unacceptable UI delay.
- [ ] Validate performance for off-roster warning generation:
  observable result: warning-strip computation stays bounded and does not require a synchronous live health sweep across the full discovered repo set.
- [ ] Pause and escalate if any spike result contradicts the current plan:
  observable result: blockers captured in this doc before Phase 1 starts.

## Phase 1 - Data Contract and Collector

Goal: Create a reliable device-local data source for the `Focus 5` view.

Status: shipped in PR #54 (2026-06-05). Implemented in
[src/rebalance/ingest/focus5_scan.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/ingest/focus5_scan.py:1)
with migration `0003_focus5_roster.sql`.

- [x] Define the `Focus 5` repo card contract in one place:
  observable result: `summarize_focus5()` is the single owner of the card shape (name, local path, `vscode_url`, `newest_pr`, tree health, `recent_activity`).
- [x] Add a small device-local collector to [src/rebalance/ingest/index_ops.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/ingest/index_ops.py:1):
  observable result: `focus5` collector registered opt-in (`included_in_all=False`); runs via `refresh_index(scope=["focus5"])`.
- [x] Implement zero-config repo discovery for active local work:
  observable result: `iter_git_repos` finds repos with no manual registration, reusing the ask_self scan-root defaults.
- [x] Bound discovery so zero-config does not become full-machine drag:
  observable result: bounded by the shared prune list + max-depth, stopping at each repo boundary (95 ms / 21 repos measured).
- [x] Persist the roster snapshot and related stable summary fields:
  observable result: `focus5_roster` stores position + rank_reason + ranking_mode + computed_at; raw signals persisted separately so re-rank needs no re-scan.
- [x] Persist off-roster health summaries for warning-strip use:
  observable result: `focus5_repo_signals` caches every discovered repo's health; `summarize_focus5()` derives off-roster warnings from it.
- [x] Keep working tree health as a live read with freshness metadata:
  observable result: each signal row carries `probed_at`; the live top-5 re-probe on page load is wired in Phase 3.
- [x] Join local repo records to existing GitHub corpus data:
  observable result: `newest_pr` joins `github_items` on `repo_full_name` (newest PR by number).
- [x] Define enrichment fallback states in the repo card contract:
  observable result: explicit "no open PR synced yet", "non-GitHub remote", and "no remote configured" states; never drops the repo.
- [x] Capture last-activity signals for each repo:
  observable result: `recent_activity` returns the last 3 local commits, local-git-first, via read-only `git log`.

## Phase 2 - Web View and Interaction Model

Goal: Add the new additive dashboard page and make the 5-column layout useful for fast context switching.

Status: shipped in PR #54 (2026-06-05).

Rendering-approach decision (recorded): stay in the existing single-file
FastAPI surface (`web.py`), but extract a **pure** `_focus5_body(data)` renderer
plus small `_f5_*` section helpers that take a `summarize_focus5()` dict and
return HTML. This keeps the route thin (resolve DB → summarize → render) and
makes the view unit-testable without a DB, git, or an HTTP client. The
`summarize_focus5()` read contract is the single owner of the card shape
(`vscode_url`, `newest_pr`, `recent_activity`, tree-health fields).

- [x] Add a new `Focus 5` page to the local web server in [src/rebalance/web.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/web.py:1):
  observable result: home page and shared nav link to `/focus-5`; existing pages unchanged.
- [x] Decide whether the first implementation stays in single-file HTML rendering or extracts a small helper layer:
  observable result: decision recorded above — single file + pure renderer seam.
- [x] Build a responsive 5-column layout for desktop:
  observable result: CSS-grid `repeat(5, 1fr)` collapsing to 2 then 1 column at 1100px / 620px; wide main for the focus view.
- [x] Add `Open in VS Code` affordance per repo:
  observable result: repo name links to `vscode://file/<path>` (URL-encoded), opening the repo root.
- [x] Render the newest remote PR per repo:
  observable result: number + title link to the PR; explicit "no open PR synced yet / non-GitHub remote / no remote configured" fallbacks otherwise.
- [x] Render current tree health per repo:
  observable result: dirty/clean dot, modified/untracked counts, branch, and ahead/behind (or "no upstream") drift.
- [x] Render the last 3 activity items per repo:
  observable result: last 3 local commits (subject + short SHA + relative age) via a live `git log` read on the top-5 only.

Deferred to Phase 3 (intentionally): the off-roster hidden-attention strip, the
24h TTL recompute, the manual refresh control, and live top-5 health re-probe on
load. Phase 2 lazily bootstraps the roster once when it is empty so the page is
useful on first visit; full refresh semantics are Phase 3.

## Phase 3 - Refresh Behavior and Safety Signals

Goal: Keep the focused view fresh without hiding risky repos.

Status: shipped in PR #54 (2026-06-05). Roster TTL = 24h (`FOCUS5_ROSTER_TTL_SECONDS`); the route uses a cheap `get_roster_meta()` check before any live-probe render.

- [x] Implement 24-hour automatic roster refresh:
  observable result: `get_roster_meta()` + `_roster_stale()` lazily recompute on visit when the snapshot is past 24h (no scheduler needed).
- [x] Add manual refresh control:
  observable result: `↻ Refresh` button hits `/focus-5?refresh=1` → forces `sync_focus5` → 303 redirect (post/redirect/get) so a reload doesn't re-scan.
- [x] Surface roster snapshot metadata:
  observable result: meta line shows "Roster computed {age} · ranked by {mode} · {n} discovered"; a manual refresh resets it to "just now".
- [x] Allow the roster to admit newly active repos on refresh:
  observable result: every recompute re-discovers and re-ranks all repos, so a newly active repo can enter the top 5 on manual or TTL refresh.
- [x] Refresh local tree health on page load:
  observable result: `summarize_focus5(with_live_health=True)` re-probes each top-5 repo's `git status` per load, overlaying the snapshot with a fresh `health_probed_at`.
- [x] Keep roster freshness and repo-health freshness separate in the UI:
  observable result: roster age ("computed {age}") and live health ("● tree health checked live" + per-card "Tree health · live") are shown distinctly.
- [x] Add hidden-attention warning strip above the grid:
  observable result: amber strip lists off-roster repos that are dirty or unpushed, sourced from the cached `focus5_repo_signals` (no full live sweep), labeled with the roster's age.
- [x] Define stale-data behavior:
  observable result: off-roster strip is labeled "as of roster computed {age}"; a roster past TTL that failed to refresh renders a "⚠ stale" marker rather than silently showing old data.

## Phase 4 - Testing, Observability, and Rollout

Goal: Ship the new view with confidence and operational visibility.

- [ ] Add collector tests before full integration:
  observable result: mocks cover happy path, missing repo, auth gap, git failure, and empty activity cases.
- [ ] Add web-route coverage for the new page:
  observable result: automated test proves the route renders and includes the expected repo-card sections.
- [ ] Add timing and structured logs around the collector path:
  observable result: slow repo scans and repeated failures are diagnosable from logs.
- [ ] Add at least one integration-style happy-path test:
  observable result: seeded local repo data produces a populated 5-column page.
- [ ] Run manual smoke test on desktop and narrow/mobile widths:
  observable result: layout remains usable and the page still supports quick context switching.
- [ ] Update this plan with final rollout notes:
  observable result: completed phases and any follow-up items are recorded here instead of drifting into chat.

## Definition of Done

- [x] A new additive `Focus 5` route exists in the local web dashboard (`/focus-5`, served by both `rebalance serve` :8787 and the always-on pulse server :8767, with a sidebar link).
- [x] The page shows exactly 5 recent repos in a left-to-right layout (responsive 5-col grid).
- [x] Repo discovery requires zero manual config from the operator.
- [x] Each repo column includes repo open action, newest remote PR, current tree health, and last 3 activity items.
- [x] Manual refresh works and 24-hour automatic roster refresh is defined.
- [x] Roster recompute semantics are explicit and based on persisted snapshot timestamps rather than an implicit server-side session.
- [x] Local git data is sufficient to keep cards useful even when GitHub enrichment is unavailable.
- [x] Hidden attention warnings reduce the risk of losing sight of unhealthy repos outside the top 5.
- [ ] Tests and logs are in place for the collector and the new page. _(52 tests in place; structured timing logs around the collector path are the remaining Phase 4 item.)_
