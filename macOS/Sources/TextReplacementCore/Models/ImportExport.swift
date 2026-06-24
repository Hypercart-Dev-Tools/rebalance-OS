import Foundation

public enum ReplacementImportSource: String, Codable, Hashable, Sendable {
    case applePlist = "apple-plist"
    case appleDatabase = "apple-database"
    case csv
    case json
}

public enum ReplacementExportFormat: String, Codable, Hashable, Sendable, CaseIterable {
    case applePlist = "apple-plist"
    case csv
    case json
    case markdown
}

public struct ReplacementImportRequest: Hashable, Sendable {
    public var source: ReplacementImportSource
    public var url: URL?
    public var data: Data?
    public var mergePolicy: ReplacementMergePolicy

    public init(
        source: ReplacementImportSource,
        url: URL? = nil,
        data: Data? = nil,
        mergePolicy: ReplacementMergePolicy = .previewConflicts
    ) {
        self.source = source
        self.url = url
        self.data = data
        self.mergePolicy = mergePolicy
    }
}

public struct ReplacementExportRequest: Hashable, Sendable {
    public var format: ReplacementExportFormat
    public var includeDisabled: Bool
    public var sortByShortcut: Bool

    public init(
        format: ReplacementExportFormat,
        includeDisabled: Bool = false,
        sortByShortcut: Bool = true
    ) {
        self.format = format
        self.includeDisabled = includeDisabled
        self.sortByShortcut = sortByShortcut
    }
}

public enum ReplacementMergePolicy: String, Codable, Hashable, Sendable {
    case previewConflicts
    case keepLocal
    case replaceLocal
    case addOnly
}

public struct ReplacementImportResult: Hashable, Sendable {
    public var source: ReplacementImportSource
    public var imported: [Replacement]
    public var diff: ReplacementDiff
    public var validationIssues: [ReplacementValidationIssue]

    public init(
        source: ReplacementImportSource,
        imported: [Replacement],
        diff: ReplacementDiff,
        validationIssues: [ReplacementValidationIssue] = []
    ) {
        self.source = source
        self.imported = imported
        self.diff = diff
        self.validationIssues = validationIssues
    }
}

public struct ReplacementExportResult: Hashable, Sendable {
    public var format: ReplacementExportFormat
    public var data: Data
    public var exportedCount: Int
    public var warnings: [ReplacementValidationIssue]

    public init(
        format: ReplacementExportFormat,
        data: Data,
        exportedCount: Int,
        warnings: [ReplacementValidationIssue] = []
    ) {
        self.format = format
        self.data = data
        self.exportedCount = exportedCount
        self.warnings = warnings
    }
}
