---
title: "GH-198 — Local Qwen embedding proof on this Mac"
status: "Active — Phase 0 passed 2026-07-22; Phase 1 next. Issue #198 reopened to carry Phases 1–2."
created: 2026-07-22
updated: 2026-07-22
owner: Noel
gh_issue: 198
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/198"
branch: development
doc_type: project
goal: >
  Prove that this Mac can build and query a representative RebalanceOS semantic
  signal corpus with the local MLX Qwen embedding runtime, while preserving the
  existing production database — then turn that manual proof into a reproducible,
  observable path before deciding on any full rollout.
non_goals: >
  This is not a provider migration for ask-self, a full-corpus rollout, or a
  change to the Qwen model or vector dimension. It does not alter production
  source rows or delete production vectors.
related:
  - src/rebalance/ingest/index_ops.py
  - src/rebalance/ingest/semantic_index.py
  - src/rebalance/ingest/embedder.py
  - src/rebalance/ingest/_job_guard.py
  - ARCHITECTURE.md
effort: 2
complexity: 2
risk: 2
phases: 3
---

## Status

| What was just completed | What's next |
|---|---|
| **Phase 0 passed 2026-07-22.** A guarded local MLX run projected, embedded, and cold-queried a 1,560-document RebalanceOS code corpus with Qwen against a gitignored staging database. Production `rebalance.db` was never selected as a write target and remains at 0 `semantic_documents` / 0 `semantic_embeddings`. Evidence is recorded on [#198](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/198) and in [Evidence record](#evidence-record) below. | **Phase 1** — turn the manual proof into a reproducible, stage-owned smoke test and surface its runtime evidence through the existing orchestrator/`doctor` path. Phase 2 (rollout decision) is gated behind it. |

## Table of contents

- [Baseline](#baseline)
- [Phase 0 — bounded spike](#phase-0--bounded-spike)
- [Phase 1 — operationalize the proven path](#phase-1--operationalize-the-proven-path)
- [Phase 2 — rollout decision](#phase-2--rollout-decision)
- [Evidence record](#evidence-record)
- [Provenance](#provenance)

## Baseline

- The shared local runtime is `Qwen/Qwen3-Embedding-0.6B` via MLX, fixed at 1,024 dimensions.
- `embed_pending()` is the stage-owned writer for `semantic_documents` and `semantic_embeddings`; user-facing refreshes must reach it through `refresh_index(scope=[...])`.
- The production database is empty for the relevant source and vector tables. It is therefore unsuitable as proof of either success or failure, and will not be mutated by this work.
- The ask-self portable index is **not** a control: it uses Gemini (`gemini-embedding-001`, 768 dimensions) and a separate database.

## Phase 0 — bounded spike

**Timebox: 1–2 hours. Blocking gate for all later phases. — PASSED 2026-07-22.**

- [x] Create a staging SQLite database under `temp/`; never write the production DB.
- [x] Use the `code` derived scan and `semantic` projection through `refresh_index` to build one representative RebalanceOS repository corpus.
- [x] Capture source-document count, eligible-document count, vector-row count, model/version metadata, elapsed time, and peak RSS.
- [x] Restart the Python process and run a grounded semantic query against the staging database.
- [x] Exercise a controlled model-version mismatch in staging and verify all stale documents are re-embedded, with no mixed model versions.
- [x] Record results below. The blocking gate passed; proceed only with the separate Phase 1 implementation work.

### Success criteria

1. Every eligible projected document has exactly one 1,024-dimension vector. ✅
2. Every embedded document records `Qwen/Qwen3-Embedding-0.6B|1024`. ✅
3. A fresh process returns a relevant result from the staging corpus. ✅
4. The production database row counts remain unchanged. ✅

## Phase 1 — operationalize the proven path

Only start after Phase 0 succeeds. **This is the next action.**

- [ ] Add a reproducible, stage-owned local embedding smoke test with deterministic fixtures.
- [ ] Surface bounded runtime metrics and actionable failure reporting through the existing orchestrator/`doctor` path.
- [ ] Add tests for successful embedding, stale model-version re-embedding, malformed vectors, and MLX load failure.

## Phase 2 — rollout decision

Only start after Phase 1 passes.

- [ ] Size and schedule a full local semantic-corpus build.
- [ ] Require a dry-run preview and preserve the production DB until validation completes.
- [ ] Decide whether ask-self remains Gemini-backed; changing it is explicitly a separate issue and migration.

## Evidence record

**Result: passed 2026-07-22.** The staging database is gitignored at
`temp/gh-198/qwen-spike.db`; it is the only database written by this spike.

| Check | Evidence |
|---|---|
| Runtime | macOS 15.6.1; MLX 0.31.2; mlx-embeddings 0.1.0; job guard measured 64.0 GiB physical memory. |
| Corpus | The orchestrated `semantic` stage projected 1,560 `code` documents from this RebalanceOS checkout. |
| Local embedding | `Qwen/Qwen3-Embedding-0.6B`, 1,024 dimensions, batch size 32: **1,560 / 1,560** vectors. The full guarded run took **222.1s** with a **1.468 GiB** peak tree RSS; the 22.4 GiB ceiling did not trip. |
| Metadata | All 1,560 rows report `Qwen/Qwen3-Embedding-0.6B\|1024`; semantic metadata records the same model, dimension, and embedder version. |
| Cold retrieval | A new process queried "How does `refresh_index` run the semantic embedding stage?" and returned `_refresh_semantic_only` in `src/rebalance/ingest/index_ops.py` as the top result. |
| Stale-model repair | One staging document was deliberately stamped `phase0-probe-mismatch`; `embed_semantic_pending()` re-embedded exactly one row in 3.69s, skipped 1,559, and restored a single Qwen/1,024 model version across the corpus. |
| Production isolation | After the spike, production `rebalance.db` remains at 0 `semantic_documents` and 0 `semantic_embeddings`; it was never passed to the staging commands. |

**Environment note.** Headless sandbox sessions cannot access Metal, so the actual embedding and cold-query calls were run with normal local Metal access. That is an execution-environment constraint, not an MLX failure. **No local-embedding blocker was found.**

### Defect split out during Phase 0

An earlier Phase 0 attempt pointed `--database` at a staging path that did not yet exist. Because `resolve_database_path()` selects the first *existing* candidate, resolution fell through to the canonical app-data DB and projected 1,560 `code` documents there before embedding started. No vectors were created there and no rows were deleted; the rows were left intact rather than doing an unapproved destructive rollback, and all later work used a pre-initialized staging file.

That is a general resolver defect, not Qwen-specific, and is tracked separately as **[#201](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/201)** — an explicit `--database` at a nonexistent path must never silently resolve to the canonical DB.

A second Phase 0 attempt was stopped cleanly by the existing GH-172 job guard at 57.2s when system-available memory fell to 7.3 GiB against its 7.7 GiB floor (peak process-tree RSS was only 1.47 GiB, so this was global machine pressure, not a Qwen spike). No override or automatic retry was performed — the guard behaved correctly.

## Provenance

Phase 0 ran in a dedicated worktree on branch `codex/gh-198-local-qwen-embedding-spike` (`29dbd93`). That branch was **deliberately not merged**: it changed no code, wrote only to a gitignored staging database, and its evidence is fully recorded on #198 and in this doc. It was torn down during the 2026-07-22 PDDA EOD wrap. This doc is the source of truth going forward.
