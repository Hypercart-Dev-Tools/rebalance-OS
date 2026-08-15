---
title: "p1 — R7: make the direct-commit writer idempotent"
status: "Phase complete (merged 2026-08-04, PR #253)"
created: 2026-08-04
updated: 2026-08-14
owner: noel
gh_issue: 250
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). The tracked effort is GH-250,
  parked in ROADMAP.md via PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/SCOPE.md.
---

# p1 — R7: make the direct-commit writer idempotent

## Status

| What was just completed | What's next |
|---|---|
| Phase complete, merged 2026-08-04 in PR #253. Confirmed holding in production on 2026-08-14: the orphan count sat at 2,678,350 across four measurements spanning 1h40m and two completed syncs, against a pre-fix rate of ~15,500 per sync. | Nothing. The phase is closed; this brief archives with GH-250. |

> ## ⚠️ NEVER write the absolute repo path in your transcript
>
> The turn shim scans your transcript for the real repo root and fails the turn as an "isolation
> breach" if it appears (`agy-turn.sh` does a literal `grep -qF "$ROOT"`). This already failed two
> turns. So refer to the interpreter ONLY through the exported variable **`$GH250_PY`** — never
> spell out the path, not in a command, not in prose, not in a quoted log line.
>
> ```
> PYTHONPATH="$PWD/src" "$GH250_PY" -m pytest <your test files> -q
> ```


> ## ⚠️ Sandbox constraint — do NOT run the full test suite in your turn
>
> Verified 2026-08-04: MLX cannot enumerate a Metal device inside the codex/agy turn sandbox
> (`-s workspace-write`). Any test that performs an MLX device operation **hard-crashes the whole
> Python process with SIGABRT** — `mlx::core::metal::Device::Device()` indexes an empty device
> array, throws an ObjC exception, and aborts. This is NOT catchable: `tests/conftest.py` guards
> only `ImportError`, and an abort bypasses `try/except` entirely. Three crashes in ~4 minutes were
> traced to exactly this (parent process `codex`).
>
> MLX works fine outside the sandbox on this machine (M1 Max, Metal 3), so this is a turn-sandbox
> limitation, not a broken repo.
>
> **Run only this** (the interpreter matters — see below):
> ```
> PYTHONPATH="$PWD/src" "$GH250_PY" -m pytest \\
>   tests/test_github_direct_commits.py tests/test_db_github.py \\
>   tests/test_github_knowledge.py tests/test_github_coverage.py -q
> ```
> Verified clean (33 passed). Add the specific new test file for your phase.
>
> **Why not plain `python`:** your isolated worktree has NO virtualenv — `.venv/` is gitignored,
> so it does not exist there and bare `python` either is not found or cannot import `rebalance`.
> Use the absolute interpreter above. **Do not go looking for a working environment in the real
> repo root** — that is an isolation breach and the shim will fail your turn (it already did once).
>
> **Why `PYTHONPATH="$PWD/src"`:** that venv has rebalance installed *editable*, pointing at the
> MAIN repo's `src/`. Without PYTHONPATH your edits in the worktree are not what gets imported, so
> you would be testing the wrong code and a green run would mean nothing.
>
> Never `pytest tests/` — it collects the MLX suite. As of GH-250 those tests skip cleanly via the
> `requires_metal` marker rather than aborting, but the full suite is still slow and carries
> unrelated pre-existing failures (5 order-dependent in test_hiqs_pipeline.py, 1 in
> test_scheduler_liveness.py). Stick to the scoped command.

> ## ⚠️ No scratch files anywhere in the repo
>
> Your turn is confined to the artifact allowlist, and that includes **file CREATION**, not just
> edits. A throwaway like `query_test.py` at the repo root fails the whole turn — this already
> happened once (`agy-turn: OFF-ALLOWLIST change: query_test.py — reverting`).
>
> If you need to try a query or a snippet, run it inline (`python -c '...'`) or write it under
> `$TMPDIR`, never inside the working tree. Only the files named in your allowlist may appear or
> change.





## Context

`sync_direct_commit_documents()` in `src/rebalance/ingest/github_direct_commits.py` used to strand
its vectors; #249 fixed that by pruning `github_embeddings` in the same transaction as the document
delete. That made the writer **correct**. It is still **wasteful**:

