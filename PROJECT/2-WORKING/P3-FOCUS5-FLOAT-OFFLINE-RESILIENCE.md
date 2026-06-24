---
title: Focus 5 Float — Offline Cache & Manual Server Start
status: in-progress
doc_type: project-plan
owner: Noel Saw
created: 2026-06-24
updated: 2026-06-24
goal: "Make Focus 5 Float useful when rebalance serve is down: persist the last-known roster to disk for an instant cold-start, and add a one-click control to start the local server."
priority: P3
parent: PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md
branch: development
rollout_rule: each phase leaves the app buildable (`swift build` green) and degrades safely when the server is absent
---

## Status

| What was just completed | What's next |
|---|---|
| **Phases 1 + 2 — DONE (both features built).** Offline cache (instant cold-start, "cached · {age}", corruption-safe) **and** one-click "Start rebalance serve" (detached `Process`, login-shell binary resolution, poll-until-healthy, button in offline state + header + ⌘S menu). Headless verified: cache round-trip + binary resolution (`/Users/noelsaw/bin/rebalance`). `swift build` green. | **Operator litmus:** cold-launch offline → "Start server" brings the roster up. Then bundled-`.app` re-verify of binary resolution lands with parent Phase 5 packaging. |

## Table of Contents

- [Goal](#goal)
- [Context & Current Behavior](#context--current-behavior)
- [Non-Goals](#non-goals)
- [Phase 1 — Offline Roster Cache](#phase-1--offline-roster-cache)
- [Phase 2 — Manual "Start rebalance serve" Control](#phase-2--manual-start-rebalance-serve-control)
- [Open Questions](#open-questions)

## Goal

Two follow-on enhancements to the now-feature-complete [Focus 5 Float](../2-WORKING/P2-MACOS-FOCUS5-FLOAT.md) app, both about the case the app can't currently handle well — **`rebalance serve` is not running**:

1. **Offline cache** — persist the last successful roster so a cold launch shows real data instantly (and stays useful) even with the server down, instead of an empty "offline" state.
2. **Manual server start** — a one-click control to start the local `rebalance serve` from the panel, so the operator never has to drop to a terminal.

This is a **non-competing follow-on** to the parent plan (which owns the core build, Phases 0–5). It only extends the offline-handling that today lives in memory.

## Context & Current Behavior

- `Focus5Model` keeps the last-known roster **in memory only**. A cold start with no server → the `.failed` empty state ("Can't reach the Focus 5 server / start `rebalance serve`"). Nothing is shown from a prior session.
- This **supersedes the deferred Phase-4 GRDB read-only fallback**: caching the JSON the app already fetched is simpler, schema-decoupled, and preserves the *live-probed* values from the last success (GRDB would only have the stale roster snapshot, no live health).
- The app is a **non-sandboxed, ad-hoc-signed menu-bar agent** (`setActivationPolicy(.accessory)`), so launching a subprocess (`Process`) or `launchctl` is permitted.
- **GUI apps do not inherit the shell `PATH`**, so the `rebalance` binary must be resolved deliberately (a configured path, a login-shell lookup, or known venv/bin locations) — this is the main risk in Phase 2.
- The operator already runs launchd-managed `com.rebalance-os.*` jobs; a serve job may be `launchctl kickstart`-able rather than spawned fresh (decision in Phase 2).
- Boundary unchanged: the roster carries local-only / PII fields (`local_path`, `vscode_url`, `remote_url`, `author_email`), so any cache file stays in the user's app-support dir on the same machine — never exported (see [CONTRACT.md](../../macOS/Apps/Focus5Float/CONTRACT.md)).

## Non-Goals

- Not a general server supervisor — no crash-watch / auto-restart loop (one manual start action only).
- No remote server management — localhost only; the local-only data boundary is unchanged.
- No caching beyond the roster JSON — no GRDB mirror, no full-DB copy, no extra artifacts.
- No new background daemon beyond what the operator already runs.

---

## Phase 1 — Offline Roster Cache

> Persist the last successful `/focus-5.json` and render it instantly on launch; keep showing it (clearly marked) while the server is unreachable.

- [x] `RosterCache` type ([RosterCache.swift](../../macOS/Apps/Focus5Float/Sources/Focus5Float/RosterCache.swift)): atomic save/load of the last successful response to `~/Library/Application Support/Focus5Float/roster-cache.json`, stamped with `fetchedAt` + `schemaVersion`.
- [x] On launch, `model.loadCache()` runs synchronously and renders immediately (instant cold start); the live `refresh()` then fires in the background.
- [x] On fetch **success**, `cache.save(resp)` overwrites; `showingCache=false`, server-fresh.
- [x] On fetch **failure with data present**, the cached/last-known roster stays on screen; header shows **"cached · {age}"** (when from disk) — distinct from the server-fresh "updated · {age}".
- [x] Cache invalidation: parse error / `schemaVersion` mismatch → `load()` returns nil (ignored), degrading to empty/offline — never a crash.
- [x] **Codec correction (vs original plan):** the cache uses its **own** round-trip codec (camelCase + ISO-8601), NOT `Focus5JSON.decoder()`. Re-encoding the models to disk produces camelCase keys, so decoding them back with the snake_case wire decoder would mismatch. The **live wire decode is still a single path** (`Focus5JSON.decoder()`); the cache is a separate Swift↔disk format. `apply(_:)` mapping is reused unchanged.

### QA Checklist — Phase 1

- [x] **DRY:** one `apply(_:)` → view-state mapping for live + cache; the live wire decode is still single (`Focus5JSON.decoder()`). The cache's own codec is intentional and documented (see codec correction above).
- [x] **SOLID:** `RosterCache` is a small injectable collaborator (`init(url:)`); `Focus5Model` keeps its shape — cache wired only at the `loadCache()` / success / failure boundaries.
- [x] **Resilience:** missing / corrupt / old-schema cache → `nil`, never a crash; `save` is best-effort `.atomic` and never throws into the caller.
- [x] **Observability:** `os_log` (category `cache`) on save (with repo count) and on miss/unreadable/stale-schema.
- [x] **Security/boundary:** cache lives only in the user's App Support dir (same machine); no field leaves the device — documented in [CONTRACT.md](../../macOS/Apps/Focus5Float/CONTRACT.md) ("Offline cache (local-only)").
- [~] **Litmus:** cache round-trip verified headlessly (`FOCUS5_CACHETEST` → 5 repos saved+loaded). _Operator: cold-launch with the server stopped shows "cached · {age}"; starting it + Refresh flips to "updated · {age}"._
- [x] **Anti-goal guard:** only the roster JSON envelope is cached — no DB mirror, no extra files.

---

## Phase 2 — Manual "Start rebalance serve" Control

> A one-click control that starts the local server and refreshes once it's healthy — no terminal needed.

- [x] **Start mechanism decided → detached `Process`.** Recon found **no `serve` launchd label** (operator runs `rebalance serve` manually), so `ServerLauncher.start()` spawns a detached `rebalance serve` (its own lifetime, IO → `/dev/null`). (Open Question 1 resolved.)
- [x] **Binary resolved robustly** ([ServerLauncher.swift](../../macOS/Apps/Focus5Float/Sources/Focus5Float/ServerLauncher.swift)): `REBALANCE_BIN` override → login-shell `<$SHELL> -lc 'command -v rebalance'` → known `/opt/homebrew`, `/usr/local`, `~/.local/bin` paths. Verified headlessly (`FOCUS5_RESOLVETEST` → `/Users/noelsaw/bin/rebalance`).
- [x] **"Start server" control** in the offline/failed state **and** the header (when offline) **and** the right-click menu (⌘S): `model.startServer()` spawns, shows a spinner, polls via `refresh()` until reachable (20s bound), applies the roster.
- [x] **Lifecycle = detached:** spawned with `Process` and not awaited → survives app quit, like the operator's normal `serve`. (Open Question 3 resolved.)
- [x] **Failure handling:** binary-not-found → actionable message; never-healthy-within-20s → "try Refresh"; bounded poll, no hang/crash. `isStartingServer` guards re-entry.
- [x] **Security:** fixed executable + `["serve"]` args; the only shell string is the hardcoded literal `command -v rebalance` (no user input); localhost only.

### QA Checklist — Phase 2

- [x] **Security:** fixed command + args, no user input on the command line, no interpolated shell beyond the hardcoded `command -v rebalance`; localhost only — reviewed for injection.
- [x] **SOLID:** `ServerLauncher` (resolve + start) is a standalone enum; the model orchestrates start → poll; the UI just calls `startServer()` and renders `isStartingServer`/`startError`.
- [x] **Resilience:** missing binary, slow/no start (20s timeout), and re-entry (`isStartingServer` guard) all yield clear bounded states — no infinite poll, no crash.
- [x] **Observability:** `os_log` (category `launcher`) on resolve failure, chosen binary + spawned PID; `panel` log on the manual start action.
- [~] **Deploy/packaging note:** bundled `.app` must resolve the binary at runtime without a shell `PATH` — the login-shell lookup handles this; **re-verify from the installed `.app`** in Phase 5 packaging (the riskiest cross-cut).
- [~] **Litmus:** binary-resolution verified headlessly; build green. _Operator: from a cold, offline app, click **Start server** → server comes up → roster appears, no terminal._
- [x] **Anti-goal guard:** a single manual start action only — no auto-restart loop, no supervision.

---

## Open Questions

1. ~~**Start mechanism**~~ — **RESOLVED: detached `Process`.** No `serve` launchd label exists, so spawn `rebalance serve` directly.
2. ~~**Binary resolution**~~ — **RESOLVED: auto-resolve with override.** `REBALANCE_BIN` → login-shell lookup → known paths.
3. ~~**Started-server ownership**~~ — **RESOLVED: detached** (survives app quit, like the operator's normal serve).
4. **Auto-start option:** a setting to auto-start the server on launch when it's down? _Still deferred — manual button shipped; add auto-start only if wanted._
