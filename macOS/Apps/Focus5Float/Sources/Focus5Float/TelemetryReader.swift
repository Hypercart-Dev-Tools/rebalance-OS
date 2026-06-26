import Foundation
import os

private let log = Logger(subsystem: "me.neochro.Focus5Float", category: "telemetry")

enum TelemetryReader {
    /// Read all *.json files from ~/Documents/telemetry/, decode each as
    /// [TelemetryEntry], merge, and sort newest-first by updatedAt.
    /// Missing folder returns []. Malformed files are skipped with a warning.
    static func load() -> [TelemetryEntry] {
        guard let folder = FileManager.default
            .urls(for: .documentDirectory, in: .userDomainMask).first?
            .appendingPathComponent("telemetry"),
              FileManager.default.fileExists(atPath: folder.path) else {
            return []
        }

        guard let files = try? FileManager.default.contentsOfDirectory(
            at: folder, includingPropertiesForKeys: nil
        ) else { return [] }

        let decoder = JSONDecoder()
        var all: [TelemetryEntry] = []

        for file in files where file.pathExtension == "json" {
            guard let data = try? Data(contentsOf: file) else {
                log.warning("telemetry: could not read \(file.lastPathComponent)")
                continue
            }
            guard let entries = try? decoder.decode([TelemetryEntry].self, from: data) else {
                log.warning("telemetry: malformed JSON in \(file.lastPathComponent), skipping")
                continue
            }
            all.append(contentsOf: entries)
        }

        // Newest-first by updatedAt; undated rows fall below dated rows.
        return all.sorted { a, b in
            switch (a.updatedAt, b.updatedAt) {
            case (let la?, let lb?): return la > lb
            case (nil, _):           return false
            case (_, nil):           return true
            }
        }
    }
}
