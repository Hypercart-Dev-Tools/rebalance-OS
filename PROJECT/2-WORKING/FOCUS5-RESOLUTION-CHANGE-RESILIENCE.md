---
title: "Focus5Float: survive a same-session display resolution change without a reboot"
owner: Noel
status: "Active (2-WORKING) — planned 2026-07-06, not yet started. Root cause identified: no screen-parameter observer re-clamps the autosaved panel frame."
created: 2026-07-06
updated: 2026-07-06
doc_type: bugfix
related:
  - PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md
  - PROJECT/2-WORKING/P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md
effort: 2
complexity: 3
risk: 3
phases: 2
goal: >
  When the macOS display resolution (or display arrangement) changes while
  Focus5Float is already running, the floating panel must reposition and re-clamp
  itself onto a visible screen automatically — the operator should never have to
  reboot the device (or quit/relaunch the app) to recover a usable, on-screen panel.
---

## Status

| What was just completed | What's next |
|---|---|
| **Planning only (2026-07-06).** Root-caused: `buildPanel()` sets `panel.setFrameAutosaveName("Focus5FloatPanel.v5")` and only calls `panel.center()` when `panel.frame.origin == .zero` ([Focus5FloatApp.swift:201-204](../../macOS/Apps/Focus5Float/Sources/Focus5Float/Focus5FloatApp.swift#L201)). Nothing observes `NSApplication.didChangeScreenParametersNotification`, so on a resolution change the panel keeps its old absolute frame — which can land fully or partially off the resized screen, with no path back short of a reboot resetting window-server state. | Start **Phase 1**: install a screen-parameters observer that re-clamps the panel into the current `visibleFrame`. |

## Table of contents

- [Phase 1 — Core fix: re-clamp on screen change](#phase-1--core-fix-re-clamp-on-screen-change)
- [Phase 2 — Fine-tune: multi-display, edge cases, self-test](#phase-2--fine-tune-multi-display-edge-cases-self-test)

## Problem

Focus5Float is a menu-bar-toggled `FloatingPanel` whose frame is persisted via
AppKit frame autosave (`Focus5FloatPanel.v5`). Autosaved frames are stored in
**absolute screen coordinates**. When the operator changes display resolution
mid-session (e.g. switching an external monitor's scaled resolution, unplugging a
display, or a Sidecar/AirPlay handoff), the screen's `visibleFrame` changes but
the panel's saved frame does not. Two failure modes result:

1. **Off-screen panel** — the panel's origin now falls outside every screen's
   `visibleFrame`; toggling it from the menu bar shows nothing visible.
2. **Clipped panel** — the panel straddles the new screen edge, with its header /
   controls partly unreachable.

Currently the only reliable recovery the operator has found is **rebooting the
device**, because a reboot clears the window-server placement state. That is a
disproportionate remedy for a routine display change.

### Root cause

- `buildPanel()` ([Focus5FloatApp.swift:151](../../macOS/Apps/Focus5Float/Sources/Focus5Float/Focus5FloatApp.swift#L151))
  configures the panel and its autosave name, but registers **no** observer for
  `NSApplication.didChangeScreenParametersNotification`.
- The only re-centering guard (`if panel.frame.origin == .zero { panel.center() }`)
  runs once at build time and never again.
- `togglePanelWidth()` ([ContentView.swift:195](../../macOS/Apps/Focus5Float/Sources/Focus5Float/ContentView.swift#L195))
  and `showPanel()` also do no on-screen validation before display.

## Approach

Add a single point of truth for "make the panel's frame legal for the current
screen configuration" and call it (a) whenever screen parameters change and (b)
defensively just before `showPanel()`. Keep the operator's chosen position when
it is still valid; only nudge when it would be off-screen.

## Phase 1 — Core fix: re-clamp on screen change

**Scope:** the smallest change that eliminates the reboot requirement.

- [ ] Add a `clampPanelToVisibleScreen()` helper on the app/panel controller that:
  - Resolves the target `NSScreen` (the screen containing the panel's current
    frame center if any, else `NSScreen.main`, else `NSScreen.screens.first`).
  - Computes an intersection of `panel.frame` with that screen's `visibleFrame`;
    if the visible intersection is below a threshold (e.g. < 40% of panel area,
    or header row not visible), reposition the panel fully inside `visibleFrame`
    (preserving size, clamping origin), else leave it untouched.
  - Respects `panel.minSize` when the new `visibleFrame` is smaller than the
    panel (shrink height toward `minSize` before clamping origin).
- [ ] Register for `NSApplication.didChangeScreenParametersNotification` in
  `applicationDidFinishLaunching` (or right after `buildPanel()`); on fire, call
  `clampPanelToVisibleScreen()` on the main actor. Deregister on teardown.
- [ ] Call `clampPanelToVisibleScreen()` at the top of `showPanel()` so a panel
  hidden across a resolution change is corrected before it is shown.
- [ ] Do **not** change the autosave name (`Focus5FloatPanel.v5`) — clamping
  should coexist with, not discard, the persisted position.

### Phase 1 QA gate

- [ ] `swift build` green (release).
- [ ] Manual repro: with the panel visible, change the main display's scaled
  resolution in System Settings → Displays. Panel remains fully visible and
  usable **without** relaunch or reboot. Repeat with the panel hidden, then
  toggle it open — it opens on-screen.
- [ ] Regression: normal drag-to-reposition still persists across a plain
  quit/relaunch (autosave not broken by the clamp).
- [ ] No new retain cycles — observer holds `[weak self]`; verify no crash on app
  quit.
- [ ] `rebalance doctor` clean (no repo-level regressions from the build).

### Phase 1 anti-goals

- Not rebuilding the window/panel on every screen change (avoid flicker / lost
  state) — only re-clamp the existing panel.
- Not introducing a settings UI for panel placement.
- Not touching server-side / `/focus-5.json` code — this is purely macOS-client
  window geometry.

## Phase 2 — Fine-tune: multi-display, edge cases, self-test

**Scope:** hardening once the core reboot-free behavior is proven.

- [ ] **Display removed:** if the screen the panel lived on is unplugged, move the
  panel to `NSScreen.main`'s `visibleFrame` rather than leaving it on a
  now-absent screen.
- [ ] **Display added / arrangement change:** keep the panel on its current screen
  if still present; only migrate when its screen disappears.
- [ ] **Debounce:** coalesce rapid consecutive `didChangeScreenParameters`
  notifications (macOS often emits several during a mode switch) so the panel
  settles once, not mid-transition.
- [ ] **Menu-bar anchor sanity:** confirm the status-item toggle still works after
  the change (the `NSStatusItem` is managed by AppKit, but verify the toggle path
  in `togglePanel()`).
- [ ] Extend `SelfTest.swift` with a non-visual assertion that
  `clampPanelToVisibleScreen()` maps an off-screen synthetic frame back inside a
  given `visibleFrame` (pure geometry function, testable without a live display
  change).

### Phase 2 QA gate

- [ ] `swift build` green.
- [ ] Multi-display manual matrix: (a) unplug the panel's display → panel appears
  on remaining display; (b) change external monitor resolution with panel on it →
  panel re-clamps; (c) rapid resolution toggle → panel settles once, no drift.
- [ ] Self-test geometry assertion passes (`FOCUS5_SELFTEST` path or equivalent).
- [ ] `pytest tests/` unaffected (no Python surface touched) — spot-run to confirm
  no accidental repo-wide breakage from the build/version bump.

### Phase 2 anti-goals

- Not implementing per-display remembered positions (one live position is enough).
- Not handling Stage Manager / full-screen Spaces relayout beyond keeping the
  panel on a valid `visibleFrame`.

## Verification summary

_(fill in as phases complete — build results, manual repro notes, self-test output)_

## Notes

- Ship the built app via `make-app.sh` (per standing guidance — `swift build`
  alone does not update `/Applications`).
- Consider filing a GH issue to back this doc when work starts, mirroring the
  other Focus5 lanes; not required to begin.
