# GH-217 — Hard MLX memory limit (fail the job, not the machine)

> Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/217
> Status: **proposed** — captured 2026-07-27.

**Component**: `src/rebalance/ingest/embedder.py`, `src/rebalance/ingest/_job_guard.py`

## Why

In all three memory events the **machine** absorbed the damage, never the job. On 07-27 free RAM
reached 0.09 GB with the compressor at 28.99 GB and swap at 24.7 / 26 GB. The two 07-27 episodes
self-recovered only because the process happened to exit on its own; 07-25 and 07-26 did not.

On that same day `job_guard.py` ran **233 guarded jobs and tripped zero times** — it keys on RSS,
and MLX Metal buffers are `iokit` in `phys_footprint`, never RSS.

So every containment mechanism protecting this machine is either external to the process or
reading the wrong number. `mx.set_memory_limit()` closes that gap from the inside, in the one
component that actually knows how much Metal memory has been requested: MLX itself.

## Key concepts

**Redundancy here is the point, not waste.** #215 fixes *why* memory grows. This bounds *how bad
it can get* when that fix is wrong, incomplete, or regressed by a later change. The 07-27 data is
a direct argument for defence in depth: three consecutive incidents got through precisely because
a single line of defence keyed on a single metric.

**Independent of the #215 hypothesis.** #215 is inferred pending #216's measurement. This issue
holds regardless of what that measurement shows, because it constrains the outcome rather than the
cause.

**A limit that wedges the next run is not a fix.** The failure path has to release the
`rebalance-embed` flock. `README.md:254` already documents an "already running" failure mode;
turning a memory blowup into a permanently stuck lock trades one incident for a worse one.

## Triage

| Axis | Rating | Note |
|---|---|---|
| Severity | Medium-High | Bounds a whole-machine failure to a single job failure |
| Confidence | High | Mechanism is a documented MLX API, not a hypothesis |
| Cost | Low | One call plus error handling |
| Blast radius | Medium | A too-tight limit fails legitimate passes — needs sizing from data |

## Phases

### Phase 1 — set the limit
- [ ] `mx.set_memory_limit(<bytes>)` at embedding-module import
- [ ] Size as a fraction of physical RAM, matching `job_guard.py`'s existing
      `DEFAULT_MAX_RSS_FRACTION = 0.35` convention rather than hardcoding 64 GB assumptions
- [ ] Environment-overridable, consistent with `REBALANCE_JOB_GUARD_MAX_RSS_GB`

### Phase 2 — make the failure legible and safe
- [ ] MLX allocation failure surfaces as a clean error naming the limit, the pass, and the batch
- [ ] Verify the `rebalance-embed` flock is released on the failure path
- [ ] Verify a subsequent run starts normally after a limit-triggered failure

### Phase 3 — size it from evidence
- [ ] Set the final value from #216's measured figures, not from the initial guess
- [ ] Document the value and reasoning

## Ordering

Land **after** #215 (root cause) and ideally after #216 has produced real numbers to size against.
Landing it first would work, but the limit would be guessed rather than derived — and a guessed
ceiling that fails legitimate passes is how safety mechanisms get disabled.

## Anti-goals

- Not a replacement for #215. A ceiling that stops a leak is not a fixed leak.
- Not a replacement for #213's guard work.
- Not a retry/backoff mechanism — failing cleanly is the goal here.

## Related

- #215 — root cause. Should land first.
- #216 — instrumentation; supplies the data to size this limit.
- #213 — guard-side RSS → footprint; the external backstop, its ceiling should be sized knowing
  footprint legitimately includes Metal.
