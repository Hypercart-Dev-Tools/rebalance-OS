---
gh_issue: 105
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/105
title: "Focus 5: single-row \"newest dirty repo\" banner above card #1"
status: Proposed (1-INBOX — not yet active)
created: 2026-07-03
doc_type: feedback
---

## Problem

Focus 5's headline ranking (`rank_recent_activity`) intentionally excludes
dirty/uncommitted-only repos from the top-5 (see GH-81,
`PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md`) — mixing dirty
state into the primary ranking previously buried genuinely active clean/pushed
work. Dirty repos currently only surface via the secondary "Dirty Five" mode
toggle or the generic off-roster "needs attention" strip (see GH-104 for making
that strip legible).

That split is correct for ranking, but it means an operator has to manually
switch views to notice they left uncommitted work in some other repo. There's
no lightweight nudge on the default view.

## Ask

Add a very slim, single-row "bonus" banner ABOVE the #1 card on the default
Focus 5 view — something like "BTW, recent work on [repo name] made it dirty"
— showing only the single most-recently-touched dirty repo (not in the current
top-5). Purpose: passive visibility into forgotten uncommitted work without
requiring a manual switch to Dirty Five.

Scope constraints:
- Does NOT change top-5 ranking eligibility/logic — informational only
- Shows at most one repo (the newest dirty one), not a list
- "Most recently touched" should rank by `my_local_commit_ts` (last local
  commit before it went dirty), not raw `.git/index` mtime — consistent with
  the codebase's existing anti-mtime-signal doctrine (`focus5_scan.py`)

## Feasibility (researched 2026-07-03, not yet built)

Verdict: **small**. No new probe or migration needed — `RepoSignals` already
carries `my_local_commit_ts`/`is_dirty`/`modified_count`/`untracked_count`/`ahead`,
and `summarize_focus5()` already builds `off_roster_warnings` with these fields
(just sorted by dirty/ahead, not recency — needs a filter+sort, not a new
query). Web rendering (`_focus5_body()`/`web.py`) has an existing single-row
banner pattern (`_f5_warning_strip()`) to copy. `/focus-5.json` already carries
the needed fields, unused by the current renderer.

The macOS app (Focus5Float) has an equivalent reusable single-row UI pattern
(`OffRosterFooter`/`TopBanner`), but its `OffRosterWarning` Swift struct doesn't
currently decode `my_local_commit_ts`, and the wire format is governed by a
"frozen" `CONTRACT.md` — adding the field means updating both in lockstep.
Process overhead, not technical difficulty.

Existing test harness: 135 tests across `test_focus5_scan.py`/`test_web_focus5.py`
to extend (~2-3 new tests estimated for the web-only slice). No Swift test
target exists for Focus5Float.

## Acceptance criteria

- Default `/focus-5` view shows a single-row banner above card #1 when at
  least one dirty, non-top-5 repo exists
- Banner names the single newest dirty repo, ranked by `my_local_commit_ts`
- No banner shown when no such repo exists (empty state — no regression to
  existing empty/zero-roster rendering)
- Top-5 ranking eligibility/order is unchanged
- (Web slice first; macOS app parity + `CONTRACT.md` update tracked as a
  follow-on, not required for v1)
