import Foundation

/// Reads/writes the canonical `keyboard-replacements.v1` JSON that the Python scripts produce and
/// consume (native_to_json.py, json_to_apple_sqlite.py, md_to_json.py, the web editor). Maps the
/// Python field names (`group`, string `id`, no timestamps) onto the Swift `Replacement` model.
public protocol CanonicalReplacementCoding: Sendable {
    func decode(_ data: Data) throws -> [Replacement]
    func encode(_ replacements: [Replacement]) throws -> Data
}

public struct CanonicalReplacementCodec: CanonicalReplacementCoding {
    public static let schema = "keyboard-replacements.v1"

    public init() {}

    private struct Payload: Codable {
        var schema: String?
        var source: String?
        var generated_at: String?
        var items: [Item]
    }

    private struct Item: Codable {
        var id: String?
        var shortcut: String
        var phrase: String
        var enabled: Bool?
        var group: String?
        var notes: String?
    }

    public func decode(_ data: Data) throws -> [Replacement] {
        let payload = try JSONDecoder().decode(Payload.self, from: data)
        return payload.items.map { item in
            Replacement(
                id: item.id.flatMap(UUID.init(uuidString:)) ?? UUID(),
                shortcut: item.shortcut,
                phrase: item.phrase,
                enabled: item.enabled ?? true,
                groupName: item.group,
                notes: item.notes
            )
        }
    }

    /// Writes every item (incl. disabled) with its `enabled` flag — the Python writer's preflight
    /// decides whether to drop disabled entries (via --include-disabled), so we keep them here.
    public func encode(_ replacements: [Replacement]) throws -> Data {
        let items = replacements.map { replacement in
            Item(
                id: replacement.id.uuidString,
                shortcut: replacement.shortcut,
                phrase: replacement.phrase,
                enabled: replacement.enabled,
                group: replacement.groupName,
                notes: replacement.notes
            )
        }
        let payload = Payload(
            schema: Self.schema,
            source: "TextReplacementStudio",
            generated_at: ISO8601DateFormatter().string(from: Date()),
            items: items
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted]
        return try encoder.encode(payload)
    }
}
