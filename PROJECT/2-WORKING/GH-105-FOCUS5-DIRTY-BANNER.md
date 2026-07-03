---
title: "Focus 5: single-row \"newest dirty repo\" banner above card #1"
gh_issue: 105
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/105"
status: "Active (2-WORKING) — Phases 1 & 2 shipped 2026-07-03; awaiting operator litmus"
created: 2026-07-03
updated: 2026-07-03
owner: noel@neochro.me
branch: feature/gh-105-focus5-dirty-banner
doc_type: bugfix
rollout_rule: each phase leaves the system runnable (`pytest tests/` green, `rebalance doctor` clean); no change to top-5 ranking eligibility/order
goal: >
  Give the operator passive visibility into the single most-recently-touched dirty
  repo directly on the default Focus 5 view, without requiring a manual switch to
  Dirty Five, and without altering the deliberately commit-recency-only top-5
  ranking (GH-81).
---

## Status

| What was just completed | What's next |
|---|---|
| **Phases 1 & 2 shipped (2026-07-03).** P1: `pick_newest_dirty_off_roster()` in `focus5_scan.py`; `summarize_focus5()` returns `dirty_banner` (gated to the default `recent_activity` view, `None` on the transient Dirty Five rerank — mirrors the existing `rank_cutoff_ts` gate); `_f5_dirty_banner()` renders it above the card grid in `web.py`. 9 new tests; full suite green (1271 passed, 0 failed, 10 skipped); `rebalance doctor` clean. P2: `CONTRACT.md` amended (additive), `Models.swift` + new `DirtyBannerView` in `ContentView.swift`; `swift build` (debug + release) green, all 4 self-test flavors OK; installed to `/Applications` via `make-app.sh`. | **Operator litmus**: quit + relaunch "Focus 5 Float" (was running during install) and confirm the banner renders against a live dirty repo, then move to `3-COMPLETED`. |

## Table of Contents

- [Problem](#problem)
- [Scope](#scope)
- [Phase 1 — Backend + Web Rendering](#phase-1--backend--web-rendering)
- [Phase 2 — macOS Focus5Float Parity](#phase-2--macos-focus5float-parity)

## Problem

See GH-105 / GH-104 / GH-81 for full history. Short version: Focus 5's top-5
ranking correctly excludes dirty-only repos (no regression there), but an
operator currently has no passive way to notice forgotten uncommitted work
without manually switching to the Dirty Five view.

## Scope

- Single-row banner above card #1 on the default `/focus-5` view (and the
  macOS Focus5Float card stack), naming only the single most-recently-touched
  dirty repo that isn't already in the top-5.
- "Most recently touched" = `my_local_commit_ts` (last local commit before it
  went dirty) — NOT `.git/index` mtime (explicitly banned as a recency signal
  elsewhere in this codebase; clone/fetch pollutes it).
- No banner when no qualifying dirty repo exists.
- Does not change `rank_recent_activity` eligibility/ordering.

## Phase 1 — Backend + Web Rendering

- [x] `focus5_scan.py`: helper to pick the single newest dirty off-roster repo
      (filter `is_dirty=1` + not in current top-5, sort by `my_local_commit_ts`
      desc, take first) from data `summarize_focus5()` already computes.
- [x] `web.py`: `_f5_dirty_banner()` render helper (single-row, same shape as
      `_f5_warning_strip()`), spliced into `_focus5_body()` above the card grid
      — only for the default `recent_activity` view, not the Dirty Five view.
- [x] Tests: ranking-helper unit tests (newest-dirty selection + empty/no-dirty/
      never-committed cases), seeded-signal integration tests through
      `summarize_focus5()`, web-rendering tests (banner present/absent/escaped),
      extending `test_focus5_scan.py` / `test_web_focus5.py`.

**QA — Phase 1**
- [x] `pytest tests/` green (1271 passed, 0 failed, 10 skipped)
- [x] `rebalance doctor` clean (pre-existing, unrelated warnings only)
- [x] Top-5 ranking output unchanged for a fixture with no dirty repos
- [x] Banner absent when no dirty off-roster repo exists (no empty-state regression)

## Phase 2 — macOS Focus5Float Parity

- [x] `macOS/Apps/Focus5Float/CONTRACT.md`: added top-level `dirty_banner`
      (`OffRosterWarning` shape or null) and `OffRosterWarning.my_local_commit_ts`
      to the documented wire schema, with an amendment note (additive,
      backward-compatible — both optional).
- [x] `Models.swift`: `Focus5Response.dirtyBanner: OffRosterWarning?`;
      `OffRosterWarning.myLocalCommitTs: Int?`. `Focus5Model` carries
      `dirtyBanner` through `apply()`.
- [x] SwiftUI: new `DirtyBannerView` (single-row, accent-tinted — deliberately
      lighter than `OffRosterFooter`'s warning tint), rendered above the roster
      `ForEach` in `ContentView.swift`'s `.loaded` case. No client-side view
      check needed — `dirtyBanner` is already `nil` server-side on the Dirty
      Five rerank.
- [x] `swift build` green (release + debug); `FOCUS5_SELFTEST` /
      `FOCUS5_CACHETEST` / `FOCUS5_VSCODETEST` / `FOCUS5_HEALTHTEST` all OK.
      Bundled `sample-focus5.json` fixture updated with a `dirty_banner` entry
      so the self-test and previews demonstrate the new row.
- [x] Installed to `/Applications` via `make-app.sh` (2026-07-03). The app was
      running at install time (pid held the old bundle in memory) — left
      running rather than force-killed; picks up the change on next relaunch.
