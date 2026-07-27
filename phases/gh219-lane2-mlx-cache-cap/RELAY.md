# Marathon Phase gh219-lane2-mlx-cache-cap
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-GH219-LANE2 builder=agy reviewer=codex round-cap=5 -->

## Phase Brief

# Lane 2 (GH-219 marathon) — #215: cap and clear the MLX buffer cache — THE FIX

## Status: the diagnosis is PROVEN, not inferred. Do not re-litigate it.

Live telemetry on this hardware, 2026-07-27, through this repo's own
`_load_model` / `_embed_batch` path:

| Metric | Batch 1 | Batch 18 | Δ |
|---|---|---|---|
| `mx.get_active_memory()` | 1.110 GB | 1.110 GB | **+0.000** |
| `mx.get_cache_memory()` | 0.510 GB | 11.546 GB | **+11.036** |
| `phys_footprint` | 1.84 GB | 13.00 GB | **+11.16** |

Active memory never grew. Footprint growth is accounted for by **cache** growth to within 0.12 GB.
Each new tokenized shape allocates a new buffer size; MLX caches every one; nothing is released.
18 batches → 11.5 GB, extrapolating cleanly to the 46.9 GB production episode.

**The remedy is already validated.** Identical load plus `mx.clear_cache()` after each batch held
cache at **0.000 GB** and footprint at **1.35 GB** — a 9.6× reduction.

**Critical caveat that will mislead you if you ignore it:** a run with *uniform* input shapes shows
**no growth at all** (60 batches, cache 0.752 → 0.722 GB, footprint pinned at 2.09 GB). MLX's cache
is keyed by buffer **size**, so identical shapes reuse identical buffers. **Any test you write with
fixed-length inputs will pass whether or not the fix works.** Variable-length inputs are mandatory.

## Required work

### 1. Bound the cache (`embedder.py`)

- `mx.set_cache_limit(...)` **once**, at embedding-module level — not per call
- `mx.clear_cache()` at the end of each batch iteration in the loop at `embedder.py:172-177`
- **Size the limit from the measured numbers, not a guess.** The model occupies ~1.11 GB active.
  The project contract is ≤ 8 GB peak `phys_footprint` per process. Leave real headroom for cache
  reuse while keeping total footprint far below that ceiling, and **write the derivation into a
  comment** so the next person does not have to re-measure.
- Make it environment-overridable, consistent with the existing `REBALANCE_JOB_GUARD_MAX_RSS_GB`
  convention.

All four call sites funnel through `_embed_batch` / `_load_model`, so the fix belongs at those
shared helpers — **not** copy-pasted into four places. Verify all four benefit:
`embedder.py:105` `embed_chunks`, `embedder.py:216` `query_similar`,
`semantic_index.py:613` `embed_pending`, `github_knowledge.py:855` `_default_embed_texts`.

### 2. Throughput — measure it, do not assume it

`clear_cache()` after every batch discards reuse that the cache exists to provide. `set_cache_limit`
alone bounds growth while *keeping* some reuse. These trade off.

- Measure batches/sec before and after, on variable-length inputs
- If clearing every batch costs meaningful throughput, evaluate clearing every N batches, or
  relying on `set_cache_limit` alone
- **Record the numbers in the code comment or the test.** A regression that is measured and
  accepted is fine; one that is silently introduced is not.

### 3. Fix the telemetry visibility defect (found by the live run)

Lane 1's telemetry emits at `INFO`, but `src/rebalance/__init__.py:38` pins the `rebalance` logger
to `WARNING` unless `REBALANCE_LOG_LEVEL` is set. **Scheduled launchd passes set no such variable,
so none of this telemetry is recorded in the runs that actually blow up.** The Lane 1 verdict was
only obtainable because a harness set the level by hand.

Fix so memory telemetry is recorded in a default production run. Prefer the smallest change that
achieves it — e.g. emit the memory lines at `WARNING`, or have the embedding path raise its own
logger level. Do **not** change the global default log level for the whole package.

## Write-set (do not edit anything else)

- `src/rebalance/ingest/embedder.py`
- `src/rebalance/ingest/semantic_index.py`
- `src/rebalance/ingest/github_knowledge.py`
- `tests/test_mlx_cache_cap.py` (new)

## Tests — required

`tests/test_mlx_instrumentation.py` already solves the two traps in this area; **read it first and
reuse its fixtures.** Specifically: the `rebalance` logger has `propagate=False` *and* is set to
WARNING, and `mlx` is a real installed package so `sys.modules["mlx.core"]` patching is ignored —
you must patch the attribute on the parent package.

Cover:

1. **Cache stays bounded across many VARIABLE-length batches** — the central test. Fixed-length
   inputs cannot detect this bug.
2. `set_cache_limit` is applied once, not per call
3. `clear_cache` is invoked on the expected cadence
4. All four call sites are covered (parametrized, as in the existing test file)
5. Telemetry is emitted at a level that survives the default production logger configuration
6. Behaviour degrades safely when MLX is unavailable — the fix must not become a new crash path

## Acceptance

- Gate: `.venv/bin/python3 -m pytest tests/test_semantic_index.py tests/test_semantic_hybrid.py
  tests/test_semantic_source_contract.py tests/test_github_knowledge.py
  tests/test_dashboard_refresh_integration.py tests/test_mlx_instrumentation.py
  tests/test_mlx_cache_cap.py -q` passes
- No regressions. The full suite has **6 known pre-existing failures**
  (`test_hiqs_pipeline.py` ×5, `test_scheduler_liveness.py` ×1) — those are not yours, do not
  attempt to fix them, and do not let them fail your gate.

## Out of scope

- `mx.set_memory_limit()` — that is Lane 3 (#217)
- `utils/job_guard.py` / the RSS→footprint switch — Lane 4 (#213)
- Adding guards to the two unguarded call sites — Lane 6
- Anything under `temp/` — gitignored; edits there cannot be committed and are destroyed with the
  worktree
- Embedding-pipeline redesign, model changes, batch-size tuning


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/ingest/embedder.py,src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/github_knowledge.py,tests/test_mlx_cache_cap.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-GH219-LANE2 --agent agy --paths "phases/gh219-lane2-mlx-cache-cap/RELAY.md,src/rebalance/ingest/embedder.py,src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/github_knowledge.py,tests/test_mlx_cache_cap.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-GH219-LANE2 --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH219-LANE2 --agent agy --to codex
4. Edit ONLY these paths: phases/gh219-lane2-mlx-cache-cap/RELAY.md and src/rebalance/ingest/embedder.py,src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/github_knowledge.py,tests/test_mlx_cache_cap.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/ingest/embedder.py,src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/github_knowledge.py,tests/test_mlx_cache_cap.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH219-LANE2 --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-GH219-LANE2 --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh219-lane2-mlx-cache-cap/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
