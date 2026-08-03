# Marathon Phase hiqs-m4-p3
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M4-P3-TURN builder=agy reviewer=codex round-cap=5 -->

## Phase Brief

---
title: "M4 p3 — mcp_server.py: four thin tools"
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
# M4 p3 — mcp_server.py: four thin tools

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m4-p2` is approved. |

**Canonical spec:** `HIQS-PROJECT.md` §10 (MCP is the product surface), §7 (the payload), §11
(~120 LOC), Phase 3 gate.

## Build

`HiQS/hiqs/mcp_server.py` — standard JSON-RPC MCP exposing exactly four tools:
`refresh` · `status` · `search` · `ask`. All structured JSON, all attested.

**Thin wrappers, zero logic.** Marshalling only.

## Acceptance

- A test asserts the module contains no ranking, scoring, filtering, or ordering logic — it calls
  `ask.py` and returns what it gets.
- **Parity:** for the same DB state, the MCP `ask` tool and `ask()` return byte-identical rankings.
  A behavioural difference between CLI and MCP for one query is a defect, not a nuance.
- Tool descriptions state the RANKED tenet in whatever wording §7.1's gates currently justify —
  if the obligation-coverage gate has not passed, the description says "ordered by recency and
  source weight". The claim in the tool description is a claim like any other (§2).
- Errors surface as structured MCP errors, never a silent empty result.

## Do not

- Do not add a fifth tool. Decision 4 counts them; §18.3's SMALL invariant makes a fifth a recorded
  decision.
- Do not reimplement anything from `ask.py`, `search.py`, or `events.py`.


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/mcp_server.py,HiQS/tests/test_mcp.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M4-P3-TURN --agent agy --paths "phases/hiqs-m4-ask-mcp--hiqs-m4-p3/RELAY.md,HiQS/hiqs/mcp_server.py,HiQS/tests/test_mcp.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M4-P3-TURN --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M4-P3-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m4-ask-mcp--hiqs-m4-p3/RELAY.md and HiQS/hiqs/mcp_server.py,HiQS/tests/test_mcp.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/mcp_server.py,HiQS/tests/test_mcp.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M4-P3-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M4-P3-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m4-ask-mcp--hiqs-m4-p3/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
