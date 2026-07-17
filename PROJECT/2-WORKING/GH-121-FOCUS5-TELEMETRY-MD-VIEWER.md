---
title: "Focus5Float telemetry viewer: support .md (text viewer) alongside JSON (structured viewer)"
owner: noel@neochro.me
gh_issue: 121
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/121"
status: "Active (2-WORKING) — base .md viewer shipped 2026-07-15 outside the marathon process (all agy findings closed except the size ceiling); size ceiling closed 2026-07-16 via MARATHON-2026-07-16 Lane B. All 3 accepted agy [Should] findings now implemented."
created: 2026-07-06
updated: 2026-07-16
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
| **Base .md viewer shipped 2026-07-15** outside the marathon process (picker accepts `.md`, safe `UTType`, symmetric state clear, markdown rendering reused from the `focus5.md` note path — later also gained a GFM table renderer). **Size-ceiling finding closed 2026-07-16** via [MARATHON-2026-07-16 Lane B](MARATHON-2026-07-16.md): `refreshTelemetry()`'s `.md` branch now caps the read at 1MB (byte-safe truncation, never mid-codepoint) with a visible `"…truncated (file exceeds 1 MB)"` note; 2 new tests, `swift test` green (25/25), `make-app.sh` reinstalled. | All 3 accepted agy [Should] findings from the 2026-07-06 relay-xyz review are now implemented — **Phase 1 complete.** **Phase 2** (header/status-reflects-kind polish, large-file scroll safety, extending the self-test) remains open, not addressed by this pass. |

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

- [x] **Picker accepts .md.** `openFilePicker()` `allowedContentTypes` = `[.json, UTType(filenameExtension: "md") ?? .plainText]` — **no force-unwrap**. Title generalized to "Select Telemetry or Markdown File". _(agy [Should] #1, 2026-07-06 — shipped 2026-07-15.)_
- [x] **A file-kind discriminator.** `telemetryIsMarkdown: Bool` computed property on `Focus5Model`, single source of truth used by both load and render. _(Shipped 2026-07-15.)_
- [x] **Branch the load, clearing the *other* mode's state both ways.** `refreshTelemetry()`: `.json` decode sets `telemetryMarkdownContent = nil`; `.md` read sets `telemetryEntries = []`. Symmetric clearing confirmed. _(agy [Should] #3, 2026-07-06 — shipped 2026-07-15.)_
- [x] **Size ceiling on the `.md` read.** `refreshTelemetry()`'s `.md` branch now caps the read at `Focus5Model.telemetryMarkdownByteCeiling` (1MB): reads raw `Data`, and above the ceiling truncates the **bytes** first (`data.prefix(ceiling)`) then lossy-decodes with `String(decoding:as: UTF8.self)` (never fails — a boundary-split multi-byte character becomes one U+FFFD instead of corrupting output), appending a visible `"…truncated (file exceeds 1 MB)"` note. Files under the ceiling are byte-identical to before. _(agy [Should] #2, 2026-07-06 — closed 2026-07-16 via MARATHON-2026-07-16 Lane B.)_
- [x] **Branch the render.** `telemetryContent` shows a scrollable read-only markdown viewer (reusing the shared `MarkdownBody`/note renderer, later extended with GFM table support) for `.md`; the existing structured list for `.json`. No-file / error states shared. _(Shipped 2026-07-15.)_
- [x] **Unreadable file → existing error state**, not a crash (parity with the JSON error path) — confirmed by `testMissingFileReportsLoadErrorForBothKinds`.

### Phase 1 — QA gate

- [x] `swift build` green (release) — confirmed 2026-07-16 (`make-app.sh`).
- [x] **Litmus (both paths):** covered by `TelemetryFileLoadingTests` (`testJSONFileDecodesIntoTelemetryEntries`, `testMarkdownFileLoadsAsRawTextNotTelemetryEntries`) plus a live `make-app.sh` reinstall.
- [x] **Error parity:** `testMalformedJSONReportsLoadError` + `testMissingFileReportsLoadErrorForBothKinds`, both kinds land in the visible error state, no crash.
- [x] **Persistence:** `testSelectionPersistsAcrossModelRelaunchForBothKinds` — the selected file (either kind) persists across relaunch via `telemetryFilePath` UserDefaults.
- [x] `rebalance doctor` clean (no repo-level regression from the build).

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
