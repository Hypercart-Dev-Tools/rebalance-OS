# Marathon Phase gh219-lane4-footprint-guard
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-GH219-LANE4 builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

# Lane 4 (GH-219 marathon) — #213: switch the job guard from RSS to `phys_footprint`

## Why this lane is the highest-value work remaining

`utils/job_guard.py` is the external safety net for long-running jobs. On 2026-07-27 it ran
**233 jobs and tripped zero times** while the machine fell to 0.09 GB free, 28.99 GB compressor,
and 24.7 of 26 GB swap.

It failed for a structural reason, not a tuning one. `tree_rss_bytes()` (`job_guard.py:194-233`)
sums **RSS** from `ps -eo pid=,ppid=,rss=`. The processes that killed the machine held ~46.9 GB of
`phys_footprint` while reporting **~0.08 GB RSS**, because MLX's Metal buffers are charged as
`iokit` to the footprint and are **never counted in RSS**. The guard was measuring a number that
physically cannot see this class of allocation.

Lane 2 fixed the specific MLX leak. **This lane fixes the instrument**, so the *next* memory bug —
MLX or not — gets caught by the system instead of by someone noticing Activity Monitor.

## Required work

### 1. Measure `phys_footprint` instead of RSS

**The mechanism is already verified working on this machine** — do not go hunting. `ps` cannot
provide footprint; `libproc`'s `proc_pid_rusage` can, via `ctypes`:

```python
libc.proc_pid_rusage(pid, 2, byref(buf))   # flavour 2 = RUSAGE_INFO_V2
# -> buf.ri_phys_footprint  (bytes), buf.ri_resident_size (bytes)
```

`RUSAGE_INFO_V2` layout, in order: `ri_uuid[16]`, then `uint64` fields — `user_time`,
`system_time`, `pkg_idle_wkups`, `interrupt_wkups`, `pageins`, `wired_size`, `resident_size`,
**`phys_footprint`**, `proc_start_abstime`, `proc_exit_abstime`, `child_*`, `diskio_*`.

**Confirmed behaviours you must handle:**

- Returns `0` and a valid footprint for processes **we own** — the Rebalance tree, which is all
  this guard cares about.
- Returns **`-1` for processes we do not own** (verified against root-owned pid 1) and for pids
  that exit mid-walk. A tree walk **must skip these**, not crash, and **must not** treat an
  unreadable process as `0` — silently reading a runaway as zero is precisely the failure mode
  this lane exists to remove. Count them and surface the count.
- Keep an RSS fallback for any platform where `proc_pid_rusage` is unavailable, and make the
  degraded mode **visible in the failure message**, not silent.

### 2. Re-size the ceiling — the current value is NOT transferable

`DEFAULT_MAX_RSS_FRACTION = 0.35` (`job_guard.py:82`) is 22.4 GB on this 64 GB machine. That was
chosen for RSS semantics. Footprint legitimately includes Metal, so the number means something
different now — and 22.4 GB is far too permissive against measured reality:

| Measurement | Value |
|---|---|
| Model resident in MLX | 1.11 GB active |
| Healthy embedding pass, post-Lane-2 | **1.36 GB** footprint |
| Same workload pre-Lane-2 | 13.00 GB at batch 18, still climbing |
| Project contract, per process | **≤ 8 GB** peak `phys_footprint` |
| Project contract, aggregate concurrent | ≤ 16 GB |

Size the default from these numbers and the 8 GB contract, and **write the derivation into a
comment**. Rename the constant and the env var if they now say the wrong thing
(`REBALANCE_JOB_GUARD_MAX_RSS_GB` names a metric this no longer uses) — but keep the old env var
working as a deprecated alias so existing plists and docs do not silently stop applying.

### 3. Settle the available-memory floor

`available_memory_bytes()` (`:155-191`) counts **free + inactive + speculative**. Determine whether
that is still the right definition under memory pressure — inactive and speculative pages are
reclaimable in principle, but the 07-27 data shows the machine dying while that sum looked
survivable. `MIN_AVAILABLE_FLOOR = 4 * GIB` (`:90`) deliberately matches the project contract's
`free_gb >= 4.0`; keep them aligned or change both together.

## Carried finding — context, not a task

