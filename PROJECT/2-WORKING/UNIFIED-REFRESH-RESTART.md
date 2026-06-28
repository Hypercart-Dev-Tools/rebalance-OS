---
title: Unified UI Refresh + Restart (system-wide)
doc_type: project-plan
status: active
owner: Noel Saw
created: 2026-06-27
updated: 2026-06-27
goal: "One durable, UI-triggered refresh and restart for the whole rebalance surface — two endpoints on the always-on pulse-server that every UI (pulse dashboard, Focus 5 app) calls, so no source is ever stale and no manual terminal scripts are needed again."
priority: P2
related:
  - scripts/pulse_server.py
  - scripts/pulse_web.py
  - src/rebalance/ingest/index_ops.py
  - src/rebalance/ingest/apple_reminders.py
  - scripts/apple_reminders_helper_app.swift
  - macOS/Apps/Focus5Float/
---

## Status

| What was just completed | What's next |
|---|---|
| Plan written + /ponytail-scoped, then **SWE-rubric reviewed and tightened (2026-06-27)**: dropped `pulse-server` self-restart (Blast race), re-scoped `/api/refresh` to fast data only (Minimal — no inline heavy sync that blocks the server), and added the Diagnosability section (JSONL audit per call, helper poll stop-condition, single-write-path, UTC, idempotent). Shape: **two endpoints on the always-on pulse-server (`POST /api/refresh`, `POST /api/restart`), every UI a thin caller**; reminders route through the signed helper (EventKit, no FDA). | **Phase 1** — add an FDA-free `list-active` EventKit op to the helper and read it for the dashboard column. |

## Problem

Data goes stale and there is no durable, UI-based way to refresh or restart the system:

- The pulse dashboard "Refresh" button (`/api/refresh`) only **re-renders** the HTML; it runs no data sync.
- The Apple Reminders column is empty because its source is opt-in and the daily launchd job excludes it; the only current fix is a **manual terminal sync from an FDA host** — exactly the hacky re-paste the operator wants gone.
- `com.rebalance-os.daily-sync` is currently exiting `1` with no UI to restart it.
- The Focus 5 app is now multi-functional (roster + Obsidian notes + JSON telemetry) and needs the same refresh/restart, not a per-app reimplementation.

## Architecture

One source of truth, every UI a thin caller. No surface owns refresh logic.

```
pulse dashboard button ┐
Focus 5 app menu item  ├── POST ──▶ pulse-server :8767 (launchd, always on)
(future surfaces)      ┘             ├─ POST /api/refresh → refresh all data + render
                                     └─ POST /api/restart → launchctl kickstart -k <allowlist>
```

- **`/api/refresh`** refreshes **fast, user-facing data only** — Apple Reminders via the signed helper (`open` it → EventKit `list-active`, no FDA) + re-render. It does **not** run the heavy `refresh_index()` sources (github/vault scans) inline: those would block the single-threaded server for seconds–minutes. They stay on their scheduled launchd jobs and are recovered via `/api/restart`. Returns per-source status (one source failing never fails the whole call) and appends one JSONL audit line.
- **`/api/restart`** runs `launchctl kickstart -k` against a **hardcoded allowlist** of `com.rebalance-os.*` **sync** labels. **`pulse-server` is excluded** — self-restart would SIGKILL the process serving the request (kill-group race); a rare server restart stays a manual action. Idempotent (safe to click twice); appends one JSONL audit line.

Why durable: logic lives in committed code, buttons live in committed UI, the launchd jobs are already installed. Reboot-safe; nothing to re-paste.

Why it sidesteps FDA: the launchd server can't hold FDA, so reminders go through the helper (Reminders grant, durable on bundle id). Every other source already runs under launchd today.

Known launchd labels (2026-06-27): `pulse-server`, `pulse-sync`, `pulse-web-sync`, `daily-sync`, `github-sync`, `vault-sync`, `obsidian-rollover`, `com.user.git-pulse`. The restart allowlist is the **sync** subset (excludes `pulse-server`).

## Diagnosability

- Every `/api/refresh` and `/api/restart` call appends one **JSONL** line to `temp/logs/refresh-restart.jsonl` (append-only, **UTC**): action, labels/sources touched, per-item outcome, `duration_ms`. This is both the audit trail and the repro breadcrumb.
- The helper `open`+poll has a **fixed timeout** (default 30s) — the loop's stop condition. A non-responding helper returns a typed error and a logged line, never an unbounded wait.
- Both endpoints are **idempotent / crash-safe**: safe to click twice; a mid-run crash leaves no half-written state (column writes an atomic temp JSON; `kickstart` is naturally re-runnable).
- **Single write path:** the column read path writes only the ephemeral JSON above — it is **not** a second writer to the `apple_reminders` table (whose sole writer stays `upsert_apple_reminders`).

