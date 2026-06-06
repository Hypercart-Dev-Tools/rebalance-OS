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
| Phase 0 technical spike executed against the real device (2026-06-05). Discovery, live git-health reads, and the live-vs-cached split all validated. One contradiction found and escalated: the naive "most recently active" ranking by `.git/index` mtime is invalid — it surfaces dormant third-party clones over the operator's own dirty work-in-progress. | Resolve the ranking-signal policy (escalated below), then proceed to Phase 1 collector with the corrected signal. |

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

- [ ] Define the `Focus 5` repo card contract in one place:
  observable result: a single writer owns fields for repo name, local path, VS Code link, newest PR, tree health, and last 3 activity items.
- [ ] Add a small device-local collector to [src/rebalance/ingest/index_ops.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/ingest/index_ops.py:1):
  observable result: collector is registered and callable through the existing orchestration pattern.
- [ ] Implement zero-config repo discovery for active local work:
  observable result: collector finds repos being actively worked on without any manual repo registration step.
- [ ] Bound discovery so zero-config does not become full-machine drag:
  observable result: collector avoids expensive or noisy whole-disk scans while still finding active repos automatically.
- [ ] Persist the roster snapshot and related stable summary fields:
  observable result: the app can explain why a repo is in the top 5 without recomputing the full ranking history on every render.
- [ ] Persist off-roster health summaries for warning-strip use:
  observable result: the app can surface hidden-attention warnings without live-probing every discovered repo on each request.
- [ ] Keep working tree health as a live read with freshness metadata:
  observable result: the app can answer "did I forget to commit or push?" using visibly fresh repo-health probes rather than stale stored status.
- [ ] Join local repo records to existing GitHub corpus data:
  observable result: each visible repo can show the newest remote PR title and number when available.
- [ ] Define enrichment fallback states in the repo card contract:
  observable result: the contract explicitly supports "no remote configured", "non-GitHub remote", and "GitHub repo not yet synced" without breaking the page.
- [ ] Capture last-activity signals for each repo:
  observable result: each repo can render 3 recent activity items in a stable, documented order based on local work first and remote context second.

## Phase 2 - Web View and Interaction Model

Goal: Add the new additive dashboard page and make the 5-column layout useful for fast context switching.

- [ ] Add a new `Focus 5` page to the local web server in [src/rebalance/web.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/web.py:1):
  observable result: the existing home page links to the new view and current screens remain unchanged.
- [ ] Decide whether the first implementation stays in single-file HTML rendering or extracts a small helper layer:
  observable result: the plan records an intentional rendering approach instead of drifting into ad hoc complexity.
- [ ] Build a responsive 5-column layout for desktop:
  observable result: five repo columns render left-to-right with readable labels and no ambiguity about what each section means.
- [ ] Add `Open in VS Code` affordance per repo:
  observable result: clicking the repo name or action opens the local repo root in VS Code.
- [ ] Render the newest remote PR per repo:
  observable result: title and PR number are visible and link to the remote artifact when present.
- [ ] Render current tree health per repo:
  observable result: user can immediately see dirty working tree, untracked files, and branch drift reminders.
- [ ] Render the last 3 activity items per repo:
  observable result: each column helps the user resume context without opening GitHub first.

## Phase 3 - Refresh Behavior and Safety Signals

Goal: Keep the focused view fresh without hiding risky repos.

- [ ] Implement 24-hour automatic roster refresh:
  observable result: the selected top 5 repos can roll forward based on device-local activity when the persisted roster TTL expires and the page is next visited, unless a scheduler-backed refresh is added explicitly.
- [ ] Add manual refresh control:
  observable result: user can force re-ranking and push inactive repos out of the grid immediately.
- [ ] Surface roster snapshot metadata:
  observable result: the page can explain when the current top-5 roster was computed and whether it came from lazy TTL refresh or manual refresh.
- [ ] Allow the roster to admit newly active repos on refresh:
  observable result: repos that become active after the current roster snapshot can enter the top 5 on manual refresh or TTL-based recompute.
- [ ] Refresh local tree health on page load:
  observable result: commit/push reminders are not stale for a full day.
- [ ] Keep roster freshness and repo-health freshness separate in the UI:
  observable result: user can tell whether the roster snapshot is older than the live git-health probe for a given repo.
- [ ] Add hidden-attention warning strip above the grid:
  observable result: repos outside the top 5 with dirty trees or unhealthy branch state still surface as summary warnings.
- [ ] Define stale-data behavior:
  observable result: the page clearly shows when local or remote repo data is old instead of silently presenting stale status.

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

- [ ] A new additive `Focus 5` route exists in the local web dashboard.
- [ ] The page shows exactly 5 recent repos in a left-to-right layout.
- [ ] Repo discovery requires zero manual config from the operator.
- [ ] Each repo column includes repo open action, newest remote PR, current tree health, and last 3 activity items.
- [ ] Manual refresh works and 24-hour automatic roster refresh is defined.
- [ ] Roster recompute semantics are explicit and based on persisted snapshot timestamps rather than an implicit server-side session.
- [ ] Local git data is sufficient to keep cards useful even when GitHub enrichment is unavailable.
- [ ] Hidden attention warnings reduce the risk of losing sight of unhealthy repos outside the top 5.
- [ ] Tests and logs are in place for the collector and the new page.
