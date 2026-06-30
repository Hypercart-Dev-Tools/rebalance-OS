import Foundation
import Testing
@testable import TextReplacementCore

/// True end-to-end coverage of the macOS integration: Swift → canonical JSON →
/// `json_to_apple_sqlite.py` (apply) → SQLite → `native_to_json.py` (import) → Swift.
///
/// SAFETY: every run operates on a *temporary copy* of the database — never the user's
/// live `~/Library/KeyboardServices/TextReplacements.db`. The whole suite is gated by
/// `BridgeTestSupport.canRun`, so it auto-skips when python3, the repo `scripts/`, or a
/// source database aren't available (e.g. headless CI). Point it at a fixture explicitly
/// with `FKR_TEST_DB=/path/to/TextReplacements.db`.
struct AppleDatabaseBridgeE2ETests {

    @Test(.enabled(if: BridgeTestSupport.canRun,
                   "Needs python3 + repo scripts/ + a source DB (set FKR_TEST_DB to override)."))
    func applyThenReimportRoundTripsANewReplacement() async throws {
        let env = try BridgeTestSupport.makeSandbox()
        defer { env.cleanup() }

        let importer = AppleDatabaseImporter(bridge: env.bridge)
        let before = try await importer.importReplacements(request: .init(source: .appleDatabase)).imported

        // A shortcut unlikely to already exist, so this is unambiguously an add.
        let shortcut = "zz_e2e_\(Int.random(in: 100_000...999_999))"
        let phrase = "end-to-end round-trip \(UUID().uuidString.prefix(8))"
        let writer = AppleDatabaseWriter(bridge: env.bridge, backupDirectory: env.backupDir)

        let outcome = try writer.apply(before + [Replacement(shortcut: shortcut, phrase: String(phrase))],
                                       strategy: .merge)
        #expect(outcome.applied)

        let after = try await importer.importReplacements(request: .init(source: .appleDatabase)).imported
        #expect(after.contains { $0.shortcut == shortcut && $0.phrase == String(phrase) })
        #expect(after.count >= before.count)   // merge adds/updates, never removes
    }

    @Test(.enabled(if: BridgeTestSupport.canRun,
                   "Needs python3 + repo scripts/ + a source DB (set FKR_TEST_DB to override)."))
    func planIsADryRunAndDoesNotMutate() async throws {
        let env = try BridgeTestSupport.makeSandbox()
        defer { env.cleanup() }

        let importer = AppleDatabaseImporter(bridge: env.bridge)
        let before = try await importer.importReplacements(request: .init(source: .appleDatabase)).imported

        let writer = AppleDatabaseWriter(bridge: env.bridge, backupDirectory: env.backupDir)
        let plan = try writer.plan(before + [Replacement(shortcut: "zz_plan_only", phrase: "should not persist")],
                                   strategy: .merge)
        #expect(!plan.applied)                 // dry-run

        let after = try await importer.importReplacements(request: .init(source: .appleDatabase)).imported
        #expect(after.count == before.count)   // nothing written
        #expect(!after.contains { $0.shortcut == "zz_plan_only" })
    }
}

// MARK: - Gating + sandbox

enum BridgeTestSupport {
    /// A working DB copy + a bridge pointed at it, plus a temp backup dir. Disposable.
    struct Sandbox {
        let root: URL
        let bridge: PythonBridge
        let backupDir: URL
        func cleanup() { try? FileManager.default.removeItem(at: root) }
    }

    /// Source database to copy from: explicit `FKR_TEST_DB`, else the live DB if present.
    static var sourceDatabase: URL? {
        let fm = FileManager.default
        if let p = ProcessInfo.processInfo.environment["FKR_TEST_DB"], !p.isEmpty {
            let url = URL(fileURLWithPath: (p as NSString).expandingTildeInPath)
            return fm.fileExists(atPath: url.path) ? url : nil
        }
        let live = PythonBridge.defaultDatabasePath()
        return fm.fileExists(atPath: live.path) ? live : nil
    }

    static var scriptsDirectory: URL? { try? PythonBridge.resolveScriptsDirectory() }

    static var python3Available: Bool {
        let fm = FileManager.default
        if let p = ProcessInfo.processInfo.environment["FKR_PYTHON"], fm.isExecutableFile(atPath: p) { return true }
        return ["/usr/bin/python3", "/opt/homebrew/bin/python3", "/usr/local/bin/python3"]
            .contains { fm.isExecutableFile(atPath: $0) }
    }

    static let canRun: Bool = sourceDatabase != nil && scriptsDirectory != nil && python3Available

    /// Copy the source DB (and any WAL/SHM sidecars) into a throwaway dir and build a
    /// bridge that targets the copy.
    static func makeSandbox() throws -> Sandbox {
        let fm = FileManager.default
        let src = try #require(sourceDatabase)
        let root = fm.temporaryDirectory.appendingPathComponent("fkr-e2e-\(UUID().uuidString)")
        try fm.createDirectory(at: root, withIntermediateDirectories: true)

        let dbCopy = root.appendingPathComponent("TextReplacements.db")
        try fm.copyItem(at: src, to: dbCopy)
        for suffix in ["-wal", "-shm"] {                       // keep the SQLite WAL set together
            let sidecar = URL(fileURLWithPath: src.path + suffix)
            if fm.fileExists(atPath: sidecar.path) {
                try? fm.copyItem(at: sidecar, to: URL(fileURLWithPath: dbCopy.path + suffix))
            }
        }

        let backupDir = root.appendingPathComponent("backups")
        let bridge = try PythonBridge(databasePath: dbCopy)
        return Sandbox(root: root, bridge: bridge, backupDir: backupDir)
    }
}
