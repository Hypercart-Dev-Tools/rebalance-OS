import XCTest
import SwiftUI
@testable import Focus5Float

/// Real assertions for the pure-function logic the old env-var self-tests
/// (`FOCUS5_HEALTHTEST`, `FOCUS5_VSCODETEST`) only smoke-checked by eyeballing
/// printed output. `swift test` gives these a pass/fail result and CI hookup.
final class PureLogicTests: XCTestCase {
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
