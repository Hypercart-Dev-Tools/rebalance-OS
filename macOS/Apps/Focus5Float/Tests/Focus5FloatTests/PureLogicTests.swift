import XCTest
import SwiftUI
@testable import Focus5Float

/// Real assertions for the pure-function logic the old env-var self-tests
/// (`FOCUS5_HEALTHTEST`, `FOCUS5_VSCODETEST`) only smoke-checked by eyeballing
/// printed output. `swift test` gives these a pass/fail result and CI hookup.
final class PureLogicTests: XCTestCase {
    @MainActor
    func testPanelHostingViewSuppressesHiddenTitlebarSafeArea() {
        let rect = NSRect(x: 0, y: 0, width: 340, height: 660)
        let hostingView = FirstMouseHostingView(rootView: Color.clear)
        hostingView.frame = rect

        let panel = FloatingPanel(
            contentRect: rect,
            styleMask: [.titled, .closable, .resizable, .fullSizeContentView, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
        panel.contentView = hostingView
        panel.contentView?.layoutSubtreeIfNeeded()

        XCTAssertEqual(
            hostingView.safeAreaInsets.top,
            0,
            "The hidden titlebar must not reintroduce a blank strip above the visible panel shell"
        )
        XCTAssertEqual(hostingView.safeAreaRect, hostingView.bounds)
    }

    func testPanelSizingCapsWidthWithoutCappingHeightToCurrentScreen() {
        XCTAssertEqual(PanelSizing.minimum, NSSize(width: 340, height: 360))
        XCTAssertEqual(PanelSizing.maximum.width, 420)
        XCTAssertEqual(
            PanelSizing.maximum.height,
            CGFloat(Float.greatestFiniteMagnitude),
            "Height must retain AppKit's default maximum so an offset autosaved frame can still grow upward"
        )
    }

    func testRosterHealthTint() {
        XCTAssertEqual(RosterHealth.tint(dirty: 0, total: 5), Theme.diffAdd)     // all clean → green
        XCTAssertEqual(RosterHealth.tint(dirty: 5, total: 5), Theme.diffRemove) // all dirty → red
        XCTAssertEqual(RosterHealth.tint(dirty: 2, total: 5), .orange)          // some dirty → orange
    }

    func testVSCodeLauncherArgumentsAreExactlyTheFolderNoFlags() {
        let argv = VSCodeLauncher.arguments(forRepoPath: "/repos/demo repo")
        XCTAssertEqual(argv, ["/repos/demo repo"])
    }

    func testVSCodeLauncherCandidateOrder() {
        XCTAssertEqual(VSCodeLauncher.candidates, [
            "/opt/homebrew/bin/code",
            "/usr/local/bin/code",
            "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
        ])
    }

    /// Mirrors focus5_scan.vscode_url()'s `f"vscode://file{quote(local_path, safe='/')}"`
    /// — same safe-char set (alnum + `_.-~/`), everything else percent-encoded.
    func testVSCodeLauncherFileURLMatchesServerEncoding() {
        XCTAssertEqual(
            VSCodeLauncher.fileURL(forLocalPath: "/Users/noelsaw/Documents/rebalance-OS"),
            "vscode://file/Users/noelsaw/Documents/rebalance-OS"
        )
        XCTAssertEqual(
            VSCodeLauncher.fileURL(forLocalPath: "/repos/demo repo"),
            "vscode://file/repos/demo%20repo"
        )
    }

    func testRelTimeAgoBuckets() {
        let now = Date()
        XCTAssertEqual(RelTime.ago(now.addingTimeInterval(-30), now: now), "just now")
        XCTAssertEqual(RelTime.ago(now.addingTimeInterval(-5 * 60), now: now), "5m ago")
        XCTAssertEqual(RelTime.ago(now.addingTimeInterval(-3 * 3600), now: now), "3h ago")
        XCTAssertEqual(RelTime.ago(now.addingTimeInterval(-2 * 86400), now: now), "2d ago")
        XCTAssertEqual(RelTime.ago(Date?.none), "")
    }

    func testRelTimeIsOlderThan() {
        let now = Date()
        let iso = ISO8601DateFormatter().string(from: now.addingTimeInterval(-25 * 3600))
        XCTAssertTrue(RelTime.isOlderThan(iso, hours: 24, now: now))
        XCTAssertFalse(RelTime.isOlderThan(iso, hours: 48, now: now))
        XCTAssertFalse(RelTime.isOlderThan(nil, hours: 24, now: now))
    }
}
