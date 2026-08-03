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
