import Foundation

public enum ReplacementChange: Hashable, Sendable {
    case add(Replacement)
    case update(old: Replacement, new: Replacement)
    case skip(existing: Replacement)
    case conflict(local: Replacement, incoming: Replacement)
}

public struct ReplacementDiff: Hashable, Sendable {
    public var changes: [ReplacementChange]

    public init(changes: [ReplacementChange]) {
        self.changes = changes
    }

    public var hasConflicts: Bool {
        changes.contains { change in
            if case .conflict = change {
                return true
            }
            return false
        }
    }
}