`guarded_embedding` decorates embedding **leaf** functions, so each call builds a fresh
`MemoryCeiling` with `peak_rss = 0` (PID 1391 wrote three records — 10.7 s / 1.5 s / 35.6 s —
across a 35-minute lifetime). This does **not** block the switch: footprint is absolute per-process,
so a later leaf call reads the accumulated total rather than starting from zero. That is part of
why this switch works. Do **not** restructure the decorator here — that is Lane 6.

## Write-set (do not edit anything else)

- `utils/job_guard.py`
- `tests/test_job_guard_wiring.py` and/or a new `tests/test_job_guard_footprint.py`

## Tests — required

Baseline is **27 passed** across `tests/test_job_guard_wiring.py` + `tests/test_watchlist_guard.py`.

1. A synthetic over-ceiling process **trips and is killed** — the central test
2. A process at healthy footprint (~1.4 GB) does **not** trip
3. **The 07-27 signature specifically: high footprint, near-zero RSS, must trip.** This is the
   exact case the old guard missed; if this test does not exist, the lane has not done its job
4. Unreadable pids (`rc = -1`) are skipped, counted, and **never** treated as 0
5. The RSS fallback path works and announces itself when footprint is unavailable
6. The deprecated env-var alias still applies

## Acceptance

- `.venv/bin/python3 -m pytest tests/test_job_guard_wiring.py tests/test_watchlist_guard.py
  tests/test_job_guard_footprint.py -q` passes
- The full suite has **6 known pre-existing failures** (`test_hiqs_pipeline.py` ×5,
  `test_scheduler_liveness.py` ×1). They are not yours. Do not fix them; do not let them fail
  your gate.

## Out of scope

- `src/rebalance/ingest/_job_guard.py` — a **different file** (the bridge). Not this lane.
- Guard placement / decorator restructuring / coverage gaps — Lane 6
- `mx.set_memory_limit()` — Lane 3
- Anything under `temp/` — gitignored; edits cannot be committed and are destroyed with the worktree

### Round 1 · Builder · agy

**Files Touched:**
- `utils/job_guard.py`
- `tests/test_job_guard_wiring.py`
- `tests/test_job_guard_footprint.py` (new)

**Key Decisions:**
1. **Measurement**: Implemented `tree_footprint_bytes` using `ctypes` on macOS with `proc_pid_rusage(..., 2, ...)`. It correctly returns footprint, fallback flag, and unreadable count. RSS is used as fallback (e.g. Linux). 
2. **Re-sized ceiling**: Renamed `DEFAULT_MAX_RSS_FRACTION` to `DEFAULT_MAX_FOOTPRINT_FRACTION` and set it to `0.25` (25% of 64 GB = 16 GB), aligning with the aggregate concurrent project contract.
3. **Available memory floor**: Updated `available_memory_bytes()` to *only* sum `Pages free:` and skip `inactive` and `speculative` pages, ensuring true pressure is captured.
4. **Compatibility**: Left `--max-rss-gb` as a deprecated alias CLI argument and supported `max_rss_gb` as a kwarg fallback in `guard` and `MemoryCeiling` for backwards compatibility with existing plists and docs. We also rename output keys to `peak_footprint_bytes` and updated existing tests in `test_job_guard_wiring.py` to match.
5. **Tests**: Added comprehensive footprint tests in `tests/test_job_guard_footprint.py` including high-footprint/low-rss scenario, fallback verification, unreadable process counting, and the `_job_guard` deprecated env var fallback via monkeypatching. All tests pass (33 total).

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): utils/job_guard.py,tests/test_job_guard_wiring.py,tests/test_job_guard_footprint.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-GH219-LANE4 --agent agy --paths "phases/gh219-lane4-footprint-guard/RELAY.md,utils/job_guard.py,tests/test_job_guard_wiring.py,tests/test_job_guard_footprint.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-GH219-LANE4 --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH219-LANE4 --agent agy --to codex
4. Edit ONLY these paths: phases/gh219-lane4-footprint-guard/RELAY.md and utils/job_guard.py,tests/test_job_guard_wiring.py,tests/test_job_guard_footprint.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: utils/job_guard.py,tests/test_job_guard_wiring.py,tests/test_job_guard_footprint.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH219-LANE4 --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-GH219-LANE4 --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh219-lane4-footprint-guard/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
