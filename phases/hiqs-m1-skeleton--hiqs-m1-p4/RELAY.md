# Marathon Phase hiqs-m1-p4
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M1-P4-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

---
title: "M1 p4 — events.py: the observability spine"
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
# M1 p4 — events.py: the observability spine

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m1-p2` is approved; writes to the schema it creates. |

**Canonical spec:** `HIQS-PROJECT.md` §8 (verbatim table + the status payload shape), §6.2 (degrade
rungs), L4/L6/L8 (unknown is a first-class state).

This is the most load-bearing module in Phase 0. §8 exists **before any source does** because the
plan's entire answer to the incumbent's 68 versions is "health is derived from what actually
happened, never from process archaeology".

## Build

`HiQS/hiqs/events.py`:
- `log_event(kind, source, status, payload)` — **the sole writer** to `events`. Append-only.
  `status` constrained to `ok|warn|error|unknown`.
- `status()` — the aggregator. Per-source freshness + row counts + last error tail + search mode +
  search quality + ranking quality, derived from `events` and table state. Returns the §8 JSON
  shape; `search.quality` and `ranking.quality` report **`unknown`** when never measured.

## Acceptance

- A test asserts exactly one function writes `events` (grep-pinned, per the Phase 0 gate).
- Round trip: `log_event()` → row → `status()` reads it back. If the event is not written, the test
  fails — telemetry is a contract side-effect, not optional.
- `status()` on an empty DB returns valid structured JSON with `unknown` for both quality fields
  and for search mode. **Never a default that reads healthy.**
- An unreadable probe yields `unknown`, not `ok` and not an exception (L6).
- A `status` value outside the four-token vocabulary is rejected at the write boundary.

## Do not

- Do not read process state, exit codes, or `launchctl` anywhere. §8 is explicit: health comes from
  the events table. L6 is six months of this repo's history disagreeing with the alternative.
- Do not add a second writer, a convenience wrapper that writes, or an "internal" bypass.


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/events.py,HiQS/tests/test_events.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M1-P4-TURN --agent codex --paths "phases/hiqs-m1-skeleton--hiqs-m1-p4/RELAY.md,HiQS/hiqs/events.py,HiQS/tests/test_events.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M1-P4-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P4-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m1-skeleton--hiqs-m1-p4/RELAY.md and HiQS/hiqs/events.py,HiQS/tests/test_events.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/events.py,HiQS/tests/test_events.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P4-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M1-P4-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m1-skeleton--hiqs-m1-p4/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
