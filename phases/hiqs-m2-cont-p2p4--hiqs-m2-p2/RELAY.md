# Marathon Phase hiqs-m2-p2
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M2-P2-TURN-2 builder=agy reviewer=codex round-cap=11 -->

## Phase Brief

---
title: "M2 p2 — docs_index.py: projection and delta embedding"
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
# M2 p2 — docs_index.py: projection and delta embedding

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m2-p1` is approved. |

**Canonical spec:** `HIQS-PROJECT.md` §6.1, §9 (`docs_vec` PK), §5 rule 2, §3.1 (Decision 1 —
`sentence-transformers`, torch backend), §11 (~130 LOC).

## Build

`HiQS/hiqs/docs_index.py`:
- raw → `docs` projection. **The sole writer to `docs`** (§5 rule 1).
- Delta-only embedding keyed by content hash, writing `docs_vec(doc_id, model, dim, vec)`.
  The **model name is part of the key**, so a model swap re-embeds lazily and two models' vectors
  coexist — that is what makes the Phase 1 comparison free of migration machinery.
- Within-unit reconciliation applied to **both** `docs` and `docs_vec` (§5 rule 2).

Embedding goes through `SentenceTransformer(...).encode()` and nothing else. Decision 1 is explicit
that hand-rolled pooling is rejected: wrong pooling or a missing L2 norm produces fast,
valid-looking, quietly degraded vectors and nothing throws (L8, twice in the incumbent).

## Acceptance

- A test asserts `docs` has exactly one writer.
- Delta behaviour: unchanged content re-runs with zero embed calls (assert the encoder is not
  called, don't time it).
- Both models resident: embed a fixture under two model names, assert both rows persist with
  correct `dim`, and that reading one does not return the other's vector.
- Reconciliation removes `docs_vec` rows for pruned chunks too — an orphaned vector is as
  corrupting as an orphaned doc row, and easier to miss.
- `embed_ms` and `peak_rss_mb` recorded in `SyncReport.meta` (§8, L7).
- Runs offline in tests: the encoder is stubbed. No network, no model download in the suite.

## Do not

- Do not implement pooling, normalization, or tokenization yourself (Decision 1, L8).
- Do not embed on every run "to be safe" — the delta is the design, and L7 is what unbounded
  embedding cost this machine.


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_contract.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M2-P2-TURN-2 --agent agy --paths "phases/hiqs-m2-cont-p2p4--hiqs-m2-p2/RELAY.md,HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_contract.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M2-P2-TURN-2 --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P2-TURN-2 --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m2-cont-p2p4--hiqs-m2-p2/RELAY.md and HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_contract.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py,HiQS/tests/test_contract.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P2-TURN-2 --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M2-P2-TURN-2 --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m2-cont-p2p4--hiqs-m2-p2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

---

### Round 1 · Builder · agy

- **Status / Summary**: Completed implementation and verification of `docs_index.py` (projection & delta vector embedding) and test suite.
- **Files Touched**:
  - `HiQS/hiqs/docs_index.py`: Implemented raw → `docs` projection (sole writer to `docs`), delta embedding keyed by content hash & model into `docs_vec(doc_id, model, dim, vec)`, within-unit reconciliation for `docs` and `docs_vec`, `SentenceTransformer(...).encode()` wrapper, and RSS/embed duration metrics in `SyncReport.meta`.
  - `HiQS/tests/test_docs_index.py`: Complete test suite covering single-writer AST assertions, delta zero-embed calls, metadata update zero-embed calls, atomic rollback, model coexistence & vector isolation, pruned chunk reconciliation, RSS/embed timing metrics, and vector serialization.
  - `HiQS/tests/test_contract.py`: Seam contract test ensuring `project_docs` is the sole `docs` table writer.
- **Verification**: `pytest HiQS/tests/test_docs_index.py HiQS/tests/test_contract.py` passed cleanly (23 passed, 1 expected xfail for M3 ranking seam).

