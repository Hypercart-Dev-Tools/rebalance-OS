# Marathon Phase hiqs-m2-p2
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M2-P2-TURN builder=agy reviewer=codex round-cap=7 -->

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



### Round 1 · Builder · agy

Implemented `HiQS/hiqs/docs_index.py` and `HiQS/tests/test_docs_index.py` per canonical spec (§6.1, §9, §5 rule 2, §3.1 Decision 1):

1. **Projection (`project_docs`)**:
   - `docs_index.py` is established as the sole writer to the `docs` table (`_sql_writers` contract test asserts this).
   - Projects `Doc` objects from raw source readers into `docs`.
2. **Delta Embedding (`docs_vec`)**:
   - Delta-only embedding keyed by `(doc_id, model)` in `docs_vec(doc_id, model, dim, vec)`.
   - Embeds only new or modified docs, or docs missing vector representations for the requested model tier. Unchanged runs invoke zero embed calls.
   - Multiple models (e.g. `all-MiniLM-L6-v2` 384-dim and `Qwen3-Embedding-0.6B` 1024-dim) coexist in `docs_vec` without vector crosstalk.
3. **Within-Unit Reconciliation**:
   - Pruning a chunk from a source removes rows from both `docs` and `docs_vec`. Orphaned vector cleanup is enforced.
4. **Observability & Performance**:
   - `SyncReport.meta` records `embed_ms` and `peak_rss_mb` via `resource.getrusage`.
5. **Testing**:
   - Added suite in `HiQS/tests/test_docs_index.py` (6 tests passing offline with stubbed embedder).

---

### Round 2 · Reviewer · codex

swept file: yes

Focused verification: `PYTHONPATH=HiQS pytest -q HiQS/tests/test_docs_index.py` — 6 passed.

The complete `docs_index.py` and its test file were swept. Pre-existing defects in these
touched files are in scope; none were identified apart from the implementation/test gaps below.

Changes requested:

1. **Delta is not keyed by content hash.** `project_docs()` treats every metadata difference
   (`url`, `ts`, `project`, or `author`) as a reason to embed. That breaks the stated
   content-hash delta contract and turns metadata refreshes into unnecessary model calls.
   Compare a stable hash (or equivalent stable comparison) of the actual embedding input
   (`title` + `body`) and add a test proving a metadata-only update makes zero encode calls.

2. **The document/vector update is not atomic.** `docs` changes commit before `encode()` runs.
   If encoding fails after a content change, the new document remains paired with its old vector;
   the next run calls it unchanged and sees a vector for that model, so it never repairs it.
   Make projection/vector persistence atomic with failure rollback (or persist the embedded-content
   hash and reliably retry stale vectors), and test an encoder exception during a changed-document
   update.

3. **The sole-writer test has the wrong scope.** It inspects only `docs_index`, so another
   `hiqs` module could write `docs` and the test would still pass. Scan the relevant package
   modules (excluding schema/trigger declarations) so the test actually enforces the phase
   contract across HiQS.

4. **Source identity is inconsistent.** Existing rows and reconciliation are keyed by
   `source.name`, while inserts/updates use `doc.source`. A mismatched source document causes
   missed existing rows and then a primary-key failure (and can make reconciliation incorrect).
   Validate that `doc.source == source.name` before writing, or consistently use one canonical
   source identity, with a regression test.

**Verdict:** Changes requested

---

### Round 3 · Builder · agy

Addressed all requested changes from Round 2 review in `HiQS/hiqs/docs_index.py` and `HiQS/tests/test_docs_index.py`:

1. **Content-Based Delta Embedding**:
   - Updated `project_docs()` to compare content (`title`, `body`) rather than full doc tuples when deciding whether to add documents to `docs_to_embed`.
   - Metadata-only updates (e.g. `url`, `ts`, `project`, `author`) update the `docs` table without invoking embedding encode calls. Added regression test `test_metadata_update_makes_zero_embed_calls`.
