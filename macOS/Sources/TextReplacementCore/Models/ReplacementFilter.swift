import Foundation

public enum ReplacementFilter: Hashable, Sendable {
    case all
    case duplicates
    case disabled
    case recentlyChanged
    case ungrouped
    case group(String)
}
