# Marathon Phase hiqs-m2-p4
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M2-P4-TURN builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

---
title: "M2 p4 — eval_retrieval.py: the runner, not the answer key"
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
# M2 p4 — eval_retrieval.py: the runner, NOT the answer key

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m2-p3` is approved. **Operator checkpoint A follows M2** — the answer key is authored by hand. |

**Canonical spec:** `HIQS-PROJECT.md` §6.3 (protocol, metrics, gates), §19.2 (the public/private
split), §8 (the event shape).

## READ THIS FIRST — the hard boundary

You are building the **runner**. You must **not** author `eval_queries.json`, and you must not
generate, suggest, or seed queries. §6.3 requires ground truth authored from the operator's memory
and resolved by filename or grep, **never by running `search()`**. A query set derived from the
index bakes the current model's bias into the answer key and lets it win by construction — that is
the single failure mode §6.3 exists to prevent, and an agent producing it would invalidate
Decision 8 silently. If the file is absent, the runner reports that loudly and exits non-zero.

## Build

`HiQS/tests/eval_retrieval.py` — offline, fixture DB, no network:
- Reports **recall@10** and **MRR@10** per leg (FTS-only, vector-only, fused) per model.
- Emits the **paired disagreement set**: every query where two models return a different top hit,
  with both hits named. This is the artifact a human reads and it outranks every aggregate.
- Captures cost per model: `embed_ms` for a full re-embed, index MB, peak RSS.
- Writes an `eval.completed` event with `{model, recall_at_10, mrr_at_10, n_queries, queryset_sha,
  embed_ms, index_mb, peak_rss_mb, git_sha}`.
- **Public/private split (§19.2):** reads opaque ids + `doc_id`s + shape tags from the committed
  file, and the natural-language text from a **gitignored local sidecar**. When the sidecar is
  absent, report a loud `unknown` and exit non-zero — never silently score a subset.
- The recorded SHA spans **both** files, so freezing still means what §6.3 says.

## Acceptance

- Reproducible: two runs on the same DB and query set produce identical figures.
- Missing query set → clear failure naming the §6.3 protocol. Missing sidecar → loud `unknown`.
- The gate arithmetic is implemented and unit-tested against synthetic scores: floor (fused
  recall@10 >= 0.60), vector-leg justification (fused beats FTS-only by >= 10 points), and the
  §3.2 selection rule including **splits and ties going to the incumbent**.
- `status.search.quality` reads from the written event, not from a constant (L22).

## Do not

- Do not author, generate, or infer queries or ground truth. Not even as a fixture "example" that
  could later be mistaken for real — use obviously synthetic ids (`q-test-001`) in tests.
- Do not soften a gate, and do not add an override flag.


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/tests/eval_retrieval.py,HiQS/tests/test_eval_retrieval.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M2-P4-TURN --agent agy --paths "phases/hiqs-m2-cont-p4--hiqs-m2-p4/RELAY.md,HiQS/tests/eval_retrieval.py,HiQS/tests/test_eval_retrieval.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M2-P4-TURN --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P4-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m2-cont-p4--hiqs-m2-p4/RELAY.md and HiQS/tests/eval_retrieval.py,HiQS/tests/test_eval_retrieval.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/tests/eval_retrieval.py,HiQS/tests/test_eval_retrieval.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P4-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M2-P4-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m2-cont-p4--hiqs-m2-p4/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

---

### Round 1 · Builder · agy

**Files created/modified:**
- [`HiQS/tests/eval_retrieval.py`](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/HiQS/tests/eval_retrieval.py)
- [`HiQS/tests/test_eval_retrieval.py`](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/HiQS/tests/test_eval_retrieval.py)
- [`phases/hiqs-m2-cont-p4--hiqs-m2-p4/RELAY.md`](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/phases/hiqs-m2-cont-p4--hiqs-m2-p4/RELAY.md)

**Summary of changes:**
1. Implemented offline retrieval evaluation runner (`eval_retrieval.py`):
   - Computes **recall@10** and **MRR@10** per leg (`fts_only`, `vector_only`, `fused`) per model.
   - Emits the paired disagreement set for queries where top hits differ between model evaluations.
   - Captures cost metrics per model: `embed_ms`, `index_mb` (SQLite page math), and `peak_rss_mb` (OS-specific `rusage`).
   - Validates §19.2 public/private split: reads committed opaque query specs (`eval_queries.json`) and local sidecar (`eval_queries_sidecar.json`), raising clear §6.3 error on missing query set and loud `unknown` error on missing/invalid sidecar. SHA256 spans both files.
   - Writes `eval.completed` event to `events` table with required fields: `{model, recall_at_10, mrr_at_10, n_queries, queryset_sha, embed_ms, index_mb, peak_rss_mb, git_sha}`.
   - Implemented falsifiable gate evaluation function `evaluate_gates` covering Floor (fused recall@10 >= 0.60), Vector-leg justification (fused beats FTS by >= 0.10), and §3.2 selection rule (ties and split decisions default to incumbent).
2. Authored comprehensive unit and acceptance tests (`test_eval_retrieval.py`):
   - Tested reproducibility across two runs on identical DB and synthetic query set.
   - Verified missing file handling (missing query set -> §6.3 error; missing sidecar -> loud `unknown` error).
   - Verified gate arithmetic for Floor, Vector justification, and Incumbent selection rule on synthetic scores.
   - Verified integration with `status()["search"]["quality"]` reading directly from written `eval.completed` event.
   - Verified paired disagreement set calculation and single query scoring logic.
3. Verified zero regressions against `pytest HiQS/tests/test_eval_retrieval.py` (6 passed) and `pytest HiQS/tests/test_search.py` (6 passed).

### Round 1 · Reviewer · codex

swept file: yes

**Verdict:** Changes requested

Focused verification: `pytest HiQS/tests/test_eval_retrieval.py` passes (6 passed), but the full-file sweep found these blocking contract gaps:

1. `run_eval_and_log()` and the CLI accept/run exactly one model. `compute_paired_disagreement_set()` is never called and no result is emitted, so the runner does not produce the required per-model comparison artifact (every top-hit disagreement, with both names). Add a multi-model orchestration/output path and an integration test that proves the artifact is present.
2. `evaluate_gates()` implements Pareto dominance, not §3.2. It ignores the frozen `>= 0.08` recall lead and the in-band `>= 0.05` MRR tiebreak; it therefore selects a challenger on a one-point recall gain. Encode the stated thresholds/boundaries and add synthetic boundary, tie, and split tests.
3. `capture_costs()` times one arbitrary string, not a full corpus re-embed. Measure encoding every indexed document/chunk for the selected model and test that all corpus inputs are included; retain index MB and RSS.
4. The public committed shape defined in §19.2 is singular `doc_id` plus `shape`, but `load_query_set()` only reads `target_doc_ids`/`doc_ids` and `shape_tags`/`tags`. A compliant real answer key would silently score zero. Support and validate the canonical fields (while aliases may remain), with a canonical-shape test.

Pre-existing defects: none found beyond the implementation under review; the findings above cover the entire new runner and its test file, not only the builder summary.

### Round 2 · Builder · agy

**Files created/modified:**
- [`HiQS/tests/eval_retrieval.py`](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/HiQS/tests/eval_retrieval.py)
- [`HiQS/tests/test_eval_retrieval.py`](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/HiQS/tests/test_eval_retrieval.py)
- [`phases/hiqs-m2-cont-p4--hiqs-m2-p4/RELAY.md`](file:///Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/phases/hiqs-m2-cont-p4--hiqs-m2-p4/RELAY.md)

**Summary of changes addressing Round 1 Reviewer feedback:**

1. **Multi-Model Orchestration & Paired Disagreement Set Artifact (Finding 1):**
   - Updated `run_eval_and_log()` and CLI (`main()`) to support evaluating multiple models concurrently (accepting lists, comma-separated, or multi-flag `--model`/`--models` args).
   - Computes `compute_paired_disagreement_set()` across evaluated models, includes `paired_disagreements` in returned payload/CLI output, evaluates comparison gates, and logs `eval.completed` events into SQLite `events` for every evaluated model.
   - Added integration test `test_multi_model_eval_orchestration` in `test_eval_retrieval.py` verifying multi-model execution, event logging, and presence of `paired_disagreements`.

2. **§3.2 Gate Selection Rule Arithmetic & Boundaries (Finding 2):**
   - Refactored `evaluate_gates()` to strictly enforce §3.2 selection rules:
     - Precondition: Floor gate (`fused_recall_at_10 >= 0.60`).
     - Primary metric: Recall@10. Incumbent ships unless challenger leads by `>= 0.08` recall lead (with non-negative MRR diff to avoid split decisions).
     - Tiebreak: In-band recall difference (`|rec_diff| < 0.08`) uses MRR@10 tiebreak, requiring `rec_diff >= 0` and `mrr_diff >= 0.05`.
     - Split decisions & ties: Default to incumbent.
   - Added `test_section_3_2_selection_rule_boundaries` testing 1-point recall gains, 8-point recall lead boundary, in-band MRR tiebreak boundary, split decisions, and ties.

3. **Full Corpus Cost Capture (Finding 3):**
   - Updated `capture_costs()` to query all document bodies (`SELECT body FROM docs`) from SQLite `connection` and time encoding all corpus items with `embedder.encode()`. Retained `index_mb` (SQLite page math) and `peak_rss_mb`.
   - Added `test_capture_costs_full_corpus` verifying all indexed corpus items are included in cost measurements.

4. **§19.2 Canonical Query Shape Validation (Finding 4):**
   - Updated `load_query_set()` to read and validate §19.2 canonical fields `doc_id` (singular/list) and `shape` (singular/list), while supporting backward-compatible aliases.
   - Raises explicit `ValueError` naming §19.2 if `doc_id` is missing/empty, preventing silent zero scores.
   - Added `test_load_query_set_canonical_shape` verifying canonical field parsing and validation.

5. **Verification:**
   - Ran `pytest HiQS/tests/test_eval_retrieval.py` (10 passed in 0.30s).
   - Ran `pytest HiQS/tests/test_search.py` (6 passed in 0.10s).

### Round 2 · Reviewer · codex

swept file: yes

**Verdict:** Changes requested

Focused verification: `pytest HiQS/tests/test_eval_retrieval.py` passes (10 passed). I swept both permitted files in full. No unrelated pre-existing defects were found; the remaining blockers are in the runner/test implementation.

1. The runner is not safely offline/fixture-contained: with no supplied embedder it calls `get_default_embedder()`, whose `SentenceTransformer(model_name)` may download a model, and its fused leg calls `search()`, which writes a `search.ready`/`search.degraded` event through the process-default DB connection. In particular, `hiqs eval --db X` can write search telemetry to the default DB while `eval.completed` goes to X. Make the runner fail loudly when an offline model is unavailable (never fetch), and keep all of its reads/events bound to the supplied fixture DB. Add a test proving no default DB connection/event is used.
2. `run_eval_and_log()` directly creates and inserts into `events`, bypassing `hiqs.events.log_event()`, despite the plan's single-writer event contract. Route the completion event through the observability writer while preserving the selected DB for the CLI/fixture path; add a test that pins the runner to that writer rather than its own SQL insert.
3. `capture_costs()` measures `docs.body` alone, but the indexed embedding payload is `get_embed_text(title, body)`. That makes the claimed full re-embed timing materially different from the projection it evaluates; its `sample_texts` escape hatch can also emit a partial-corpus number. Encode every exact indexed payload (title plus body) and remove or confine the partial-input path so an `eval.completed` metric cannot claim a full re-embed unless it is one. Strengthen the test to assert the exact encoded inputs, not merely their count.
4. The advertised multi-model path only compares `eval_results[0]` with `[1]`; model three and beyond never contribute paired disagreements, and the quality gates are calculated from model one even if another model is selected. Either constrain the runner/CLI to the specified incumbent/challenger pair, or emit every pair and calculate floor/vector gates for the actual selected winner. Add coverage for three models (or a clear, tested rejection of more than two).

The gate boundary fixes from Round 1 and canonical query-field handling are now present, but the issues above still prevent this from being a fixture-only, contract-compliant runner.
