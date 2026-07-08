---
title: "Focus5Float telemetry viewer: support .md (text viewer) alongside JSON (structured viewer)"
owner: noel@neochro.me
gh_issue: 121
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/121"
status: "Active (2-WORKING) — promoted 2026-07-07; queued in MARATHON-2026-07-07 Lane D, ready to fire (not yet fired, serializes after Lane C). QA'd via relay-xyz (reviewer=agy, 2026-07-06): Changes requested → 3 [Should] findings accepted + folded into Phase 1 (safe UTType, symmetric state clear, .md read size ceiling); seam/folder-scope/collision all [Pass]."
created: 2026-07-06
updated: 2026-07-07
doc_type: project
goal: >
  Let the Focus5Float telemetry tab open Markdown (.md) files in addition to structured JSON: when the
  selected file is .json render the existing structured TelemetryEntry viewer, and when it is .md render
  a read-only text/markdown viewer — chosen by file extension, with unreadable/unsupported files falling
  through to the existing visible error state.
non_goals: >
  No change to the JSON structured viewer's schema or the ~/Documents/telemetry/*.json folder auto-load.
  Read-only — no markdown editing. No new file types beyond .json and .md. No server/Python surface.
related:
  - PROJECT/2-WORKING/P2-FOCUS5-TELEMETRY-TAB.md
  - PROJECT/2-WORKING/FOCUS5-RESOLUTION-CHANGE-RESILIENCE.md
effort: 2
complexity: 2
risk: 2
phases: 2
---

## Status

| What was just completed | What's next |
|---|---|
| **Captured 2026-07-06** from issue #121, grounded in the current code. Confirmed the seam: `openFilePicker()` restricts `NSOpenPanel` to `UTType.json` ([Focus5Model.swift:141](../../macOS/Apps/Focus5Float/Sources/Focus5Float/Focus5Model.swift#L141)); `refreshTelemetry()` JSON-decodes into `telemetryEntries` ([Focus5Model.swift:154](../../macOS/Apps/Focus5Float/Sources/Focus5Float/Focus5Model.swift#L154)); `telemetryContent` renders structured rows ([ContentView.swift:265](../../macOS/Apps/Focus5Float/Sources/Focus5Float/ContentView.swift#L265)). The app already renders markdown for the bottom `focus5.md` note — reuse that path for the .md viewer. | **Phase 1** — allow `.md` in the picker, branch load + render on `pathExtension`. Queued as [MARATHON-2026-07-07 Lane D](MARATHON-2026-07-07.md). ⚠ Shares `ContentView.swift`/`SelfTest.swift` with the resolution-change lane — must serialize after it. |

---

## Table of contents

