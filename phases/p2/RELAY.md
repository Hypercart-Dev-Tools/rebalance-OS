# Marathon Phase p2
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-P2-TURN builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

# Phase 2 — GH-104: off-roster warning reason badge (desktop + web)

## Scope lock

Edit ONLY `src/rebalance/ingest/focus5_scan.py`, `src/rebalance/web.py`,
`tests/test_focus5_scan.py`, `tests/test_web_focus5.py`. Do not touch `rank_recent_activity` or any
top-5 ranking/eligibility logic — that part is explicitly working as designed and out of scope. Do
not touch any relay/marathon scaffolding files (`phases/`, `phases-briefs/`) or dependency lock
files (`uv.lock`) — those are outside your allowlist and will fail the turn if touched. Do not run
the full test suite as your gate — the pre-advance check runs the two named test files.

## Problem

The off-roster "needs attention" warning strip (desktop Focus5Float + `/focus-5` web view) shows a
generic label for every excluded repo, regardless of *why* it's excluded. A repo with 4
staged-but-uncommitted files gets the same label as one that's merely unpushed or has some other
issue — the operator has to read source code to tell them apart.

`RepoSignals`/the off-roster warning data already carries `is_dirty`, `modified_count`,
`untracked_count`, and `ahead` (see the sibling GH-105 implementation,
`pick_newest_dirty_off_roster` in `focus5_scan.py`, for the field names and shapes already in use —
reuse those fields, do not invent new ones).

## Task

Off-roster warning entries should carry a short, specific reason badge derived from those existing
fields instead of a generic "needs attention" label — e.g. "uncommitted changes" (dirty),
"N ahead of origin" (unpushed), or a fallback for anything else.

## Acceptance criteria

- Off-roster warning UI (desktop Focus5Float + web `/focus-5`) shows a specific reason per repo, not
  just "needs attention".
- Reason text distinguishes at minimum: uncommitted/dirty vs. unpushed/ahead vs. other.
- No change to top-5 ranking eligibility logic.
- New/updated tests in both `tests/test_focus5_scan.py` and `tests/test_web_focus5.py` cover at
  least the dirty case and the unpushed/ahead case.

## Provenance

`PROJECT/1-INBOX/GH-104-FOCUS5-OFFROSTER-REASON.md`. Reuses the already-shipped GH-105 pattern
(`PROJECT/3-COMPLETED/GH-105-FOCUS5-DIRTY-BANNER.md`) for field names/shapes — do not duplicate that
logic, extend it.

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/ingest/focus5_scan.py,src/rebalance/web.py,tests/test_focus5_scan.py,tests/test_web_focus5.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-P2-TURN --agent agy --paths "phases/p2/RELAY.md,src/rebalance/ingest/focus5_scan.py,src/rebalance/web.py,tests/test_focus5_scan.py,tests/test_web_focus5.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-P2-TURN --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-P2-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/p2/RELAY.md and src/rebalance/ingest/focus5_scan.py,src/rebalance/web.py,tests/test_focus5_scan.py,tests/test_web_focus5.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/ingest/focus5_scan.py,src/rebalance/web.py,tests/test_focus5_scan.py,tests/test_web_focus5.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-P2-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-P2-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/p2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
