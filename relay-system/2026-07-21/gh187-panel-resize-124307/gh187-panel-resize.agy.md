### ANSWER

The most likely difference between your isolated test app and the real Focus5Float app is the presence of SwiftUI via `NSHostingView`. By default, `NSHostingView` translates the SwiftUI view's intrinsic layout into strict `NSWindow` constraints, frequently overriding manual `panel.maxSize` settings. If your `ContentView` does not have a flexible vertical layout (e.g., lacks a `Spacer()` or `.frame(maxHeight: .infinity)`), `NSHostingView` will strictly cap the window's height. When you attempt to drag the top edge past this hidden intrinsic ceiling, the window server refuses the resize. Consequently, the click falls through to the background, and `isMovableByWindowBackground = true` kicks in—turning what you intended as a resize into a window move or a tiling snap. The isolated test app used a plain `NSView`, avoiding these SwiftUI-driven constraints entirely.

### FINDINGS

[Blocker] **NSHostingView Intrinsic Content Sizing (Highly Likely)**
`NSHostingView` dynamically dictates the window's bounds based on the SwiftUI layout. If `ContentView` evaluates to a fixed maximum height, the window cannot be resized taller regardless of your manual `panel.maxSize = ...` assignment. Because width resizing works ("edge to edge"), your SwiftUI content likely has a flexible width but a constrained height. 
*How to check:* In `Focus5FloatApp.swift:181`, append `.frame(maxWidth: .infinity, maxHeight: .infinity)` directly to `ContentView(...)`. Alternatively, add a timer to print `panel.maxSize` 2 seconds after launch to prove `NSHostingView` is stomping your manual `maxSize`.

[Should] **Hit-Testing / `ignoresSafeArea` Conflict (Confident)**
With `fullSizeContentView` and a hidden title bar, the top resize border is extremely thin (~4pt). If `ContentView` uses `.ignoresSafeArea(.all)` to push background colors into the title bar area, SwiftUI's hit-testing can inadvertently swallow the top-edge click. Because `isMovableByWindowBackground = true` is enabled, this click is instantly converted into a drag gesture.
*How to check:* Temporarily set `panel.isMovableByWindowBackground = false`. If the top edge becomes completely unclickable (dead) instead of moving the window, it proves SwiftUI is eating the resize hit-test.

[Nit] **Autosave Frame State Contention (Low Confidence)**
The real app uses `panel.setFrameAutosaveName("Focus5FloatPanel.v5")` (line 228), which your initial isolated test app lacked. A stale, persisted autosave frame height could be fighting your live `minSize`/`maxSize` configurations or interacting poorly with `NSHostingView` on launch.
*How to check:* Run `defaults delete me.neochro.Focus5Float` in the terminal to clear state, and comment out `setFrameAutosaveName` during your next test run to cleanly eliminate it as a variable.

### RECOMMENDATION

Wrap your `ContentView` initialization in `.frame(maxHeight: .infinity)` to force SwiftUI to accept vertical growth, and temporarily disable `isMovableByWindowBackground` to verify if SwiftUI is swallowing the top-edge resize hit-test.
