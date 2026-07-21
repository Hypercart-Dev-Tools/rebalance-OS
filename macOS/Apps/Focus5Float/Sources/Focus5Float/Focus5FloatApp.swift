import SwiftUI
import AppKit
import ServiceManagement
import os

// Phase 2 entry point: An AppKit-driven lifecycle that runs the app as a
// menu-bar agent (no Dock icon) and hosts the SwiftUI card stack in an
// interactive, non-activating floating panel (NSPanel + NSStatusItem).

private let log = Logger(subsystem: "me.neochro.Focus5Float", category: "panel")

@main
struct Focus5FloatApp {
    static func main() {
        Focus5SelfTest.runIfRequested()   // FOCUS5_SELFTEST=1 → headless decode + exit

        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
    }
}

// A non-activating floating panel that can still take key focus when a control
// needs it, but does not activate the app on show. Esc hides it.
final class FloatingPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
    /// Esc hides the panel; click-away intentionally leaves it open.
    override func cancelOperation(_ sender: Any?) {
        orderOut(nil)
        log.info("panel hidden (esc)")
    }
}

// Container that accepts the first mouse click even while the window is inactive,
// so buttons fire on the first click over a frontmost fullscreen app.
final class FirstMouseHostingView<Content: View>: NSHostingView<Content> {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    // GH-187 REGRESSION GUARD: `.fullSizeContentView` makes the AppKit content
    // view fill the panel frame, but NSHostingView still inherits the hidden
    // titlebar's 28pt safe-area inset. If this override is removed, the window
    // can be flush with the menu bar while the visible SwiftUI shell starts
    // 28pt lower and looks artificially height-capped. Keep this invariant at
    // the AppKit/SwiftUI boundary; the regression test mounts this real hosting
    // view in the real FloatingPanel chrome and asserts a zero top inset.
    override var safeAreaInsets: NSEdgeInsets { NSEdgeInsets() }
}

/// Frame-size constraints for the floating panel. Width is intentionally
/// bounded, but height must retain AppKit's default maximum: a screen-height
/// cap prevents a slightly off-screen/autosaved panel from growing its top edge
/// back to the menu bar.
enum PanelSizing {
    static let minimum = NSSize(width: 340, height: 360)
    static let maximum = NSSize(
        width: 420,
        height: CGFloat(Float.greatestFiniteMagnitude)
    )
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate, NSWindowDelegate {
    private var panel: FloatingPanel!
    private var statusItem: NSStatusItem!
    private var contextMenu: NSMenu!
    private var focus5Item: NSMenuItem!
    private var dirtyFiveItem: NSMenuItem!
    private var launchAtLoginItem: NSMenuItem!
    private var selectTelemetryItem: NSMenuItem!
    private var selectPromptLogItem: NSMenuItem!
    private let model = Focus5Model()
    private var pollTimer: Timer?
    private let pollInterval: TimeInterval = 90   // re-pull cadence

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Accessory policy → menu-bar agent, no Dock icon. (The bundled .app
        // also sets LSUIElement in Info.plist; that's Phase 5 packaging.)
        NSApp.setActivationPolicy(.accessory)

        // Setup status item in system menu bar
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.title = "F5"
            button.target = self
            button.action = #selector(togglePanel)
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }

        // Construct right-click context menu
        buildContextMenu()

        // Build the floating panel
        buildPanel()
        updateModeMenuState()

        // Show panel on launch
        showPanel()

        // Show the cached roster instantly (if any), then pull live and poll.
        model.loadCache()
        model.refreshTelemetry()   // restore previously-selected telemetry file on cold-start
        model.refreshPromptLog()   // restore previously-selected prompt log file on cold-start
        Task { await model.refresh(); updateModeMenuState() }
        startPolling()
    }

