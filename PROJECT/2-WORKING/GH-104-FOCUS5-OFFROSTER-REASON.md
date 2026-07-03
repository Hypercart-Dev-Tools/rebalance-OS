---
gh_issue: 104
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/104
title: "Focus 5: off-roster warning gives no signal that a repo is uncommitted, not stale/broken"
owner: Noel
status: "Active (2-WORKING) — web slice shipped 2026-07-03. macOS Focus5Float desktop parity NOT done."
created: 2026-07-03
updated: 2026-07-03
doc_type: feedback
goal: >
  Give the Focus 5 off-roster "needs attention" strip a specific reason per repo (uncommitted/dirty
  vs. unpushed/ahead vs. other) instead of a generic label, on both the web view and the macOS
  Focus5Float desktop app.
---

## Status

| What was just completed | What's next |
|---|---|
| **Web slice shipped 2026-07-03.** `off_roster_reason()` added to `src/rebalance/ingest/focus5_scan.py` — returns "uncommitted changes" (dirty), "N ahead of origin" (unpushed), or "needs attention" (fallback). Wired into `_f5_warning_strip()` in `web.py`. New `OffRosterReasonTests` (3 cases: dirty, ahead, fallback) + updated `test_web_focus5.py` assertions. `pytest tests/` 1281 passed / 10 skipped; `rebalance doctor` clean. Built via a live XYZ marathon relay turn (builder=agy, reviewer=codex) — the builder's turn committed cleanly; the reviewer's turn was separately escalated for an off-lane edit in its own isolated worktree (never touched the real repo), so the phase shows as "failed" in marathon's own bookkeeping despite the shipped code being correct and independently re-verified. | **macOS Focus5Float desktop parity is NOT done** — the issue's acceptance criteria explicitly cover "desktop + web," but this pass only touched Python/web files (confirmed: no Swift files in the commit). The off-roster strip in the Focus5Float app still shows the old generic label. Port `off_roster_reason()`'s logic (or an equivalent) into the Swift off-roster rendering, matching how GH-105's `DirtyBannerView` shipped desktop parity for its banner. |

## Problem

Ranking correctly excludes repos with no qualifying local commit from the top-5
(`rank_recent_activity` in `src/rebalance/ingest/focus5_scan.py` requires
`my_local_commit_ts is not None`). Uncommitted/dirty work is tracked separately
and surfaces only in the generic off-roster "needs attention" strip in both the
macOS Focus5Float app and the `/focus-5` web view.

Reproduced 2026-07-03: `sleuth-app` had 4 staged-but-uncommitted files (visible
in GitHub Desktop, commit button never clicked). It didn't appear in the Focus 5
top-5 on either the desktop app or web app, and repeated manual refreshes did not
surface it. The off-roster strip gave no indication *why* — "needs attention"
reads identically whether a repo is dirty-uncommitted, behind on push, or
something else entirely. Diagnosing this required reading the ranking/scan
source directly.

## Prior art

GH-81 (`PROJECT/3-COMPLETED/GH-81-FOCUS5-RANK-VECTOR.md`) added an
`explain_recency` strip + `basis_badge` for *why a repo ranked where it did*
within the top-5. This issue is the analogous gap for repos that don't make the
top-5 at all — the off-roster warning strip has no equivalent "why" surfaced to
the user.

## Ask (acceptance criteria)

- [x] Off-roster warning UI shows a specific reason per repo, not just "needs
      attention" — **web done**, **desktop not done**.
- [x] Reason text distinguishes at minimum: uncommitted/dirty vs. unpushed/ahead
      vs. other — implemented in `off_roster_reason()`.
- [x] No change to top-5 ranking eligibility logic — confirmed, `rank_recent_activity`
      untouched.

## Verification (web slice)

- `pytest tests/test_focus5_scan.py tests/test_web_focus5.py` — 151 passed.
- Full `pytest tests/` — 1281 passed / 10 skipped, 0 failed.
- `rebalance doctor` — clean.
