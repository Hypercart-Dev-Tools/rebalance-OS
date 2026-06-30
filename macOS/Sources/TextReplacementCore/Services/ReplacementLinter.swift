import Foundation

public protocol ReplacementLinter: Sendable {
    func validate(_ replacement: Replacement) -> [ReplacementValidationIssue]
    func validate(_ replacements: [Replacement]) -> [ReplacementValidationIssue]
}

public struct DefaultReplacementLinter: ReplacementLinter {
    public init() {}

    public func validate(_ replacement: Replacement) -> [ReplacementValidationIssue] {
        var issues: [ReplacementValidationIssue] = []

        if replacement.shortcut.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            issues.append(.init(
                replacementID: replacement.id,
                severity: .error,
                code: "shortcut.empty",
                message: "Shortcut cannot be empty."
            ))
        }

        if replacement.phrase.isEmpty {
            issues.append(.init(
                replacementID: replacement.id,
                severity: .error,
                code: "phrase.empty",
                message: "Phrase cannot be empty."
            ))
        }

        if replacement.shortcut != replacement.normalizedShortcut {
            issues.append(.init(
                replacementID: replacement.id,
                severity: .warning,
                code: "shortcut.whitespace",
                message: "Shortcut has leading or trailing whitespace."
            ))
        }

        if replacement.shortcut.contains(where: { $0.isWhitespace }) {
            issues.append(.init(
                replacementID: replacement.id,
                severity: .warning,
                code: "shortcut.contains-whitespace",
                message: "Shortcut contains whitespace."
            ))
        }

        return issues
    }

    public func validate(_ replacements: [Replacement]) -> [ReplacementValidationIssue] {
        var issues = replacements.flatMap(validate(_:))

        let grouped = Dictionary(grouping: replacements, by: \.shortcut)
        for (shortcut, duplicates) in grouped where duplicates.count > 1 {
            for duplicate in duplicates {
                issues.append(.init(
                    replacementID: duplicate.id,
                    severity: .error,
                    code: "shortcut.duplicate",
                    message: "Shortcut '\(shortcut)' appears \(duplicates.count) times."
                ))
            }
        }

        return issues
    }
}
