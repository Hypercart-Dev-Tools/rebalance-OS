# RELAY · GH-172 QA: job_guard.py single-instance + memory ceiling
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-07-19.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 1 / 4

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

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
