---
title: Unified UI Refresh + Restart (system-wide)
doc_type: project-plan
status: active
owner: Noel Saw
created: 2026-06-27
updated: 2026-06-27
goal: "Make the pulse dashboard's existing Refresh button repopulate the Apple Reminders column (FDA-free, via the signed EventKit helper) so it never silently empties — then, only if the need proves out, grow to a system-wide refresh/restart. v1 is the column; everything else is deferred."
priority: P2
related:
  - scripts/pulse_server.py
  - scripts/pulse_web.py
  - src/rebalance/ingest/apple_reminders_write.py
  - scripts/apple_reminders_helper_app.swift
---

## Status

| What was just completed | What's next |
|---|---|
| Plan written → /ponytail-scoped → SWE-rubric reviewed → **/ponytail-trimmed to a v1 (2026-06-27)**: cut the JSONL audit log, the 4-phase scaffold, and (for v1) the restart endpoint + Focus 5 wiring — all deferred. **v1 = make the existing Refresh button populate the reminders column via the signed helper (EventKit, no FDA).** Kept the SWE correctness wins that are free for v1 (fast-data-only refresh, helper poll stop-condition, single-write-path). | **Build v1** — 3 edits: helper `list-active` op → `/api/refresh` reads it → column renders it. |

## Problem

The pulse dashboard's Apple Reminders column shows "No active reminders" and silently empties after any reindex: the source is opt-in, the daily launchd job excludes it, and the only current fix is a manual terminal sync from an FDA host. The dashboard's Refresh button (`/api/refresh` in `scripts/pulse_server.py`) currently only re-renders HTML — it runs no data refresh.

The launchd `pulse-server` has **no Full Disk Access**, so it can't run the SQLite reminders sync. But the signed helper we already shipped holds a durable **Reminders (EventKit) grant — no FDA** — and reads reminders fine.

## v1 scope (the only thing being built now)

Make the **existing** Refresh button populate the column, FDA-free, via the helper. Three edits, no new files, no DB writes, no log files.

1. **Helper** (`apple_reminders_helper_app.swift`): add a `list-active` op — list incomplete reminders in the configured list via EventKit, write `[{reminder_id, title, due_at}]` to the response JSON.
2. **`/api/refresh`** (`pulse_server.py`): before the existing render, `open` the helper (reuse the orchestrator's invoker) with a `list-active` request, read the response, write it to `temp/apple-reminders/active.json`. Catch failure → status in the response, never fatal. Does **not** run the heavy `refresh_index()` sources inline (they'd block the single-thread server; they stay scheduled).
3. **Column** (`pulse_web.py`): render the column from `active.json`.

### Observable checklist
- [ ] Helper `list-active` op returns incomplete reminders for the configured list via EventKit.
- [ ] `/api/refresh` populates `temp/apple-reminders/active.json` via the helper, then renders; a helper failure is reported in the response, not fatal.
- [ ] Column renders active reminders from that JSON.

### QA gate
- [ ] Clicking Refresh repopulates the column in **<2s** on a machine where the helper holds only the Reminders grant (no FDA); no UI freeze.
- [ ] No FDA dependency and no inline `refresh_index` heavy sync in the render path.
- [ ] **Single write path:** the column path writes only the ephemeral `active.json` — it is **not** a second writer to the `apple_reminders` table (sole writer stays `upsert_apple_reminders`).
- [ ] Helper `open`+poll has a fixed timeout (default 30s) → typed error, never an unbounded wait.
- [ ] `pytest tests/` green; one self-check parses a fixture `list-active` payload.

## Deferred follow-ups (not v1 — build when the trigger fires)

- **`/api/restart` + button.** Restart wedged launchd sync jobs from the UI. **Trigger:** only if `daily-sync` keeps failing — the real fix is *why `com.rebalance-os.daily-sync` exits 1*, not a button to re-kick it. If built: `launchctl kickstart -k` against a **hardcoded allowlist of sync labels** (exclude `pulse-server` — self-restart SIGKILLs the responder); localhost-only, list-form subprocess args (no shell, no injection); a one-line `logging.info` is enough — no JSONL contract.
- **Focus 5 app wiring.** "Refresh All"/"Restart" menu items that POST the endpoints. **Trigger:** when you actually live in the Focus 5 app and want it to drive a server refresh. ~20 LOC; the app owns no refresh logic, just calls endpoints. (Focus 5 doesn't show the reminders column, so it's irrelevant to v1.)
- **JSONL audit log.** Append-only log of refresh/restart actions. **Trigger:** only if a state-changing action (i.e. restart) ships AND a silent failure ever needs history. A re-read button doesn't earn a log file.

## Non-Goals (ponytail)

- No full `refresh_index()` on the button (blocks the server; stays scheduled).
- No new DB table/writer, no audit log, no per-service restart UI, no WebSocket progress, no auth/queue — single-user localhost tool.
- `pulse-server` self-restart — excluded by design (kill-group race).

## Risks and Mitigations

- **Helper grant drift** — the Reminders grant is durable on the stable bundle id; a rebuild keeps the id (codesign id verified before trust).
- **`open` from a launchd process** — `pulse-server` is a LaunchAgent (gui domain), so LaunchServices/`open` works; a system LaunchDaemon would not. Mitigation: keep it a LaunchAgent.
- **Helper latency on the button** — ~0.3–0.5s per click (`open` + EventKit + file). Acceptable for an explicit button; not called on the timed auto-render. `# ponytail: button-gated, not per-render`.
