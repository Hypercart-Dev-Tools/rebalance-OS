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
