import Foundation

public protocol ReplacementStore: Sendable {
    func fetchAll() async throws -> [Replacement]
    func fetch(id: Replacement.ID) async throws -> Replacement?
    func fetch(shortcut: String) async throws -> Replacement?
    func save(_ replacement: Replacement) async throws
    func save(_ replacements: [Replacement]) async throws
    func delete(id: Replacement.ID) async throws
    func deleteAll() async throws
}