Every run it deletes all ~15.5k `direct_commit` documents and re-inserts them with fresh
autoincrement ids and `embedded_hash = NULL`. So on every one of 18 daily `github_sync` runs, ~15.5k
byte-identical documents are re-embedded from scratch — roughly **280k needless embedding
operations per day**. That is what keeps the MLX embedding pass running long and hot, and it feeds
directly into the `job_guard` compressor-ceiling failures (2026-08-04 06:34: 16.9 GB vs a 16.0 GB
ceiling, run failed fatally) and the runaway in GH-215.

It also makes document-embedding coverage a **sawtooth**: measured 9.7% missing at 11:20 and 67.9%
at 16:26 on the same day, purely from where in the churn cycle the sample landed.

## Goal

Unchanged direct commits keep their document row, their `id`, their `embedded_hash`, and therefore
their existing vector. Only genuinely new or genuinely changed commits do any embedding work.

## Required behaviour

1. **Upsert, don't delete-and-recreate.** Key on `source_key`
   (`f"{repo}:direct_commit:{sha}"`, already unique per commit and already what the function
   builds). A commit whose computed `content_hash` matches the stored row must leave that row
   **byte-identical** — same `id`, same `embedded_hash`, no vector churn.
2. **Changed content re-embeds.** If `content_hash` differs, update the row in place and null its
   `embedded_hash` so the embedder picks it up. Keep the same `id` so the existing vector is
   replaced (via `gh.upsert_github_embedding`, which is already `INSERT OR REPLACE`) rather than
   orphaned.
3. **Vanished commits are pruned.** A `direct_commit` document whose commit no longer qualifies
   (now PR-overlapping, or gone) must have its **vector deleted before its document** — the #249
   invariant. Do not regress it.
4. **Preserve the return contract carefully.** The function currently `return len(rows)` — the
   number of qualifying commits materialised. `tests/test_github_direct_commits.py` asserts `== 1`
   and `== 0` against it. Decide deliberately whether the return stays "qualifying commits" (keeps
   existing tests meaningful) or becomes "documents written"; if you change the meaning, update
   every caller and existing assertion, and say so in the relay file. Do not silently redefine it.

## Constraints

- Reuse existing helpers in `src/rebalance/ingest/db/github.py`. If you need a new one, put it
  there — ingest code must not embed INSERT/DELETE SQL (that module's stated contract).
- One transaction, as now.
- No new dependencies.
- Do not touch the reclaim of existing orphans; that is p3–p5 and R4.

## Tests to add (extend `tests/test_github_direct_commits.py`)

Mirror the style of the existing `DirectCommitEmbeddingPruningTests` — a `_seed_direct_commit`
fixture and an `_embed_all_pending` stand-in for the embedder already exist there; reuse them.

1. **Idempotence, the headline:** seed a commit, sync, embed, record the document `id` and
   `embedded_hash`. Sync twice more. Assert the `id` and `embedded_hash` are **unchanged** and that
   the pending-embed count is **0** after each — i.e. no re-embedding was scheduled.
2. **Vector stability:** across those repeated syncs, assert the vector count stays at 1 and the
   orphan count stays at 0.
3. **Changed content does re-embed:** mutate the underlying commit message, sync, assert the
   document keeps its `id`, `embedded_hash` is now NULL, and after embedding there is still exactly
   one vector and zero orphans.
4. **Vanished commit prunes both:** make a commit PR-overlapping (the existing
   `test_pr_overlap_removes_direct_document_but_keeps_raw_provenance` shows how), then assert the
   document is gone **and** no vector is left behind.
5. **Scale:** 5 commits, sync 3x, assert zero pending embeds after the first cycle and zero orphans
   throughout.

**Every one of these must be verified to fail against the current `main`-branch writer before you
claim it passes.** State in the relay file which tests failed pre-change and how. A test that
passes both before and after proves nothing — that check is the whole point of this phase.

## Definition of done

- Repeated syncs of unchanged commits schedule **zero** embedding work.
- Zero orphaned vectors under every scenario above.
- The scoped pre-advance suite passes.
- The relay file records the before/after pending-embed count for a 3-sync cycle — the concrete
  number this phase exists to drive to zero.
