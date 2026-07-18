---
title: Focus 5 Float — CLIO Prompt Log Tab
status: in progress
doc_type: project-plan
owner: Noel Saw
created: 2026-07-17
updated: 2026-07-17
goal: "Bring CLIO (the cross-device Claude Code prompt-log hook + Markdown exporter) into rebalance-OS as its canonical home, and add a fifth Focus5Float tab that reads the CLIO-rendered Markdown as source-of-truth, showing recent prompts newest-first with a 5-slot FIFO pin list so Noel can recover the original intent behind a task after a rabbit hole."
priority: P2
parent: PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md
related:
  - PROJECT/2-WORKING/P2-FOCUS5-TELEMETRY-TAB.md
  - PROJECT/3-COMPLETED/GH-121-FOCUS5-TELEMETRY-MD-VIEWER.md
  - utils/CLIO/INSTALL.md
branch: development
rollout_rule: app must remain buildable (`swift build` green) after every change; existing Focus 5 / Dirty Five / Telemetry tab behavior must be unchanged
---

## Status

| What was just completed | What's next |
|---|---|
| **Both phases DONE (2026-07-17).** CLIO migration: append+cursor exporter + hardening fixes pulled from `Claude-AI-Tools-Ventura-County/CLIO-Claude-Prompts@ef96a44` into `utils/CLIO/` (commit `cfeafe4`), re-installed and smoke-tested on this Mac Studio. Prompt Log tab: `PromptLogEntry`/`PromptLogReader` (parses the CLIO MD format below the `<!-- CLIO:ENTRIES -->` marker), FIFO pin queue on `Focus5Model` (max 5, `UserDefaults`-persisted, newest-pin-at-top/oldest-at-bottom, evicts oldest on a 6th pin), 5th segmented-control tab reusing `RepoCardView`'s exact visual language, reset-all confirm dialog, "Select Prompt Log File…" menu item. `swift build` green; 41/41 `swift test` green (15 new); `FOCUS5_PROMPTLOGTEST=1` and `FOCUS5_SELFTEST=1` both pass. | **Not yet wired to the real shared Obsidian note** — the tab works against any selected `.md` file, but pointing it (and this machine's exporter) at the actual synced vault note stays a deliberate separate step, plus an **operator litmus**: launch the app, select the real prompt log file, confirm rows/pins/truncation/reset-dialog all look right, then archive this doc. |

## Table of Contents

