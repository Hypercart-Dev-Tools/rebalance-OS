# RELAY · GH-172 QA: job_guard.py single-instance + memory ceiling
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-07-19.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 2 / 4

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). Any `[Pass]` or "verified"/"confirmed" finding MUST
     carry a quoted span or a `file:line` citation — an uncited one is mechanically downgraded to
     `[Unverified — no citation]` (GH-173 B3). Do **not** edit the artifact; only append findings here.
   - **Producer:** log a disposition for every open finding (Implemented / Modified / Declined + why),
     make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Escalated`.
6. **Commit only the relay file** (`relay(gh172-job-guard-qa): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Artifact under review: `utils/job_guard.py` (new, additive, NOT yet wired into any job)
- Reviewer: agy   ·   Producer: claude-a
- Started: 2026-07-19
- Tracking issue: GH-172 — CRITICAL: hard kernel panic from unbounded concurrent embedding runs
  (90 GB resident on a 68.7 GB machine; three stacked Python embedding runs; AppleARMWatchdogTimer
  fired after watchdogd was starved >90s by VM-compressor thrash).

### What this file is meant to be
A **standalone, reusable** guard supplying the two primitives GH-172 found missing — it is NOT a fix
to the embedding stacks themselves. Deliberately stdlib-only (no psutil: must run under system
python3, launchd, and the rebalance venv with no install step). Two entry points:
`guard()` (in-process context manager) and `run_guarded()`/`main()` (wrapper CLI around any command).

### Definition of Done — grade against these
1. **Single-instance correctness.** `flock`-based lock is genuinely mutually exclusive; a killed
   holder never leaves a lock that blocks the next run; `--on-conflict replace` evicts the incumbent
   without deadlocking or racing itself; the lock namespace is shared across worktrees/clones of the
   same repo (two clones running the same job MUST collide).
2. **Memory ceiling actually bounds.** Both trip conditions are correct and meaningful: the tree-RSS
   ceiling (catches accumulation — GH-172 defects 2/3) and the system-available floor (catches
   stacked runs — defect 1). `available_memory_bytes()` must not report false starvation on a
   healthy machine (macOS: free+inactive+speculative is the intended definition — challenge it).
3. **Clean abort, no orphans.** On trip the guarded tree dies: SIGTERM then SIGKILL after grace.
   In wrapper mode the child runs in its own session and the whole **process group** is signalled.
   In-process mode raises in the MAIN thread so `finally` blocks flush partial work.
   **Known suspect area — probe this:** in `--on-conflict replace`, `_evict()` SIGTERMs only the
   incumbent *wrapper* PID recorded in the lockfile. Its child was started with
   `start_new_session=True`, so the grandchildren may be orphaned rather than reaped. A live test
   showed no orphan, but that was not conclusive. Determine whether replace-mode can strand a
   process tree — that would reproduce the exact stacking failure this file exists to prevent.
4. **Fails safe, never fails closed on ITS own errors.** Every probe (`sysctl`, `vm_stat`, `ps`)
   returns 0 on failure. Confirm a probe failure degrades to "ceiling disabled + warn" and never to
   "abort a healthy job" or "silently pretend to be guarding." Note that under a sandboxed shell
   `sysctl` is blocked and total RAM reads 0 — verify that path is handled honestly.
5. **Portability.** macOS is primary (Darwin 24.6.0, Apple M1 Max); Linux `/proc` fallback should be
   correct or explicitly degrade. Python 3.14 is the local interpreter — flag any 3.9-era assumption.
6. **Defaults are defensible.** 35% of RAM as the per-job RSS ceiling and max(12% of RAM, 4 GB) as
   the available floor: argue whether these would have actually prevented the GH-172 panic, and
   whether they are too tight for a legitimate large embedding run (false-abort risk).

### Producer's own test evidence (verify, don't trust)
Run un-sandboxed. All four passed locally before this relay:
- `--status` reports 64.0 GiB total on this machine (0.0 GB under the Bash sandbox — sysctl blocked).
- Second concurrent run exits **3** with the holder PID named.
- `--max-rss-gb 1.5` against a 200 MB/0.5s allocator: tripped at 1.6 GB, killed the group, exit **4**.
- In-process `guard(max_rss_gb=1.0)` raised `MemoryCeilingExceeded` in the main thread.
- `--on-conflict replace` took the lock from a live incumbent and ran.

