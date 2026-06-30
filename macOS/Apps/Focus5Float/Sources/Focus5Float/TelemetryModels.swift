import Foundation

enum HealthStatus: String, Codable {
    case green, orange, red
}

// Wire model for ~/Documents/telemetry/*.json rows.
// Required keys: health, title, description. updatedAt is optional ISO-8601.
// Unknown keys are ignored (Codable default behavior).
struct TelemetryEntry: Codable, Identifiable {
    let health: HealthStatus
    let title: String
    let description: String
    let updatedAt: String?

    var id: String { "\(health.rawValue)_\(title)" }
}
