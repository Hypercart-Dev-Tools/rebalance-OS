---
title: MARATHON — 2026-07-27 (5 lanes — MLX embedding memory: instrument → measure → fix → bound → backstop)
status: "Planned, not fired. All 5 lanes captured and parked 2026-07-27; no code written."
created: 2026-07-27
updated: 2026-07-27
owner: noel@neochro.me
branch: marathon/2026-07-27-mlx-memory
roadmap_exempt: true
goal: >
  End the recurring whole-machine memory starvation on the Mac Studio (three events: 07-25,
  07-26, 07-27) by fixing the allocation that causes it, bounding the damage when that fix is
  wrong, and repairing the two instruments that failed to see it.

  Root cause, identified 2026-07-27: the embedding backend is MLX, not torch. MLX allocates
  Metal buffers charged to `phys_footprint` as `iokit` and never counted in RSS, caches freed
  buffers with an effectively unbounded default limit, and the repo performs no MLX cache
  management anywhere. A single `rebalance-embed` process reaches ~46.9 GB footprint while
  reporting ~0.08 GB RSS.

  This file exists because the five issues are NOT independent: #216 produces the measurement
  that validates #215, #217 must be sized from #216's numbers, #213's ceiling only means the
  right thing once footprint semantics are settled, and #218 repairs the health instrument the
  marathon itself uses as a gate. Firing them in issue-number order would be actively wrong.
---

# MARATHON 2026-07-27 — MLX embedding memory

## Why these five, and why in this order

The sequence is **instrument → measure → fix → bound → backstop**. Each lane exists to make the
next one verifiable rather than argued.

The ordering constraint is real, not stylistic:

- **#215 is currently INFERRED, not PROVEN.** `mx.get_cache_memory()` has never been sampled
  during a live run — no Metal device is reachable from a sandboxed shell. Landing the fix before
  the measurement means shipping a remedy that cannot be confirmed, for a bug that has already
  survived two misdiagnoses.
- **#217's limit must be sized from data.** A guessed ceiling that fails legitimate passes is how
  safety mechanisms get switched off by the person they annoy.
- **#213's ceiling changes meaning** once it reads footprint instead of RSS — footprint
  legitimately includes Metal, so the existing 35%-of-RAM value is not transferable unexamined.
- **#218 comes first because the marathon leans on `doctor` as a gate**, and doctor currently
  lies about scheduler state in restricted shells. It already cost this investigation a false
  lead. Fix the instrument before using it to certify the work.

## Lane sequencing