## Phase 1 - FDA-free reminders read for the column

Objective: populate the Apple Reminders column without Full Disk Access, reusing the signed helper.

### Observable checklist
- [ ] Add a `list-active` op to `apple_reminders_helper_app.swift`: list incomplete reminders in the configured list via EventKit, write them to the response JSON.
- [ ] Add a small Python entry (in `apple_reminders_write.py` or a sibling) that `open`s the helper with a `list-active` request and returns the parsed reminders.
- [ ] `pulse_web.py` renders the column from that result (cache to a temp JSON; no new DB writer).

### QA gate
- [ ] Column populates with active reminders on a machine where the helper holds only the Reminders grant (no FDA).
- [ ] No FDA dependency introduced into the launchd render path.
- [ ] `pytest tests/` green; one self-check parses a fixture reminder list.

## Phase 2 - `/api/refresh` does a real refresh

Objective: make the existing Refresh button refresh **data**, not just repaint.

### Observable checklist
- [ ] `/api/refresh` refreshes fast data — the Phase 1 helper read for reminders — then re-renders. Heavy `refresh_index()` sources are **not** run inline (they stay scheduled; recovered via `/api/restart`).
- [ ] Returns a per-source status object; a single source error is reported, not fatal.
- [ ] Appends one JSONL line per refresh (UTC ts, sources touched, per-source outcome, `duration_ms`).

### QA gate
- [ ] Clicking Refresh repopulates the reminders column in **<2s** (no UI freeze); partial failure surfaces in the response and never 500s the whole call.
- [ ] The refresh never blocks the server on a heavy sync (no inline `refresh_index` of github/vault).
- [ ] `pytest tests/` green; self-check asserts the partial-failure status shape **and** that a JSONL line is written.

## Phase 3 - `/api/restart` + dashboard button

Objective: restart wedged services (e.g. `daily-sync`) from the UI.

### Observable checklist
- [ ] `/api/restart` kickstarts a hardcoded allowlist of `com.rebalance-os.*` **sync** labels (e.g. `daily-sync`, `pulse-sync`, `vault-sync`, `github-sync`); **`pulse-server` excluded** (no self-restart).
- [ ] Each restart appends one JSONL line (UTC ts, labels, outcome).
- [ ] Add a "Restart services" button to the pulse dashboard next to Refresh.

### QA gate
- [ ] Restart bounces `daily-sync` (its `launchctl list` non-zero exit clears); the dashboard stays up (pulse-server not in the set).
- [ ] Restart is idempotent — clicking twice is safe.
- [ ] **Trust boundary:** server stays localhost-only; restart takes NO user-supplied label; subprocess args passed as a list (no shell). Self-check asserts the label set is a fixed constant with no caller input.

## Phase 4 - Focus 5 app wiring

Objective: same two endpoints, surfaced in the Focus 5 app — zero refresh logic in the app.

### Observable checklist
- [ ] Add "Refresh All" + "Restart services" menu items that POST `/api/refresh` and `/api/restart`.
- [ ] App shows the returned status (toast/menu state); owns no sync/restart logic of its own.

### QA gate
- [ ] Both menu items drive the server endpoints end-to-end; `swift build` green.
- [ ] App contains no EventKit/launchctl/sync code — it only calls the endpoints.

## Non-Goals (ponytail cuts — add when)

- **Generic service-manager UI / per-service toggles** — one restart-all. Add granularity when bouncing a single service is actually needed.
- **WebSocket/streamed progress** — spinner + final status. Add when a refresh runs >~10s and the stage matters.
- **Auth / request queue** — localhost, single user. Add only if it ever leaves localhost.
- **Config for the restart label list** — hardcode it (labels change ~never); a `# ponytail:` comment names it.
- **Combined restart+refresh "Reset" button** — keep them separate; add a combo only if you find yourself always clicking both.

## Risks and Mitigations

- **`/api/restart` is command execution over HTTP** (undo class: *easy* — `kickstart` is idempotent) — mitigated by localhost-only bind (already enforced), a fixed label allowlist, and list-form subprocess args (no shell, no injection). Shield: the allowlist; tripwire: n/a (reversible). Note: localhost endpoints are reachable by any browser page via `fetch` (same exposure as the existing `/api/refresh`/`/api/goals/complete`) — acceptable for a single-user local tool.
- **Self-restart race (avoided, not mitigated)** — restarting `pulse-server` from itself SIGKILLs the responder and races the kill-group; **resolved by excluding `pulse-server` from the allowlist**, not by engineering a detached double-fork. The one-way door is removed by scope cut.
- **Helper grant drift** — the Reminders grant is durable on the stable bundle id; a rebuild keeps the id, so the grant survives (codesign id verified before trust).
