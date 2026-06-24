import Foundation

public protocol ReplacementImporter: Sendable {
    var source: ReplacementImportSource { get }

    func importReplacements(request: ReplacementImportRequest) async throws -> ReplacementImportResult
}

public protocol ReplacementImportCoordinator: Sendable {
    func register(_ importer: any ReplacementImporter)
    func importer(for source: ReplacementImportSource) -> (any ReplacementImporter)?
    func importReplacements(request: ReplacementImportRequest) async throws -> ReplacementImportResult
}
