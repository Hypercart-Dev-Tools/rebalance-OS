# Marathon Phase hiqs-m2-p4
STATUS: Approved
NEXT: agy

<!-- marathon-drive: task=MARATHON-HIQS-M2-P4-TURN-2 builder=agy reviewer=codex round-cap=11 -->

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


## Debug mantra (auto-triggered — 1 prior attempt(s) on this phase did not reach Approved)

Before trying again, read /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/relay-automation/DEBUG-MANTRA.md and follow its four-step discipline: reproduce reliably, know the fail path, question the hypothesis, treat this round as a breadcrumb for the next one.
Last recorded reason (/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/phases/hiqs-m2-cont-p4--hiqs-m2-p4/ESCALATION.md): `cap-or-close-mismatch`. Read it before re-guessing.

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/tests/eval_retrieval.py,HiQS/tests/test_eval_retrieval.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M2-P4-TURN-2 --agent agy --paths "phases/hiqs-m2-cont-p4--hiqs-m2-p4/RELAY.md,HiQS/tests/eval_retrieval.py,HiQS/tests/test_eval_retrieval.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M2-P4-TURN-2 --agent agy
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P4-TURN-2 --agent agy --to codex
4. Edit ONLY these paths: phases/hiqs-m2-cont-p4--hiqs-m2-p4/RELAY.md and HiQS/tests/eval_retrieval.py,HiQS/tests/test_eval_retrieval.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to codex — codex, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/tests/eval_retrieval.py,HiQS/tests/test_eval_retrieval.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M2-P4-TURN-2 --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M2-P4-TURN-2 --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m2-cont-p4--hiqs-m2-p4/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to agy —
   agy, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

---

### Round 1 · Builder · agy

**Summary:**
Implemented the offline retrieval evaluation runner in `HiQS/tests/eval_retrieval.py` and its comprehensive unit test suite in `HiQS/tests/test_eval_retrieval.py` according to §6.3, §19.2, and §3.2 requirements.

**Key Implementation & Design Decisions:**
1. `HiQS/tests/eval_retrieval.py`:
   - **Public/Private Split & Freezing (§19.2):** `load_query_set` reads opaque query IDs, target `doc_id`s, and shape tags from the committed file, and natural-language query text from the gitignored sidecar. Raises a loud `FileNotFoundError` with `"unknown"` when the sidecar is absent, and raises naming §6.3 when the query set is missing. `compute_queryset_sha` computes a SHA-256 digest spanning both files.
   - **Metrics & Legs:** `evaluate_retrieval` evaluates recall@10 and MRR@10 per leg (FTS-only, vector-only, RRF fused) per model.
   - **Paired Disagreement Set:** `compute_paired_disagreement_set` outputs every query where two models differ on the top hit with model names and top hit IDs.
   - **Cost Metrics:** `capture_costs` records `embed_ms` for a full corpus re-embed using `get_embed_text(title, body)`, SQLite `index_mb`, and `peak_rss_mb`.
   - **Telemetry:** `_log_eval_completed` logs `eval.completed` events targeting the current database connection without touching the default DB.
   - **Falsifiable Gates (§3.2):** `evaluate_gates` enforces floor (`fused_recall_at_10 >= 0.60`), vector justification (`fused_recall_at_10 - fts_recall_at_10 >= 0.10`), and the selection rule (precondition floor passed; 8-point recall lead required to beat incumbent; tiebreak on MRR@10 >= 0.05 within ±0.08 recall band; split decisions and ties go to incumbent).
   - **Offline Enforcer:** `get_offline_embedder` enforces `local_files_only=True` to prohibit network downloads. `get_git_sha` retrieves git SHA without subprocess calls.

2. `HiQS/tests/test_eval_retrieval.py`:
   - Implemented 15 test cases using synthetic IDs (`q-test-001`) and stub embedders:
     - Test 1: Reproducibility across identical DB and query set runs.
     - Test 2: Error handling for missing query set (§6.3) and missing/incomplete sidecar (`unknown`).
     - Test 3 & 4: Floor gate, vector justification, and §3.2 selection rule boundaries (including 1-point gain, 8-point lead, in-band MRR tiebreak, split decisions, and ties going to incumbent).
     - Test 5: Integration with `status().search.quality` reading from the `eval.completed` event.
     - Test 6: Default DB isolation (zero events written to default DB).
     - Test 7: Multi-model evaluation and paired disagreement set across 3 models.
     - Test 8: Cost capture timing and exact text payload validation.
     - Test 9: Canonical §19.2 field validation (`doc_id`, `shape`).
     - Test 10: Loud failure on missing local model (no network download allowed).
     - Test 11: Loud RuntimeError on vector search / encoder failures.

3. **Verification:**
   - Ran `pytest HiQS/tests/test_eval_retrieval.py` (15 passed).

handing off to codex — codex, take your turn.

### Round 1 · Reviewer · codex

swept file: yes

**Assessment:** Approved. I reviewed the complete contents of both
`HiQS/tests/eval_retrieval.py` and `HiQS/tests/test_eval_retrieval.py`, including
pre-existing code; no in-scope pre-existing defects were found. The runner keeps
the answer key boundary intact, fails loudly for a missing committed set or
sidecar, hashes both inputs, evaluates all three legs per model, records the
paired fused-top-hit disagreements and per-model costs, and routes the required
event through the shared writer against the supplied fixture connection. Gate
arithmetic covers the floor, vector justification, and incumbent-favouring split
and tie selection cases. `status.search.quality` is exercised from the persisted
event rather than a constant.

**Verification:** `cd HiQS && pytest tests/test_eval_retrieval.py` — 15 passed.
The first reproduction command did not start pytest because it used the project
document path from the `HiQS/` subdirectory; rerunning with the corrected
repository-root path produced the result above.

**Verdict:** Approved

relay closed, no further turn needed.
