import Foundation

public protocol ReplacementExporter: Sendable {
    var format: ReplacementExportFormat { get }

    func exportReplacements(
        _ replacements: [Replacement],
        request: ReplacementExportRequest
    ) async throws -> ReplacementExportResult
}

public protocol ReplacementExportCoordinator: Sendable {
    func register(_ exporter: any ReplacementExporter)
    func exporter(for format: ReplacementExportFormat) -> (any ReplacementExporter)?
    func exportReplacements(
        _ replacements: [Replacement],
        request: ReplacementExportRequest
    ) async throws -> ReplacementExportResult
}
