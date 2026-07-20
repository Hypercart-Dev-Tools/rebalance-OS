---
title: Hard kernel panic — unbounded concurrent embedding runs exhausted memory (90 GB on a 68.7 GB machine)
status: "Fixed — guard built in PR #174, wired to the embedding leaves in PR #181, merged to development 2026-07-20"
gh_issue: 172
created: 2026-07-19
updated: 2026-07-20
branch: development
supersedes: []
synthesizes: []
goal: >
  On 2026-07-19 15:43:46 PDT the Mac Studio hard kernel-panicked with an AppleARMWatchdogTimer
  timeout after 4.91 days uptime. Root cause: three concurrent Python embedding processes held
  ~90 GB resident on a 68.7 GB machine, saturating the VM compressor until watchdogd was starved
  for 90s. Nothing in the embedding stack prevented concurrent invocation and nothing aborted
  before the compressor cliff. Fix is a single-instance lock plus an in-process memory ceiling,
  applied at the library leaves so it covers agent-spawned runs, not just launchd ones.
---

# Embedding job guard (GH-172)

## Contents
- [Symptom](#symptom)
- [Root cause (proven)](#root-cause-proven)
- [Attribution — and the correction](#attribution--and-the-correction)
- [Fix — implemented](#fix--implemented)
- [What did NOT fix it](#what-did-not-fix-it)
- [Verification](#verification)
- [Follow-on work](#follow-on-work)

## Symptom

Full machine lockup and kernel panic, 2026-07-19 15:43:46 PDT. Previous boot 2026-07-14 17:53:22,
so 4.91 days uptime lost. The operator was re-running local Qwen embeddings at the time.

```
panic(cpu 0): watchdog timeout: no checkins from watchdogd in 90 seconds
Compressor Info: 26% of compressed pages limit (OK) and
                 100% of segments limit (BAD) with 74 swapfiles
```

## Root cause (proven)

`JetsamEvent-2026-07-19-153519.ips` and `-153811.ips`, fired 8 and 5 minutes before the panic,
name the culprits directly:

| Resident | Process | PID |
|---:|---|---|
| 45.86 GB | Python | 91023 |
| 35.78 GB | Python | 72027 |
| 9.20 GB | Python | 22186 |

Physical RAM 68.7 GB; Python alone ~90.8 GB; total resident across 7009 processes 157.04 GB —
roughly 2.3x physical. That is what drives the compressor to 100% of its segment limit and spawns
74 swapfiles. `kernel_task` then consumed both top CPU slots doing compression work, starving
`watchdogd` past its 90s threshold.

**Rising PIDs (22186 < 72027 < 91023) mean the three runs stacked rather than replaced.** Each new
run began while the previous was still resident — exactly the "re-running the embeddings" flow.
Nothing enforced single-instance: no lock, no PID file, no advisory flock anywhere in either
embedding stack.

The watchdog timeout is the *symptom*. The machine did not hang; it thrashed until the kernel shot
itself.

## Attribution — and the correction

The first RCA filed on this issue blamed the ask_self ingest stack. **That was wrong and was
corrected in-issue before any code was written.** The evidence:

- **ask_self ruled out** — it runs Gemini (`gemini-embedding-001`, dim 768) since `4ef8c39`, its
  index/cache/event-log were last written 2026-07-02, and it emits `embed.start` per chunk, so a
  partial run would have left a trail. It left none.
- **cognee ruled out** — `~/.cognee` last written 10:33 that day, 20 KB total, outside the window.
- **Not shell-launched** — zero embed invocations in `~/.zsh_history`; PID 22186 sits adjacent to
  22163, a Claude session PID. The runs were **agent-spawned**.

The actual path is the **HiQS signal / activity RAG** — `src/rebalance/ingest/embedder.py`,
`Qwen/Qwen3-Embedding-0.6B` via MLX, dim 1024. It commits per batch, so a run that ballooned and
died before its first commit leaves *no disk trace at all*, which is why no embedding artifact was
written despite 90 GB of resident Python.

Two independent embedding systems existed and had been conflated. That conflation is the reason
attribution took several rounds, and is now documented explicitly in `MEMORY.md`.

## Fix — implemented

`utils/job_guard.py` (PR #174) supplies two primitives, stdlib-only so it also runs under system
`python3` in launchd wrappers:

1. **`SingleInstanceLock`** — advisory `flock`; a second run refuses (default) or replaces the
   incumbent. Kernel-released, so a killed job never leaves a blocking lock.
2. **`MemoryCeiling`** — watchdog thread sampling process-tree RSS *and* system-available memory,
   aborting cleanly (SIGTERM → SIGKILL after grace) before the compressor saturates. Also a
   `preflight()` that refuses to start on an already-starved machine.

**PR #174 shipped this with zero callers.** The crash path stayed open for a day. PR #181 wired it:

- Guard applied at the **library leaves** — `embed_chunks` (vault) and `embed_pending` (semantic) —
  via a `guarded_embedding` decorator in `src/rebalance/ingest/_job_guard.py`.
- **Leaves, not launchd wrappers**, because the causing run was agent-spawned. Every caller now
  funnels through the guard: launchd, CLI, MCP, agents, interactive shells.
- **One shared lock** across both leaves; they load the same model, so memory cost is cumulative
  and they must serialise against each other.
- **Facades deliberately unguarded** (`embed_vault_chunks`, `embed_semantic_pending`) — they
  delegate to the leaves, and guarding both layers would take the same `flock` twice in one process
  and self-deadlock, since `flock` is keyed on the open file description.
- **Fails open with a loud warning** if the module is missing, rather than blocking ingest.

## What did NOT fix it

Recorded because each was proposed and rejected on evidence:

- **`HardResourceLimits` in plists** — `RLIMIT_RSS` is defined but **not enforced** on Darwin.
  Verified: `ulimit -m 102400` → `cannot modify limit: Invalid argument`, and a process allocated
  300 MB unimpeded under a nominal 100 MB cap. Would have produced jobs that look bounded under
  review and are not. Struck from GH-175.
- **`Nice` on batch jobs** — `watchdogd` was starved by `kernel_task` compression work, not by
  user-process CPU contention. Kept as responsiveness hygiene; the GH-172 justification was dropped.
- **App Tamer** — throttles CPU and auto-stops background *apps*; has no RSS ceiling. Would also
  *lengthen* job runtime, widening the window for a second run to stack on the first, so it
  plausibly makes this failure mode more likely rather than less.

## Verification

- 16 tests in `tests/test_job_guard_wiring.py`, including `test_two_concurrent_runs_cannot_both_acquire`
  (spawns a child holding the lock, asserts the second acquisition raises `InstanceConflict`) and
  `test_embed_leaves_are_decorated` — the regression test for the #174 zero-callers gap.
- Full suite in clean worktrees against an `origin/development` baseline: **10 failures both sides,
  zero regressions**, 1532 → 1545 passing. The 10 are pre-existing (GH-178).
- `rebalance doctor` clean apart from an unrelated figma staleness warning.
- Re-baselined after a 5-day postgres outage was reported; unchanged, and confirmed rebalance-OS has
  no postgres dependency at all (pure SQLite).

## Follow-on work

- **GH-175** — device-fleet audit prompted by this panic; found the unbounded posture is fleet-wide,
  not specific to embedding. Closed 2026-07-20.
- **GH-177** — CI never runs on `development`, which is why this class of gap goes unnoticed.
- **GH-178** — `development` is red with 10 pre-existing failures; auto-promote is not promoting.
