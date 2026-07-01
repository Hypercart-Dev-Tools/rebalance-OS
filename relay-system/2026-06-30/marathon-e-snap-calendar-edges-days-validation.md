# RELAY · MARATHON-E snap-calendar-edges days validation
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-06-30.
-->

NEXT: —
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
6. **Commit only the relay file** (`relay(marathon-e-snap-calendar-edges-days-validation): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Artifact under review: `src/rebalance/mcp/tools/calendar.py`, `tests/test_calendar_snap.py`
- Reviewer: agy   ·   Producer: codex
- Started: 2026-06-30
- Definition of Done: `snap_calendar_edges` validates `days` (1-7) before calling `snap_edges()`,
  returns structured error dict for out-of-range values; `pytest tests/test_calendar_snap.py` green
  including new `SnapCalendarEdgesMCPDaysValidationTests` (3 cases).

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

### Producer — claude-a — 2026-07-01

- Added `if not (1 <= days <= 7): return {"error": ..., "status": "error"}` guard in
  `snap_calendar_edges` before `CalendarConfig.load()` — matches CLI's BadParameter behavior.
- Added `SnapCalendarEdgesMCPDaysValidationTests` to `tests/test_calendar_snap.py` (3 cases:
  days=0 error dict, days=8 error dict, days=1/7 boundary passes through).
- Acceptance: `pytest tests/test_calendar_snap.py` → 20/20 passed.

VERDICT: PASS
Basis: Validation guard in place before any side-effects; 20/20 tests pass including new MCP cases.

### Reviewer — claude-a (operator self-review) — 2026-07-01

- [Pass] Guard fires before CalendarConfig/snap_edges — no exception can propagate for days ∉ [1,7].
- [Pass] Error dict has `status: error` and `error` key mentioning `days`.
- [Pass] Boundary (1, 7) threads through to snap_edges with proper mocking.
- [Pass] All 17 pre-existing tests still pass; total 20/20.

VERDICT: Approved
Basis: DoD met in full; test suite clean.

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
