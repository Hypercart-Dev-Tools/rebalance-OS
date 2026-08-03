# Marathon Phase hiqs-m2-p3
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M2-P3-TURN builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

---
title: "M2 p3 — search.py: the hybrid retrieval path"
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
# M2 p3 — search.py: the hybrid path

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m2-p2` is approved. |

**Canonical spec:** `HIQS-PROJECT.md` §6.1 (the path, verbatim, including both load-bearing
details), §6.2 (degrade rungs), §11 (~95 LOC).

## Build

`HiQS/hiqs/search.py` — one `search(query, limit=10)`:
1. FTS5 BM25, top 50.
2. numpy cosine, top 50, **filtered `WHERE model = <active>`**.
3. RRF fuse, k=60.
4. `cap_per_document(hits, max_chunks=2)` — **before** the slice.
5. `(RERANKER or identity)(query, hits)[:limit]`, with `RERANKER = None` in v1.

Steps 2 and 4 were both found in review and both have a written reason in §6.1. Read it.

## Acceptance

- **Model filter:** with 384-dim and 1024-dim vectors both resident, search returns correct results
  and does not raise. Removing the filter must make the test fail — demonstrate that, don't assume.
- **Per-document cap:** a query matching five headings of one note returns at most 2 of its chunks
  in the top-10, and other relevant notes are not starved.
- **Degrade rungs (§6.2, L8):** force the model unavailable and assert `status.search.mode` reports
  `fts_only` **and** a `search.degraded` event is written. Force the probe unreadable and assert
  `unknown`. A degraded mode is a state you can query, never something discovered weeks later.
- Exact-phrase queries resolve through the FTS leg; paraphrases resolve through the vector leg.
- Offline: fixture DB, stubbed encoder.

## Do not

- Do not add a hidden fallback chain. Every degrade is an explicit, queryable rung (§6.2).
- Do not implement a reranker. It is `None` in v1 with a numeric trigger in §14.


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/search.py,HiQS/tests/test_search.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M2-P3-TURN --agent agy --paths "phases/hiqs-m2-cont-p2p4--hiqs-m2-p3/RELAY.md,HiQS/hiqs/search.py,HiQS/tests/test_search.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M2-P3-TURN --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P3-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m2-cont-p2p4--hiqs-m2-p3/RELAY.md and HiQS/hiqs/search.py,HiQS/tests/test_search.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/search.py,HiQS/tests/test_search.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P3-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M2-P3-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m2-cont-p2p4--hiqs-m2-p3/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
