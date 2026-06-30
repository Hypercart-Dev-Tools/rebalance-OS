import Foundation

public struct ReplacementSnapshot: Identifiable, Codable, Hashable, Sendable {
    public var id: UUID
    public var label: String
    public var createdAt: Date
    public var replacements: [Replacement]

    public init(
        id: UUID = UUID(),
        label: String,
        createdAt: Date = Date(),
        replacements: [Replacement]
    ) {
        self.id = id
        self.label = label
        self.createdAt = createdAt
        self.replacements = replacements
    }
}

public protocol SnapshotStore: Sendable {
    func createSnapshot(label: String, replacements: [Replacement]) async throws -> ReplacementSnapshot
    func fetchSnapshots() async throws -> [ReplacementSnapshot]
    func fetchSnapshot(id: ReplacementSnapshot.ID) async throws -> ReplacementSnapshot?
    func deleteSnapshot(id: ReplacementSnapshot.ID) async throws
}
