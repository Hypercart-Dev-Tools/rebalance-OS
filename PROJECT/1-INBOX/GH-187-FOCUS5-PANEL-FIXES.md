---
gh_issue: 187
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/187
title: "GH-187 Focus 5 Float: Dock-icon reopen (fixed) + panel can't resize taller (paused, unresolved)"
status: "Paused — Dock-reopen fixed and shipped; top-edge resize still broken; Codex+agy consult captured, not yet tried"
created: 2026-07-21
updated: 2026-07-21
doc_type: bugfix
branch: fix/gh-187-focus5-dock-reopen-and-panel-height
roadmap_exempt: false
---

# GH-187 — Focus 5 Float: Dock reopen + panel resize

## Status

| What was just completed | What's next |
|---|---|
| Dock/Launch-Services reopen fix shipped and verified live (hiding the panel, then reactivating the app, brings it back). Panel-height investigation ruled out several hypotheses via a disposable isolation test app but has **not** found the real root cause; the custom top-edge resize handle was found to make native resize *worse* and was reverted. | Pick a debugger-first approach (attach LLDB / Instruments to a real user-driven drag) instead of headless synthetic-event probing, which proved unreliable for simulating held-button drags in this environment. See the "Next steps" section for the concrete remaining hypotheses to test. |

## Original ask

Two bugs in the Focus 5 Float menu-bar app (`macOS/Apps/Focus5Float`):
1. Hiding the panel (the in-panel "x" button, `panel.orderOut(nil)`) and then clicking the app's Dock tile did nothing — the panel never came back.
2. The panel can't be resized taller to fill the space between it and the menu bar — dragging the top edge doesn't work.

## Fix 1 — Dock/reopen (DONE, shipped)

`AppDelegate` never implemented `applicationShouldHandleReopen(_:hasVisibleWindows:)`, so AppKit's default reopen handling had nothing to unhide — the panel is an `NSPanel` we manually `orderOut()`, not a standard hidden window.

**Fix:** added `applicationShouldHandleReopen` to call `showPanel()` when the panel isn't visible. Verified live via unified log (`panel hidden` → `panel shown` after a simulated Dock reopen) and by the operator directly ("1 is good now"). Commit `c75a5f0`.

## Fix 2 — Panel can't resize taller (PAUSED, unresolved)

### Investigation log (chronological, debug-mantra breadcrumbs)

1. **Hypothesis: `panel.maxSize.height` hardcoded to 1200 is the cap.**
   `git log` showed `panel.maxSize` was introduced in commit `2e59ff1` ("feat: refresh Focus5Float panel UI") — before that commit there was **no** `maxSize` at all (unbounded resize). Changed `maxSize.height` to `NSScreen.main?.visibleFrame.height` so the cap tracks the actual screen instead of a flat constant. Commit `c75a5f0`.
   **Verified via Accessibility-forced resize:** the live cap did increase (1200 → ~1415 on the connected 2560×1440 display) and the OS-level ceiling is not the current display's visible height.
   **Disproved as the fix:** operator reported still unable to drag taller — "It seems like something is locking it to a max height."

2. **Hypothesis: `isMovableByWindowBackground = true` wins hit-testing over the native resize border in the top strip**, since this is a hidden-titlebar (`titlebarAppearsTransparent` + `fullSizeContentView` + hidden title/buttons) `NSPanel`.
   Confirmed via synthetic-click sweep (Accessibility position of the hide button + `CGEventPost`) that a drag starting a bit lower in the header (not the exact top few px) triggers a **window move**, and — when dragged far enough toward the screen's top edge — triggers **macOS's native window-tiling snap-to-fullscreen**, not a resize.
   Added a custom `TopEdgeResizeHandle` (an 8pt-tall `NSView` overlay pinned to the top edge, manually computing frame growth on `mouseDragged`) to bypass the native path entirely. Commit `bd6fd1b`.
   **Verification limits hit:** `CGEventPost`-simulated held-button drags proved unreliable in this headless environment — the *same* script that once reproduced the native tiling-snap stopped reproducing anything on a retry. Confirmed via logging that the handle's frame is computed correctly and that a plain synthetic click does reach it (`mouseDown` fires), but could not get a synthetic `mouseDragged` sequence to reliably fire at all, on either the handle or the native background-move path. Treated as an environment limitation, not evidence against the fix — asked the operator to test with a real mouse instead.

