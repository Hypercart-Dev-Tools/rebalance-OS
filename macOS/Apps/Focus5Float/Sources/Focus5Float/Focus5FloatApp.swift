import SwiftUI
import AppKit

// Phase 2 entry point: An AppKit-driven lifecycle that runs the app as a
// menu-bar agent (no Dock icon) and hosts the SwiftUI card stack in an
// interactive, non-activating floating panel (NSPanel + NSStatusItem).

@main
struct Focus5FloatApp {
    static func main() {
        Focus5SelfTest.runIfRequested()
        
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
    }
}

// A non-activating floating panel that can still take key focus when a control
// needs it, but does not activate the app on show.
final class FloatingPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

// Container that accepts the first mouse click even while the window is inactive,
// so buttons fire on the first click over a frontmost fullscreen app.
final class FirstMouseHostingView<Content: View>: NSHostingView<Content> {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var panel: FloatingPanel!
    private var statusItem: NSStatusItem!
    private var contextMenu: NSMenu!
    private let model = Focus5Model()

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Set accessory policy so it doesn't show in the Dock.
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

        // Load the sample data fixture for Phase 2
        model.loadSample()

        // Build the floating panel
        buildPanel()

        // Show panel on launch
        showPanel()
    }

    private func buildContextMenu() {
        let menu = NSMenu()
        
        let refreshItem = NSMenuItem(title: "Refresh (re-pull)", action: #selector(refreshData), keyEquivalent: "r")
        menu.addItem(refreshItem)
        
        let modeMenu = NSMenu()
        let focus5Item = NSMenuItem(title: "🎯 Focus 5", action: #selector(setFocus5Mode), keyEquivalent: "")
        let dirtyFiveItem = NSMenuItem(title: "🧹 Dirty Five", action: #selector(setDirtyFiveMode), keyEquivalent: "")
        modeMenu.addItem(focus5Item)
        modeMenu.addItem(dirtyFiveItem)
        
        let modeParentItem = NSMenuItem(title: "Ranking Mode", action: nil, keyEquivalent: "")
        modeParentItem.submenu = modeMenu
        menu.addItem(modeParentItem)
        
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit", action: #selector(NSApp.terminate(_:)), keyEquivalent: "q")
        
        self.contextMenu = menu
    }

    private func buildPanel() {
        let defaultRect = NSRect(x: 0, y: 0, width: 360, height: 600)
        
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
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.contentView = hostingView
        
        // Frame autosave
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
        panel.orderFrontRegardless()
    }

    private func hidePanel() {
        panel.orderOut(nil)
    }

    @objc private func refreshData() {
        model.loadSample()
    }

    @objc private func setFocus5Mode() {
        model.rankingMode = "recent_activity"
    }

    @objc private func setDirtyFiveMode() {
        model.rankingMode = "dirty_first"
    }
}

