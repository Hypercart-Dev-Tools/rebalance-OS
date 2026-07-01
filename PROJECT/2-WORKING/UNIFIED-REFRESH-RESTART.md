---
title: Unified UI Refresh + Restart (system-wide)
doc_type: project-plan
status: active
owner: Noel Saw
created: 2026-06-27
updated: 2026-07-01
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
| **Phase QA-R remediation shipped + merged (2026-07-01, PR #100).** All 7 findings (F1–F7) addressed: helper failure now surfaces `ok: false` + a dashboard "⚠ Reminders stale" badge (last-good `active.json` preserved); 8 new tests in `tests/test_unified_refresh_remediation.py` (fixture parse, failing-invoker unchanged-snapshot, cold-start); DB-less rendering documented as an intentional design choice; `ACTIVE_JSON_PATH` promoted to a shared module-scope constant in both `pulse_server.py`/`pulse_web.py`; imports lifted to module scope with the private-symbol coupling documented; envelope versioned (`{"schema_version": 1, "items": [...]}`, backward-compat reader for the old bare-list shape); Swift `semaphore.wait()` bounded to 4.5s with a typed timeout error. agy review: **Approved**, all 7 findings `[Pass]`. → `relay-system/2026-07-01/marathon-a-unified-refresh-qa-r.md` | **Gather feedback / operator litmus** on the live dashboard, then fold this doc into `3-COMPLETED`. No further build work queued — the deferred follow-ups below (`/api/restart`, Focus 5 wiring, audit log) stay parked until their triggers fire. |

## Problem

The pulse dashboard's Apple Reminders column shows "No active reminders" and silently empties after any reindex: the source is opt-in, the daily launchd job excludes it, and the only current fix is a manual terminal sync from an FDA host. The dashboard's Refresh button (`/api/refresh` in `scripts/pulse_server.py`) currently only re-renders HTML — it runs no data refresh.

The launchd `pulse-server` has **no Full Disk Access**, so it can't run the SQLite reminders sync. But the signed helper we already shipped holds a durable **Reminders (EventKit) grant — no FDA** — and reads reminders fine.

## v1 scope (the only thing being built now)

Make the **existing** Refresh button populate the column, FDA-free, via the helper. Three edits, no new files, no DB writes, no log files.

1. **Helper** (`apple_reminders_helper_app.swift`): add a `list-active` op — list incomplete reminders in the configured list via EventKit, write `[{reminder_id, title, due_at}]` to the response JSON.
2. **`/api/refresh`** (`pulse_server.py`): before the existing render, `open` the helper (reuse the orchestrator's invoker, **short timeout ~5s** for this synchronous handler) with a `list-active` request. **Last-good-snapshot-wins:** write `temp/apple-reminders/active.json` **only** after a fully-parsed successful response (atomic tmp→rename); on timeout/malformed/failure, **leave the prior `active.json` untouched** and return the error in the status — a failed refresh must never empty the column. Does **not** run the heavy `refresh_index()` sources inline (they'd block the single-thread server; they stay scheduled).
3. **Column** (`pulse_web.py`): render the column from `active.json`.

### Observable checklist
- [x] Helper `list-active` op returns incomplete reminders for the configured list via EventKit.
- [x] `/api/refresh` populates `temp/apple-reminders/active.json` via the helper, then renders; a helper failure is reported in the response, not fatal.
- [x] Column renders active reminders from that JSON.

### QA gate
- [x] Normal refresh repopulates the column in **<2s** on a machine where the helper holds only the Reminders grant (no FDA); a helper failure returns a typed error within the bounded **~5s** timeout (no longer hang, no full-page freeze).
- [x] **Last-good-snapshot-wins:** a failed/timed-out/malformed helper response leaves the prior `active.json` intact — a failed refresh never empties the column. (Self-check: feed a failing invoker, assert `active.json` unchanged.) — `FailingInvokerTests`, 2026-07-01.
- [x] No FDA dependency and no inline `refresh_index` heavy sync in the render path.
- [x] **Single write path:** the column path writes only the ephemeral `active.json` (atomic tmp→rename) — it is **not** a second writer to the `apple_reminders` table (sole writer stays `upsert_apple_reminders`).
- [x] `pytest tests/` green; one self-check parses a fixture `list-active` payload. — `ListActiveParseTests`, 8/8 in `tests/test_unified_refresh_remediation.py`.

## Phase QA-R — v1 Remediation (2026-06-29)

> QA review of the Lane B build (commit `74b8b52`). The code is close, but it
> shipped with the v1 **Observable checklist and QA gate above still unchecked**,
> and three of those gate items are not actually met. The Status said "tests pass"
> — true of the pre-existing suite, but **no test exercises the new path**. Fix the
> following before v1 is considered gate-passed and feedback is gathered.

**Findings (what the review surfaced):**

- **Silent helper failure (contradicts the v1 mandate "a failed refresh must never empty the column").** `/api/refresh` captures `helper_error` but still returns `{"ok": True, …, "helper_error": …}` (`pulse_server.py`). The dashboard only keys off `ok`, so a helper failure is invisible: the button reports success while the column silently serves stale/empty data. The error is *in the response* but not *surfaced to the operator*.
- **No automated coverage.** QA gate "one self-check parses a fixture `list-active` payload" and "feed a failing invoker, assert `active.json` unchanged" are both unmet — nothing under `tests/` references `list-active` / `active.json` / `/api/refresh`. Last-good-wins is implemented (atomic `tmp→replace`, untouched on error) but **never tested**, so a future edit can regress it silently.
- **DB read path dropped → cold-start regression.** `pulse_web.py` now reads **only** `temp/apple-reminders/active.json`; the prior `list_apple_reminders(DB_PATH, …)` render was removed. On any host where `active.json` doesn't exist yet (helper never succeeded), the column renders empty — the exact "silently empties" failure this plan exists to kill. Decide and document: seed `active.json` from the DB on first render, or accept DB-less rendering and state it explicitly.
- **One fact, two hardcoded literals.** `temp/apple-reminders/active.json` is written in `pulse_server.py` and re-derived in `pulse_web.py`. Extract a single shared constant (one canonical place) so the writer and reader cannot drift.
- **Reaching into a private API + in-handler imports.** `/api/refresh` imports `_open_bundle_invoker` (underscore = private) and does four `import`s inside the function body. Promote a public invoker entry point (or document the coupling) and lift the imports to module scope.
- **Unversioned cross-process contract.** The `{reminder_id, title, due_at}` shape in `active.json` is an implicit contract between the Swift helper and `pulse_web.py` with no `schema_version`. Add a version field or a single typed reader so a helper-side shape change is caught, not silently mis-rendered.
- **Helper fetch has no timeout.** `list-active` blocks on `semaphore.wait()` with no deadline; if EventKit never calls back the helper process hangs (the Python 5s invoker kills the `open`, but the helper can leak). Bound the wait.

### QA gate — Remediation
- [x] **Failure is visible, not swallowed:** a helper error surfaces in the dashboard (badge/marker), and the column renders last-good **with a staleness indicator** — never a silent empty. (Self-check: failing invoker → response signals not-ok **and** column shows the prior snapshot.) — F1, `pulse_server.py` returns `ok: helper_error is None`; `pulse_web.py` JS shows "⚠ Reminders stale".
- [x] **Last-good-wins is tested:** `pytest tests/` adds (a) a fixture `list-active` parse self-check and (b) a failing-invoker assertion that `active.json` is left byte-for-byte unchanged. — F2, 8/8 green.
- [x] **Cold-start decided + covered:** behavior when `active.json` is absent is explicit (seed-from-DB or documented DB-less) and has a test. — F3, DB-less rendering documented in-code; `ColdStartTests`.
- [x] **One canonical path constant** shared by writer and reader; **no private-symbol import** across modules; handler imports at module scope. — F4/F5, `ACTIVE_JSON_PATH` module constant in both files; imports lifted; `_open_bundle_invoker` coupling documented (not eliminated — acceptable per Reviewer).
- [x] **Contract versioned:** `active.json` items carry a `schema_version` (or a single typed reader guards the shape). — F6, `{"schema_version": 1, "items": [...]}` with backward-compat bare-list reader.
- [x] **Bounded helper:** the EventKit fetch wait has a timeout; a hung list returns a typed error within the ~5s budget. — F7, `semaphore.wait(timeout: .now() + 4.5)`.
- [x] The original **Observable checklist and QA gate above are checked off with evidence** (or amended with the reason a box is intentionally N/A). — see above.

**Closed 2026-07-01** via relay `relay-system/2026-07-01/marathon-a-unified-refresh-qa-r.md` (Producer PASS, Reviewer Approved, all 7 findings `[Pass]`); merged `development` in PR #100 (`df9600f`). Remaining: operator litmus on the live dashboard, then archive to `3-COMPLETED`.

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
