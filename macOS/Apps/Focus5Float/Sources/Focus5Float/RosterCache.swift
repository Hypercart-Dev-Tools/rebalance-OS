import Foundation
import os

private let cacheLog = Logger(subsystem: "me.neochro.Focus5Float", category: "cache")

/// On-disk cache of the last successful `/focus-5.json` so a cold launch renders
/// real data instantly and the panel stays useful while `rebalance serve` is down.
///
/// LOCAL-ONLY: lives in the user's Application Support dir on this machine. The
/// roster carries local-only / PII fields (`local_path`, `vscode_url`,
/// `author_email` — see CONTRACT.md), so the cache never leaves the device.
///
/// Codec note: this is OUR persistence format (Swift → disk → Swift), distinct
/// from the snake_case server wire format. It round-trips the `Codable` models
/// with a plain camelCase + ISO-8601 codec — reusing the snake_case wire decoder
/// (`Focus5JSON.decoder()`) here would mismatch the re-encoded keys.
struct RosterCache {
    static let schemaVersion = 1

    struct Envelope: Codable {
        var schemaVersion: Int
        var fetchedAt: Date
        var response: Focus5Response
    }

    private let url: URL

    init(url: URL = RosterCache.defaultURL) { self.url = url }

    static var defaultURL: URL {
        let base = (try? FileManager.default.url(
            for: .applicationSupportDirectory, in: .userDomainMask,
            appropriateFor: nil, create: true))
            ?? FileManager.default.temporaryDirectory
        return base.appendingPathComponent("Focus5Float/roster-cache.json")
    }

    private static func encoder() -> JSONEncoder {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        return e
    }
    private static func decoder() -> JSONDecoder {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }

    /// Best-effort atomic write; never throws into the caller.
    func save(_ response: Focus5Response, fetchedAt: Date = Date()) {
        let env = Envelope(schemaVersion: Self.schemaVersion, fetchedAt: fetchedAt, response: response)
        do {
            try FileManager.default.createDirectory(
                at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Self.encoder().encode(env).write(to: url, options: .atomic)
            cacheLog.info("roster cache saved (\(response.roster.count) repos)")
        } catch {
            cacheLog.error("roster cache save failed: \(String(describing: error))")
        }
    }

    /// Cached roster + when it was fetched, or nil if missing / corrupt / from an
    /// older schema (ignored, never fatal).
    func load() -> (response: Focus5Response, fetchedAt: Date)? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        guard let env = try? Self.decoder().decode(Envelope.self, from: data),
              env.schemaVersion == Self.schemaVersion else {
            cacheLog.info("roster cache miss / unreadable / stale schema")
            return nil
        }
        return (env.response, env.fetchedAt)
    }
}