    // Fires on Dock/Launch-Services reopen (e.g. clicking a pinned Dock tile
    // while already running). The panel is an NSPanel we manually orderOut(),
    // not a standard miniaturized/hidden window, so AppKit's default reopen
    // handling has nothing to unhide — bring it forward ourselves.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !panel.isVisible {
            showPanel()
        }
        return true
    }

    private func startPolling() {
        pollTimer = Timer.scheduledTimer(withTimeInterval: pollInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.model.refresh() }
        }
    }

    // MARK: - Menu

    private func buildContextMenu() {
        let menu = NSMenu()

        let refreshItem = NSMenuItem(title: "Refresh (re-pull)", action: #selector(refreshData), keyEquivalent: "r")
        menu.addItem(refreshItem)
        menu.addItem(withTitle: "Start rebalance serve", action: #selector(startServer), keyEquivalent: "s")

        let modeMenu = NSMenu()
        focus5Item = NSMenuItem(title: "🎯 Focus 5", action: #selector(setFocus5Mode), keyEquivalent: "")
        dirtyFiveItem = NSMenuItem(title: "🧹 Dirty Five", action: #selector(setDirtyFiveMode), keyEquivalent: "")
        modeMenu.addItem(focus5Item)
        modeMenu.addItem(dirtyFiveItem)

        let modeParentItem = NSMenuItem(title: "Ranking Mode", action: nil, keyEquivalent: "")
        modeParentItem.submenu = modeMenu
        menu.addItem(modeParentItem)

        menu.addItem(.separator())
        selectTelemetryItem = NSMenuItem(title: "Select Telemetry File…", action: #selector(selectTelemetryFile), keyEquivalent: "t")
        menu.addItem(selectTelemetryItem)
        selectPromptLogItem = NSMenuItem(title: "Select Prompt Log File…", action: #selector(selectPromptLogFile), keyEquivalent: "p")
        menu.addItem(selectPromptLogItem)

        launchAtLoginItem = NSMenuItem(title: "Launch at Login", action: #selector(toggleLaunchAtLogin), keyEquivalent: "")
        menu.addItem(launchAtLoginItem)

        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit Focus 5 Float", action: #selector(NSApp.terminate(_:)), keyEquivalent: "q")

        menu.delegate = self          // recompute checkmarks from model state on open
        self.contextMenu = menu
    }

    // NSMenuDelegate: refresh the checkmarks right before the menu shows, so a mode
    // change from the in-panel segmented control can't leave the menu stale.
    func menuNeedsUpdate(_ menu: NSMenu) {
        updateModeMenuState()
        updateLaunchAtLoginState()
        updateTelemetryMenuItem()
        updatePromptLogMenuItem()
    }

    private func updateTelemetryMenuItem() {
        if let url = model.telemetryFileURL {
            selectTelemetryItem.title = "Telemetry: \(url.lastPathComponent)"
        } else {
            selectTelemetryItem.title = "Select Telemetry File…"
        }
    }

    private func updatePromptLogMenuItem() {
        if let url = model.promptLogFileURL {
            selectPromptLogItem.title = "Prompt Log: \(url.lastPathComponent)"
        } else {
            selectPromptLogItem.title = "Select Prompt Log File…"
        }
    }

    /// Reflect the active ranking mode with a checkmark — single source of truth is
    /// the model's `isDirtyView`.
    private func updateModeMenuState() {
        let isDirty = model.isDirtyView
        focus5Item.state = isDirty ? .off : .on
        dirtyFiveItem.state = isDirty ? .on : .off
    }

    // MARK: - Panel

    private func buildPanel() {
        // Reference-design refresh: default back to a deliberate 340-wide shell,
        // matching the RepoMonitor panel proportions while keeping the existing
        // scroll-driven height. The header still allows a bounded wider state.
        let defaultRect = NSRect(x: 0, y: 0, width: 340, height: 660)

        let hostingView = FirstMouseHostingView(rootView: ContentView(
            model: model,
            onHide: { [weak self] in
                Task { @MainActor in
                    self?.hidePanel()
                }
            }
        ))
        hostingView.frame = defaultRect

        panel = FloatingPanel(
            contentRect: defaultRect,
            styleMask: [.titled, .closable, .resizable, .fullSizeContentView, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )

        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
        panel.isMovableByWindowBackground = true
        panel.level = .floating
        panel.isFloatingPanel = true
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.becomesKeyOnlyIfNeeded = true
        panel.hidesOnDeactivate = false
        panel.animationBehavior = .utilityWindow
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]

        // Clean chrome: this is a menu-bar-toggled panel, not a document window —
        // hide the traffic-light buttons (the grey dots seen in the spike).
        panel.standardWindowButton(.closeButton)?.isHidden = true
        panel.standardWindowButton(.miniaturizeButton)?.isHidden = true
        panel.standardWindowButton(.zoomButton)?.isHidden = true

        panel.contentView = hostingView
        panel.delegate = self

        // Keep the reference width by default but allow one bounded wider state.
        // Do not cap height to a screen here: an autosaved frame can be offset a
        // few points below the visible frame, and a screen-height maximum then
        // blocks the top edge before it can reach the menu bar.
        panel.minSize = PanelSizing.minimum
        panel.maxSize = PanelSizing.maximum

        // Frame autosave — bumped so the refreshed width/glass shell takes effect
        // once over any prior narrow saved frame, then persists again.
        panel.setFrameAutosaveName("Focus5FloatPanel.v5")
        if panel.frame.origin == .zero {
            panel.center()
        }
    }

    @objc private func togglePanel() {
        // If invoked from a right-click on the status item, show the menu instead.
        if let e = NSApp.currentEvent, e.type == .rightMouseUp {
            statusItem.menu = contextMenu
            statusItem.button?.performClick(nil)
            statusItem.menu = nil
            return
        }

        if panel.isVisible {
            hidePanel()
        } else {
            showPanel()
        }
    }

    private func showPanel() {
        panel.orderFrontRegardless()   // show WITHOUT activating the app
        logPanelGeometry("shown")
    }

    private func hidePanel() {
        panel.orderOut(nil)
        log.info("panel hidden")
    }

    func windowDidEndLiveResize(_ notification: Notification) {
        logPanelGeometry("live resize ended")
    }

    private func logPanelGeometry(_ event: String) {
        let frame = NSStringFromRect(panel.frame)
        let maximum = NSStringFromSize(panel.maxSize)
        let contentMaximum = NSStringFromSize(panel.contentMaxSize)
        let screenVisibleFrame = panel.screen.map { NSStringFromRect($0.visibleFrame) } ?? "none"
        log.info("panel \(event, privacy: .public) frame=\(frame, privacy: .public) max=\(maximum, privacy: .public) contentMax=\(contentMaximum, privacy: .public) screenVisible=\(screenVisibleFrame, privacy: .public)")
    }

    // MARK: - Actions

    @objc private func refreshData() {
        log.info("refresh (re-pull /focus-5.json)")
        Task { await model.refresh() }
    }

    @objc private func startServer() {
        log.info("manual start: rebalance serve")
        Task { await model.startServer() }
    }

    @objc private func selectTelemetryFile() {
        model.openFilePicker()
    }

    @objc private func selectPromptLogFile() {
        model.openPromptLogFilePicker()
    }

    @objc private func setFocus5Mode() {
        log.info("ranking mode → recent_activity")
        Task { await model.setMode(dirty: false) }   // server re-ranks; menu re-reads on open
    }

    @objc private func setDirtyFiveMode() {
        log.info("ranking mode → dirty_first")
        Task { await model.setMode(dirty: true) }     // server re-ranks; menu re-reads on open
    }

    // MARK: - Launch at login

    // ponytail: SMAppService.mainApp is the whole login-item API — no helper bundle,
    // no plist. Only works from the installed .app; from `swift run` status is
    // .notFound and register() throws (caught + logged, never crashes).
    @objc private func toggleLaunchAtLogin() {
        let svc = SMAppService.mainApp
        do {
            if svc.status == .enabled {
                try svc.unregister()
                log.info("launch-at-login disabled")
            } else {
                try svc.register()
                log.info("launch-at-login enabled")
            }
        } catch {
            log.error("launch-at-login toggle failed: \(error.localizedDescription)")
        }
        updateLaunchAtLoginState()
    }

    private func updateLaunchAtLoginState() {
        launchAtLoginItem.state = SMAppService.mainApp.status == .enabled ? .on : .off
    }
}
