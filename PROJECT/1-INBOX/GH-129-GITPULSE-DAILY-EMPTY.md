---
title: Git Pulse Daily Summary falsely reports "No git activity found today"
status: Inbox (root-caused + primary fix shipped; 2 follow-ups open)
gh_issue: 129
created: 2026-07-14
updated: 2026-07-14
branch: development
supersedes: []
synthesizes: []
goal: >
  The Obsidian daily-note "Git Pulse Daily Summary" block reported "No git activity
  found today" on a day with 7+ commits, and did not self-correct. Root cause is a
  timezone-boundary bug in view.sh --today; the primary fix (pin the day-boundary
  tz) has shipped and is verified. Two defense-in-depth follow-ups remain.
---

# Git Pulse Daily Summary — false "No git activity" (GH-129)

## Contents
- [Symptom](#symptom)
- [Root cause (proven)](#root-cause-proven)
- [Fix — Phase 1 (DONE)](#fix--phase-1-done)
- [Follow-ups (DEFERRED)](#follow-ups-deferred)
- [Debug ledger](#debug-ledger)

## Symptom
Daily note's Git Pulse block read *"No git activity found today."* (auto-generated 6:12 PM)
on a day with 7+ commits across two devices, and persisted all evening.

## Root cause (proven)
`experimental/git-pulse/view.sh` derives the `--today` day-boundary and per-commit `local_day`
from the **ambient `$TZ`** (`date +%Y-%m-%d` at lines 49/117, `date -r $epoch` at 154). A
scheduler running with `TZ=UTC` — or simply firing after local-evening, when UTC has already
rolled to *tomorrow* while no commit yet carries tomorrow's UTC date — computes the wrong
calendar day, filters out every commit, and the synthesizer's zero-row fallback
(`utils/git_pulse_daily_synthesis.py:188`) emits "No git activity found today."
Reproduced deterministically: `TZ=UTC view.sh --today` returned the wrong day's rows (3 vs 7).

The acute 6:12 PM block was written by the scheduled job on **another device** (this Mac Studio
has no such plist and no run today; the vault is Obsidian-synced), so the triggering device's
environment couldn't be inspected — but the failure MODE above is device-independent.

## Fix — Phase 1 (DONE)
- [x] **Pin the day-boundary tz** in `view.sh`: honor a `display_timezone` config override, else
      resolve the machine's real zone from `/etc/localtime`, and `export TZ` before any `date`.
      No-op when `TZ` was already correct; only overrides a hostile ambient `TZ`.
- [x] **Verified:** `TZ=UTC view.sh --today` now returns the local day (7 rows, was 3); clean
      launchd-like env (`env -i` + `TZ=UTC` + `TMPDIR`) also returns 7.
- [x] **Healed the live note:** re-ran the synthesis; the stale "No git activity" block was
      replaced by the real summary.

## Follow-ups (DEFERRED — defense-in-depth)
- [ ] **Pull-before-read:** `collect_today_activity` shells `view.sh` with no `git pull`, so
      freshness depends on external sync cadence. Add a bounded `git pull` (fail-soft) before read.
- [ ] **No self-heal / clobber:** the synthesis runs once/day, so any transient empty persists
      24h and the bare "no activity" fallback overwrites a good block. Consider re-running through
      the evening (upsert already replaces the block) and/or not writing the empty fallback over a
      non-empty block.
- [ ] **Coverage:** a test asserting `view.sh --today` is tz-invariant (same rows under `TZ=UTC`
      and local) would pin this regression.

## Debug ledger
- H1 data-not-in-repo — ✗ (macbook pushed 13:23).
- H2 clone-not-pulled — ✗ (clone pulled 15:58, 16:58).
- H6 tz/UTC — ✗ as *this* device's cause (launchd probe = `-0700`); ✓ as the reproducible
  failure MODE (`TZ=UTC` → wrong day). Fix targets the mode.
- Sandbox artifact caught: `env -i` without `TMPDIR` gave a false 0 (view.sh `mktemp` in `/tmp`);
  discarded, re-run with `TMPDIR` → 7.
