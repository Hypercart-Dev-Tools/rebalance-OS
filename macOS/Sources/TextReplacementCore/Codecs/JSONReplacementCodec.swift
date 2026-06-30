import Foundation
import SwiftyJSON

public protocol JSONReplacementCoding: Sendable {
    func decode(_ data: Data) throws -> [Replacement]
    func encode(_ replacements: [Replacement]) throws -> Data
}

public struct JSONReplacementCodec: JSONReplacementCoding {
    public init() {}

    public func decode(_ data: Data) throws -> [Replacement] {
        _ = try JSON(data: data)
        return try JSONDecoder().decode([Replacement].self, from: data)
    }

    public func encode(_ replacements: [Replacement]) throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try encoder.encode(replacements)
    }
}
