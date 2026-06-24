import SwiftUI
import AppKit
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
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private var panel: FloatingPanel!
    private var statusItem: NSStatusItem!
    private var contextMenu: NSMenu!
    private var focus5Item: NSMenuItem!
    private var dirtyFiveItem: NSMenuItem!
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
        Task { await model.refresh(); updateModeMenuState() }
        startPolling()
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

        let modeMenu = NSMenu()
        focus5Item = NSMenuItem(title: "🎯 Focus 5", action: #selector(setFocus5Mode), keyEquivalent: "")
        dirtyFiveItem = NSMenuItem(title: "🧹 Dirty Five", action: #selector(setDirtyFiveMode), keyEquivalent: "")
        modeMenu.addItem(focus5Item)
        modeMenu.addItem(dirtyFiveItem)

        let modeParentItem = NSMenuItem(title: "Ranking Mode", action: nil, keyEquivalent: "")
        modeParentItem.submenu = modeMenu
        menu.addItem(modeParentItem)

        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit Focus 5 Float", action: #selector(NSApp.terminate(_:)), keyEquivalent: "q")

        menu.delegate = self          // recompute checkmarks from model state on open
        self.contextMenu = menu
    }

    // NSMenuDelegate: refresh the checkmarks right before the menu shows, so a mode
    // change from the in-panel segmented control can't leave the menu stale.
    func menuNeedsUpdate(_ menu: NSMenu) {
        updateModeMenuState()
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
        let defaultRect = NSRect(x: 0, y: 0, width: 360, height: 640)

        let hostingView = FirstMouseHostingView(rootView: ContentView(model: model))
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

        // Frame autosave — remembers position & size across launches.
        panel.setFrameAutosaveName("Focus5FloatPanel")
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
        log.info("panel shown")
    }

    private func hidePanel() {
        panel.orderOut(nil)
        log.info("panel hidden")
    }

    // MARK: - Actions

    @objc private func refreshData() {
        log.info("refresh (re-pull /focus-5.json)")
        Task { await model.refresh() }
    }

    @objc private func setFocus5Mode() {
        log.info("ranking mode → recent_activity")
        Task { await model.setMode(dirty: false) }   // server re-ranks; menu re-reads on open
    }

    @objc private func setDirtyFiveMode() {
        log.info("ranking mode → dirty_first")
        Task { await model.setMode(dirty: true) }     // server re-ranks; menu re-reads on open
    }
}
