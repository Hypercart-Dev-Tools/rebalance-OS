---
title: Claude Code Cloud jobs — ingest path
status: Inbox (Phase 0-1 done; wired DORMANT, observing before first-class)
gh_issue: 128
created: 2026-07-14
updated: 2026-07-14
branch: development
supersedes: []
synthesizes: []
goal: >
  Read Claude Code Cloud jobs (the ad-hoc "Web" sessions launched from claude.ai / iOS /
  web) and their status, so cloud work becomes an ingestible signal for HiQS. Phase 0
  (API + auth discovery) is done and a standalone POC ships; promotion into the collector
  registry is deferred pending a classify/kill-check decision.
---

# Claude Code Cloud jobs — ingest path (GH-128)

## Contents
- [Why](#why)
- [Phase 0 — discovery (DONE)](#phase-0--discovery-done)
- [API reference](#api-reference)
- [Phase 1 — promote to collector (DEFERRED)](#phase-1--promote-to-collector-deferred)
- [Phase 2 — run-level detail (OPTIONAL)](#phase-2--run-level-detail-optional)
- [Anti-goals](#anti-goals)

## Why
The VS Code "Claude Code > Web" tab lists ad-hoc **cloud coding sessions** (launched from
claude.ai, the iOS app, or the web). Their outcomes — which repo/branch, done vs still
running vs failed, a one-line recap — are a real activity signal that today lives nowhere in
the rebalance/HiQS index. This captures the ingest path so that work can be counted.

## Phase 0 — discovery (DONE)
- [x] Locate the backend surface behind the "Web" sessions list.
- [x] Establish auth (subscription OAuth token, keychain).
- [x] Map the status/outcome fields.
- [x] Prove the negative boundaries (what does NOT work) so we don't re-derive them.
- [x] Ship a standalone two-pass POC and verify it live.
  - **Live proof (2026-07-14):** 4 web sessions, all `review_ready`, 0 running, 0 failed —
    `HIQS pipeline signal unification`, `Collector freshness content validation`,
    `GitHub issue 52 bugs and dials`, `PDDA - review GH 37`.
- **Deliverable:** [`scripts/cc_cloud_jobs.py`](../../scripts/cc_cloud_jobs.py) — stdlib-only,
  `--day/--since/--all`, raw JSON → gitignored `temp/cc-cloud-jobs/`, then synthesized summary.

## API reference
| Surface | Endpoint | Auth | Reachable |
|---|---|---|---|
| **Web sessions** (this doc) | `GET api.anthropic.com/v1/code/sessions` (paginate `limit`+`cursor`→`next_cursor`) | subscription **OAuth bearer**, **no beta header** | ✅ standalone |
| Scheduled triggers/routines | `/v1/code/triggers` | OAuth, non-public host | only via Claude Code `RemoteTrigger` tool |
| Managed Agents | `/v1/deployment_runs`, `/v1/sessions` (beta `managed-agents-2026-04-01`) | **API-key only** | ❌ subscription token → `401` |

Per-session fields worth ingesting: `title`, `status_bucket` (`review_ready`/`working`/`failed`),
`worker_status` (`idle`/`running`), `created_at`, `last_event_at`, `config.model`,
`config.effort_level`, `config.origin` (`web_claude_ai`/`ios`),
`external_metadata.current_branches`, `external_metadata.post_turn_summary.{status_detail,needs_action}`.

Token source: macOS keychain `Claude Code-credentials` → `claudeAiOauth.accessToken`
(fallback `~/.claude/.credentials.json`). Refresh by running any `claude` command.

## Phase 1 — wire DORMANT + observe (DONE 2026-07-14)
Wired into the ranker's registry seam but ships **dormant** so quality is watched before it
influences the verdict — mirrors the figma / GH-124 dormant-ship precedent.
- [x] **Classified** as a `derived_scan` (external API read; `included_in_all=False`).
- [x] New canonical module `src/rebalance/ingest/claude_cloud.py` — fetch + normalize + PR
      enrichment (`gh`, fail-soft) + `grade()` + the `claude_cloud_candidates` provider.
- [x] Registered `Collector("claude_cloud", …, candidates=claude_cloud_candidates)` in
      `index_ops.py` (figma pattern). A `refresh_index(scope=["claude_cloud"])` run returns the
      quality grade as a health probe; no raw table yet (that is Phase 2).
- [x] **Signal enriched with PR merge status** — each session's head branch → PR state
      (merged / open / none) via `gh`; the verdict candidate becomes "Review PR #N" (open),
      "Cloud job FAILED" (failed), or "Triage" (done, no PR); merged = done, no candidate.
- [x] **Gated dormant** behind `claude_cloud_signal_enabled` (default False,
      `get_claude_cloud_config()`) — provider yields `[]` until the operator promotes it.
- [x] **Observation surface:** `utils/claude_cloud_daily_grade.py` upserts a data-quality grade
      block into `0. Today's Notes.md` (attribution / attestation / outcome / PR-linkage).
- [x] Observability + tests — 8 tests in `tests/test_claude_cloud.py` (normalize, grade, dormant
      vs enabled, fail-soft-never-raises).

## Phase 2 — promote to first-class (DEFERRED — gated on observation + kill-check)
- [ ] After watching the daily-note grade, run the **kill-check:** is cloud-session volume
      material and NOT redundant with `github_activity` / `claude-cloud` agent tags
      (`agent_tags.py`)? If trivial/redundant, keep dormant or drop.
- [ ] If it earns promotion: add a raw `claude_cloud_sessions` table (single writer), an
      `OperatorBundle.claude_cloud_activity` field populated in `assemble_day_bundle`, and switch
      the provider to read the bundle (no live network in the ranking path). Use the shared
      secret/token resolver. Then flip `claude_cloud_signal_enabled` true.
- [ ] Schedule the daily grader (launchd, like `git-pulse-daily-synthesis`) so the observation
      block refreshes without a manual run.

## Phase 3 — run-level detail (OPTIONAL)
- [ ] `/v1/code/sessions/{id}/teleport-events` gives per-turn events (N+1 — one call per
      session; paginate `cursor`/`next_cursor`, cap pages). Only build if the headline
      `post_turn_summary` proves insufficient for the signal.

## Anti-goals
- Not migrating onto the Managed Agents API (API-key-only; wrong plane for the subscription).
- Not persisting OAuth tokens anywhere — read live from the keychain each run.
- Not a parallel ranking path — if it earns promotion it registers as a collector and rides
  the one HiQS pipeline (GH-125), or it doesn't ship.
