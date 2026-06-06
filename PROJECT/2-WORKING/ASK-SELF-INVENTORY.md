---
title: ask_self Index Inventory (Across All Repos)
status: in-progress
doc_type: project-plan
owner: Noel Saw
last_updated: 2026-06-05
surfaces:
  - mcp
  - dashboard
---

| Most recently completed phase | What's next |
|---|---|
| Phase 0 spike complete and validated on-device: an `ask_self` collector + `list_ask_self_repos` MCP tool discover every ask_self repo on this machine, read each index read-only, and bridge it to its GitHub `owner/repo`. Real run found 10 repos (5 built indexes, 4 matching the watched set). A real bug surfaced and was fixed: stale copied harnesses mislabeled repos, now corrected via the live git remote. | Phase 2 cross-device sync: export this inventory as a per-device snapshot into the pulse repo so any machine's dashboard can answer "which device holds a queryable brain for which project." First, Phase 1 hardening + the local-checkout-vs-repo granularity decision. |

## Table of Contents

1. [Phase 0 - Technical Spike](#phase-0---technical-spike)
2. [Phase 1 - Harden the Device-Local Collector](#phase-1---harden-the-device-local-collector)
3. [Phase 2 - Cross-Device Sync Plane](#phase-2---cross-device-sync-plane)
4. [Phase 3 - Dashboard Surface](#phase-3---dashboard-surface)
5. [Phase 4 - Testing and Rollout](#phase-4---testing-and-rollout)
6. [Definition of Done](#definition-of-done)

Decision lock-ins for this plan:
- The detection signal is the filesystem marker `ask_self/ask_self_harness.json`, not a registry that may omit committed/shared indexes.
- GitHub identity is derived most→least authoritative: built index `remote_url` → live `git remote get-url origin` → harness `github` block (last resort; frequently a stale template copy).
- The foreign ask_self index is opened read-only (`mode=ro`); the collector never writes to or migrates it.
- Rows are keyed by `(device_id, local_path)` so one GitHub repo with multiple local checkouts stays as distinct rows.
- The collector is opt-in (`included_in_all=False`) until cost on large trees is characterized.

## Phase 0 - Technical Spike

Goal: Prove that "query all repos with ask_self on this device" is feasible and bridges cleanly to the watched-repos set.

- [x] Confirm the detection signal for an ask_self repo:
  observable result: `ask_self/ask_self_harness.json` presence is necessary and sufficient; each built index also carries a `repo_metadata` row with remote, branch, counts, embed model, and last-ingest time.
- [x] Add a device-local collector through the existing orchestration pattern in [src/rebalance/ingest/index_ops.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/ingest/index_ops.py:1):
  observable result: an `ask_self` Collector is registered and runs via `refresh_index(scope=["ask_self"])`.
- [x] Read each index's metadata without mutating it:
  observable result: `repo_metadata` is read over a `mode=ro` connection in [src/rebalance/ingest/ask_self_scan.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/ingest/ask_self_scan.py:1).
- [x] Persist the inventory in a forward-only migration:
  observable result: [0002_ask_self_indexes.sql](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/src/rebalance/ingest/db/migrations/0002_ask_self_indexes.sql:1) creates `ask_self_indexes`; schema version advances to 2.
- [x] Bridge each local repo to its GitHub identity and join to the watched set:
  observable result: `list_ask_self_repos` returns each repo with a `watched` flag; on-device run showed 4 of 5 built indexes matching watched repos.
- [x] Validate on the real machine without touching the production DB:
  observable result: throwaway-DB run discovered 10 repos / 5 built indexes; read-only cross-reference against the real watched set confirmed the join.
- [x] Capture blockers/findings before Phase 1:
  observable result: stale-harness mislabeling found (e.g. `AI-DDTK-Fix-Iterate-Loop` claimed `WP-Code-Check`) and fixed via live-git-remote fallback.

## Phase 1 - Harden the Device-Local Collector

Goal: Make discovery dependable and cheap enough to consider running in the daily sweep.

- [ ] Characterize walk cost on large trees:
  observable result: documented timing for the default scan roots and a worst-case `$HOME` walk, with a decision on whether to flip `included_in_all` to True.
- [ ] Make zero-config discovery robust without whole-disk drag:
  observable result: depth bound and prune list are tuned so active repos are still found while heavy dirs (node_modules, .venv, build, vendor) are skipped.
- [ ] Decide ranking/granularity: local checkout vs GitHub repo:
  observable result: documented choice for how multiple checkouts of one repo (e.g. two `deckme` clones) are presented.
- [ ] Surface stale-harness identity mismatches as a signal, not a silent fix:
  observable result: rows flag when the harness `github` block disagrees with the live git remote.
- [ ] Handle missing/abnormal indexes honestly:
  observable result: harness-without-index repos are recorded `index_built=0` (not skipped), and unreadable indexes are reported rather than dropped.

## Phase 2 - Cross-Device Sync Plane

Goal: Let any machine see the ask_self inventory of every device.

- [ ] Export a per-device inventory snapshot into the pulse repo:
  observable result: `<sync_subdir>/ask_self/<device_id>.json` is written using the same snapshot/`latest.json` pattern as calendar/email.
- [ ] Consume snapshots back into the local DB:
  observable result: the collector reads other devices' snapshots so one machine's view spans all devices.
- [ ] Preserve device attribution in the joined view:
  observable result: `list_ask_self_repos` reports, per repo, which device(s) hold a built index.
- [ ] Keep the snapshot non-destructive and conflict-safe:
  observable result: commit/push reuses the existing RepairFSM path; concurrent device writes do not clobber each other.

## Phase 3 - Dashboard Surface

Goal: Make the inventory visible where the operator already looks.

- [ ] Add an `ask_self` summary block to the index-status surface:
  observable result: repo count, built-index count, and last-scanned time appear in `index_status` (already wired) and render in the dashboard.
- [ ] Show "indexed but not watched" and "watched but not indexed" gaps:
  observable result: the view highlights coverage gaps in both directions.
- [ ] Provide a per-repo drill-in:
  observable result: each repo shows local path, device, branch, head SHA, chunk/file counts, and embed model.

## Phase 4 - Testing and Rollout

Goal: Ship with confidence and operational visibility.

- [x] Unit-test the collector's pure and persistence paths:
  observable result: [tests/test_ask_self_scan.py](/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/tests/test_ask_self_scan.py:1) covers identity parsing, scanning/dedupe, upsert/unchanged/updated, unbuilt-index handling, and the watched join (10 tests passing).
- [ ] Add sync-plane tests for Phase 2:
  observable result: mocks cover snapshot export, multi-device merge, and conflict handling.
- [ ] Add timing and structured logs around the scan path:
  observable result: slow walks and unreadable indexes are diagnosable from logs.
- [ ] Decide and document the run cadence:
  observable result: opt-in vs all-scope decision recorded; if scheduled, the launchd/daily-sync wiring is noted here.
- [ ] Update this plan with rollout notes:
  observable result: completed phases and follow-ups are recorded here instead of drifting into chat.

## Definition of Done

- [ ] `list_ask_self_repos` returns every ask_self repo on the operator's devices, each bridged to `owner/repo` and flagged `watched`.
- [ ] Identity is derived from the live git remote, not the (possibly stale) harness.
- [ ] One GitHub repo with multiple local checkouts is represented without collapsing distinct work surfaces.
- [ ] The foreign ask_self index is never mutated by discovery.
- [ ] Cross-device snapshots let any machine see the full inventory with device attribution.
- [ ] Coverage gaps (indexed-not-watched, watched-not-indexed) are visible on the dashboard.
- [ ] Tests and logs are in place for the collector and the sync plane.
