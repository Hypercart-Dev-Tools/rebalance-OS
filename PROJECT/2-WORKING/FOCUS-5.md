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
| Intake and concept capture completed; additive `Focus 5` view defined and anchored to the existing web dashboard. Product decisions now fixed: use local repo activity and require zero manual repo config. | Phase 0 technical spike: validate automatic local repo discovery, local git health reads, and top-5 ranking before UI implementation. |

## Table of Contents

1. [Phase 0 - Technical Spike](#phase-0---technical-spike)
2. [Phase 1 - Data Contract and Collector](#phase-1---data-contract-and-collector)
3. [Phase 2 - Web View and Interaction Model](#phase-2---web-view-and-interaction-model)
4. [Phase 3 - Refresh Behavior and Safety Signals](#phase-3---refresh-behavior-and-safety-signals)
5. [Phase 4 - Testing, Observability, and Rollout](#phase-4---testing-observability-and-rollout)
6. [Definition of Done](#definition-of-done)

Decision lock-ins for this plan:
- Local repo activity is the ranking signal, not remote GitHub activity.
- Repo scope must be zero-config for the operator.
- The roster should reflect repos actively being worked on at the moment the session starts, plus repos that become active during the session.

## Phase 0 - Technical Spike

Goal: Prove the critical assumptions in 1-2 hours before committing to the full build.

- [ ] Confirm the additive surface will live as a new route in [src/rebalance/web.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/web.py:1) without replacing any existing page.
- [ ] Validate the best source of local repo discovery:
  observable result: documented zero-config discovery path for active local repos, without requiring operator-maintained repo lists or scan-root setup.
- [ ] Validate local git health reads for candidate repos:
  observable result: per-repo sample output for branch, ahead/behind, modified count, untracked count, and clean/dirty verdict.
- [ ] Validate ranking logic for "most recently active on this device":
  observable result: documented ranking by local repo activity at session start and during the active session.
- [ ] Validate performance for the top-5 read path:
  observable result: one-page load can discover active repos and gather their data without operator setup or unacceptable UI delay.
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
- [ ] Persist enough local repo health data to power the view:
  observable result: the app can answer "did I forget to commit or push?" without recomputing everything on every render.
- [ ] Join local repo records to existing GitHub corpus data:
  observable result: each visible repo can show the newest remote PR title and number when available.
- [ ] Capture last-activity signals for each repo:
  observable result: each repo can render 3 recent activity items in a stable, documented order based on local work first and remote context second.

## Phase 2 - Web View and Interaction Model

Goal: Add the new additive dashboard page and make the 5-column layout useful for fast context switching.

- [ ] Add a new `Focus 5` page to the local web server in [src/rebalance/web.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/web.py:1):
  observable result: the existing home page links to the new view and current screens remain unchanged.
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
  observable result: the selected top 5 repos can roll forward based on device-local activity without manual intervention.
- [ ] Add manual refresh control:
  observable result: user can force re-ranking and push inactive repos out of the grid immediately.
- [ ] Capture session-start roster state:
  observable result: the page can explain which repos were considered active when the session began.
- [ ] Allow the roster to admit newly active repos during the session:
  observable result: repos that become active after page load can enter the top 5 on refresh instead of waiting for the next day.
- [ ] Refresh local tree health on page load:
  observable result: commit/push reminders are not stale for a full day.
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
- [ ] Session-start activity and in-session activity both influence which repos appear.
- [ ] Hidden attention warnings reduce the risk of losing sight of unhealthy repos outside the top 5.
- [ ] Tests and logs are in place for the collector and the new page.