- [Thesis](#thesis)
- [Current shape (grounded)](#current-shape-grounded)
- [Phase 1 — Load + render .md as text, .json as structured](#phase-1--load--render-md-as-text-json-as-structured)
- [Phase 2 — Polish + self-test](#phase-2--polish--self-test)
- [Anti-goals](#anti-goals)

---

## Thesis

The telemetry tab is already a "pick a file, view it" surface — it just assumes the file is JSON. The
change is a **discriminator on file extension**: `.json` keeps the structured `TelemetryEntry` viewer;
`.md` reads the raw text and shows it in a scrollable read-only viewer (reusing the markdown rendering
the bottom-note already uses). Small, additive, reversible — no new tab, no schema change.

## Current shape (grounded)

- **Picker:** `openFilePicker()` sets `panel.allowedContentTypes = [UTType.json]` and title "Select
  Telemetry JSON File" ([Focus5Model.swift:141](../../macOS/Apps/Focus5Float/Sources/Focus5Float/Focus5Model.swift#L141)).
- **Load:** `telemetryFileURL.didSet` → `refreshTelemetry()`, which reads `Data(contentsOf:)` and
  `JSONDecoder().decode([TelemetryEntry].self)`, setting `telemetryEntries` or `telemetryLoadError`.
- **Render:** `telemetryContent` shows a no-file state, an error state, an empty state, or the
  `TelemetryRowView` list ([ContentView.swift:265](../../macOS/Apps/Focus5Float/Sources/Focus5Float/ContentView.swift#L265)).
- **Existing markdown:** `noteContent` (the vault `focus5.md`) is already rendered in-app — the .md
  viewer should reuse that renderer, not invent a second one.

---

## Phase 1 — Load + render .md as text, .json as structured

**Scope:** the smallest change that makes .md selectable and viewable without disturbing JSON.

**Observable checklist:**

- [ ] **Picker accepts .md.** `openFilePicker()` `allowedContentTypes` = `[.json, UTType(filenameExtension: "md") ?? .plainText]` — **no force-unwrap** (`UTType(filenameExtension:"md")` returns `nil` if MD isn't registered; a `!` would crash). Title/label generalized to "Select Telemetry File (.json or .md)". _(agy [Should] #1, 2026-07-06.)_
- [ ] **A file-kind discriminator.** Derive kind from `telemetryFileURL.pathExtension` (`json` → structured, `md` → text) — a small enum or computed property, single source of truth used by both load and render.
- [ ] **Branch the load, clearing the *other* mode's state both ways.** `refreshTelemetry()`: for `.json` keep the existing decode into `telemetryEntries` **and set `telemetryText = nil`**; for `.md` read the text into a new `telemetryText: String?` **and set `telemetryEntries = []`**; anything else sets `telemetryLoadError`. Symmetric clearing prevents a stale viewer from a prior selection. _(agy [Should] #3, 2026-07-06.)_
- [ ] **Size ceiling on the `.md` read.** The read is synchronous on `@MainActor` (`Focus5Model`), so cap it (e.g. read the first ~1 MB / N chars, append a "…truncated" note) to avoid freezing the UI on a huge file. `// ponytail: assumes telemetry .md < 1MB; truncate above that`. _(agy [Should] #2, 2026-07-06.)_
- [ ] **Branch the render.** `telemetryContent`: when the selected file is `.md`, show a scrollable read-only text viewer (reuse the note markdown renderer); when `.json`, the existing structured list. No-file / error states shared.
- [ ] **Unreadable file → existing error state**, not a crash (parity with today's JSON error path).

### Phase 1 — QA gate

- [ ] `swift build` green (release).
- [ ] **Litmus (both paths):** selecting a `.json` telemetry file still shows the structured health rows; selecting a `.md` file shows its rendered text; switching between them updates the view. Screenshot both.
- [ ] **Error parity:** an unreadable/garbage `.md` and a malformed `.json` both land in the visible error state, no crash.
- [ ] **Persistence:** the selected file (either kind) persists across relaunch (existing `telemetryFilePath` UserDefaults path still works for .md).
- [ ] `rebalance doctor` clean (no repo-level regression from the build).

### Phase 1 — anti-goals

- Not adding a third tab or a new folder scan — same telemetry tab, same picker.
- Not changing the `TelemetryEntry` schema or `~/Documents/telemetry/*.json` auto-load behavior.

---

## Phase 2 — Polish + self-test

**Scope:** hardening once the two-path viewer is proven.

**Observable checklist:**

- [ ] **Header/status reflects kind.** The telemetry status line names the file and its kind (e.g. "signals · N" for JSON, "markdown" for .md) so the mode is legible.
- [ ] **Large-file safety.** A big `.md` renders in the `ScrollView` without blocking the main thread (read is already sync + small; note the assumption if a size ceiling is set).
- [ ] **Self-test.** Extend `SelfTest.swift` with a pure assertion that the file-kind discriminator maps `foo.json` → structured and `foo.md` → text (extension logic is testable without a file dialog).

### Phase 2 — QA gate

- [ ] `swift build` green; `FOCUS5_SELFTEST` (or equivalent) passes incl. the new kind-discriminator assertion.
- [ ] Manual: a multi-KB markdown file renders fully and scrolls; a `.json` with many rows still renders structured.
- [ ] `pytest tests/` unaffected (no Python surface touched) — spot-run to confirm no accidental repo-wide breakage.
- [ ] Ship via `make-app.sh` (per standing guidance — `swift build` alone doesn't update `/Applications`).

### Phase 2 — anti-goals

- Not adding markdown editing, syntax highlighting, or export.
- Not supporting formats beyond `.json` and `.md`.

---

## Anti-goals

- **Not a rewrite of the telemetry tab.** One picker + one render branch on file extension; the JSON
  path is byte-for-byte unchanged.
- **Not a second markdown renderer.** Reuse the bottom-note markdown rendering the app already ships.
- **Not editing.** Read-only viewer. No write-back, no format conversion.
- **Not touching Python/server.** Pure macOS-client change under `macOS/Apps/Focus5Float/*`.
