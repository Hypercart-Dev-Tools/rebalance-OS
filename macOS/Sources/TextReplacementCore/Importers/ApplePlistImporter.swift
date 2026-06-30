import Foundation

public struct ApplePlistImporter: ReplacementImporter {
    public let source: ReplacementImportSource = .applePlist
    private let codec: any ApplePlistCoding
    private let linter: any ReplacementLinter
    private let mergeEngine: any ReplacementMergeEngine
    private let store: (any ReplacementStore)?

    public init(
        codec: any ApplePlistCoding = ApplePlistCodec(),
        linter: any ReplacementLinter = DefaultReplacementLinter(),
        mergeEngine: any ReplacementMergeEngine = DefaultReplacementMergeEngine(),
        store: (any ReplacementStore)? = nil
    ) {
        self.codec = codec
        self.linter = linter
        self.mergeEngine = mergeEngine
        self.store = store
    }

    public func importReplacements(request: ReplacementImportRequest) async throws -> ReplacementImportResult {
        let data: Data
        if let requestData = request.data {
            data = requestData
        } else if let url = request.url {
            data = try Data(contentsOf: url)
        } else {
            throw ReplacementImportExportError.missingInputData
        }

        let items = try codec.decode(data)
        let incoming = items.map(Replacement.init(appleTextReplacementItem:))
        let local = try await store?.fetchAll() ?? []
        let diff = mergeEngine.diff(local: local, incoming: incoming)
        let issues = linter.validate(incoming)

        return ReplacementImportResult(
            source: .applePlist,
            imported: incoming,
            diff: diff,
            validationIssues: issues
        )
    }
}