2. **Atomic Document / Vector Updates**:
   - Refactored `project_docs()` so that model encoding (`_encode_texts`) executes prior to committing DB mutations.
   - All DB updates (`docs` inserts/updates/prunes and `docs_vec` inserts/prunes) are executed in a single atomic transaction block. If an encoder exception occurs, DB state remains untouched. Added regression test `test_atomic_vector_update_rollback_on_encoder_exception`.
3. **Package-Wide Sole-Writer Test Scope**:
   - Updated `test_docs_has_exactly_one_writer()` to scan all Python modules across the `hiqs` package via AST. Confirmed `project_docs` in `docs_index.py` is the only function writing to `docs`.
4. **Source Identity Validation**:
   - Added explicit validation enforcing `doc.source == source.name` prior to database writes. Added regression test `test_source_identity_mismatch_raises_error`.

All 9 tests in `HiQS/tests/test_docs_index.py` passing offline.

---

### Round 4 · Reviewer · codex

swept file: yes

Focused verification: `PYTHONPATH=HiQS pytest -q HiQS/tests/test_docs_index.py` — 9 passed.

I swept both scoped files. The pre-existing defects below are in scope and must be
addressed before approval.

Changes requested:

1. **Embedding can bypass `.encode()`, violating the explicit Decision 1 contract.**
   `_encode_texts()` accepts arbitrary callables and, for the `MagicMock` fixtures used
   here, invokes the mock itself rather than `embedder.encode()`. Require an encoder
   object with `.encode()` and call that method exclusively; update the offline stub so
   tests assert `.encode()` calls (including zero calls for an unchanged document).

2. **A malformed encoder result can commit documents without their requested vectors.**
   `zip(docs_to_embed, raw_vectors)` silently truncates when the encoder returns fewer
   vectors. Validate that it returns exactly one vector per requested document (and
   reject invalid/empty vectors as appropriate) before opening the write transaction.
   Add a regression test showing a short result raises and leaves the database unchanged.

3. **Cross-source duplicate document IDs corrupt `docs_vec`.** `docs` permits the same
   `id` under two sources, but `docs_vec` is keyed only by `doc_id`. A second source can
   overwrite the first source's vector, and later reconciliation can delete it. Enforce
   global document-ID uniqueness before writing (the vector-schema contract requires it),
   including collisions among sources in one call and against existing documents; add a
   regression test.

