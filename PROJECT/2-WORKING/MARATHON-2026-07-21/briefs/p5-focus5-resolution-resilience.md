---
title: "MARATHON-2026-07-21 P5 — Focus5Float resolution-change resilience (Phase 1)"
status: "Brief authored; phase not yet run"
created: 2026-07-21
updated: 2026-07-21
owner: noel
related:
  - PROJECT/2-WORKING/FOCUS5-RESOLUTION-CHANGE-RESILIENCE.md
roadmap_exempt: true
---

# Phase 5 — Focus5Float: survive a display-resolution change without a reboot (Phase 1 only)

Parent doc: `PROJECT/2-WORKING/FOCUS5-RESOLUTION-CHANGE-RESILIENCE.md` (read it for full root-cause
detail — this brief scopes only its **Phase 1**, not Phase 2). No GH issue filed for this one; it
predates the issue-per-lane convention and was never fired as part of MARATHON-2026-07-07 Lane C.
Disjoint from every other phase in this marathon — **different toolchain (Swift/macOS), different
write surface.** **Artifact:** `macOS/Apps/Focus5Float/Sources/Focus5Float/Focus5FloatApp.swift`,
`.../ContentView.swift`, `.../SelfTest.swift`.

## The problem

When the macOS display resolution changes while Focus5Float is running, the floating panel's
autosaved frame (absolute screen coordinates) doesn't update. The panel can land off-screen or
clipped, and the only reliable recovery found so far is rebooting the device. Root cause: nothing
observes `NSApplication.didChangeScreenParametersNotification`, and the only re-centering guard
(`if panel.frame.origin == .zero`) runs once at build time and never again.

## ⛔ Hard invariants

- **Do not change the autosave name** (`Focus5FloatPanel.v5`). Clamping must coexist with the
  persisted position, not discard it.
- **Only re-clamp when necessary.** If the panel's current frame is still valid for the new
  `visibleFrame`, leave it untouched — don't rebuild or reposition on every screen-parameter event.
- **This phase (Phase 1) is the core fix only.** Multi-display edge cases (display removed/added,
  debounce, menu-bar anchor sanity) are Phase 2 in the parent doc — explicitly not in scope here.
- **Not a settings UI.** No new user-facing configuration for panel placement.
- **Not server-side.** Purely macOS-client window geometry — do not touch `/focus-5.json` or any
  Python surface.
- Observer must hold `[weak self]` — no new retain cycles, no crash on quit.

## Task (Phase 1, per the parent doc verbatim)

1. Add a `clampPanelToVisibleScreen()` helper on the app/panel controller that:
   - Resolves the target `NSScreen` (the screen containing the panel's current frame center if
     any, else `NSScreen.main`, else `NSScreen.screens.first`).
   - Computes the intersection of `panel.frame` with that screen's `visibleFrame`; if the visible
     intersection is below a threshold (e.g. < 40% of panel area, or header row not visible),
     reposition the panel fully inside `visibleFrame` (preserving size, clamping origin) — else
     leave it untouched.
   - Respects `panel.minSize` when the new `visibleFrame` is smaller than the panel (shrink height
     toward `minSize` before clamping origin).
2. Register for `NSApplication.didChangeScreenParametersNotification` in
   `applicationDidFinishLaunching` (or right after `buildPanel()`); on fire, call
   `clampPanelToVisibleScreen()` on the main actor. Deregister on teardown.
3. Call `clampPanelToVisibleScreen()` at the top of `showPanel()` so a panel hidden across a
   resolution change is corrected before it's shown.
4. Pull the pure-geometry clamp logic into a `SelfTest.swift` assertion (an off-screen synthetic
   frame maps back inside a given `visibleFrame`) so this phase has a machine-checkable gate
   beyond manual repro.

## Acceptance (machine gate — this is what the phase's automated gate checks)

- [ ] `swift build` green (release).
- [ ] `SelfTest.swift` geometry assertion passes: an off-screen synthetic frame maps back inside a
      given `visibleFrame`.
- [ ] No new retain cycles — observer holds `[weak self]`; no crash on quit.
- [ ] `rebalance doctor` clean (no repo-level regressions from the build).

## Acceptance (operator litmus, post-build — not machine-checkable, do not block the phase gate on it)

- Change the main display's scaled resolution in System Settings → Displays while the panel is
  visible. Panel remains fully visible and usable without relaunch or reboot. Repeat with the
  panel hidden, then toggle it open — it opens on-screen.
- Normal drag-to-reposition still persists across a plain quit/relaunch (autosave not broken).
- Ship the built app via `make-app.sh` once merged — `swift build` alone does not update
  `/Applications`.
