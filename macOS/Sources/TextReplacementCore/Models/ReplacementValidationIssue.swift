import Foundation

public struct ReplacementValidationIssue: Identifiable, Codable, Hashable, Sendable {
    public enum Severity: String, Codable, Hashable, Sendable {
        case warning
        case error
    }

    public var id: UUID
    public var replacementID: Replacement.ID?
    public var severity: Severity
    public var code: String
    public var message: String

    public init(
        id: UUID = UUID(),
        replacementID: Replacement.ID? = nil,
        severity: Severity,
        code: String,
        message: String
    ) {
        self.id = id
        self.replacementID = replacementID
        self.severity = severity
        self.code = code
        self.message = message
    }
}
