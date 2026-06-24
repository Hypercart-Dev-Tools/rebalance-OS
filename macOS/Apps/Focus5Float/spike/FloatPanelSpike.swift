// FloatPanelSpike.swift — Phase 0 throwaway spike for Focus 5 Float.
//
// PURPOSE: de-risk the HARD macOS behavior before building any real UI — an
// *interactive*, non-activating floating panel that stays above fullscreen apps
// AND still lets you click controls on the FIRST click (no focus round-trip),
// expand/collapse rows, flip a segmented control, open a context menu, and open
// a link — all while another app is frontmost. Appearance alone is NOT a pass.
//
// RUN:   swift macOS/Apps/Focus5Float/spike/FloatPanelSpike.swift
//        (a menu-bar "F5" item appears; click it to toggle the panel)
// QUIT:  menu-bar item → Quit, or Ctrl-C in the terminal.
//
// WHAT TO VERIFY (Phase 0 QA litmus — capture a clip):
//   1. Put another app in FULLSCREEN and make it frontmost.
//   2. Toggle the panel from the menu bar — it appears OVER the fullscreen app.
//   3. Click "Clicked 0×" ONCE — the counter increments on the first click
//      (proves accepts-first-mouse; no "click to focus, click again to act").
//   4. Toggle the disclosure — the detail row shows/hides.
//   5. Switch the segmented control between Focus 5 / Dirty Five.
//   6. Right-click the panel body — a context menu opens.
//   7. Click "Open github.com ↗" — the link opens in the browser.
//   8. Type in the other (fullscreen) app — the panel did NOT steal key focus.

import AppKit

// A non-activating floating panel that can still take key focus when a control
// needs it, but does not activate the app on show.
final class FloatingPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

