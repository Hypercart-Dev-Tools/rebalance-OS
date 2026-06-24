import Foundation

public protocol ApplePlistCoding: Sendable {
    func decode(_ data: Data) throws -> [AppleTextReplacementItem]
    func encode(_ items: [AppleTextReplacementItem]) throws -> Data
}

public struct ApplePlistCodec: ApplePlistCoding {
    public init() {}

    public func decode(_ data: Data) throws -> [AppleTextReplacementItem] {
        try PropertyListDecoder().decode([AppleTextReplacementItem].self, from: data)
    }

    public func encode(_ items: [AppleTextReplacementItem]) throws -> Data {
        let encoder = PropertyListEncoder()
        encoder.outputFormat = .xml
        return try encoder.encode(items)
    }
}
