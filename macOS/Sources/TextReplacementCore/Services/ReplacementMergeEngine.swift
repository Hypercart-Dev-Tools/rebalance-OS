import Foundation

public protocol ReplacementMergeEngine: Sendable {
    func diff(local: [Replacement], incoming: [Replacement]) -> ReplacementDiff
    func merge(local: [Replacement], incoming: [Replacement], policy: ReplacementMergePolicy) -> [ReplacementChange]
}

public struct DefaultReplacementMergeEngine: ReplacementMergeEngine {
    public init() {}

    public func diff(local: [Replacement], incoming: [Replacement]) -> ReplacementDiff {
        ReplacementDiff(changes: merge(local: local, incoming: incoming, policy: .previewConflicts))
    }

    public func merge(
        local: [Replacement],
        incoming: [Replacement],
        policy: ReplacementMergePolicy
    ) -> [ReplacementChange] {
        let localByShortcut = Dictionary(grouping: local, by: \.shortcut).compactMapValues(\.first)

        return incoming.map { incomingReplacement in
            guard let localReplacement = localByShortcut[incomingReplacement.shortcut] else {
                return .add(incomingReplacement)
            }

            if localReplacement.phrase == incomingReplacement.phrase {
                return .skip(existing: localReplacement)
            }

            switch policy {
            case .previewConflicts:
                return .conflict(local: localReplacement, incoming: incomingReplacement)
            case .keepLocal:
                return .skip(existing: localReplacement)
            case .replaceLocal:
                var updated = incomingReplacement
                updated.id = localReplacement.id
                updated.createdAt = localReplacement.createdAt
                updated.updatedAt = Date()
                return .update(old: localReplacement, new: updated)
            case .addOnly:
                return .skip(existing: localReplacement)
            }
        }
    }
}
