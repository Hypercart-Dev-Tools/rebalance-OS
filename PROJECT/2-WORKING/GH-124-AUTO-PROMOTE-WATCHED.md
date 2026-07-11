---
gh_issue: 124
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/124
title: Auto-promote watched repos to active projects
status: "Active (2-WORKING)"
owner: Noel
created: 2026-07-10
updated: 2026-07-10
doc_type: project
goal: >
  A repo the operator has actually committed to should become a confirmed active project
  automatically after a small commit threshold, with no manual "promote" step — surfaced
  non-silently (auth-log alert + repo-pie top item), never overwriting curated registry state.
related:
  - PROJECT/4-MISC/DECOUPLE-OBSIDIAN-AS-SOT.md
  - PROJECT/3-COMPLETED/CLIENT-AUTO-DISCOVERY.md
  - PROJECT/3-COMPLETED/WATCHLIST-COVERAGE-GUARD.md
  - PROJECT/2-WORKING/REPO-HEALTH-AXES.md
  - PROJECT/3-COMPLETED/GH-81-FOCUS5-RANK-VECTOR.md
effort: 3
complexity: 3
risk: 2
phases: 3
---

# GH-124 — Auto-promote watched repos to active projects

## Status

| What was just completed | What's next |
|---|---|
| **Phase 2 shipped:** `log_project_auto_promoted()` + `project_auto_promoted` auth-log badge; `render_repo_pie()` "New repo added" top-item annotation backed by `fetch_recent_auto_promotion()`. 6 new tests green, full suite zero-regression, doctor clean, markup-level litmus confirmed (no browser available on this machine for a visual screenshot). | Phase 3 — wire into `_refresh_github` + docs. |

## Table of contents