// Container that accepts the first mouse click even while the window is inactive,
// so buttons fire on the first click over a frontmost fullscreen app.
final class FirstMouseView: NSView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var panel: FloatingPanel!
    private var statusItem: NSStatusItem!
    private var clickCount = 0
    private var clickButton: NSButton!
    private var detailRow: NSView!
    private var statusLabel: NSTextField!
    private var cardsStack: NSStackView!

    // Two static rosters so the view toggle visibly swaps the cards. Real data
    // (a live GET /focus-5.json?view=dirty) is Phase 4 — this just proves the
    // non-activating panel re-renders its card stack on a state change.
    private let focus5Cards = [
        ("#1 rebalance-OS", "your commit 18m ago · 5M 7U"),
        ("#2 WP-DB-Toolkit", "your commit 1h ago · clean"),
    ]
    private let dirtyCards = [
        ("#1 WP-DB-Toolkit", "↑2 ↓0 · 3 modified · UNPUSHED"),
        ("#2 rebalance-OS", "5 modified, 7 untracked · dirty"),
    ]

    func applicationDidFinishLaunching(_ note: Notification) {
        // Menu-bar agent: no Dock icon, no main menu activation.
        NSApp.setActivationPolicy(.accessory)

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "F5"
        statusItem.button?.target = self
        statusItem.button?.action = #selector(togglePanel)

        let menu = NSMenu()
        menu.addItem(withTitle: "Toggle Panel", action: #selector(togglePanel), keyEquivalent: "t")
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit", action: #selector(NSApp.terminate(_:)), keyEquivalent: "q")
        // Right-click the status item → menu; left-click → toggle (handled above).
        statusItem.menu = nil  // keep left-click = toggle; show menu on demand below
        statusItem.button?.sendAction(on: [.leftMouseUp, .rightMouseUp])
        self.contextMenu = menu

        buildPanel()
        togglePanel()  // show on launch so the spike is immediately interactive
    }

    private var contextMenu: NSMenu!

    private func buildPanel() {
        let content = FirstMouseView(frame: NSRect(x: 0, y: 0, width: 320, height: 360))

        statusLabel = label("Non-activating floating panel — interact freely.")
        statusLabel.font = .systemFont(ofSize: 11)
        statusLabel.textColor = .secondaryLabelColor

        clickButton = NSButton(title: "Clicked 0×", target: self, action: #selector(bump))
        clickButton.bezelStyle = .rounded

        let disclosure = NSButton(checkboxWithTitle: "Expand detail row", target: self, action: #selector(toggleDetail))

        detailRow = makeCard(title: "rebalance-OS", subtitle: "↑2 ↓0 · 5M 7U · dirty")
        detailRow.isHidden = true

        let seg = NSSegmentedControl(labels: ["🎯 Focus 5", "🧹 Dirty Five"],
                                     trackingMode: .selectOne,
                                     target: self, action: #selector(segChanged(_:)))
        seg.selectedSegment = 0

        let link = NSButton(title: "Open github.com ↗", target: self, action: #selector(openLink))
        link.bezelStyle = .rounded

        // Stacked "cards" — rebuilt when the view toggle flips.
        cardsStack = NSStackView()
        cardsStack.orientation = .vertical
        cardsStack.alignment = .leading
        cardsStack.spacing = 8
        renderCards(dirty: false)

        let stack = NSStackView(views: [
            statusLabel, seg, cardsStack, clickButton, disclosure, detailRow, link,
        ])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8
        stack.edgeInsets = NSEdgeInsets(top: 12, left: 12, bottom: 12, right: 12)
        stack.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            stack.topAnchor.constraint(equalTo: content.topAnchor),
        ])

        // Right-click context menu on the body (tests menus in a non-activating panel).
        let bodyMenu = NSMenu()
        bodyMenu.addItem(withTitle: "Refresh (re-pull)", action: #selector(bump), keyEquivalent: "r")
        bodyMenu.addItem(withTitle: "Open in VS Code", action: #selector(openLink), keyEquivalent: "")
        content.menu = bodyMenu

        panel = FloatingPanel(
            contentRect: content.frame,
            styleMask: [.titled, .closable, .fullSizeContentView, .nonactivatingPanel],
            backing: .buffered, defer: false)
        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
        panel.isMovableByWindowBackground = true
        panel.level = .floating
        panel.isFloatingPanel = true
        panel.becomesKeyOnlyIfNeeded = true
        panel.hidesOnDeactivate = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.contentView = content
        panel.setFrameAutosaveName("Focus5FloatSpikePanel")
        if panel.frame.origin == .zero { panel.center() }
    }

    private func renderCards(dirty: Bool) {
        cardsStack.arrangedSubviews.forEach { $0.removeFromSuperview() }
        for (title, subtitle) in (dirty ? dirtyCards : focus5Cards) {
            cardsStack.addArrangedSubview(makeCard(title: title, subtitle: subtitle))
        }
    }

    private func makeCard(title: String, subtitle: String) -> NSView {
        let v = NSView()
        v.wantsLayer = true
        v.layer?.backgroundColor = NSColor.controlBackgroundColor.cgColor
        v.layer?.cornerRadius = 8
        let t = label(title); t.font = .systemFont(ofSize: 13, weight: .semibold)
        let s = label(subtitle); s.font = .systemFont(ofSize: 11); s.textColor = .secondaryLabelColor
        let st = NSStackView(views: [t, s]); st.orientation = .vertical; st.alignment = .leading; st.spacing = 2
        st.edgeInsets = NSEdgeInsets(top: 8, left: 10, bottom: 8, right: 10)
        st.translatesAutoresizingMaskIntoConstraints = false
        v.addSubview(st)
        NSLayoutConstraint.activate([
            st.leadingAnchor.constraint(equalTo: v.leadingAnchor),
            st.trailingAnchor.constraint(equalTo: v.trailingAnchor),
            st.topAnchor.constraint(equalTo: v.topAnchor),
            st.bottomAnchor.constraint(equalTo: v.bottomAnchor),
            v.widthAnchor.constraint(equalToConstant: 290),
        ])
        return v
    }

    private func label(_ s: String) -> NSTextField {
        let l = NSTextField(labelWithString: s)
        l.lineBreakMode = .byTruncatingTail
        return l
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
            panel.orderOut(nil)
        } else {
            panel.orderFrontRegardless()   // show WITHOUT activating the app
        }
    }

    @objc private func bump() {
        clickCount += 1
        clickButton.title = "Clicked \(clickCount)×"
        statusLabel.stringValue = "First-click worked ✓ (count \(clickCount))"
    }

    @objc private func toggleDetail() { detailRow.isHidden.toggle() }

    @objc private func segChanged(_ s: NSSegmentedControl) {
        let dirty = s.selectedSegment == 1
        statusLabel.stringValue = dirty ? "View: Dirty Five" : "View: Focus 5"
        renderCards(dirty: dirty)   // the cards now actually swap on toggle
    }

    @objc private func openLink() {
        if let url = URL(string: "https://github.com") { NSWorkspace.shared.open(url) }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
