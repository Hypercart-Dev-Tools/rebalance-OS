import Foundation

public final class DefaultReplacementImportExportRegistry: ReplacementImportCoordinator, ReplacementExportCoordinator, @unchecked Sendable {
    private var importers: [ReplacementImportSource: any ReplacementImporter] = [:]
    private var exporters: [ReplacementExportFormat: any ReplacementExporter] = [:]

    public init() {}

    public func register(_ importer: any ReplacementImporter) {
        importers[importer.source] = importer
    }

    public func register(_ exporter: any ReplacementExporter) {
        exporters[exporter.format] = exporter
    }

    public func importer(for source: ReplacementImportSource) -> (any ReplacementImporter)? {
        importers[source]
    }

    public func exporter(for format: ReplacementExportFormat) -> (any ReplacementExporter)? {
        exporters[format]
    }

    public func importReplacements(request: ReplacementImportRequest) async throws -> ReplacementImportResult {
        guard let importer = importer(for: request.source) else {
            throw ReplacementImportExportError.unsupportedImportSource(request.source)
        }

        return try await importer.importReplacements(request: request)
    }

    public func exportReplacements(
        _ replacements: [Replacement],
        request: ReplacementExportRequest
    ) async throws -> ReplacementExportResult {
        guard let exporter = exporter(for: request.format) else {
            throw ReplacementImportExportError.unsupportedExportFormat(request.format)
        }

        return try await exporter.exportReplacements(replacements, request: request)
    }
}

public enum ReplacementImportExportError: Error, LocalizedError, Sendable {
    case unsupportedImportSource(ReplacementImportSource)
    case unsupportedExportFormat(ReplacementExportFormat)
    case missingInputData
    case invalidInput(String)

    public var errorDescription: String? {
        switch self {
        case .unsupportedImportSource(let source):
            return "No importer is registered for \(source.rawValue)."
        case .unsupportedExportFormat(let format):
            return "No exporter is registered for \(format.rawValue)."
        case .missingInputData:
            return "The import request did not include a URL or data payload."
        case .invalidInput(let message):
            return message
        }
    }
}
