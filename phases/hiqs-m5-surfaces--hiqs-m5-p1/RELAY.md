# Marathon Phase hiqs-m5-p1
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M5-P1-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

---
title: "M5 p1 — web.py: one page, one port, zero JS"
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
# M5 p1 — web.py: one page

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after **operator checkpoint B**. Fire M5 with `--builder codex`. |

**Canonical spec:** `HIQS-PROJECT.md` §10, §7 (the ranking it renders), §11 (~150 LOC), L10.

## Build

`HiQS/hiqs/web.py` — `hiqs serve` → **one** localhost page on `127.0.0.1:8790`, stdlib
`http.server`, **zero JS**, server-rendered, meta-refresh:
- next-actions ranking with receipts at top (source, author, time, link — all four, as fields)
- per-source health strip
- last-sync line
- search mode + last measured search quality + last measured ranking quality
- a `/refresh` link that triggers a sync and redirects back — the entire interactive layer

## Acceptance

- **One server, one port, one route table (L10).** A test greps for a second `http.server` handler
  and finds none. The incumbent's `pulse_server.py`/`web.py` route drift bit twice and is *still
  live there* — this is the lesson HiQS adopts from an open defect, not a closed one.
- **The page renders the persisted ranking; it does not re-rank.** Asserted, not assumed (L1).
- **Loopback only:** binds `127.0.0.1` and refuses a non-loopback `Host`/origin. Verified by an
  actual request that fails, not by reading the bind address.
- Unmeasured quality renders as `unknown`, never blank and never a default that reads healthy.
- Zero JavaScript in the served HTML — asserted by a test.

## Do not

- Do not add a second server, a second port, an API surface, or a websocket.
- Do not add client-side JS "just for the refresh". Meta-refresh plus a link is the design.


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/web.py,HiQS/tests/test_web.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M5-P1-TURN --agent codex --paths "phases/hiqs-m5-surfaces--hiqs-m5-p1/RELAY.md,HiQS/hiqs/web.py,HiQS/tests/test_web.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M5-P1-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M5-P1-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m5-surfaces--hiqs-m5-p1/RELAY.md and HiQS/hiqs/web.py,HiQS/tests/test_web.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/web.py,HiQS/tests/test_web.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M5-P1-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M5-P1-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m5-surfaces--hiqs-m5-p1/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
