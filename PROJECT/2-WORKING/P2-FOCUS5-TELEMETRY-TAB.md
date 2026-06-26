---
title: Focus 5 Float — Telemetry Tab
status: planning
doc_type: project-plan
owner: Noel Saw
created: 2026-06-25
updated: 2026-06-25
goal: "Add a third Telemetry tab to Focus 5 Float that reads health-annotated JSON rows from ~/Documents/telemetry/ and renders them with the existing Theme/RosterHealth styling plus the smallest safe status-dot extension needed for orange health."
priority: P2
parent: PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md
branch: development
rollout_rule: app must remain buildable (`swift build` green) after every change; existing Focus 5 / Dirty Five behavior must be unchanged
---

## Status

| What was just completed | What's next |
|---|---|
| **Phases 0 + 1 — DONE (2026-06-25).** `ViewMode` enum added alongside existing `rankingMode`; `HealthDot` (orange-capable) added to `Components.swift`; `TelemetryModels`, `TelemetryReader`, `TelemetryRowView` implemented; header Picker migrated to `ViewMode` with `isDirtyView` shim preserved; telemetry tab renders newest-first with `RosterHealth.tint` header rollup. `swift build` clean; `FOCUS5_SELFTEST=1` passes (fixture path unchanged). Demo seed at `~/Documents/telemetry/focus5float-demo.json`. | **Operator litmus:** launch the app, switch to 📊 Telemetry tab, confirm three demo rows appear green/orange/red. Then move doc to `3-COMPLETED`. |

## Table of Contents