4. **The sole-writer contract test is still too weak.** It compares only function names,
   so another module's `project_docs` would pass, and it does not recognize `DELETE FROM
   docs` (a write) or SQL supplied via keywords. Make it assert the exact qualified
   writer location and scan all relevant write forms (`INSERT`/`UPDATE`/`DELETE`/replace),
   while excluding schema/trigger declarations as intended.

**Verdict:** Changes requested

---

### Round 5 · Builder · agy

Addressed all requested changes from Round 4 review in `HiQS/hiqs/docs_index.py` and `HiQS/tests/test_docs_index.py`:

1. **Strict `.encode()` Interface Contract**:
   - `_encode_texts()` requires an embedder with an `.encode()` method exclusively and raises `TypeError` if missing or uncallable. Updated test mocks to set `mock.encode.return_value`. Added regression test `test_embedder_without_encode_method_raises_type_error`.
2. **Encoder Output Validation**:
   - Added validation before opening DB write transaction to verify `raw_vectors` has exact matching length (`len(raw_vectors) == len(docs_to_embed)`) and non-zero vector dimension (`dim > 0`). Added regression test `test_malformed_encoder_result_raises_and_rolls_back`.
3. **Global Document ID Uniqueness across Sources**:
   - Enforced global document ID uniqueness across sources both within batch and against existing DB documents. Conflicting cross-source doc IDs raise `ValueError` prior to DB writes. Added regression test `test_cross_source_duplicate_doc_id_raises_error`.
4. **AST Sole-Writer Contract Test**:
   - Refactored `_sql_writers("docs")` to use regex matching across positional and keyword arguments for `INSERT`, `UPDATE`, `DELETE FROM`, and `REPLACE INTO` statements. `test_docs_has_exactly_one_writer` asserts exact qualified writer location `("hiqs/docs_index.py", "project_docs")`.

All 12 tests in `HiQS/tests/test_docs_index.py` passing offline.

---

### Round 6 · Reviewer · codex

swept file: yes

Focused verification: `PYTHONPATH=HiQS pytest -q HiQS/tests/test_docs_index.py` — 12 passed.

I swept both scoped files. The pre-existing defects below are in scope; the focused
suite currently does not cover them.

Changes requested:

1. **The global-ID check does not detect an already-corrupt database.**
   `existing_global_docs = {row[0]: row[1] ...}` collapses multiple existing sources
   for the same document ID to whichever row SQLite returns last.  A subsequent document
   from that same last source is accepted, leaving the other row sharing `docs_vec.doc_id`
   and allowing its vector to be overwritten or deleted.  Preserve *all* existing sources
   per ID and reject a database that has cross-source duplicates before any write.  Add a
   regression test that seeds both rows, then proves projection raises and preserves them.

2. **`embed_ms` measures the entire projection, not embedding.**
   The timer begins before source fetching/scans and stops after reconciliation and every
   database write, so a slow source or prune is reported as embedding work.  Time only the
   `.encode()` call (and report `0` when no encoding is needed); retain RSS separately.
   Add a deterministic regression test, such as a patched clock, to keep this metric
   truthful.

3. **The sole-writer AST contract silently excludes async writers.**
   `_sql_writers()` visits only `ast.FunctionDef`; an `async def` elsewhere in `hiqs`
   can execute an `INSERT`/`UPDATE`/`DELETE` against `docs` without being detected.  Include
   `ast.AsyncFunctionDef` in the package-wide scan and add a focused fixture/regression
   assertion for it (or otherwise prove the helper catches that form).

---

### Round 7 · Builder · agy

Addressed all requested changes from Round 6 review in `HiQS/hiqs/docs_index.py` and `HiQS/tests/test_docs_index.py`:

1. **Pre-existing Corrupt Database Detection & Preservation**:
   - Refactored `existing_global_docs` in `project_docs()` to group all existing sources by doc ID into a set (`dict[str, set[str]]`).
   - Validates that no pre-existing doc ID is shared across multiple sources prior to any processing/writes, raising `ValueError` and preserving all pre-existing database rows.
   - Added regression test `test_preexisting_corrupt_db_duplicate_doc_id_raises_and_preserves`.
2. **Isolated `embed_ms` Measurement**:
   - Restricted `embed_ms` timing strictly to the `_encode_texts()` call execution.
   - Defaults `embed_ms` to `0.0` when no documents require vector embedding (`docs_to_embed` is empty).
   - Added deterministic regression test `test_embed_ms_times_only_encode_and_reports_zero_when_no_encode`.
3. **Async Writer Detection in AST Sole-Writer Scan**:
   - Updated `_sql_writers()` in `HiQS/tests/test_docs_index.py` to inspect `(ast.FunctionDef, ast.AsyncFunctionDef)` nodes across all `hiqs` package modules.
   - Added regression test `test_sql_writers_detects_async_function`.

All 15 tests in `HiQS/tests/test_docs_index.py` passing offline.

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M2-P2-TURN --agent agy --paths "phases/hiqs-m2-vault-search--hiqs-m2-p2/RELAY.md,HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M2-P2-TURN --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P2-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m2-vault-search--hiqs-m2-p2/RELAY.md and HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/docs_index.py,HiQS/tests/test_docs_index.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P2-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M2-P2-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m2-vault-search--hiqs-m2-p2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
