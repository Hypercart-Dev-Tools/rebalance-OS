import Foundation

/// Reads the live macOS Text Replacements DB by shelling out to the hardened `native_to_json.py`
/// (read-only `mode=ro`, tombstone-aware, deduped) rather than re-implementing Core Data parsing.
public struct AppleDatabaseImporter: ReplacementImporter {
    public let source: ReplacementImportSource = .appleDatabase
    private let bridge: PythonBridge
    private let codec: any CanonicalReplacementCoding
    private let linter: any ReplacementLinter
    private let mergeEngine: any ReplacementMergeEngine
    private let store: (any ReplacementStore)?

    public init(
        bridge: PythonBridge,
        codec: any CanonicalReplacementCoding = CanonicalReplacementCodec(),
        linter: any ReplacementLinter = DefaultReplacementLinter(),
        mergeEngine: any ReplacementMergeEngine = DefaultReplacementMergeEngine(),
        store: (any ReplacementStore)? = nil
    ) {
        self.bridge = bridge
        self.codec = codec
        self.linter = linter
        self.mergeEngine = mergeEngine
        self.store = store
    }

    /// Convenience: build a default bridge (resolves python + scripts dir + live DB path).
    public init() throws {
        try self.init(bridge: PythonBridge())
    }

    public func importReplacements(request: ReplacementImportRequest) async throws -> ReplacementImportResult {
        // native_to_json.py requires --output, so capture into a temp file and read it back.
        let outURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("fkr-import-\(UUID().uuidString).json")
        defer { try? FileManager.default.removeItem(at: outURL) }

        let dbPath = request.url?.path ?? bridge.databasePath.path
        let result = try bridge.run("native_to_json.py", ["--db", dbPath, "-o", outURL.path])
        guard result.ok else {
            throw ReplacementImportExportError.invalidInput(
                "native_to_json.py failed (exit \(result.exitCode)): " +
                (result.stderr.isEmpty ? result.stdout : result.stderr)
            )
        }

        let data = try Data(contentsOf: outURL)
        let incoming = try codec.decode(data)
        let local = try await store?.fetchAll() ?? []
        let diff = mergeEngine.diff(local: local, incoming: incoming)
        let issues = linter.validate(incoming)

        return ReplacementImportResult(
            source: .appleDatabase,
            imported: incoming,
            diff: diff,
            validationIssues: issues
        )
    }
}
