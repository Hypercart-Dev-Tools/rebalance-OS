import Foundation
import GRDB

public final class GRDBReplacementStore: ReplacementStore, @unchecked Sendable {
    public let databaseURL: URL

    public init(databaseURL: URL) {
        self.databaseURL = databaseURL
    }

    public func fetchAll() async throws -> [Replacement] {
        throw ReplacementStoreError.notImplemented("GRDBReplacementStore.fetchAll")
    }

    public func fetch(id: Replacement.ID) async throws -> Replacement? {
        throw ReplacementStoreError.notImplemented("GRDBReplacementStore.fetch(id:)")
    }

    public func fetch(shortcut: String) async throws -> Replacement? {
        throw ReplacementStoreError.notImplemented("GRDBReplacementStore.fetch(shortcut:)")
    }

    public func save(_ replacement: Replacement) async throws {
        throw ReplacementStoreError.notImplemented("GRDBReplacementStore.save(_:)")
    }

    public func save(_ replacements: [Replacement]) async throws {
        throw ReplacementStoreError.notImplemented("GRDBReplacementStore.save(_:)")
    }

    public func delete(id: Replacement.ID) async throws {
        throw ReplacementStoreError.notImplemented("GRDBReplacementStore.delete(id:)")
    }

    public func deleteAll() async throws {
        throw ReplacementStoreError.notImplemented("GRDBReplacementStore.deleteAll")
    }
}

public enum ReplacementStoreError: Error, LocalizedError, Sendable {
    case notImplemented(String)

    public var errorDescription: String? {
        switch self {
        case .notImplemented(let method):
            return "\(method) is not implemented yet."
        }
    }
}
