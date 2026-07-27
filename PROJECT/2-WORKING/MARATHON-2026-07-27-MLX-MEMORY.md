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

## Regression archaeology — what changed in the last 7 days

The first version of this plan did **no** regression analysis. That was a gap: three events
starting 07-25 on a machine that had been fine invites the question "what changed?", and the plan
went straight to mechanism without asking it. Bounded first pass, run 2026-07-27:

**Ruled out (PROVEN, negative results):**

- **No code regression.** Zero commits in the last 7 days touch `embedder.py`,
  `semantic_index.py`, `ingest/_job_guard.py`, `utils/job_guard.py`, or `doctor.py`. 44 commits
  landed in the window; exactly one touched `src/rebalance/ingest/` or `scripts/` at all
  (`0d4b6f0`, 07-23, Anthropic→Gemini key removal).
- **No dependency change.** MLX 0.31.2 and `mlx_embeddings` 0.1.0 were installed **2026-04-24**.
  MLX has been in the tree since March. The allocation behaviour is not newly introduced.

These negatives matter: they eliminate the two most common explanations and **narrow** the
remaining search rather than widening it. The cause is data, configuration, schedule, or load —
not a recent edit to the embedding path.

**Live candidates (INFERRED, not yet tested):**

- **The 3-Eyes fleet rollout, 2026-07-22** — ~12 commits landing `skill-sync`, `selfcheck`,
  `collector-health` and a machine-local registry overlay. The single largest change in the
  window, and 3 days before the first event. `3eyes.skill-sync` now runs **every 120 s** (216
  executions on 07-27 alone). Its own memory is trivial (peak RSS 0.010 GB), so it is not the hog
  — but whether it *triggers* embedding work, or contends with it, is untested.
- **Both scheduler plists were rewritten 2026-07-20 08:16:11** (`vault-sync`, `daily-sync`). The
  fleet was reinstalled 7 days ago. Whether cadence changed at that point is not yet established
  — the current cadence (`vault-sync` hourly at :15, 06:00–23:00) needs comparing against the
  pre-07-20 plists.
- **Corpus growth.** Not yet measured. Both tracked databases (`rebalance.db`,
  `temp/rebalance.ask.db`) are stale from June, so the live embedding index is elsewhere on this
  device and was not located in this pass. Finding it is a prerequisite for testing this
  hypothesis at all.

**This archaeology is deliberately bounded.** It runs as Lane 0.5 below with a hard timebox. If
the cause is not found inside that box, the marathon proceeds anyway — because #215's fix bounds
the allocation regardless of what started it. Knowing the trigger is valuable; it is not a
prerequisite for stopping the bleeding.

## Lane sequencing

| Order | Issue | Lane | Write-set | Depends on |
|---|---|---|---|---|
| 0 | [#218](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/218) | C (parallel) | `src/rebalance/doctor.py` | — |
| 0.5 | archaeology (no issue) | D (parallel, **timeboxed**) | read-only | — |
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

## Lane 0.5 — regression archaeology (read-only, **hard timebox**)

**Goal:** find what changed around 07-25, or establish within a fixed budget that it cannot be
found cheaply. No issue; no code changes; read-only.

- [ ] Locate the **live** embedding index on this device (both tracked DBs are stale from June)
- [ ] Measure corpus size and its growth across the last 14 days
- [ ] Diff the pre-/post-07-20 `vault-sync` and `daily-sync` plists — did cadence change?
- [ ] Test whether the 07-22 3-Eyes jobs trigger or contend with embedding work
- [ ] Record the verdict in `TRIAGE-LOG.md` — including "not found within budget", which is a
      legitimate and reportable outcome

**Timebox: 90 minutes.** On expiry, write down what was eliminated and **stop**. Do not extend.

**Explicitly not a blocker.** Lanes 1–4 proceed regardless. #215 bounds the allocation whatever
started it; archaeology only tells us whether something *else* also needs changing. If this lane
finds nothing, the marathon still delivers its acceptance criteria.

→ findings land in `temp/memory-issues/TRIAGE-LOG.md` (device-local)

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

## Scope discipline — what "70–80%" means here, and how this ends

**The 70–80% is one number: peak `phys_footprint` during an embedding pass.** Today it is
~46.9 GB against 64 GB of RAM, three times a day. If Lanes 1–2 land and that peak sits under an
explicit documented bound with `free_gb` never approaching zero, the problem is solved for
practical purposes — regardless of how many adjacent imperfections remain. Lanes 3–4 exist so a
*recurrence* is caught automatically rather than by the operator noticing Activity Monitor again.

**This marathon is scoped to the memory blowup and the two instruments that hid it.** It is
explicitly **not** a general audit of this device's launchd / auto-loading fleet. That honest
boundary matters, because "Rebalance auto-loading script problems" is a wider surface than what is
planned here.

**Out of scope — named, so they cannot creep in:**

- General launchd fleet health beyond #218's specific false-negative path
- The `figma: last refresh advanced 46d` warning (unrelated, pre-existing)
- The `deep work` / `commit coverage` doctor warnings (pre-existing, separate signals)
- Rewriting the scheduler policy table or `SCHEDULER.md`
- Any embedding-pipeline redesign, model change, or throughput optimisation
- The `temp/` gitignore question — device-local logs are fine for now, deliberately deferred
- Making the sampler cross-device

**Stopping rule.** The marathon is done when the acceptance list below passes, even if:

- Lane 0.5 never identifies what changed on 07-25
- The 2 of 3 unattributed episodes remain unattributed **and no new episodes occur**
- Adjacent doctor warnings are still present

**The one finding that legitimately reopens scope:** if Lane 1's instrumentation shows a second,
non-embedding path reaching a comparable footprint. That would mean #215 fixes only part of the
allocation, and the peak — the actual acceptance number — would not come down. Nothing else on
the open-questions list justifies extending this effort.

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
