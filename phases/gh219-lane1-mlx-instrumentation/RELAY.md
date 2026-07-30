# Marathon Phase gh219-lane1-mlx-instrumentation
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-GH219-LANE1 builder=agy reviewer=codex round-cap=5 -->

## Phase Brief

# Lane 1 (GH-219 marathon) — #216: MLX memory instrumentation — measure before remedy

## Context

A Mac Studio (64 GB) suffered three whole-machine memory-starvation events (07-25, 07-26, 07-27).
On 07-27 a single `rebalance-embed` process reached **~46.9 GB `phys_footprint` while reporting
~0.08 GB RSS**, and the machine hit `free` 0.09 GB / compressor 28.99 GB / swap 24.7 of 26 GB.

The working hypothesis: the embedding backend is **MLX**, which allocates Metal buffers charged to
`phys_footprint` as `iokit` and **never counted in RSS**, and caches freed buffers with an
effectively unbounded default limit. The repo performs **no MLX cache management anywhere** —
`mx.clear_cache`, `mx.set_cache_limit`, `mx.set_memory_limit`, `mx.get_active_memory`,
`mx.get_cache_memory`, `mx.get_peak_memory` have **zero usages** in the tree.

**This hypothesis is INFERRED, not PROVEN. `mx.get_cache_memory()` has never been sampled during a
live run.** This lane exists to settle it with data. It has already survived two misdiagnoses;
do not treat it as established.

**Your deliverable is the instrumentation code, NOT the verdict.** A sandboxed shell has no Metal
device, so the CONFIRMED/REFUTED call happens later, when a real embedding pass runs on real
hardware. Build the measurement; do not fabricate or infer readings.

## The four call sites (a preflight correction — the issue text says two)

Every caller of `_load_model()` / `_embed_batch()`:

| # | Site | Guard status |
|---|---|---|
| 1 | `src/rebalance/ingest/embedder.py:105` `embed_chunks` | `@guarded_embedding` |
| 2 | `src/rebalance/ingest/semantic_index.py:613` `embed_pending` | `@guarded_embedding` |
| 3 | `src/rebalance/ingest/embedder.py:216` `query_similar` (`_load_model`/`_embed_batch` at `:227-228`) | **UNGUARDED** |
| 4 | `src/rebalance/ingest/github_knowledge.py:855` `_default_embed_texts` (`:855-856`) | **UNGUARDED** — the module never imports the guard |

Sites 3 and 4 are a live candidate explanation for this project's sharpest open question: **2 of
the 3 episodes on 07-27 have no `job_rss.jsonl` record at all.** An unguarded path produces exactly
that signature. Instrument all four or the question stays unanswerable by construction.

## Required work

**MLX telemetry** — at the shared allocation helpers (`_embed_batch` / `_load_model` in
`embedder.py`), so all four sites inherit it rather than each growing its own copy:

- Log `mx.get_active_memory()`, `mx.get_cache_memory()`, `mx.get_peak_memory()` every N batches
- Call `mx.reset_peak_memory()` once per pass so peaks are attributable to a single run
- **Reuse an existing log surface. Do not invent a new one.**
- Overhead must be negligible — these are counter reads, not allocations

**Attribution — the part that makes the unattributed episodes solvable:**

- Emit an **invocation-wide run ID** and a **PID → entry-point record** on every embedding pass:
  which caller (launchd job / CLI / MCP tool / agent / interactive shell), which of the four sites,
  which PID
- Without this, no amount of per-batch MLX telemetry can attribute an episode after the fact

**Sampler columns — NOT in this phase.** Adding `inactive_gb`/`speculative_gb` to
`temp/memory-issues/sys-mem-attribute.py` is deliberately excluded: `temp/` is gitignored
(`.gitignore:4`), so an edit made in this phase's isolated worktree could not be committed and
would be **destroyed** when the worktree is torn down. It is handled separately, outside the
marathon. Do not touch anything under `temp/`.

## Write-set (do not edit anything else)

- `src/rebalance/ingest/embedder.py`
- `src/rebalance/ingest/semantic_index.py`
- `src/rebalance/ingest/github_knowledge.py`
- `tests/test_mlx_instrumentation.py` (new)

## Tests — required

MLX is not importable in CI and there is no Metal device in a sandbox, so **mock `mlx.core`**.
`tests/test_dashboard_refresh_integration.py:24` already has a `_fake_embed_batch` pattern to
follow. Cover:

1. Telemetry is emitted at the expected cadence, with the expected keys
2. `reset_peak_memory` is called once per pass, not per batch
3. Every one of the four call sites produces a run-ID + entry-point + PID record
4. Instrumentation degrades safely when MLX is absent — **it must not become a new crash path**
   (an embedding pipeline that dies because telemetry failed is strictly worse than the leak)

## Acceptance

- `.venv/bin/python3 -m pytest tests/ -q` passes with no regressions
- A full pass emits MLX figures plus run-ID/entry-point attribution at negligible overhead
- All four call sites are covered — verifiable by grep, not by assertion

## Explicitly NOT in this lane

- **Do not add `mx.clear_cache()` or `mx.set_cache_limit()`.** That is Lane 2, and it is gated
  behind this lane's measurement. Landing the remedy now destroys the ability to confirm the
  diagnosis — you would be measuring a system you already changed.
- Do not add `mx.set_memory_limit()` (Lane 3)
- Do not touch `utils/job_guard.py` (Lane 4)
- Do not add guards to the two unguarded sites (Lane 6) — **instrument** them, don't fix them
- No embedding-pipeline redesign, model change, or throughput optimisation


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/ingest/embedder.py,src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/github_knowledge.py,tests/test_mlx_instrumentation.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-GH219-LANE1 --agent agy --paths "phases/gh219-lane1-mlx-instrumentation/RELAY.md,src/rebalance/ingest/embedder.py,src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/github_knowledge.py,tests/test_mlx_instrumentation.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-GH219-LANE1 --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH219-LANE1 --agent agy --to codex
4. Edit ONLY these paths: phases/gh219-lane1-mlx-instrumentation/RELAY.md and src/rebalance/ingest/embedder.py,src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/github_knowledge.py,tests/test_mlx_instrumentation.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/ingest/embedder.py,src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/github_knowledge.py,tests/test_mlx_instrumentation.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH219-LANE1 --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-GH219-LANE1 --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh219-lane1-mlx-instrumentation/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
