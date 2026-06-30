import Foundation

// Relative-time + staleness helpers (the Swift analogue of the web `_ago`).
// Parses the ISO-8601 strings the contract carries (computed_at, committed_at).
enum RelTime {
    /// "just now" / "5m ago" / "3h ago" / "2d ago"; "" for nil.
    static func ago(_ date: Date?, now: Date = Date()) -> String {
        guard let date else { return "" }
        let s = max(0, now.timeIntervalSince(date))
        switch s {
        case ..<60:    return "just now"
        case ..<3600:  return "\(Int(s / 60))m ago"
        case ..<86400: return "\(Int(s / 3600))h ago"
        default:       return "\(Int(s / 86400))d ago"
        }
    }

    /// Same, from an ISO-8601 string; "" for nil/unparseable.
    static func ago(_ iso: String?, now: Date = Date()) -> String {
        guard let iso, let date = parse(iso) else { return "" }
        return ago(date, now: now)
    }

    static func isOlderThan(_ iso: String?, hours: Double, now: Date = Date()) -> Bool {
        guard let iso, let date = parse(iso) else { return false }
        return now.timeIntervalSince(date) > hours * 3600
    }

    static func parse(_ iso: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: iso) { return d }
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: iso)
    }
}
