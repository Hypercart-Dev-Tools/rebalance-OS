---
gh_issue: 104
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/104
title: "Focus 5: off-roster warning gives no signal that a repo is uncommitted, not stale/broken"
status: Proposed (1-INBOX — not yet active)
created: 2026-07-03
doc_type: feedback
---

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

- Off-roster warning UI (desktop + web) shows a specific reason per repo, not
  just "needs attention"
- Reason text distinguishes at minimum: uncommitted/dirty vs. unpushed/ahead vs.
  other
- No change to top-5 ranking eligibility logic (that part is working as
  designed)
