import Foundation

/// Shared, bounded file-read policy for the panel's two file-backed viewers —
/// the telemetry `.md` render and the CLIO prompt-log feed. Both read a
/// user-selected file synchronously on the main actor and re-read it on the poll
/// timer, so both must cap what they pull into memory: a multi-MB file (a CLIO
/// prompt log accumulates forever and never rotates) would otherwise freeze the
/// panel and balloon its footprint on every poll.
///
/// The read *mechanism* is identical; only what each viewer does with the text
/// differs (structured entries vs. raw Markdown). So we share the read, not the
/// viewer — merging the two parsers would force unlike things together.
enum FileLoad {
    /// Max bytes read from a Markdown-backed viewer file before truncating.
    static let markdownByteCeiling = 1_000_000

    /// Max rows a feed holds in memory / renders (newest-first after ordering).
    static let feedRowCap = 10_000

    /// Reads `url` as UTF-8 text, capped at `byteCeiling` bytes.
    ///
    /// - Returns `nil` only when the file itself can't be read (missing /
    ///   permission), or a full — un-truncated — read isn't valid UTF-8. The
    ///   caller surfaces that as a load error, matching prior per-viewer behavior.
    /// - `truncated` is `true` when the file exceeded the ceiling; the returned
    ///   text is its leading `byteCeiling` bytes. A multi-byte character split at
    ///   the boundary decodes to U+FFFD (via `String(decoding:as:)`) rather than
    ///   failing the whole read.
    static func boundedText(_ url: URL, byteCeiling: Int = markdownByteCeiling)
        -> (text: String, truncated: Bool)? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        if data.count > byteCeiling {
            return (String(decoding: data.prefix(byteCeiling), as: UTF8.self), true)
        }
        guard let text = String(data: data, encoding: .utf8) else { return nil }
        return (text, false)
    }
}
