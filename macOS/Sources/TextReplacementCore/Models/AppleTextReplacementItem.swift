import Foundation

public struct AppleTextReplacementItem: Codable, Hashable, Sendable {
    public let phrase: String
    public let shortcut: String

    public init(phrase: String, shortcut: String) {
        self.phrase = phrase
        self.shortcut = shortcut
    }
}

public extension Replacement {
    var appleTextReplacementItem: AppleTextReplacementItem {
        AppleTextReplacementItem(phrase: phrase, shortcut: shortcut)
    }

    init(appleTextReplacementItem item: AppleTextReplacementItem) {
        self.init(shortcut: item.shortcut, phrase: item.phrase)
    }
}
