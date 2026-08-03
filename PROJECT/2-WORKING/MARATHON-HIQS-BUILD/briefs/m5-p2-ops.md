---
title: "M5 p2 — ops: one scheduled job, and coexistence with the incumbent"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M5 p2 — ops: one scheduled job, no baked paths

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m5-p1` is approved. **Operator checkpoint C follows M5** — install, keyring, TCC, one week unattended. |

**Canonical spec:** `HIQS-PROJECT.md` §10 (one job), §13 (canonical paths), L11, L12, L21.

## Build

- `HiQS/ops/com.hiqs.refresh.plist.template` — `{{HIQS_DIR}}` / `{{PYTHON}}` placeholders,
  runs `hiqs refresh` every 2 h. **One job. Not a fleet.**
- `HiQS/ops/install_scheduler.sh` — renders the template per machine and loads it. Always
  `launchctl unload` before `load` (a gated `grep` check misses a job that is loaded but
  momentarily absent from `launchctl list`, which fails `load` with an opaque I/O error — the
  incumbent has this scar).
- The rendered plist is gitignored.

## Acceptance

- **No absolute user path anywhere** in the template, the installer, or `HiQS/**` (L11). A test
  greps the whole subtree and fails on any absolute home-directory prefix (the macOS users root, the Linux home root) or a Windows drive letter. One developer's home
  directory baked into five plists is a real incident in this repo's history.
- The installer is idempotent: run twice, one job loaded, no duplicate.
- **The DB path is verified outside any TCC-protected folder** by the installer, which refuses and
  explains rather than installing a job that will fail with exit 128 on every fire, invisibly
  (L11, 0.18.2).
- **No shell in the runtime path** (L21): the plist invokes the Python entry point directly. The
  installer is a shell script the *operator* runs once; nothing scheduled depends on a shell.
  Where shell is used, it is POSIX-safe under macOS's stock Bash 3.2 — no empty-array expansion
  under `set -u`.
- Exactly one job is installed. A second is a §14 conversation with a stated trigger (L12).

## Do not

- Do not install the job, load it, or touch `~/Library/LaunchAgents` from a test or a build turn.
  That is checkpoint C, on the operator's real device.
- Do not add a watchdog, a second job, or a KeepAlive daemon.

## Coexistence with the running incumbent — the machine-killing one

This build runs on the **same machine that already runs rebalance-OS**, which has **7 live launchd
jobs** including `com.rebalance-os.vault-sync` and `com.rebalance-os.github-sync`. Both embed.
HiQS's own `refresh` embeds every 2 hours.

**This is GH-172 exactly.** Three concurrent Python embedding runs stacked to ~90 GB on a 68.7 GB
machine, saturated the VM compressor until `watchdogd` starved, and the kernel panicked. The fix
shipped as a `flock` single-instance lock plus an in-process memory ceiling applied **at the
incumbent's library leaves** (`embed_chunks`, `embed_pending`) — and a separate HiQS process knows
nothing about that lock. Two systems each correctly guarding themselves is not a guard.

So the installer must establish coexistence, and this is a **blocking** part of this phase:

- **Shared embedding lock.** HiQS's embed path takes the *same machine-scoped* `flock` the incumbent's
  guard uses, so the two can never stack. Read the incumbent's lock path rather than inventing a
  parallel one — a second lock file is two systems politely guarding different doors.
- **Own memory ceiling** regardless, since a lock does not bound a single run (L7: the watchdog read
  RSS and missed compressed pages; record peak RSS per run, §8).
- **Schedule offset.** The 2-hourly job is offset from the incumbent's sync cadence so the common
  case never contends for the lock in the first place.
- **Port check.** HiQS serves `127.0.0.1:8790`; the incumbent already holds `:8767` and others. The
  installer **probes and refuses** on a bound port rather than starting a second listener that
  half-works (L10 is what two servers cost this project).
- **Label check.** Refuse to install if a `com.hiqs.*` label is already loaded — the incumbent's own
  `supersedes` guard exists because a managed job was once stood up beside the incumbent it replaced.

## Do not disable, uninstall, or unload any `com.rebalance-os.*` job

Not in this phase, not in any build turn. The incumbent is the **fallback** until HiQS meets §13's
done-criterion, and Decision 7 keeps it running deliberately. Decommissioning it is an operator
action at cutover (HiQS Phase 6), not a build step — and unloading 7 launchd jobs on the operator's
machine is precisely the destructive, hard-to-reverse act that must never happen in an unattended
turn.
