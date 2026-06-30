---
title: Focus 5 Float — Apple Reminders Bottom Panel
doc_type: project-plan
status: active
owner: Noel Saw
created: 2026-06-29
updated: 2026-06-29
goal: "Split the Focus 5 Float bottom into two sections: a live Apple Reminders list (10 most recent active tasks from the default list, with complete-checkbox write-back via EventKit) above the existing Obsidian focus5.md note viewer, which moves below it into its own scrollable area."
priority: P2
branch: feat/apple-reminders-write
related:
  - PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md
  - PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md
  - macOS/Apps/Focus5Float/Sources/Focus5Float/ContentView.swift
---

## Status

| What was just completed | What's next |
|---|---|
| **Build landing (2026-06-29).** Decided the data path: the app reads/writes Apple Reminders **directly via EventKit**, NOT through `rebalance serve`. This is sound because Focus 5 Float is the exact runtime [APPLE-REMINDERS-UNIFIED-PLAN.md](APPLE-REMINDERS-UNIFIED-PLAN.md) Phase 5.0 proved can hold the Reminders TCC grant — a signed, LaunchServices-launched app bundle (`me.neochro.Focus5Float`, ad-hoc signed, installed to `/Applications`). The Python server path can't write (suppressed under the agent tree) and its read is stale by design (freshness gap), so EventKit-direct is both fresher and write-capable with no FDA needed (FDA was only for the SQLite read-back path). Implemented: `RemindersStore` (EventKit), bottom split (A: reminders + B: scrollable note), make-app.sh TCC strings. | **Operator litmus (TCC-gated, cannot be automated):** reinstall via `./make-app.sh`, launch, tap **Enable Apple Reminders**, approve the prompt, confirm 10 recent default-list tasks render and a checkbox completes one (verify in the Reminders app). Then `.icns` + archive with the parent Focus 5 Float track. |

## Decision: data path = EventKit-direct (not the server)

The user asked: *"Are we able to write back to Apple Reminders now? If not, just show read-only."* Answer, and why it shapes the design:

- **Server/Python path → no live write.** Phase 5.0 of the Apple Reminders plan proved EventKit writes are TCC-suppressed under the VS Code/agent responsible process tree, so the server can only write via the separate signed helper + `rebalance apple-reminders` CLI (deliberately human-in-the-loop). Its *read* is also stale (opt-in, FDA-gated sync — the documented "freshness gap").
- **Focus 5 Float → yes.** It is a signed app bundle launched via LaunchServices with a stable bundle id — exactly the runtime contract Phase 5.0 proved viable for EventKit CRUD. Talking to EventKit directly gives a **live** read and a working **complete** write, needs **only** the Reminders grant (no FDA, since read-back is via EventKit not SQLite), and avoids a server roundtrip for data the server can't serve well anyway.

Tradeoff accepted: this departs from the app's "thin HTTP read-only projection" posture (roster + note still come over HTTP). Justified because reminders genuinely cannot go through the server. The roster/note architecture is untouched.

**Write scope v1 = complete-only** (matches the Apple Reminders plan's Phase 6 stance). `create`/`edit`/`delete` stay out of this UI; the `rebalance apple-reminders` CLI remains the human-in-the-loop surface for those.

## Layout

```
header / tabs
─────────────
roster ScrollView         (flexible — the hero, takes remaining height)
─────────────
A · REMINDERS             EventKit: ≤10 most-recent active tasks from the
  ☐ task title  · due       default list; checkbox completes via EventKit.
  ☐ …                       Access states: enable button / denied hint / empty.
─────────────
B · NOTE                  the existing focus5.md viewer, moved here into its
  (scrollable area)         own bounded ScrollView ("scrollable view area").
```

Bottom sections render only in Focus 5 / Dirty Five (not Telemetry), mirroring the prior note-footer gating.

## Phases

### Phase 1 — EventKit store + bottom split (this change)

- [x] `RemindersStore` (`@MainActor @Observable`, `EKEventStore`): authorization state machine, request full access, fetch ≤10 most-recent active reminders from `defaultCalendarForNewReminders()`, `complete(_:)` write-back + re-read. → `Sources/Focus5Float/RemindersStore.swift`
- [x] Held on `Focus5Model` (`reminders`); `syncAuthorization()` on init; `reminders.refresh()` folded into the non-telemetry `Focus5Model.refresh()` so the existing Refresh button + 90s poll keep it fresh.
- [x] `ContentView`: roster scroll no longer carries the note footer; new `bottomSections` below it = Section A (`RemindersSection` + `ReminderRow`) over Section B (note wrapped in a bounded `ScrollView`).
- [x] `make-app.sh` Info.plist: `NSRemindersFullAccessUsageDescription` + legacy `NSRemindersUsageDescription`.
- [x] Default panel height bumped to fit two bottom sections (560→660, autosave `.v4`).
- [x] `swift build` green (release; EventKit links cleanly) + headless `FOCUS5_SELFTEST` still decodes 5 cards.
- [ ] **Operator litmus (TCC):** reinstall, launch, grant Reminders, confirm 10 tasks + a working complete. _(Cannot be automated — the grant requires a human click on a LaunchServices-launched bundle.)_

### QA checklist — Phase 1

- [x] **Single writer / boundary:** all reminder reads+writes go through `RemindersStore`/EventKit; no SQLite, no server write. Roster/note HTTP path untouched.
- [x] **Safe by default:** shows only active (incomplete) tasks; the only mutation is `complete` (least destructive). No create/delete/edit in the UI.
- [x] **Honest failure:** denied/restricted access shows a System-Settings hint, not a blank; a failed `complete` reverts the optimistic state and surfaces an error. No false "done".
- [x] **No FDA claim:** the app requests only Reminders (EventKit); FDA is not requested (read-back is via EventKit, not the SQLite extractor).
- [x] **DRY:** reuses `Theme`, `KeyCap`/section styling, `RelTime`; the note viewer (`Focus5NoteView`) is reused verbatim, only relocated + wrapped in a scroll.
- [~] **Litmus (visual):** `swift build` green + headless self-test unaffected. _Operator: eyeball the two-section bottom + tune section heights if cramped on the 200-wide panel._

## Non-Goals

- No reminder create/edit/delete in the app UI (CLI owns those).
- No routing reminders through `rebalance serve` (the server can't write and reads stale).
- No FDA request (Reminders/EventKit grant only).
- No change to the roster or note HTTP data paths.