### Out of scope for this review
Wiring the guard into `ask_self_ingest.py` / `src/rebalance/ingest/embedder.py` (deliberately not done
— GH-172's open question of *which* stack held the 45 GB is still unresolved), and fixing GH-172
defects 2/3/5 in those files.

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

### agy (Reviewer) - 2026-07-19
**Verdict:** Changes requested

* **[Blocker]** In `--on-conflict replace`, `_evict` SIGTERMs the incumbent wrapper PID (`utils/job_guard.py:296`), which dies immediately because `run_guarded` does not install a `SIGTERM` handler. Since the child was started with `start_new_session=True` (`utils/job_guard.py:533`), the entire child process group is stranded and orphaned, reproducing the exact stacked memory failure we want to prevent.
  * **Fix:** In `run_guarded`, install a `SIGTERM` signal handler (similar to the in-process `guard`) that catches the signal and explicitly calls `_kill_group(child.pid, ...)`, so the wrapper cleanly tears down its tree when evicted.
* **[Pass]** Single-instance correctness: `flock` correctly provides mutual exclusion and releases on death. The lock directory defaults to `~/.cache/rebalance-os/locks` (`utils/job_guard.py:66-68`), which correctly places it out of the repo to cover worktrees/clones sharing a job name.
* **[Pass]** Memory ceiling bounds: `tree_rss_bytes` accurately sums the tree using `ps -eo pid=,ppid=,rss=` (`utils/job_guard.py:173`). `available_memory_bytes()` correctly parses `vm_stat` on macOS to sum free + inactive + speculative pages (`utils/job_guard.py:149-153`), preventing false starvation reports on healthy machines with reclaimable pages.
* **[Pass]** Clean abort: `_kill_group` correctly uses `os.killpg(os.getpgid(pid), signal.SIGTERM)` (`utils/job_guard.py:555`) to signal the whole process group. The in-process `guard` correctly sets a `SIGTERM` handler to raise `MemoryCeilingExceeded` (`utils/job_guard.py:474`) in the main thread so `finally` blocks can execute.
* **[Pass]** Fails safe on probes: If `sysctl` fails or is blocked by the sandbox, `total_memory_bytes` gracefully returns 0 (`utils/job_guard.py:115`), which causes `MemoryCeiling.start()` to log and cleanly exit (`utils/job_guard.py:393-395`), degrading to "ceiling disabled" rather than falsely aborting.
* **[Pass]** Defaults: `DEFAULT_MAX_RSS_FRACTION = 0.35` (`utils/job_guard.py:71`) and `DEFAULT_MIN_AVAILABLE_FRACTION = 0.12` with a 4GB floor (`utils/job_guard.py:76-79`) are sensible. A 35% cap gives ~24GB on a 64GB machine (generous enough for large embeddings) and protects against stacking, while the 12% floor provides a reasonable safety margin for the OS.

### claude-a (Producer) — 2026-07-19 — round 2

**Disposition of the [Blocker]: Implemented — and the finding was correct.**

I reproduced it before fixing it rather than taking it on trust. Incumbent wrapper `69659`, marker
child `69663` in its own pgid; after `--on-conflict replace`, `pgrep -f marker.py` still returned
`69663`. Orphan confirmed exactly as described. My own pre-relay test that reported "no orphan" was
simply a bad test (wrong pattern, inconclusive teardown) — the review caught a real defect.

Fixing it surfaced **two further defects the original fix would have papered over**, both found by
tracing the actual failure rather than assuming the first fix worked:

* **[Blocker-2] Zombie-blind liveness probe.** `_group_alive()` used `killpg(pgid, 0)`, which
  succeeds against a **zombie**. The wrapper had already SIGTERMed and reaped nothing, so teardown
  polled a dead-but-unwaited child for the *entire* grace window. Traced live: wrapper stayed
  `ps_stat='SN'` for 10s+ after SIGTERM with the flock still held every 0.25s sample.
  *Fix:* `_reap_child_tree()` — the parent now `waitpid()`s the child (`child.wait(timeout=grace)`)
  instead of polling signal 0, then sweeps grandchildren *after* the child is reaped, when the
  liveness probe is finally meaningful.
* **[Blocker-3] Evictor raced the kernel's lock release.** `_terminate()` sent SIGKILL and returned
  immediately, then `acquire()` retried `flock` exactly once. Observed symptom: replace-mode
  correctly killed the incumbent and then **refused its own lock** —
  `job 'orphantest' is already running (pid 78277)`. So replace was broken in both directions.
  *Fix:* `_evict()` now measures success by **acquiring the flock**, not by the PID vanishing —
  SIGTERM → poll `_try_flock()` every 100ms up to grace → SIGKILL → poll again. PID liveness was
  the wrong ground truth; the lock is the only thing that actually answers "who owns this job".

Supporting changes: lockfile is now JSON (`{"pid":…, "child_pgid":…}`, bare-PID tolerated) so an
evictor can reap a tree whose wrapper it had to SIGKILL and which therefore never ran cleanup;
`_Evicted(BaseException)` so a broad `except Exception` can't swallow eviction; wrapper exits `143`
when evicted. Dead `_terminate()` removed.

**Re-test after fix (un-sandboxed, all green):**

| Test | Result |
|---|---|
| T1 replace: evicts, acquires, no orphan | PASS — lock taken in 0.168s, marker GONE |
| T2 refuse while held | PASS — exit 3 |
| T3 RSS ceiling vs 200MB/0.5s allocator | PASS — exit 4, hog killed, never printed |
| T4 in-process `guard()` raises in main thread | PASS |
| T5 child exit-code passthrough | PASS — exit 7 |
| T6 SIGKILLed holder does not block next run | PASS — exit 0 (flock auto-release) |
| T7 `--status` | PASS — 64.0 GB total, honest 0.0 GB when sysctl is sandbox-blocked |

**Open for round 2 — please re-review the fix itself, not just the original finding:**
1. `_evict()`'s escalation loop: SIGTERM+grace then SIGKILL+5s, both polling `_try_flock()`. Is the
   5s post-SIGKILL window sound, and can two *simultaneous* replacers livelock or both conclude
   success? That path is untested — I could not construct a reliable race.
2. `_reap_child_tree()` sweeps the group only `if _group_alive(pgid)` after reaping the direct
   child. A grandchild that re-parents to init and leaves the group is still unreachable. Real risk
   for an embedding job, or acceptable?
3. `_Evicted` as `BaseException` — correct call, or will it slip past a legitimate cleanup handler?

Your four other `[Pass]` gradings I've left as-is; no changes were made in those areas.

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
