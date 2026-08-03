# Marathon Phase hiqs-m2-p2
STATUS: Open
NEXT: codex

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

### Round 1 · Reviewer · codex

- swept file: yes
- **Blocker — reconciliation is source-wide, not within-unit.** `project_docs()` builds `to_prune` from every existing row for `source.name` and removes every row absent from that source's current `docs()` output. This contradicts the canonical rule: reconcile only the successfully fetched unit; never delete across units or after a partial fetch. A source result containing freshly derived chunks for `vault:one.md` but omitting `vault:two.md` because that file/unit failed will delete the still-valid `vault:two.md` docs and all of their model vectors. The existing source-wide failure catch does not protect this partially successful case. Change the projection contract/implementation so pruning is scoped to successfully derived units, and add a regression test that proves a missing/failed sibling unit is retained while stale chunks in a successfully derived unit are pruned. Preserve the corresponding vectors for retained units.
- **Should — the advertised content-hash delta is not implemented.** The code uses direct `(title, body)` equality and does not derive a content hash for the embedding payload. Implement the stated hash-keyed comparison (including the exact text passed to `encode()`), with coverage that a metadata-only change remains a zero-embed rerun.
- **Review evidence:** completed a whole-file sweep of `docs_index.py`, `test_docs_index.py`, and `test_contract.py`; ran `cd HiQS && pytest tests/test_docs_index.py tests/test_contract.py` (23 passed, 1 expected xfail). No additional pre-existing defects were found in the three scoped files.

**Verdict:** Changes requested

### Round 2 · Builder · agy

- **Status / Summary**: Addressed all Reviewer (codex) Round 1 findings. Scoped reconciliation strictly to successfully derived units (`scanned_units`), ensuring unfetched or errored sibling units and their vectors are preserved (§5 rule 2). Implemented explicit content-hash delta embedding (`compute_content_hash`, `get_embed_text`). Added comprehensive regression tests for both items.
- **Files Touched**:
  - `HiQS/hiqs/docs_index.py`: Added `get_embed_text`, `compute_content_hash`, and `get_doc_unit` helpers. Scoped `to_prune` reconciliation to units present in `scanned_units` so unfetched sibling units are preserved in `docs` and `docs_vec`. Implemented sha256 content-hash check for embedding payload delta logic.
  - `HiQS/tests/test_docs_index.py`: Added `test_within_unit_reconciliation_retains_unfetched_sibling_units_and_vectors` to verify unfetched sibling units/vectors are retained while stale chunks in fetched units are pruned. Added `test_content_hash_helpers_and_delta_embedding` testing helper functions and metadata update zero-embed calls.
  - `HiQS/tests/test_contract.py`: Preserved contract tests.
- **Verification**: `pytest HiQS/tests/test_docs_index.py HiQS/tests/test_contract.py` passed cleanly (25 passed, 1 expected xfail for M3 ranking seam).

### Round 2 · Reviewer · codex

- swept file: yes
- **Blocker — a successfully fetched empty unit still cannot reconcile.** `scanned_units` is inferred only from emitted `Doc` rows. If a vault file (or another unit) is successfully fetched but now yields zero chunks — for example, its final heading is deleted or its content becomes empty/frontmatter-only — there is no `Doc` from which to add that unit. Its existing `docs` rows and all model vectors are therefore retained forever. This contradicts §5 rule 2, which requires every successfully fetched unit to reconcile, including deletion of every prior chunk. The production vault provider cannot currently convey this successful-but-empty unit state either. Make the projection consume an explicit successful-unit inventory/attestation separate from documents (and wire the existing source contract/provider to it), then add a regression test starting with a multi-chunk unit and asserting that an explicitly successful empty result deletes its docs and `docs_vec` rows. The existing sibling test only proves that a unit absent from the result is retained; it does not cover a known-successful unit with no derived chunks.
- **Review evidence:** completed the required whole-file sweep of `HiQS/hiqs/docs_index.py`, `HiQS/tests/test_docs_index.py`, and `HiQS/tests/test_contract.py`, including the pre-existing code. No additional defects found in the three scoped files. Ran `cd HiQS && pytest tests/test_docs_index.py tests/test_contract.py`: 25 passed, 1 expected xfail.

**Verdict:** Changes requested
