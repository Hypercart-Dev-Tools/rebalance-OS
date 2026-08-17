# Marathon Phase hiqs-m4-p2
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M4-P2-TURN builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

---
title: "M4 p2 — ask.py: attested context and the one Ranker"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M4 p2 — ask.py: attested context and the one Ranker

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m4-p1` is approved. |

**Canonical spec:** `HIQS-PROJECT.md` §7 (seams, `RankedAction`, the return shape verbatim), §7.1
(what the ranking is measured against), §3.1 Decision 5, §11 (~180 LOC), L1, L9.

This module carries the plan's namesake invariant. Read §7 in full.

## Build

`HiQS/hiqs/ask.py`:
- Context gather across sources → the §7 JSON shape, verbatim, including `synthesis: null`
  (`null`, not `""` — a host must be able to tell "no synthesizer" from "returned nothing").
- The deterministic `Ranker` (~40 LOC, §3.1 Decision 5). Terms in §7's stated weight order:
  **obligation** (`owed_by` set; `due` proximity when stated) → **activity** (recency of
  `activity_at`, never `updated_at`) → **source weight**.
- `RankedAction` carrying `author`, `owed_by`, `due`, **`source_age_s`**, **`source_status`**.
- **Exactly one ranking**, written by `refresh`, read by everyone.

## Acceptance

- **The namesake invariant, proved (L1):** a test asserts `ask()` and the persisted ranking are
  identical for the same DB state, and that no other module computes an ordering. The incumbent's
  core claim was two-thirds true because nothing enforced this; the test is the enforcement.
- **Determinism:** same candidates in, same order out. No clock-dependent or network-dependent
  tiebreak. **No LLM anywhere in the path** (Decision 5, L9).
- **Freshness rides on the item:** every `RankedAction` carries `source_age_s` and `source_status`
  from the source's last *successful* sync. A source that has not synced in three weeks cannot put
  a three-week-old item at rank 1 looking current — that is the incumbent's 0.57.0 shape. Unmeasured
  is `-1` / `unknown`, never a default that reads healthy.
- **Attestation is total:** every ranked item carries source, author, time, and link **as fields**.
  A receipt reachable only by parsing `evidence` prose fails this.
- Obligation ordering is testable: a due-soon assigned item outranks a newer unassigned one.

## Do not

- Do not call an LLM, add a synthesis step, or populate `synthesis`. The `Synthesizer` seam is
  `None` in v1 with a trigger in §14.
- Do not let any surface re-rank. If a consumer needs a different order, that is a §14 conversation.


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/ask.py,HiQS/tests/test_ask.py,HiQS/tests/test_contract.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M4-P2-TURN --agent agy --paths "phases/hiqs-m4-ask-mcp--hiqs-m4-p2/RELAY.md,HiQS/hiqs/ask.py,HiQS/tests/test_ask.py,HiQS/tests/test_contract.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M4-P2-TURN --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M4-P2-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m4-ask-mcp--hiqs-m4-p2/RELAY.md and HiQS/hiqs/ask.py,HiQS/tests/test_ask.py,HiQS/tests/test_contract.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/ask.py,HiQS/tests/test_ask.py,HiQS/tests/test_contract.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M4-P2-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M4-P2-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m4-ask-mcp--hiqs-m4-p2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