- [Goal](#goal)
- [Effort Estimate](#effort-estimate)
- [Context](#context)
- [Reuse Map](#reuse-map)
- [Non-Goals](#non-goals)
- [Demo Seed](#demo-seed)
- [Phase 0 — Spike (ViewMode Enum + JSON Schema)](#phase-0--spike-viewmode-enum--json-schema)
- [Phase 1 — Telemetry Tab Implementation](#phase-1--telemetry-tab-implementation)
- [Open Questions](#open-questions)

## Goal

Extend the Focus 5 Float panel with a third **Telemetry** tab that reads `.json` files from `~/Documents/telemetry/`, decodes them as a flat array of health-status rows, and renders each row with a health dot, a title, and a short description — reusing the existing visual system and only extending shared health-dot behavior where the current API is too narrow.

## Effort Estimate

**Small-Medium — ~3–4 hours.** Most of the styling is already present, but the current shared health dot only expresses green/red/grey, the model stores `rankingMode` rather than a persisted boolean mode, and the app already has a 90-second refresh loop. The least-risk implementation adds a JSON model, a file reader, a small `viewMode` layer for panel selection, and one centralized orange-dot path. There are no backend changes and no new dependencies.

Breakdown:

| Area | Lines changed/new | Notes |
|---|---|---|
| `ViewMode` enum + header Picker | ~25 changed | Adds a panel-selection mode without replacing `rankingMode` / `isDirtyView` |
| `TelemetryModels.swift` (new) | ~25 new | `TelemetryEntry` Codable + `HealthStatus` enum |
| `TelemetryReader.swift` (new) | ~40 new | Reads `~/Documents/telemetry/*.json`, decodes, merges rows |
| `ContentView.swift` telemetry block | ~40 changed/new | Route `.telemetry` case and keep empty-state reuse local to the file |
| `Components.swift` | ~10 changed | Add one orange-capable path to the shared status dot or a thin wrapper |
| `Focus5FloatApp.swift` | 0 | Right-click menu can remain ranking-only for v1 if `isDirtyView` stays as a shim |

## Context

The current panel header has a two-option segmented control:

```
Picker → "🎯 Focus 5" (isDirtyView = false) / "🧹 Dirty Five" (isDirtyView = true)
```

In the actual code, `Focus5Model` stores `rankingMode: String?` and derives `isDirtyView` from it; the app shell also has a separate right-click **Ranking Mode** menu and a 90-second polling timer. Adding a third panel tab most safely means:

1. Adding `viewMode: ViewMode` for panel selection without replacing `rankingMode`.
2. Keeping `isDirtyView` as a computed shim so the fetch/cache/menu code stays intact.
3. Updating the panel `Picker` to bind to `ViewMode` and route focus/dirty through the existing `setMode(dirty:)` path.
4. Routing the third case to a telemetry list in `ContentView.content`, and deciding explicitly whether telemetry should participate in the existing poll-driven refresh.

The **health-signal rendering** is only partially reusable as-is — `StatusDot` in `Components.swift` currently models green/red/grey from `isDirty + healthAvailable`, so telemetry's orange state needs a small shared extension or wrapper. `RosterHealth.tint()` is still useful for the header rollup, but it does not by itself solve per-row orange mapping.

Data source: `~/Documents/telemetry/*.json`. Each file is a JSON array of objects; for v1 the reader should merge all rows and sort them newest-first by `updatedAt` descending so the latest incoming signal renders at the top.

## Reuse Map

| Existing asset | Telemetry use |
|---|---|
| `StatusDot` (`Components.swift`) | Reuse after a small orange-capable API expansion or a thin wrapper; current API is only green/red/grey |
| `RosterHealth.tint(dirty:total:)` | Header health rollup over all telemetry rows |
| `Theme.*` | All spacing, typography, and existing semantic colors; add a theme token only if orange needs to become first-class |
| `emptyState(...)` (`ContentView.swift`) | Reusable with the least code if the telemetry list stays in `ContentView.swift` for v1 |
| `LoadState` enum (`Focus5Model.swift`) | Reused as-is for the telemetry load path |
| `RelTime.ago()` (`Time.swift`) | Available for `updatedAt` timestamps if present in JSON |

## Non-Goals

- No backend changes — file read only; no MCP/server involvement.
- No write-back to the telemetry files.
- No new filesystem watch service (`FSEvents`, polling loop, or watcher daemon) beyond the app's existing refresh behavior.
- No expanding rows (flat list only for v1; `CardSection` available later if needed).
- No sorting UI — rendered newest-first by `updatedAt`, with no user-selectable sort mode in v1.

## Demo Seed

Local demo seed created at `~/Documents/telemetry/focus5float-demo.json`.

```json
[
	{
		"health": "green",
		"title": "GitHub sync healthy",
		"description": "Hourly repo sync completed on schedule with no retries.",
		"updatedAt": "2026-06-25T14:15:00Z"
	},
	{
		"health": "orange",
		"title": "Calendar edge lag",
		"description": "Calendar edge snapshot is 47 minutes old; refresh is behind but not failed.",
		"updatedAt": "2026-06-25T13:41:00Z"
	},
	{
		"health": "red",
		"title": "Pulse publish blocked",
		"description": "Latest pulse publish attempt failed because the target repo remote was unavailable.",
		"updatedAt": "2026-06-25T12:58:00Z"
	}
]
```

Assumed v1 schema: `health`, `title`, and `description` required; `updatedAt` optional ISO-8601; unknown extra keys ignored.

---

## Phase 0 — Spike (ViewMode Enum + JSON Schema)

> Validate the two structural assumptions before writing UI: (1) adding `viewMode` alongside the existing ranking contract compiles cleanly, and (2) the telemetry JSON schema is well-defined.

- [x] Define `enum ViewMode: String { case focus5, dirtyFive, telemetry }` in app code; add `viewMode` to `Focus5Model` without replacing `rankingMode`.
- [x] Keep `isDirtyView` as a computed shim and confirm its existing call sites still compile unchanged.
- [x] Confirm the telemetry JSON schema against the demo seed: each file is an array of objects with at minimum `health` (`"green"` | `"orange"` | `"red"`), `title` (String), `description` (String). Optionally `updatedAt` (ISO-8601).
- [x] Define the v1 sort contract: rows with `updatedAt` sort descending (newest first); rows missing `updatedAt` fall below dated rows in stable file-read order.
- [x] `swift build` green after the `viewMode`-only change (no telemetry rows wired yet).

### QA Checklist — Phase 0

- [x] **No regression:** existing Focus 5 / Dirty Five ranking, mode switch, and server fetch behavior unchanged after `viewMode` is added.
- [x] **Schema truth:** telemetry JSON schema documented here before Phase 1 starts; nullable fields noted.
- [x] **Build:** `swift build` green on the spike branch.

---

## Phase 1 — Telemetry Tab Implementation

> Add the full Telemetry tab: model, file reader, view, wired into the panel.

- [x] **`TelemetryModels.swift`** — define `HealthStatus` (`.green` / `.orange` / `.red`; maps to `Theme.diffAdd` / `.orange` / `Theme.diffRemove`) and `TelemetryEntry: Codable, Identifiable` (`id`, `health`, `title`, `description`, optional `updatedAt`).
- [x] **`TelemetryReader.swift`** — `TelemetryReader.load() -> [TelemetryEntry]`: reads `~/Documents/telemetry/*.json` (using `FileManager`), decodes each file as `[TelemetryEntry]`, merges all rows, sorts by `updatedAt` descending, and returns. Rows with missing/unparseable `updatedAt` sort after dated rows. Handles missing folder (returns `[]`), malformed files (skips with `Logger` warning, never crashes).
- [x] **`Focus5Model.swift`** — add `viewMode: ViewMode`, telemetry storage, and a refresh path that fetches server data for focus/dirty modes and re-reads files for telemetry mode. Keep `rankingMode` and `isDirtyView` intact for the existing server contract.
- [x] **`ContentView.swift`** — swap the panel `Picker` binding from `Bool` to `ViewMode`; add `.telemetry` → `"📊 Telemetry"`; route `.telemetry` in `content` to a small local telemetry list so the existing `emptyState(...)` helper can be reused without extra extraction.
- [x] **`Components.swift`** — add one centralized orange-capable status-dot path (`HealthDot` wrapping `HealthStatus`) so telemetry rows do not duplicate dot logic.
- [x] Refresh button (`↻`) in the header calls `model.refresh()` — for telemetry, `refresh()` re-reads the files. The existing 90-second poll reuses the same path while telemetry is selected; no separate watcher in v1.
- [x] `swift build` green; `FOCUS5_SELFTEST=1 swift run Focus5Float` still exits clean (fixture path unchanged).

### QA Checklist — Phase 1

- [x] **DRY:** orange-dot handling lives in `HealthDot` (`Components.swift`) only; telemetry rows do not duplicate status-dot color logic.
- [x] **Regression guard:** Focus 5 and Dirty Five tabs render identically to pre-change behavior (same data, same components, same fetch path).
- [x] **Error safety:** missing `~/Documents/telemetry/` folder → empty state, no crash; malformed JSON file → that file skipped, others still load.
- [x] **Ordering:** telemetry rows render top-to-bottom newest first by `updatedAt`; undated rows, if any, fall after dated rows.
- [x] **SOLID:** `TelemetryReader` is a pure read function (no side effects); `TelemetryRowView` is a pure function of `TelemetryEntry`; no networking in the view.
- [x] **Observability:** malformed-file skip logged via `Logger`; folder-missing case is silent (empty state, not an error).
- [x] **Build litmus:** `swift build` green; `FOCUS5_SELFTEST=1` passes (roster=5 mode=recent_activity).

---

## Phase 2 — Explicit File Selection + Visible Decode Errors

> Add "Select Telemetry File…" to the F5 menu bar, persist the selection, and surface decode errors in the UI. Replaces the implicit auto-folder-scan as the primary entry point.

### Design

- **No file selected (default):** `telemetryFileURL == nil` → "No file selected" empty state in the tab. Auto-folder scan is no longer the default; explicit selection is the only path.
- **File selected, decode fails:** `telemetryLoadError` is non-nil → error message shown in the tab instead of rows.
- **File selected, valid:** rows render as before.
- **Menu item:** shows the selected filename ("Telemetry: focus5float-demo.json") when a file is set; reverts to "Select Telemetry File…" when not set. Reflected live via `menuNeedsUpdate`.
- **Persistence:** file path stored in `UserDefaults` under `"telemetryFilePath"` (path string). Loaded in `Focus5Model.init()` so cold-launch restores the last selection.

### Checklist

- [x] `Focus5Model` — add `telemetryFileURL: URL?` (with `didSet` → persist to `UserDefaults` + call `refreshTelemetry()`); add `telemetryLoadError: String?`; add `init()` to restore path from `UserDefaults`; update `refreshTelemetry()` to read from the explicit URL (nil = clear entries + error, URL + bad decode = set `telemetryLoadError`, URL + good decode = clear error + set entries).
- [x] `Focus5FloatApp.swift` — add `selectTelemetryItem: NSMenuItem`; add "Select Telemetry File…" menu item (`⌘T`); add `selectTelemetryFile()` action (opens `NSOpenPanel` for `.json`, saves URL to model, switches to telemetry tab); update `menuNeedsUpdate` to reflect selected filename; import `UniformTypeIdentifiers` for `UTType.json`.
- [x] `ContentView.swift` — update `telemetryContent` to branch on `telemetryFileURL == nil` ("No file selected"), `telemetryLoadError != nil` (error + icon), and `entries.isEmpty` ("no signals"); update header info row to show selected filename instead of "N signals".
- [x] `AppDelegate.applicationDidFinishLaunching` — call `model.refreshTelemetry()` after `model.loadCache()` so a previously-selected file loads at cold-start.
- [x] `swift build` green; `FOCUS5_SELFTEST=1` passes.

### QA Checklist — Phase 2

- [ ] **Cold-start restore:** quit and relaunch with a file selected — telemetry tab shows the same file's rows without re-selecting. _(Operator litmus)_
- [ ] **No file selected default:** fresh launch with no UserDefaults entry → Telemetry tab shows "No file selected"; no folder scan occurs. _(Operator litmus)_
- [ ] **Decode error visible:** point at a `.json` file with valid JSON but wrong structure (e.g. `{}` or `[{"foo":1}]`) → Telemetry tab shows an actionable error message, not a blank screen. _(Operator litmus)_
- [ ] **Regression guard:** Focus 5 and Dirty Five tabs unaffected; `FOCUS5_SELFTEST=1` passes. ✓
- [ ] **Menu label:** after selecting a file, F5 right-click shows "Telemetry: <filename>" not "Select Telemetry File…". _(Operator litmus)_
- [ ] **Build:** `swift build` green. ✓

---

## Open Questions

1. **Refresh cadence:** Telemetry should reuse the app's existing 90-second poll loop while selected, plus manual refresh on `↻`. _Lean: keep 90 seconds for v1; it avoids introducing a second timer path._
2. **Undated rows:** If a producer omits `updatedAt`, should those rows sink below dated rows or be hidden? _Lean: keep them visible below dated rows._
3. **View extraction:** Keep telemetry rows local to `ContentView.swift` for the first pass, or extract a dedicated `TelemetryView` immediately? _Lean: keep it local for v1; extract only if the view grows._