- [Goal](#goal)
- [Context](#context)
- [Data source & format](#data-source--format)
- [Reuse Map](#reuse-map)
- [Non-Goals](#non-goals)
- [Phase 0 — Bring CLIO into the repo (DONE)](#phase-0--bring-clio-into-the-repo-done)
- [Phase 1 — Prompt Log tab](#phase-1--prompt-log-tab)
- [Open Questions](#open-questions)

## Goal

Two tightly-coupled pieces of work:

1. **CLIO becomes a rebalance-OS-owned tool**, not an external dependency the operator has to track down across machines. `utils/CLIO/` is now the source of truth for the skill; installs on any machine read from here.
2. **A fifth Focus5Float tab ("Prompt Log")** gives the operator a fast way to re-orient after getting pulled into a rabbit hole: a reverse-chronological feed of everything CLIO has logged (repo, timestamp, prompt text), with up to 5 entries pinnable as a persistent "what I actually started" anchor list above the scrollable feed.

## Context

CLIO installs a `UserPromptSubmit` hook (user-scope, every repo) that appends one JSON line per prompt to `~/.claude/prompt-log.jsonl`, plus an optional exporter that renders that JSONL to a human-readable Markdown file — the version now in `utils/CLIO/INSTALL.md` renders it by **appending only new entries since last run** (cursor tracked in `~/.claude/prompt-log-to-md.state`), which is what makes it safe to point multiple machines' exporters at one synced file (e.g. an Obsidian vault note) and have both devices' history accumulate instead of clobbering each other.

The operator already runs this against a personal Obsidian vault note (`~/Documents/Noel Saw/0. Claude Prompts.md`, **not** part of this repo). The Prompt Log tab reads that rendered note as its source of truth so the app is a genuine 1:1 mirror of what's in Obsidian — not a second, potentially-divergent rendering of the raw JSONL.

## Data source & format

Each entry in the exporter's output looks like:

```
## HYPERCART
2026-07-09T18:42:11Z  
Noels-MacBook-Pro · main

> "Help me refactor the wpdbtk delta-sync logic"
```

Entries are already newest-first in the file (each sync run prepends new ones directly below the `<!-- CLIO:ENTRIES -->` marker) — the reader does not need to re-sort. Multi-line prompts continue as further `> ` blockquote lines.

## Reuse Map

| Existing asset | Prompt Log tab use |
|---|---|
| `telemetryFileURL` / `UserDefaults["telemetryFilePath"]` pattern (`Focus5Model.swift`) | Mirror exactly for `promptLogFileURL` — explicit `NSOpenPanel` selection, persisted path, cold-launch restore |
| `LoadState` enum (`Focus5Model.swift`) | Reused as-is for the prompt-log load path |
| `emptyState(...)` (`ContentView.swift`) | Reused for "No file selected" / decode-error / empty states, same as the Telemetry tab |
| `RelTime.ago()` (`Time.swift`) | Available if relative timestamps are wanted alongside the absolute ones |
| `ViewMode` enum | Extend with a `.promptLog` case, same routing pattern as `.telemetry` |

## Non-Goals

- No editing of the rendered Markdown from the app — read-only.
- No launchd auto-sync setup performed *by* the app; that's an operator-driven `utils/CLIO/INSTALL.md` step, independent of this tab.
- No cross-device merge logic lives in the app — that property comes entirely from CLIO's append+cursor exporter design; the tab only ever reads whatever the file currently contains.
- No change to the existing Focus 5 / Dirty Five / Telemetry tabs' data or behavior.

---

## Phase 0 — Bring CLIO into the repo (DONE)

- [x] Confirm upstream `Claude-AI-Tools-Ventura-County/CLIO-Claude-Prompts` had the append+cursor exporter + hardening fixes pushed (`3f1f72c`, `ef96a44`).
- [x] Pull `SKILL.md`/`README.md`/`LICENSE` into `utils/CLIO/INSTALL.md`/`README.md`/`LICENSE`; commit (`cfeafe4`).
- [x] Re-install on this Mac Studio: rewrite `~/.claude/hooks/log-prompt.sh` (unchanged), replace `~/.claude/hooks/prompt-log-to-md.sh` with the append+cursor version.
- [x] Smoke test: hook logs a new entry; exporter run against the safe default local path (`~/.claude/prompt-log.md`) produces the marker-based, atomically-written output; `~/.claude/settings.json` still valid with all 5 hook events intact.

## Phase 1 — Prompt Log tab

- [x] `PromptLogModels.swift` — `PromptLogEntry` (repo, timestamp, machine, branch, prompt) parsed from the `## REPO` block format above.
- [x] `PromptLogReader.swift` — reads the selected Markdown file, splits on `## ` blocks below the `<!-- CLIO:ENTRIES -->` marker (falls back to scanning the whole text if no marker is present), parses each into a `PromptLogEntry`. Malformed/empty blocks skipped, not fatal.
- [x] FIFO pin queue on `Focus5Model` — `pinnedPromptLogIDs: [String]`, max 5, `UserDefaults`-persisted; pinning a 6th evicts the oldest (last-index) pin; newest pin at index 0 (top), oldest at the end (bottom). `pinnedPromptLogEntries`/`unpinnedPromptLogEntries` computed properties partition the current entry list.
- [x] `Focus5Model.swift` — `promptLogFileURL: URL?` + persistence, mirroring `telemetryFileURL`; `.promptLog` case on `ViewMode`; `refreshPromptLog()`, `openPromptLogFilePicker()`, `togglePin(_:)`, `isPinned(_:)`, `resetAllPromptLogPins()`.
- [x] `ContentView.swift` — new 4th segmented-control tab ("Prompts", `text.bubble` icon); pinned section (fixed top, "PINNED (n/5)" header) + independently scrollable feed below; `PromptLogRowView` reuses `RepoCardView`'s exact visual language (KeyCap relative-time badge, bold title, `GroupTag` meta row, zebra/hover background) with a pin button (`pin`/`pin.fill`) in place of the open/expand controls; each row shows `truncatedPrompt` (200 chars); reset-all icon (same `arrow.clockwise` glyph as the header refresh) gated behind a `confirmationDialog`.
- [x] `Focus5FloatApp.swift` — "Select Prompt Log File…" menu item (⌘P), same shape as "Select Telemetry File…"; cold-start restore wired into `applicationDidFinishLaunching`.
- [x] `swift build` green; `FOCUS5_SELFTEST=1` still passes; new `FOCUS5_PROMPTLOGTEST=1` parser discriminator passes.

### QA Checklist — Phase 1

- [x] **Regression guard:** Focus 5, Dirty Five, and Telemetry tabs unaffected — full suite (41/41, including all pre-existing tests) green.
- [x] **FIFO correctness:** `testPinningASixthEvictsTheOldestPin` proves pinning a 6th entry evicts exactly the oldest pin (not arbitrary), and the evicted entry reappears via `unpinnedPromptLogEntries`.
- [x] **Truncation:** `testPromptOver200CharsIsTruncatedWithEllipsis`/`testPromptUnder200CharsIsNotTruncated` cover both sides of the 200-char boundary.
- [x] **Confirm dialog:** reset-all is wired behind `confirmationDialog`, not a direct action — matches the "are you sure" requirement; cancel path leaves `resetAllPromptLogPins()` uncalled.
- [ ] **Cold-start restore:** quit and relaunch with a file selected and pins set — both the file selection and the pinned entries persist. _(Operator litmus — unit-tested via `testFileSelectionAndPinsPersistAcrossModelRelaunch`, but not yet eyeballed in the real running app.)_
- [x] **Build:** `swift build` green.

## Open Questions

None blocking — resolved with the operator during spec: max-5 FIFO eviction, newest-pin-at-top ordering, 200-char truncation, Obsidian MD as SOT. The only deliberately-deferred decision is *when* to point this machine's exporter at the real shared vault note (own step, tracked in `utils/CLIO/INSTALL.md`'s own install flow, not blocking this tab's build).
