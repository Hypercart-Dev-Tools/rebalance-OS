# Marathon Phase hiqs-m4-p4
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M4-P4-TURN builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

---
title: "M4 p4 — eval_ranking.py: the runner, not the judgment set"
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
# M4 p4 — eval_ranking.py: the runner, NOT the judgment set

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m4-p3` is approved. **Operator checkpoint B follows M4** — OAuth consent + 20–30 real mornings. |

**Canonical spec:** `HIQS-PROJECT.md` §7.1 (protocol, metrics, four gates), §19.2 (public/private
split), §8.

## READ THIS FIRST — the hard boundary

You are building the **runner**. You must **not** author `eval_ranking.json`, and must not
generate, suggest, or seed snapshots or judgments. §7.1 requires the operator's own top-5 for real
mornings, recorded **before** seeing HiQS's output, across days that have not happened yet. A
model-authored judgment set measures the model's own persuasiveness. If the file is absent, report
loudly and exit non-zero.

## Build

`HiQS/tests/eval_ranking.py` — offline, fixture-backed:
- Metrics: **top-5 overlap**, **pairwise inversion rate**, **obligation coverage** (% of ranked
  items with `owed_by` or `due` populated), **staleness leakage** (% of top-5 whose
  `source_status != "ok"`).
- The four gates, implemented and unit-tested against synthetic scores:
  1. **Floor** — top-5 overlap >= 3/5 average. Fails → Phase 3 does not exit.
  2. **Beats recency** — >= 1 item over a recency-only baseline.
  3. **Obligation coverage** — >= 50%.
  4. **Staleness leakage** — zero top-5 items from an `error` source.
- Writes a `rank.evaluated` event; the recorded SHA spans the committed file **and** the sidecar.
- **Public/private split (§19.2):** committed file carries opaque ids and pairwise judgments; the
  candidate text lives in a gitignored sidecar. Sidecar absent → loud `unknown`, never a silently
  scored subset.

## Acceptance

- Gate arithmetic unit-tested at the boundaries, including the case a review caught: recency at 1/5
  and ranker at 2/5 **passes** gate 2 and **fails** gate 1. That interaction is why the floor exists.
- Reproducible across runs on the same inputs.
- `status.ranking.quality` reads from the written event, not a constant (L22).
- A failing gate blocks; there is **no override flag in the code**. An operator override is a
  recorded decision in the CHANGELOG plus a tenet reword, not a command-line switch.

## Do not

- Do not author snapshots or judgments, even as a fixture that could be mistaken for real. Use
  obviously synthetic ids.
- Do not implement a "close enough" or partial-credit mode.


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/tests/eval_ranking.py,HiQS/tests/test_eval_ranking.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M4-P4-TURN --agent agy --paths "phases/hiqs-m4-ask-mcp--hiqs-m4-p4/RELAY.md,HiQS/tests/eval_ranking.py,HiQS/tests/test_eval_ranking.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M4-P4-TURN --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M4-P4-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m4-ask-mcp--hiqs-m4-p4/RELAY.md and HiQS/tests/eval_ranking.py,HiQS/tests/test_eval_ranking.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/tests/eval_ranking.py,HiQS/tests/test_eval_ranking.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M4-P4-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M4-P4-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m4-ask-mcp--hiqs-m4-p4/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
