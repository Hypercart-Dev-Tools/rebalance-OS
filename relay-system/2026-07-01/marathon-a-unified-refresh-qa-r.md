# RELAY · MARATHON-A unified-refresh v1 remediation (QA-R)
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded 2026-07-01.
-->

NEXT: codex
STATUS: Open
ROUND: 1 / 4

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Producer:** implement ALL QA-R findings below. Log a disposition per finding (Implemented / Declined + why). Run acceptance check. Set VERDICT.
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). Do **not** edit the artifact; only append findings here.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Escalated`.
6. **Commit only the relay file** (`relay(marathon-a-unified-refresh-qa-r): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Artifact under review: `scripts/pulse_web.py`, `scripts/apple_reminders_helper_app.swift`,
  `scripts/build_apple_reminders_helper_app.sh`, `tests/test_unified_refresh_remediation.py`
- Producer: codex   ·   Reviewer: agy
- Started: 2026-07-01
- Source of truth: `PROJECT/2-WORKING/UNIFIED-REFRESH-RESTART.md` → "Phase QA-R"
- Definition of Done: all 7 QA-R gate items below are implemented and tested.
  `pytest tests/test_unified_refresh_remediation.py` green. `rebalance doctor` clean.

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.
7. **graphify-out/graph.json exists in this repo.** Run `graphify query "<question>"` before grepping
   source files. Only grep after graphify has oriented you, or to modify/debug specific lines.

## QA-R Findings (Producer must address ALL before claiming DoD)

The v1 build (commit `74b8b52`) shipped with the Observable checklist and QA gate unchecked.
The following 7 items must be remediated:

**F1 — Silent helper failure (Blocker)**
`/api/refresh` captures `helper_error` but returns `{"ok": True, ..., "helper_error": ...}`.
The dashboard only keys off `ok`, so a helper failure is invisible — button reports success,
column silently serves stale/empty data.
Fix: surface the error in the dashboard (badge/marker); column renders last-good **with a
staleness indicator**; response must signal not-ok when helper fails.
Self-check: failing invoker → response has `ok: false` AND column shows prior snapshot.

**F2 — No automated coverage (Blocker)**
Nothing under `tests/` exercises `list-active` / `active.json` / `/api/refresh`.
Last-good-wins is implemented but never tested.
Fix: add (a) a fixture `list-active` parse self-check and (b) a failing-invoker assertion
that `active.json` is left byte-for-byte unchanged.
File: `tests/test_unified_refresh_remediation.py` (already in ALLOW_PATHS).

**F3 — DB read path dropped → cold-start regression (Blocker)**
`pulse_web.py` now reads only `temp/apple-reminders/active.json`.
On any host where `active.json` doesn't exist yet, the column renders empty.
Fix: seed `active.json` from the DB on first render, OR explicitly document DB-less
rendering and add a test for the empty-file case. Choose and document.

**F4 — One fact, two hardcoded literals (Should)**
`temp/apple-reminders/active.json` is written in `pulse_server.py` and re-derived in
`pulse_web.py`. Fix: extract a single shared constant (one canonical place).

**F5 — Private symbol import + in-handler imports (Should)**
`/api/refresh` imports `_open_bundle_invoker` (underscore = private) and does 4 imports
inside the function body. Fix: promote a public invoker entry point (or document the
coupling explicitly); lift imports to module scope.

**F6 — Unversioned cross-process contract (Should)**
`{reminder_id, title, due_at}` shape in `active.json` has no `schema_version`.
Fix: add a version field OR a single typed reader so a helper-side shape change is caught,
not silently mis-rendered.

**F7 — Helper fetch has no timeout (Should)**
`list-active` blocks on `semaphore.wait()` with no deadline; helper process can hang.
Fix: bound the wait (e.g. `semaphore.wait(timeout: 4.5)` to stay within the 5s invoker cap).

## Log

### Coordinator — claude-a — 2026-07-01

Wave 2 Lane A scaffold. The v1 build shipped with 7 QA-R findings (see above); all must be
addressed before this lane is Done. Producer (codex) takes the first turn.

Context: `pulse_server.py` is NOT in ALLOW_PATHS for this turn because the marathon-A
paths don't include it. If the producer needs to touch `pulse_server.py` to fix F1/F4/F5,
it must note this in the turn — the relay thread is the signal; the relay-drive supervisor
will revert out-of-allowlist edits. Add `scripts/pulse_server.py` to ALLOW_PATHS if needed
(coordinator note: this was an oversight in the original lane definition; fix it if codex flags it).

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
