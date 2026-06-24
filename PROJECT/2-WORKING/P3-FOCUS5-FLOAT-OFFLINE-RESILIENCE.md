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
| **Phase 1 — Offline roster cache — DONE.** `RosterCache` (atomic save/load to App Support), `loadCache()` on launch for instant cold-start, "cached · {age}" header indicator, schema-versioned + corruption-safe; cache round-trip verified headlessly (`FOCUS5_CACHETEST` → 5 repos). `swift build` green. | **Phase 2 — Manual "Start rebalance serve" control:** resolve the `rebalance` binary, start the local server, poll until healthy, then refresh. |

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

- [ ] **Decide + record the start mechanism:** `launchctl kickstart -k <com.rebalance-os.* serve label>` if such a label exists, otherwise spawn a **detached** `rebalance serve`. (Open Question 1.)
- [ ] **Resolve the `rebalance` binary robustly** (GUI apps lack shell `PATH`): try a configured path setting → login-shell `zsh -lc 'command -v rebalance'` → known venv/bin locations; clear error if unresolved.
- [ ] Add a **"Start server"** button to the offline/failed state (and optionally the right-click menu): launches the server, shows a spinner, **polls `/focus-5.json` until healthy** (bounded timeout), then calls `model.refresh()`.
- [ ] **Lifecycle:** the started server should behave like the operator's normal `serve` (survives app quit) — confirm detached vs app-owned and record it. (Open Question 3.)
- [ ] **Failure handling:** binary-not-found, port-in-use, or never-healthy-within-timeout each surface an actionable message — never a hang or crash.
- [ ] **Security:** the control runs only the local `rebalance serve` with a fixed argument list — no user-supplied args, no string-interpolated shell, localhost only.

### QA Checklist — Phase 2

- [ ] **Security:** fixed command + args (no shell string interpolation, no user input in the command line); localhost only; reviewed for command-injection.
- [ ] **SOLID:** a `ServerLauncher` encapsulates resolve → start → await-healthy; the UI just calls it and renders states.
- [ ] **Resilience:** missing binary / port-in-use / slow start all yield clear, bounded states — no hang, no crash, no infinite poll.
- [ ] **Observability:** `os_log` the resolve attempts, the chosen mechanism, the start result, and the poll outcome.
- [ ] **Deploy/packaging note:** the **bundled `.app` must resolve the binary at runtime without a shell `PATH`** — coordinate with Phase 5 packaging in the parent plan (this is the riskiest cross-cut).
- [ ] **Litmus:** from a cold, offline app, clicking **Start server** brings the server up and the roster appears — with no manual terminal step.
- [ ] **Anti-goal guard:** a single manual start action only — no auto-restart loop, no supervision.

---

## Open Questions

1. **Start mechanism:** `launchctl kickstart` an existing `com.rebalance-os.*` serve label, or spawn a detached `rebalance serve`? _Depends on whether a serve launchd job exists; confirm during Phase 2._
2. **Binary resolution:** ship an explicit "rebalance path" setting, auto-resolve via a login shell, or both (setting overrides auto)? _Lean: auto-resolve with a setting override._
3. **Started-server ownership:** app-owned (quits with the app) or detached (persists like the operator's normal serve)? _Lean: detached._
4. **Auto-start option:** a setting to auto-start the server on launch when it's down? _Defer — ship the manual button first, add auto-start only if wanted._
