---
gh_issue: 104
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/104
title: "Focus 5: off-roster warning gives no signal that a repo is uncommitted, not stale/broken"
owner: Noel
status: "Done 2026-07-06 — web slice (2026-07-03) + macOS Focus5Float desktop parity (2026-07-06, MARATHON-2026-07-06 Lane C) both shipped."
created: 2026-07-03
updated: 2026-07-06
branch: marathon/2026-07-06
doc_type: feedback
goal: >
  Give the Focus 5 off-roster "needs attention" strip a specific reason per repo (uncommitted/dirty
  vs. unpushed/ahead vs. other) instead of a generic label, on both the web view and the macOS
  Focus5Float desktop app.
---

## Status

| What was just completed | What's next |
|---|---|
| **Desktop parity shipped 2026-07-06** via `relay-xyz` (Producer=codex, Reviewer=agy, Approved r1; `relay-system/2026-07-06/gh104-desktop-parity.md`), driven in an isolated worktree/branch (`marathon/2026-07-06`). Finding: the server already put `warning_reason` on the `/focus-5.json` wire (`focus5_scan.py:1103`) — no Python change needed. Swift-side only: `warningReason: String?` added to `OffRosterWarning` (`Models.swift`), `OffRosterFooter` (`ContentView.swift`) now renders the server-computed reason, falling back to the old counts string only when absent. Independently re-verified: `swift build` green. Both web (2026-07-03) and desktop are now done. | Operator: visually verify the off-roster strip in the running Focus5Float app, then archive this doc to `3-COMPLETED`. |

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
      attention" — **web done** (2026-07-03), **desktop done** (2026-07-06).
- [x] Reason text distinguishes at minimum: uncommitted/dirty vs. unpushed/ahead
      vs. other — implemented in `off_roster_reason()`.
- [x] No change to top-5 ranking eligibility logic — confirmed, `rank_recent_activity`
      untouched.

## Verification (web slice)

- `pytest tests/test_focus5_scan.py tests/test_web_focus5.py` — 151 passed.
- Full `pytest tests/` — 1281 passed / 10 skipped, 0 failed.
- `rebalance doctor` — clean.
