import Foundation

public struct ApplePlistExporter: ReplacementExporter {
    public let format: ReplacementExportFormat = .applePlist
    private let codec: any ApplePlistCoding
    private let linter: any ReplacementLinter

    public init(
        codec: any ApplePlistCoding = ApplePlistCodec(),
        linter: any ReplacementLinter = DefaultReplacementLinter()
    ) {
        self.codec = codec
        self.linter = linter
    }

    public func exportReplacements(
        _ replacements: [Replacement],
        request: ReplacementExportRequest
    ) async throws -> ReplacementExportResult {
        var exportable = request.includeDisabled
            ? replacements
            : replacements.filter(\.enabled)

        if request.sortByShortcut {
            exportable.sort { $0.shortcut.localizedStandardCompare($1.shortcut) == .orderedAscending }
        }

        let warnings = linter.validate(exportable)
        let items = exportable.map(\.appleTextReplacementItem)
        let data = try codec.encode(items)

        return ReplacementExportResult(
            format: .applePlist,
            data: data,
            exportedCount: exportable.count,
            warnings: warnings
        )
    }
}
