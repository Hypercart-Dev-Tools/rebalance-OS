---
title: Git Pulse Daily Summary falsely reports "No git activity found today"
status: Inbox (root-caused + primary fix shipped; follow-up "no self-heal/clobber" shipped 2026-07-16; 2 follow-ups open: pull-before-read, tz-invariance coverage test)
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

## Follow-ups
- [ ] **Pull-before-read (DEFERRED):** `collect_today_activity` shells `view.sh` with no `git pull`, so
      freshness depends on external sync cadence. Add a bounded `git pull` (fail-soft) before read.
      **Deliberately not built** as part of the 2026-07-16 marathon sweep — needs an operator design
      call on git-pull failure handling in a scheduled script, not something to assume unilaterally.
- [x] **No self-heal / clobber (SHIPPED 2026-07-16):** via [MARATHON-2026-07-16-B](../2-WORKING/MARATHON-2026-07-16-B.md)
      Lane E (PR #134). `synthesize()`'s zero-row fallback no longer overwrites an existing non-empty
      block — guarded on both `upsert_block` (vault) and `upsert_clio_block` (CLIO log) paths, with a
      logged SKIP when a rerun would clobber a real summary. 12 new tests in
      `tests/test_git_pulse_daily_synthesis.py`.
- [ ] **Coverage (DEFERRED):** a test asserting `view.sh --today` is tz-invariant (same rows under
      `TZ=UTC` and local) would pin this regression at the source rather than only downstream.

## Debug ledger
- H1 data-not-in-repo — ✗ (macbook pushed 13:23).
- H2 clone-not-pulled — ✗ (clone pulled 15:58, 16:58).
- H6 tz/UTC — ✗ as *this* device's cause (launchd probe = `-0700`); ✓ as the reproducible
  failure MODE (`TZ=UTC` → wrong day). Fix targets the mode.
- Sandbox artifact caught: `env -i` without `TMPDIR` gave a false 0 (view.sh `mktemp` in `/tmp`);
  discarded, re-run with `TMPDIR` → 7.
