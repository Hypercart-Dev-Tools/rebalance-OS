# Marathon Phase hiqs-m5-p2
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M5-P2-TURN builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

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


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/ops/com.hiqs.refresh.plist.template,HiQS/ops/install_scheduler.sh,HiQS/tests/test_ops.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M5-P2-TURN --agent codex --paths "phases/hiqs-m5-surfaces--hiqs-m5-p2/RELAY.md,HiQS/ops/com.hiqs.refresh.plist.template,HiQS/ops/install_scheduler.sh,HiQS/tests/test_ops.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M5-P2-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M5-P2-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m5-surfaces--hiqs-m5-p2/RELAY.md and HiQS/ops/com.hiqs.refresh.plist.template,HiQS/ops/install_scheduler.sh,HiQS/tests/test_ops.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/ops/com.hiqs.refresh.plist.template,HiQS/ops/install_scheduler.sh,HiQS/tests/test_ops.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M5-P2-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M5-P2-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m5-surfaces--hiqs-m5-p2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