3. **Operator's real-mouse test surfaced a new, more specific symptom:** dragging the panel up shows macOS's full-screen tiling outline preview, but on release the panel **snaps to center** instead of filling the screen — and separately, plain top-edge drag to grow taller still didn't work with the handle in place.

4. **Isolation test app (`ResizeTestBar`, disposable, not part of the repo):** built a minimal AppKit-only panel mirroring Focus5Float's exact window-chrome settings (same `styleMask`, `isMovableByWindowBackground`, `isOpaque`/`backgroundColor` transparency flip, and a `maxSize.width` capped at 420 like Focus5Float) but with **no** custom drag handling and **no** SwiftUI content.
   **Result:** the test app resized and moved freely ("can be resized and moved much more freely... can drag it edge to edge"). It also showed the same width-capped centering during the OS full-tile gesture ("won't exceed a certain width and it centers itself") — but that specific behavior is now understood to be an **expected, shared side effect** of intentionally capping `maxSize.width` at 420 on both apps, not the core bug.
   **Disproves:** "`maxSize.width` blocking OS tiling → center fallback" as the *sole* cause, since the isolated test app has the identical constraint and still resizes/moves normally outside of the full-tile gesture.

5. **Follow-up isolation: reverted Focus5Float to the pre-handle state** (`git checkout c75a5f0 -- Focus5FloatApp.swift`, i.e. keep the `maxSize` dynamic fix, drop `TopEdgeResizeHandle`), rebuilt, reinstalled, operator retested on the **real** app:
   - Can drag slightly wider, but still maxes out at a set width (expected — `maxSize.width` = 420).
   - Triggering the full-screen snap only widens it slightly (doesn't grow taller) — consistent with the width-capped-centering behavior seen on the test app.
   - **Can now drag edge to edge, unlike the version with the custom handle.**

   **Conclusion:** the custom `TopEdgeResizeHandle` (step 2) was actively regressing normal native resize/drag behavior rather than fixing it. It has been reverted out of the working tree (uncommitted revert is the current state pending this pause).

### Current code state

- `panel.maxSize` dynamic-height fix (from step 1) — kept, working tree state matches commit `c75a5f0`.
- `TopEdgeResizeHandle` custom overlay (from step 2, commit `bd6fd1b`) — reverted out of the working tree. **Not yet committed as a revert** — next session should either commit this revert explicitly or `git revert bd6fd1b`.
- Installed `/Applications/Focus 5 Float.app` currently reflects the reverted (no-handle) build.
- Disposable isolation app lives at `/private/tmp/.../scratchpad/ResizeTestBar` (session-scoped temp dir, not part of this repo, safe to ignore/lose).

### Root cause: NOT yet isolated

What we know does **not** fully explain the remaining symptom (still can't grow the panel taller by dragging, even without the custom handle, even edge-to-edge width resize now works): the height-specific top-edge growth remains blocked or at least never actually tested to succeed by the operator. The investigation ran out of remaining variables that could be cheaply isolated with headless tooling.

### Next steps (for whoever resumes this)

1. **Attach a real debugger or Instruments session** to the installed `.app` while a human performs the actual drag gesture (debug-mantra step 2: "debugger first" — this was never done; all investigation so far was source-trace + synthetic-event knob-flipping because a debugger wasn't attached to a live interactive gesture).
2. Candidate remaining variables not yet isolated:
   - `panel.setFrameAutosaveName("Focus5FloatPanel.v5")` — a persisted frame from a prior (centered, narrower) session could be fighting a live resize/tiling attempt. Test by clearing the autosave defaults key (`defaults delete me.neochro.Focus5Float NSWindow\ Frame\ Focus5FloatPanel.v5` or similar) before a retest, and by adding the same autosave name to the isolation test app to see if it reproduces the remaining symptom.
   - SwiftUI `NSHostingView` content (`FirstMouseHostingView`) vs. the isolation app's plain `NSView` — the isolation app never had real SwiftUI content; layer in a trivial SwiftUI view to see if that alone changes drag behavior.
   - Whether height-only growth (not width) specifically works via the *native* resize border once the handle is gone — this was not explicitly re-confirmed by the operator; only "edge to edge" (which reads as width) and the full-tile-snap behavior were confirmed.
3. Do not reintroduce a custom resize-handle NSView without confirming (via the debugger, not synthetic events) exactly which region of the window it is being hit-tested against during a real drag — the previous attempt appears to have been receiving events meant for the native background-move/resize path and interfering with it.

## Consult — Codex + agy second opinion (2026-07-21, advisory only, not yet tried)

Ran `/consult` (both models read this doc + `Focus5FloatApp.swift` directly). Full raw transcripts:
`relay-system/2026-07-21/gh187-panel-resize-124307/gh187-panel-resize.{codex,agy}.md`.

**Reconciled call:** both independently suspect the SwiftUI `NSHostingView` content as the real
differentiator from the isolated test app — but Codex adds a sharper, more important catch: this
doc's own "can drag edge to edge" conclusion never explicitly re-confirmed *height* growth via the
native top edge post-handle-revert; "edge to edge" almost certainly described *width*. That's a gap
in our own methodology, not just a new theory, and should be closed before trusting any other
hypothesis below.

**Where they disagreed:**
- Codex flagged `[Blocker]`: post-revert testing never explicitly confirmed a successful (or failed)
  *height-only* native top-edge resize — only width ("edge to edge") and the full-tile-snap were
  confirmed. The earlier custom handle had also regressed normal resize, which may have contaminated
  what we thought we'd already ruled out. Agy did not raise this; it accepted the log at face value
  and went straight to a sizing hypothesis.
- Mechanism specificity differs: agy's theory is that `NSHostingView`'s intrinsic SwiftUI layout can
  override `panel.maxSize` outright. Codex doesn't make that literal claim but independently surfaced
  that `contentMinSize`/`contentMaxSize` are **distinct `NSWindow` properties from `minSize`/`maxSize`**
  and take precedence — a more precise, directly-checkable mechanism neither of us had inspected
  before. Not truly contradictory — same suspect (SwiftUI content constraining the window), Codex's
  framing is the more actionable one.

**Where they agreed:**
- SwiftUI/`NSHostingView` content (vs. the isolation app's plain `NSView`) is the top suspect.
- `panel.isMovableByWindowBackground = false` is a good *diagnostic* (not a permanent fix) to test
  whether background-move is swallowing the resize attempt.
- The tile-to-center-at-420 behavior is expected given `maxSize.width`, not a separate bug.
- Frame-autosave state is low-priority, unlikely to actively fight a live resize.

**Sorted, not yet attempted:**
- **Blocking (do first):** re-verify with a human, cursor-watching test whether *height-only*
  top-edge resize actually works or fails now that the handle is reverted — our "fixed" read may
  rest on an untested assumption (Codex).
- **Worth doing, optional:** inspect runtime `contentMinSize`/`contentMaxSize`/`aspectRatio`/resize
  increments and `panel.screen?.visibleFrame` vs `NSScreen.main` (can differ on multi-monitor)
  (Codex); run an A/B ladder — plain `NSView` → `FirstMouseView` → empty `NSHostingView` → real
  `ContentView`, same panel subclass/bundle/agent policy throughout — to isolate which exact layer
  changes drag behavior (Codex); temporarily flip `isMovableByWindowBackground = false` as a
  diagnostic (both); add `.frame(maxWidth: .infinity, maxHeight: .infinity)` to `ContentView` as a
  quick sizing-conflict probe (agy).
- **Skip / out of scope:** autosave-state clearing — low confidence from both, test once but don't
  treat as a likely culprit.

Per the operator's instruction, **none of this has been tried yet** — paused here for a future
session.
