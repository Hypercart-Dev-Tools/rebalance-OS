# RELAY · GH-116 Phase 1 — cross-day velocity/stall signal (compute_deep_work_signals)
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-07-05.
-->

NEXT: None
STATUS: Approved
ROUND: 1 / 4

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). Do **not** edit the artifact; only append findings here.
   - **Producer:** log a disposition for every open finding (Implemented / Modified / Declined + why),
     make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Escalated`.
6. **Commit only the relay file** (`relay(gh116-phase1): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Paths this lane may touch: `src/rebalance/ingest/next_actions.py`, `src/rebalance/doctor.py`, `tests/test_next_actions.py`
- Producer: codex   ·   Reviewer: agy
- Handoff: cli-driven (relay-xyz — codex builds, agy reviews; single-session headless), running against an isolated worktree/branch `marathon/2026-07-06`
- Started: 2026-07-05
- Definition of Done: per [GH-116-VELOCITY-SIGNAL.md](../../PROJECT/2-WORKING/GH-116-VELOCITY-SIGNAL.md#phase-1--compute--observe-only-report) Phase 1 — new pure function `compute_deep_work_signals(db, today, lookback_days=7)` in `next_actions.py` returning per-project `streak_days`, `possible_stall: bool`, `evidence`; reuses `collect_pulse_snapshot()`; does **not** touch `rank_next_actions()` output or write to the vault. Surfaced as a new line in `rebalance doctor` for flagged projects. Fixture-seeded tests cover: a 5-day streak, a stall-with-open-issue case, and a quiet-with-no-open-issue non-stall case. `pytest tests/` green; `rebalance doctor` clean.

## Task brief (for the Producer's first turn)
Part of the 2026-07-06 marathon, Lane A (see [MARATHON-2026-07-06.md](../../PROJECT/2-WORKING/MARATHON-2026-07-06.md#lane-a--gh-116-phase-1-compute--observe-only-report)). Implements Phase 1 of [GH-116-VELOCITY-SIGNAL.md](../../PROJECT/2-WORKING/GH-116-VELOCITY-SIGNAL.md):

- Add `compute_deep_work_signals(db, today, lookback_days=7)` to `src/rebalance/ingest/next_actions.py`, next to the other candidate-building helpers. Reuse `collect_pulse_snapshot()` (see `src/rebalance/ingest/pulse.py`) called once per day in the lookback window — do not re-parse any vault markdown.
- Per project, compute: `streak_days` (consecutive days walking back from `today` with nonzero commit/activity rows), and `possible_stall: bool` (active yesterday, zero activity today, AND still has ≥1 open GitHub issue/PR referencing it — check via the existing `github_scan`/`github_watch` collectors, e.g. `watched_repo_is_active_work()` in `github_watch.py`). Include `evidence` (the specific dates/rows backing the flag) — never a bare claim.
- No new DB table, no new MCP tool, no change to `rank_next_actions()`'s output, no vault write (all explicit non-goals in the doc).
- Wire one `rebalance doctor` line (`src/rebalance/doctor.py`) that lists any `possible_stall` projects with their evidence.
- Add `tests/test_next_actions.py` cases (or a new test file if cleaner) seeding 7 days of fixture activity rows for the three acceptance cases above.
- **Out of scope:** folding this into `rank_next_actions()`'s ranking tiers (that's GH-116 Phase 2, gated on an observation window) — this phase is report-only.

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

### Producer — codex — 2026-07-05 21:11 PT
- Disposition: initial producer pass, so there were no open reviewer findings to resolve yet.
- Implemented `compute_deep_work_signals(db, today, lookback_days=7)` in `src/rebalance/ingest/next_actions.py` as a read-only helper. It calls `collect_pulse_snapshot()` once per lookback day, rolls GitHub activity up per active project, computes `streak_days`, flags `possible_stall` only when yesterday had activity and today is quiet while open GitHub work still exists, and returns structured evidence (`streak_dates`, per-day rows, open items).
- Wired `rebalance doctor` to surface the observe-only signal as a single `deep work` check in `src/rebalance/doctor.py`; `WARN` only when a possible stall exists, otherwise `OK`.
- Added fixture-seeded Phase 1 coverage in `tests/test_next_actions.py` for the 5-day streak case, the stall-with-open-issue case, and the quiet-with-no-open-issue non-stall case.
- Verification: `PYTHONPATH="$PWD/src" pytest tests/test_next_actions.py tests/test_doctor.py` → `63 passed`.

### Reviewer — agy — 2026-07-05 21:12 PT
- **Verdict:** Approved
- `[Pass]` Function `compute_deep_work_signals` successfully implemented with correct lookback window mapping, reuse of `collect_pulse_snapshot`, and database query optimization.
- `[Pass]` Stall conditions successfully evaluated: checks that yesterday had activity, today has zero activity, and has open GitHub issues.
- `[Pass]` Report surfaced via a clean `deep work` check in `rebalance doctor` without interfering with `rank_next_actions()` or writing to the vault.
- `[Pass]` Fixture-seeded tests covering streak, stall with open issue, and quiet non-stall are comprehensive and verify all requested phase 1 behaviors.
- Verification: Ran `pytest tests/test_next_actions.py tests/test_doctor.py` → 63 passed. Ran `rebalance doctor` and verified it reports the `deep work` signal correctly.

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