- [Problem](#problem)
- [What already exists](#what-already-exists)
- [Non-goals](#non-goals)
- [Design decisions (Discuss)](#design-decisions-discuss)
- [Phase 1 — Detection & write path](#phase-1--detection--write-path)
- [Phase 2 — Non-silent surfacing](#phase-2--non-silent-surfacing)
- [Phase 3 — Wiring, config, docs](#phase-3--wiring-config-docs)
- [Open questions](#open-questions)

## Problem

Most users will not remember to manually register new repos into Rebalance. A new repo should
become an active project automatically once the owner/operator has pushed 2-3 commits to it — no
manual "promote" step required. Today the only write path into `project_registry` is the onboarding
`/welcome` flow's one-time human-gated "Review & promote" step (`confirm_projects()`,
`write_semantics="confirmation_gated"` per `src/rebalance/ingest/lifecycle.py:110-120`). Anything
discovered after onboarding sits in the "watched" bucket (`list_watched_repos()`) indefinitely.

**Exception:** forks/stars alone are not activity and must not trigger promotion — only actual
commits pushed by the operator (fork included) count toward the threshold.

**Not silent:** confirmed in-thread with the operator — promotion must surface via (1) a Rebalance
Log Alert on the web app, and (2) a top item on the repo-activity donut ("Circular Repo graph").

## What already exists

- `src/rebalance/ingest/project_inference.py` — `infer_project_registry()` / `sync_inferred_project_registry()`
  already write `machine_owned` rows into `project_registry`, partitioned so curated rows are never
  clobbered (`_partition_writable_rows`). CLI-only (`rebalance ingest infer-project-registry`), not
  wired into `refresh_index()`, no MCP tool. Trigger is "any GitHub activity or ≥2 calendar events" —
  not a commit count, not operator-identity-scoped.
- `PROJECT/4-MISC/DECOUPLE-OBSIDIAN-AS-SOT.md` (2026-05-31, still "In Review") — prior attempt at the
  same problem ("every repo you push to is visible by default"); never closed.
- `PROJECT/3-COMPLETED/CLIENT-AUTO-DISCOVERY.md` (#100) — adjacent (client labeling on already-
  confirmed projects), not repo→project promotion.
- `PROJECT/3-COMPLETED/WATCHLIST-COVERAGE-GUARD.md` (#82) — the inverse alarm (silent removal from
  watched); the `auth_log.log_event` + `_EVENT_BADGE` pattern it uses is the reuse target for Phase 2.
- `PROJECT/2-WORKING/REPO-HEALTH-AXES.md` — open, unresolved question on watched-vs-registry
  filtering.
- `PROJECT/3-COMPLETED/GH-81-FOCUS5-RANK-VECTOR.md` — **cautionary precedent.** GH-81 found that
  filtering by GitHub-author *email* silently drops repos when a different device/email pushed the
  commit, and fixed it by ranking on local-commit reflog recency instead. Any "operator pushed N
  commits" check in this feature risks the exact same failure mode if it keys strictly on author
  email; see [Phase 1 Discuss](#phase-1--detection--write-path).

## Non-goals

- No change to the onboarding `/welcome` "Review & promote" flow — this is a parallel, later-arriving
  path, not a replacement.
- No UI for reviewing/undoing an auto-promotion in this plan (an operator can still hand-edit or
  `github_ignored_repos` a mistaken promotion; a dedicated undo affordance is a follow-up if it proves
  needed).
- No change to `infer_project_registry`'s existing activity/calendar trigger — this adds a second,
  commit-count-gated trigger alongside it, not a replacement.

## Design decisions (Discuss)

- Reuse the existing `machine_owned` write semantics (`project_inference.py`) rather than inventing a
  second registry-write contract — one write-ownership model, not two. **Why:** `lifecycle.py`
  already documents `machine_owned` as never clobbering curated rows; a second contract would
  duplicate that guarantee and risk drifting from it.
- Gate on commit *count*, not raw activity/calendar signal — a repo with one drive-by commit should
  not out-rank a repo with zero. **Why:** matches the literal ask ("2-3 commits"), and is a clearer,
  more explainable signal to surface in an alert than a fuzzy activity score.
- Non-silent by default (auth-log + repo-pie), never a hard block — matches this repo's flag-don't-
  block calibration principle used throughout PDDA and `WATCHLIST-COVERAGE-GUARD`.

## Phase 1 — Detection & write path

**Discuss:**
- **Inline identity-resolution contract** (self-contained). **Build-time refinement (superseding the
  Codex-approved GH-81-ladder draft):** the primary signal is simpler and more grounded than reusing
  GH-81's local-reflog ladder — `github_commits.author_login` (GitHub's own resolved identity per
  commit, populated for every synced repo regardless of local clone presence) matched against
  `github_login` via the exact `_author_filter_sql()` + `CLOUD_AGENT_AUTHORS` primitive already used by
  `pulse.py:56-59` for "commits authored by me." Reusing it (not reinventing a second identity filter)
  also means cloud-agent-authored commits (Claude Code / Codex cloud sessions acting on the operator's
  behalf — the same bots `pulse.py` already counts as "mine") correctly count toward promotion. A
  commit only counts when `_author_filter_sql("author_login")` matches; GH-81's local-reflog signal
  (`focus5_repo_signals.my_local_commit_ts`) is **not required** — most watched repos have no local
  clone under `focus5_scan_roots` at all, so gating on it would starve the common case. (GH-81's third
  rung, `any_commit`, is irrelevant here — it was a ranking-only fallback, never an identity match.)
- Commit threshold and default on/off are config, not a hardcoded constant, following the
  `git_pulse_clio_enabled` naming precedent in `src/rebalance/ingest/config.py`.
- Out of scope for this phase: the alert/dashboard surfacing (Phase 2) and scheduling wiring
  (Phase 3) — this phase only proves the write path fires correctly on a synthetic commit-count
  fixture.

**Acceptance criteria (Definition of Done):**
- A watched, non-ignored repo with ≥3 distinct-SHA operator commits (all-time, not a rolling window)
  and zero prior `project_registry` row (curated or machine-owned) gets exactly one machine-owned row
  written on the next eligible refresh — deterministically, so two runs against the same DB state
  produce the same outcome.
- A repo in `github_ignored_repos` never promotes, full stop, regardless of commit count.
- A curated row is never created, updated, or deleted by this path (reuses the existing
  `_partition_writable_rows` guarantee).
- Re-running against unchanged state does not duplicate or re-promote a row that already exists.

Work:
- Add `auto_promote_enabled` (bool, default `true`) and `auto_promote_commit_threshold` (int, default
  `3`) to `src/rebalance/ingest/config.py`, alongside the existing config accessor pattern.
- **Counting contract:** count *distinct full-SHA* commits (not short-SHA — see the canonical-identity
  lesson in `PROJECT/1-INBOX/P1-SQLITE.md:147`, which explicitly warns short SHAs collide across a
  repo's history) authored by the operator identity, **cumulative all-time** for that repo, not a
  rolling window — this is "has the operator meaningfully started this repo," not a recency signal
  (recency is `list_watched_repos`' job already).
- **Identity resolution:** apply `pulse._author_filter_sql("author_login")` against `github_commits`,
  matching `github_login` and `CLOUD_AGENT_AUTHORS` (import/reuse from `pulse.py`, do not duplicate).
- **Row shape / provenance contract:** reuse `_seed_to_project_row`'s exact shape
  (`src/rebalance/ingest/project_inference.py:610-655`) — `status="active"`, `repos=[repo_full_name]`,
  `tags=["auto-promoted", "source:github"]`, `custom_fields.provenance="auto_promoted"`,
  `custom_fields.inference={"generated_by": "commit_threshold_v1", "commit_count": N,
  "threshold": auto_promote_commit_threshold, "promoted_at": <iso ts>}`. Generalize
  `_is_inference_owned()` (`project_inference.py:65-71`) to recognize **both**
  `INFERENCE_GENERATED_BY` and `"commit_threshold_v1"` as machine-owned, so the existing
  curated-collision-skip and stale-row-cleanup logic apply uniformly to auto-promoted rows without a
  parallel implementation.
- **Suppression precedence (durable vs. not):** `github_ignored_repos` is the only durable suppression
  — checked at eval time, always wins. A manually **deleted** machine-owned row is explicitly **not**
  durable suppression: like existing inferred rows (`_delete_stale_inferred_rows`), an auto-promoted
  row is recreated on the next pass if the repo still qualifies. An operator who wants a promotion to
  stick as removed must add the repo to `github_ignored_repos`, not just delete the row — document this
  plainly in the config comment and `ARCHITECTURE.md` so it isn't a surprise.
- New function in `project_inference.py` (or a sibling module if the identity-resolution logic grows
  large): resolve per-repo operator commit counts, filter to repos at/above threshold that are watched
  but **not yet** in `project_registry` (curated or machine-owned), and exclude forks/repos with zero
  operator-authored commits (starring/forking alone is not a commit).
- Write via the existing `machine_owned` partition/write path — no new registry write contract.

**Phase 1 QA gate:**
- [x] Unit tests: threshold hit / no-hit, fork-with-no-commits excluded, cloud-agent commits counted,
  `github_ignored_repos` excluded, curated row never touched, idempotent re-run, disabled-config no-op,
  no-`github_login` no-op — `tests/test_auto_promote.py`, 9/9 passing.
- [x] `pytest tests/` green (run via `python -m unittest discover`, pytest not installed in this venv).
- [x] `rebalance doctor` clean.
- **Verification summary:** `python -m unittest tests.test_auto_promote` → 9/9 passed. Full suite
  (`python -m unittest discover -s tests`) → identical 16 pre-existing failures with and without this
  change (verified by diffing failing-test names before/after via `git stash`) — zero regressions.
  `rebalance doctor` → "Health check passed with warnings" (all warnings pre-existing/environmental:
  Sleuth publisher staleness, Figma no file keys, Gmail OAuth scope, stale pulse collector, launchd
  exit codes — none related to this change). Unmet: none.

## Phase 2 — Non-silent surfacing

**Discuss:**
- Reuse `auth_log.log_event(source, event, detail)` (`src/rebalance/ingest/auth_log.py:129`) +
  `_EVENT_BADGE` (`src/rebalance/web.py:200`) exactly as `WATCHLIST-COVERAGE-GUARD` did for
  `watched_repos_reduced` — one more badge-mapped event, not a new alert subsystem.
- The repo-pie donut is `render_repo_pie()` in `scripts/pulse_web.py:884`, backed by a
  `#repo-pie-data` JSON payload consumed by Chart.js (`initRepoPie()` around line 2513). The "top
  item" annotation is a new field on that payload (e.g. `newly_added: {repo, promoted_at}`), rendered
  as a banner line in the card header — matching the "New repo added: CLIO" callout already mocked in
  the operator's screenshot.
- Out of scope: redesigning the chart itself or adding new chart types — this is one additive
  annotation on an existing card.

Work:
- Add `project_auto_promoted` to `_EVENT_BADGE` (info/ok-styled badge, e.g. `"✓ project auto-added"`).
- Call `auth_log.log_event("registry", "project_auto_promoted", {"repo": ..., "commit_count": ...,
  "threshold": ...})` at the point Phase 1's write path fires.
- Extend `render_repo_pie()`'s payload with the most-recent auto-promotion inside the display window
  (if any) and render a header banner line, styled like the operator's screenshot mock.

**Phase 2 QA gate:**
- [x] Render test asserting the `project_auto_promoted` badge renders on `/auth-log`
  (`tests/test_web_auth_log.py::test_project_auto_promoted_renders_ok_badge`, calls the real
  `auth_log_page()` route function).
- [x] Render/unit test asserting the repo-pie banner appears when a fresh promotion exists in-window,
  and is absent otherwise (`tests/test_repo_pie_auto_promote.py`, 3 tests).
- [x] `pytest tests/` green.
- [x] `rebalance doctor` clean.
- [x] Operator litmus (markup-level, not visual — see note): copied the production DB to a scratch
  path, seeded a synthetic `commit_threshold_v1` row, ran the real `scripts/pulse_web.py` page
  generator against it, and grepped the output for the badge — confirmed `New repo added:
  litmus-demo-repo` rendered with the correct CSS class in the real full-page HTML (not just the
  isolated unit test). Scratch DB/HTML deleted after.
- **Verification summary:** `python -m unittest tests.test_repo_pie_auto_promote
  tests.test_web_auth_log` → 6/6 passed. Full suite → identical 16 pre-existing failures (zero
  regressions, verified by diff). `rebalance doctor` → clean, no ERROR/FAIL lines. **Unmet: no visual
  browser screenshot** — this machine has no Chrome/Chromium/headless-browser binary installed, so the
  litmus above is markup-level (real render function, real seeded DB row, grepped output) rather than
  a rendered screenshot. If a visual check matters before shipping, it needs a machine with a browser
  installed.

## Phase 3 — Wiring, config, docs

**Discuss:**
- **Decided:** the owning path is `_refresh_github` in `src/rebalance/ingest/index_ops.py` — it calls
  the Phase 1 auto-promotion helper immediately after the existing `WATCHLIST-COVERAGE-GUARD`
  snapshot/diff step, so it rides `refresh_index(scope=["github"])` and `daily_sync.sh`'s existing
  cadence with zero new scheduling surface. Not left open for later re-evaluation; if operating
  experience later shows this cadence is wrong, that is a new issue against the shipped behavior, not
  a re-open of this plan.

Work:
- Wire Phase 1's detection+write into `_refresh_github` (`index_ops.py`), immediately after the
  watchlist-guard step, per the Discuss decision above.
- Update `ARCHITECTURE.md` (new config keys, the extended `machine_owned` trigger).
- Update `AGENTS.md` if a new MCP-visible behavior needs documenting for future agents.
- `CHANGELOG.md` entry.

**Phase 3 QA gate:**
- [ ] Full `pytest tests/` green.
- [ ] `rebalance doctor` clean.
- [ ] `utils/pdda/pdda.sh run` clean.
- [ ] Live end-to-end litmus: a real watched repo crosses the threshold, gets promoted, shows up in
  `list_projects()`, and both Phase 2 surfaces fire — on the live dashboard, not just tests.
- **Verification summary:** record actual command output + litmus result here before closing.

## Open questions

1. Default commit threshold: 2 or 3? (Problem statement says "2-3" — defaulting to 3 above as the
   more conservative choice; revisit after Phase 1 operator feedback.)
2. Should `auto_promote_enabled` default `true` (magical-by-default, matches the UX goal) or `false`
   (safer opt-in, matches the existing `git_pulse_clio_enabled` off-by-default precedent)? Recorded as
   `true` above pending Codex review — flag if this should flip.
3. Undo/demote affordance — needed now, or defer until a real false-positive happens?
