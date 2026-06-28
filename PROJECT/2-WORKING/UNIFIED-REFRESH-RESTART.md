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
| Plan written (2026-06-27) after a /ponytail review. Established the shape: **two endpoints on the always-on pulse-server (`POST /api/refresh`, `POST /api/restart`), every UI a thin caller.** Root cause captured: the launchd pulse-server has no Full Disk Access, so the Apple Reminders refresh must route through the already-built signed helper (EventKit, Reminders grant, no FDA), not the SQLite sync. | **Phase 1** — add an FDA-free `list-active` EventKit op to the helper and read it for the dashboard column. |

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

- **`/api/refresh`** runs `refresh_index()` for the launchd-capable sources **plus Apple Reminders via the signed helper** (`open` it → EventKit `list-active`, no FDA), then re-renders. Returns per-source status; one source failing never fails the whole call.
- **`/api/restart`** runs `launchctl kickstart -k` against a **hardcoded allowlist** of `com.rebalance-os.*` labels. Self-restart (pulse-server) is a detached kickstart that outlives the response; the page auto-reloads.

Why durable: logic lives in committed code, buttons live in committed UI, the launchd jobs are already installed. Reboot-safe; nothing to re-paste.

Why it sidesteps FDA: the launchd server can't hold FDA, so reminders go through the helper (Reminders grant, durable on bundle id). Every other source already runs under launchd today.

Known launchd labels (2026-06-27): `pulse-server`, `pulse-sync`, `pulse-web-sync`, `daily-sync`, `github-sync`, `vault-sync`, `obsidian-rollover`, `com.user.git-pulse`.

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
- [ ] `/api/refresh` runs `refresh_index()` for launchd-capable sources + the Phase 1 helper read for reminders, then renders.
- [ ] Returns a per-source status object; a single source error is reported, not fatal.

### QA gate
- [ ] Clicking Refresh repopulates reminders and the other sources; partial failure surfaces in the response and never 500s the whole call.
- [ ] `pytest tests/` green; self-check asserts partial-failure status shape.

## Phase 3 - `/api/restart` + dashboard button

Objective: restart wedged services (e.g. `daily-sync`) from the UI.

### Observable checklist
- [ ] `/api/restart` kickstarts a hardcoded allowlist of `com.rebalance-os.*` labels; detached self-restart for `pulse-server`.
- [ ] Add a "Restart services" button to the pulse dashboard next to Refresh.

### QA gate
- [ ] Restart bounces `daily-sync` and the page survives a pulse-server self-restart (reconnects after).
- [ ] **Trust boundary:** server stays localhost-only; restart takes NO user-supplied label; subprocess args passed as a list (no shell). Self-check asserts the label set is fixed and contains no caller input.

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

- **`/api/restart` is command execution over HTTP** — mitigated by localhost-only bind (already enforced), a fixed label allowlist, and list-form subprocess args (no shell, no injection).
- **Helper grant drift** — the Reminders grant is durable on the stable bundle id; a rebuild keeps the id, so the grant survives (codesign id verified before trust).
- **Self-restart kills the responder** — detached kickstart + the dashboard's existing auto-reload covers reconnection.
