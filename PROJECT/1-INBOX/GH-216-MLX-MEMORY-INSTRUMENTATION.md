# GH-216 — MLX memory instrumentation

> Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/216
> Status: **proposed** — captured 2026-07-27.

**Component**: `src/rebalance/ingest/embedder.py`, `src/rebalance/ingest/semantic_index.py`,
`temp/memory-issues/sys-mem-watch.sh`

## Why

The largest memory consumer on this machine is invisible to every instrument we own. Three
separate memory events were investigated after the fact, from external samplers, and the
responsible allocation was only identified on the third attempt — by reading source, not by
reading telemetry.

The #215 root cause is well-supported but **inferred**: `mx.get_cache_memory()` has never been
sampled during a live run, because no Metal device is reachable from a sandboxed shell. It must be
measured from inside the job. Landing #215 without this means shipping a fix we cannot confirm.

## Key concepts

**Three independent blind spots stack here.**

1. *RSS instruments cannot see it.* MLX Metal buffers are `iokit` in `phys_footprint`, never RSS.
   `job_guard.py` logged `peak_rss_gb: 0.232` for a process an external sampler simultaneously
   measured at 46.9 GB.
2. *The guard's window is shorter than the leak's.* `guarded_embedding`
   (`_job_guard.py:167-180`) decorates embedding *leaf* functions, so each call builds a fresh
   `MemoryCeiling` with `peak_rss = 0`. PID 1391 wrote three records (10.7 s / 1.5 s / 35.6 s)
   across a 35-minute lifetime. Cumulative growth cannot appear in that log by construction.
3. *The external sampler is coarse.* `~/Library/Logs/sysmem/` samples at 60 s and attributes per
   process — it can say a Python process grew, never which allocation grew.

**The measurement is decisive either way.** A monotonic climb in `get_cache_memory()` toward
~46.9 GB confirms #215. A flat cache with rising `get_active_memory()` refutes it and redirects
the fix. That is worth having before committing to a remedy.

## Triage

| Axis | Rating | Note |
|---|---|---|
| Severity | Medium | No user-visible defect; blocks confident remediation |
| Confidence | High | The APIs exist and are trivially callable |
| Cost | Low | Telemetry only, no behaviour change |
| Blast radius | Low | Additive; must stay cheap inside the batch loop |

## Phases

### Phase 1 — MLX telemetry in the batch loop
- [ ] Record `mx.get_active_memory()`, `mx.get_cache_memory()`, `mx.get_peak_memory()`
- [ ] Emit every N batches, not every 32-chunk iteration — overhead must stay negligible
- [ ] `mx.reset_peak_memory()` per pass so figures are attributable to a run
- [ ] Reuse an existing log surface; do not invent a new one

### Phase 2 — settle the #215 hypothesis
- [ ] Run a full pass and read the numbers
- [ ] Confirm or refute unbounded cache growth **in writing**, in the triage log
- [ ] If refuted, redirect #215 rather than closing it silently

### Phase 3 — close the floor-audit gap
- [ ] Add `inactive_gb` and `speculative_gb` to `sys-mem-watch.sh`
- [ ] Verify the guard's available-memory floor can now be reconstructed after an event

## The floor-audit gap, stated plainly

`sys-mem-watch.sh` records `free_gb` but not `inactive_gb` / `speculative_gb`. The guard's
available-memory floor computes `free + inactive + speculative` (`utils/job_guard.py:155-184`).
At 07:44:40 free RAM was 0.09 GB against a 7.68 GB floor — and yet **we cannot say whether that
floor should have tripped**, because the two terms that would settle it were never recorded.

It is neither exonerated nor convicted. It is unmeasured. That matters more than it first looks:
the floor is the half of the guard that does *not* depend on per-process accounting, and is
therefore the half most likely to still be sound.

## Anti-goals

- Not a new monitoring subsystem, dashboard, or alerting path. #213 already argues against that,
  and the argument holds.
- Not a change to embedding behaviour.

## Related

- #215 — root cause this instrumentation is designed to prove or refute.
- #217 — hard MLX memory limit.
- #213 — guard-side defence.