| Order | Issue | Lane | Write-set | Depends on |
|---|---|---|---|---|
| 0 | [#218](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/218) | C (parallel) | `src/rebalance/doctor.py` | — |
| 1 | [#216](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/216) | A | `embedder.py`, `semantic_index.py`, `temp/memory-issues/sys-mem-watch.sh` | — |
| 2 | [#215](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/215) | A | `embedder.py`, `semantic_index.py` | #216 |
| 3 | [#217](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/217) | A | `embedder.py`, `ingest/_job_guard.py` | #216, #215 |
| 4 | [#213](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/213) | B | `utils/job_guard.py` | #215 |

**Collision analysis.** Lane A's three issues all write `embedder.py` and must run strictly
sequentially in one lane — they cannot be parallelised. Lane B (`utils/job_guard.py`) and Lane C
(`doctor.py`) are path-disjoint from Lane A and from each other, so C may run concurrently
throughout and B may start once #215 lands. Note `ingest/_job_guard.py` (the bridge, Lane A) and
`utils/job_guard.py` (the guard, Lane B) are **different files** — no collision, despite the
names.

---

## Lane 0 — #218 · doctor's launchctl false negative

**Goal:** stop doctor reporting a working scheduler fleet as entirely missing.

- [ ] Treat non-zero `returncode` as unavailable (`doctor.py:502-510`)
- [ ] Treat empty/whitespace-only stdout as unavailable, not "zero jobs loaded"
- [ ] Emit exactly one "scheduler state undetermined" finding; **zero** per-job warnings
- [ ] Regression test: available+loaded, available+genuinely missing, unavailable

**Gate:** on a healthy device, zero `scheduler:*` warnings; in a restricted shell, one honest
undetermined line and no reinstall advice.

→ [GH-218-DOCTOR-LAUNCHCTL-FALSE-NEGATIVE.md](../1-INBOX/GH-218-DOCTOR-LAUNCHCTL-FALSE-NEGATIVE.md)

---

## Lane 1 — #216 · MLX instrumentation (measure before remedy)

**Goal:** make the dominant memory consumer observable, and settle #215's hypothesis with data.

- [ ] Log `mx.get_active_memory()` / `get_cache_memory()` / `get_peak_memory()` every N batches
- [ ] `mx.reset_peak_memory()` per pass so figures are attributable to a run
- [ ] Reuse an existing log surface; do not invent a new one
- [ ] Add `inactive_gb` + `speculative_gb` to `sys-mem-watch.sh`
- [ ] **Confirm or refute #215 in writing** in `temp/memory-issues/TRIAGE-LOG.md`

**Gate:** a full pass emits MLX figures at negligible overhead, and the root cause is settled
either way. A flat cache with rising active memory *refutes* #215 and redirects Lane 2 — that is
a success outcome for this lane, not a failure.

→ [GH-216-MLX-MEMORY-INSTRUMENTATION.md](../1-INBOX/GH-216-MLX-MEMORY-INSTRUMENTATION.md)

---

## Lane 2 — #215 · cap and clear the MLX buffer cache (the fix)

**Goal:** stop the allocation. Blocked on Lane 1's verdict.

- [ ] `mx.set_cache_limit(...)` once at embedding-module level, sized deliberately
- [ ] `mx.clear_cache()` at the end of each batch iteration (`embedder.py:172-186`)
- [ ] Apply to **both** leaves (`embedder.py:105`, `semantic_index.py:613`) — they share one lock
      and one model per `_job_guard.py` "Lock scoping"
- [ ] Measure throughput before/after; record any regression rather than hiding it

**Gate:** a full pass holds peak `phys_footprint` under an explicit documented bound; `free_gb`
never approaches zero; compressor stays single-digit GB.

→ [GH-215-MLX-EMBED-CACHE-LEAK.md](../1-INBOX/GH-215-MLX-EMBED-CACHE-LEAK.md)

---

## Lane 3 — #217 · hard MLX memory limit (bound the damage)

**Goal:** a runaway pass fails the job, not the machine. Sized from Lane 1's numbers.

- [ ] `mx.set_memory_limit(<bytes>)` at embedding-module import
- [ ] Size as a **fraction of physical RAM**, matching `job_guard.py`'s
      `DEFAULT_MAX_RSS_FRACTION = 0.35` convention — do not hardcode 64 GB
- [ ] Environment-overridable, consistent with `REBALANCE_JOB_GUARD_MAX_RSS_GB`
- [ ] Failure surfaces as a clean error naming the limit, the pass, and the batch
- [ ] **Verify the `rebalance-embed` flock is released on the failure path** and a subsequent run
      starts normally (`README.md:254` documents an existing "already running" mode — do not
      trade a memory blowup for a permanently stuck lock)

**Gate:** an over-limit pass fails cleanly and attributably; `free_gb` never approaches zero
during that failure; the next run starts.

→ [GH-217-MLX-HARD-MEMORY-LIMIT.md](../1-INBOX/GH-217-MLX-HARD-MEMORY-LIMIT.md)

---

## Lane 4 — #213 · guard backstop, RSS → footprint

**Goal:** repair the external net. Demoted from "the fix" to "the backstop" by #215.

- [ ] Switch the ceiling metric from tree RSS to `phys_footprint`
- [ ] **Re-size the ceiling** knowing footprint legitimately includes Metal — the current
      35%-of-RAM value is not transferable unexamined
- [ ] Settle whether the available-memory floor is sound, using Lane 1's new
      `inactive_gb`/`speculative_gb` columns

**Gate:** a synthetic over-ceiling job trips and is killed; guarded jobs on a healthy machine do
not trip.

**Carried finding — not a blocker:** the guard's window is far shorter than the leak's.
`guarded_embedding` decorates embedding *leaf* functions, so each call builds a fresh
`MemoryCeiling` with `peak_rss = 0` (PID 1391 wrote three records — 10.7 s / 1.5 s / 35.6 s —
across a 35-minute lifetime). This does **not** block the footprint switch, because footprint is
absolute per-process and a later leaf call reads the accumulated total. It does mean
`job_rss.jsonl` can never show cumulative growth, which is Lane 1's job instead.

→ [GH-213-MEMORY-PRESSURE-DEFENCE.md](../1-INBOX/GH-213-MEMORY-PRESSURE-DEFENCE.md)

---

## Marathon-level acceptance

- [ ] A full working day with **zero** episodes above the documented footprint bound
- [ ] `free_gb` never approaches zero; compressor stays single-digit GB
- [ ] `rebalance doctor` reports scheduler state honestly in both restricted and normal shells
- [ ] The root cause is recorded as **PROVEN or REFUTED** in `TRIAGE-LOG.md`, not left INFERRED
- [ ] Embedding throughput regression, if any, is measured and written down

## Open questions carried into the marathon

- **Only 1 of 3 episodes on 07-27 is confirmed as `rebalance-embed`.** PID 1391 is attributed by
  the guard's own log. PIDs 16871 (01:04) and 2886 (08:21) match on binary, peak (~46.9 GB) and
  RSS profile but have **no `job_rss.jsonl` record at all** — despite `record_peak_rss` being
  documented (`job_guard.py:614-616`) as writing on every exit path. Either they ran unguarded, or
  the guard died without recording. Lane 1 should resolve this; if those episodes are a *second*
  path to the same allocation, Lane 2's fix is incomplete.
- **The episode interval is collapsing** — 01:04, 07:09, 08:21 on 07-27 (gaps ~6 h then ~1 h 12 m)
  against roughly one per day previously. Cause unknown; may simply track vault-sync's hourly
  cadence plus agent/MCP-triggered runs.
- **Embedding passes have many entry points** — launchd, CLI, MCP tool, agent, interactive shell
  (`_job_guard.py:12-17`, the GH-172 finding that put the guard at library leaves). Any fix that
  assumes launchd-only triggering is wrong.

## Evidence

`temp/memory-issues/TRIAGE-LOG.md`, entry `2026-07-27` — full forensics with PROVEN / INFERRED /
UNRESOLVED tags. Note `temp/` is gitignored, so that log is device-local to the Mac Studio.
