# GH-215 — MLX embedding cache leak (the 46.9 GB root cause)

> Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/215
> Status: **proposed** — root cause identified 2026-07-27, fix not yet attempted.

**Component**: `src/rebalance/ingest/embedder.py`, `src/rebalance/ingest/semantic_index.py`

## Why

Three memory events on this Mac Studio (07-25, 07-26, 07-27) all trace to one process shape:
`rebalance-embed` grows to **~46.9 GB `phys_footprint`** while reporting **~0.1 GB RSS**, then the
machine runs out of free RAM and starts thrashing the compressor and swap.

Prior work (#213) framed this as a *guard* problem — the watchdog reads RSS and never trips. That
framing is correct but incomplete, and it put the effort in the wrong place. The guard is the net.
This is the bug.

## Key concepts

**MLX allocates Metal, and Metal is not RSS.** The embedding backend is MLX, not torch/MPS
(`embedder.py:65-74` imports `mlx.core` and `mlx_embeddings.generate`). MLX allocates Metal
buffers, charged to `phys_footprint` as `iokit` and **never counted in RSS**. This one fact
dissolves the whole "46.9 GB vs 73 MB" mystery: the memory is real and resident, just not in the
bucket every existing instrument reads.

**MLX caches freed buffers and does not return them.** Its default cache limit is effectively the
memory limit — unbounded in practice. The repo does **no** MLX cache management: `mx.clear_cache`,
`mx.set_cache_limit`, `mx.set_memory_limit` all exist in the installed MLX 0.31.2 and appear
**zero times** across `src/` and `utils/`.

**It is per-batch accumulation, not model reloading.** `_load_model` (`embedder.py:51-62`) caches
the model correctly. The growth is in the batch loop (`embedder.py:172-186`), which embeds 32
chunks per iteration and never releases the cache between iterations.

## Triage

| Axis | Rating | Note |
|---|---|---|
| Severity | **High** | Repeated whole-machine starvation; two prior stalls |
| Confidence | **High (inferred)** | `mx.get_cache_memory()` not yet sampled live — see #216 |
| Cost | **Low** | Order of a few lines, plus tuning |
| Blast radius | **Medium** | Touches both embedding leaves; may trade throughput for headroom |

## Phases

### Phase 1 — bound the cache
- [ ] `mx.set_cache_limit(...)` once at embedding-module level, sized deliberately
- [ ] `mx.clear_cache()` at the end of each batch iteration in `embed_chunks`
- [ ] Apply to both leaves (`embedder.py:105`, `semantic_index.py:613`) — they share one lock and
      one model per `_job_guard.py` "Lock scoping"
- [ ] Land alongside #216 so the fix is verified, not assumed

### Phase 2 — verify against real load
- [ ] Full embedding pass; peak `phys_footprint` stays under an explicit documented bound
- [ ] `free_gb` does not approach zero; compressor stays single-digit GB
- [ ] Throughput measured before/after; any regression recorded, not hidden

### Phase 3 — tune and document
- [ ] Choose the cap from measured data rather than the initial guess
- [ ] Document the chosen value and the reasoning where the next person will find it

## Anti-goals

- Not a rewrite of the embedding pipeline.
- Not a fix to `job_guard.py` — that is #213.
- Not a hard memory ceiling — that is #217.

## Evidence

Full forensic write-up with quoted PROVEN/INFERRED evidence:
`temp/memory-issues/TRIAGE-LOG.md`, entry `2026-07-27`. Note that `temp/` is gitignored, so that
log is device-local to the Mac Studio.

Headline figures: PID 1391 at 46,932.2 MB footprint / 73.2 MB RSS (07:09–07:44); free RAM 0.09 GB
with compressor 28.99 GB and swap 24.7/26 GB at 07:44:40; guard ran 233 jobs that day and tripped
zero times.

## Related

- #213 — guard-side defence (RSS → footprint). The backstop.
- #216 — MLX instrumentation. Proves or refutes this issue's hypothesis.
- #217 — hard MLX memory limit. Bounds the damage if this fix is wrong.
