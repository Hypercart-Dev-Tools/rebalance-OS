import XCTest
@testable import Focus5Float

/// Covers the telemetry-tab file picker's two supported kinds: JSON health
/// signals (existing) and freeform .md notes (new). Also proves the selection
/// survives a cold relaunch, since both kinds share the same UserDefaults
/// persistence path in `Focus5Model`.
@MainActor
final class TelemetryFileLoadingTests: XCTestCase {
    private static let defaultsKey = "telemetryFilePath"
    private var savedDefault: String?
    private var tempFiles: [URL] = []

    override func setUp() {
        super.setUp()
        // Isolate from whatever file the real app currently has selected on
        // this machine — restored in tearDown so running tests never clobbers
        // the user's live Focus5Float preference.
        savedDefault = UserDefaults.standard.string(forKey: Self.defaultsKey)
        UserDefaults.standard.removeObject(forKey: Self.defaultsKey)
    }

    override func tearDown() {
        UserDefaults.standard.set(savedDefault, forKey: Self.defaultsKey)
        for url in tempFiles { try? FileManager.default.removeItem(at: url) }
        tempFiles = []
        super.tearDown()
    }

    private func makeTempFile(named name: String, contents: String) -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("Focus5FloatTests-\(UUID().uuidString)-\(name)")
        try? contents.write(to: url, atomically: true, encoding: .utf8)
        tempFiles.append(url)
        return url
    }

    func testJSONFileDecodesIntoTelemetryEntries() {
        let json = """
        [
          {"health": "green", "title": "A", "description": "ok", "updatedAt": "2026-01-01T00:00:00Z"},
          {"health": "red", "title": "B", "description": "bad", "updatedAt": "2026-01-02T00:00:00Z"}
        ]
        """
        let model = Focus5Model()
        model.telemetryFileURL = makeTempFile(named: "signals.json", contents: json)

        XCTAssertFalse(model.telemetryIsMarkdown)
        XCTAssertNil(model.telemetryMarkdownContent)
        XCTAssertNil(model.telemetryLoadError)
        XCTAssertEqual(model.telemetryEntries.map(\.title), ["B", "A"])   // newest-first
    }

    func testMalformedJSONReportsLoadError() {
        let model = Focus5Model()
        model.telemetryFileURL = makeTempFile(named: "bad.json", contents: "{ not an array }")

        XCTAssertNotNil(model.telemetryLoadError)
        XCTAssertTrue(model.telemetryEntries.isEmpty)
    }

    func testMarkdownFileLoadsAsRawTextNotTelemetryEntries() {
        let note = "# Heading\n- item one\n- item two\n"
        let model = Focus5Model()
        model.telemetryFileURL = makeTempFile(named: "notes.md", contents: note)

        XCTAssertTrue(model.telemetryIsMarkdown)
        XCTAssertEqual(model.telemetryMarkdownContent, note)
        XCTAssertTrue(model.telemetryEntries.isEmpty)
        XCTAssertNil(model.telemetryLoadError)
    }

    func testMarkdownDetectionIsCaseInsensitiveOnExtension() {
        let model = Focus5Model()
        model.telemetryFileURL = makeTempFile(named: "notes.MD", contents: "hello")
        XCTAssertTrue(model.telemetryIsMarkdown)
    }

    /// GH-121 agy [Should] #2: the .md read is synchronous on @MainActor, so a
    /// giant file must not load unbounded — verifies the byte ceiling, the
    /// visible truncation note, and that a file under the ceiling is untouched.
    func testSmallMarkdownFileUnderCeilingLoadsFullyWithoutTruncation() {
        let note = String(repeating: "a", count: 100)
        let model = Focus5Model()
        model.telemetryFileURL = makeTempFile(named: "small.md", contents: note)

        XCTAssertEqual(model.telemetryMarkdownContent, note)
        XCTAssertNil(model.telemetryLoadError)
    }

    func testLargeMarkdownFileIsTruncatedAtByteCeilingWithVisibleNote() throws {
        let oversized = String(repeating: "a", count: Focus5Model.telemetryMarkdownByteCeiling + 500)
        let model = Focus5Model()
        model.telemetryFileURL = makeTempFile(named: "huge.md", contents: oversized)

        XCTAssertNil(model.telemetryLoadError)
        let content = try XCTUnwrap(model.telemetryMarkdownContent)

        let noteSuffix = "\n\n…truncated (file exceeds 1 MB)"
        XCTAssertTrue(content.hasSuffix(noteSuffix))

        // Body before the note is exactly the byte ceiling — no more, no less.
        let body = String(content.dropLast(noteSuffix.count))
        XCTAssertEqual(body.utf8.count, Focus5Model.telemetryMarkdownByteCeiling)
    }

    func testClearingSelectionResetsAllTelemetryState() {
        let model = Focus5Model()
        model.telemetryFileURL = makeTempFile(named: "notes.md", contents: "hi")
        XCTAssertNotNil(model.telemetryMarkdownContent)

        model.telemetryFileURL = nil

        XCTAssertNil(model.telemetryMarkdownContent)
        XCTAssertNil(model.telemetryLoadError)
        XCTAssertTrue(model.telemetryEntries.isEmpty)
    }

    /// GH-121 Phase 2: pure assertion on the extension-string discriminator —
    /// `foo.json` → structured (JSON) viewer, `foo.md` → text (markdown) viewer.
    /// No temp file / disk I/O needed: `isMarkdownKind` only inspects
    /// `URL.pathExtension`, so a non-existent path is sufficient. Mirrors the
    /// FOCUS5_KINDTEST headless self-test in SelfTest.swift, which exercises the
    /// same production function outside XCTest.
    func testFileKindDiscriminatorMapsExtensionToViewerKind() {
        XCTAssertFalse(Focus5Model.isMarkdownKind(URL(fileURLWithPath: "/tmp/foo.json")))
        XCTAssertTrue(Focus5Model.isMarkdownKind(URL(fileURLWithPath: "/tmp/foo.md")))
        XCTAssertTrue(Focus5Model.isMarkdownKind(URL(fileURLWithPath: "/tmp/FOO.MD")))
        XCTAssertFalse(Focus5Model.isMarkdownKind(URL(fileURLWithPath: "/tmp/signals.JSON")))
        XCTAssertFalse(Focus5Model.isMarkdownKind(URL(fileURLWithPath: "/tmp/notes.markdown")))
        XCTAssertFalse(Focus5Model.isMarkdownKind(URL(fileURLWithPath: "/tmp/no-extension")))
        XCTAssertFalse(Focus5Model.isMarkdownKind(nil))
    }

    func testMissingFileReportsLoadErrorForBothKinds() {
        let goneJSON = FileManager.default.temporaryDirectory.appendingPathComponent("gone-\(UUID().uuidString).json")
        let jsonModel = Focus5Model()
        jsonModel.telemetryFileURL = goneJSON
        XCTAssertNotNil(jsonModel.telemetryLoadError)

        let goneMD = FileManager.default.temporaryDirectory.appendingPathComponent("gone-\(UUID().uuidString).md")
        let mdModel = Focus5Model()
        mdModel.telemetryFileURL = goneMD
        XCTAssertNotNil(mdModel.telemetryLoadError)
        XCTAssertNil(mdModel.telemetryMarkdownContent)
    }

    /// The selection is written to UserDefaults on set and re-read in `init()` —
    /// this is what makes it survive an app relaunch (and a device reboot, since
    /// UserDefaults is disk-backed). A fresh `Focus5Model()` simulates cold start.
    func testSelectionPersistsAcrossModelRelaunchForBothKinds() {
        let mdURL = makeTempFile(named: "persisted.md", contents: "persisted note")
        let first = Focus5Model()
        first.telemetryFileURL = mdURL

        let relaunched = Focus5Model()
        XCTAssertEqual(relaunched.telemetryFileURL, mdURL)
        XCTAssertEqual(relaunched.telemetryMarkdownContent, "persisted note")

        let jsonURL = makeTempFile(named: "persisted.json", contents: "[]")
        first.telemetryFileURL = jsonURL

        let relaunchedAgain = Focus5Model()
        XCTAssertEqual(relaunchedAgain.telemetryFileURL, jsonURL)
        XCTAssertFalse(relaunchedAgain.telemetryIsMarkdown)
    }
}
