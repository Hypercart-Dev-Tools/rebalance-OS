import Foundation

// Parses the CLIO exporter's Markdown format (utils/CLIO/INSTALL.md in
// rebalance-OS). Each entry below the `<!-- CLIO:ENTRIES -->` marker looks
// like:
//
//   ## REPO
//   2026-07-09T18:42:11Z
//   Noels-MacBook-Pro · main
//
//   > "prompt text
//   > continued on further lines"
//
// Entries are already newest-first in the file (each sync run prepends new
// ones directly below the marker), so the reader never re-sorts.
enum PromptLogReader {
    private static let marker = "<!-- CLIO:ENTRIES -->"

    static func parse(_ text: String) -> [PromptLogEntry] {
        let body: Substring
        if let markerRange = text.range(of: marker) {
            body = text[markerRange.upperBound...]
        } else {
            body = text[...]
        }

        let lines = body.components(separatedBy: "\n").filter {
            !$0.trimmingCharacters(in: .whitespaces).hasPrefix("<!--")
        }
        var entries: [PromptLogEntry] = []
        var i = 0

        while i < lines.count {
            guard lines[i].hasPrefix("## ") else { i += 1; continue }
            let repo = String(lines[i].dropFirst(3)).trimmingCharacters(in: .whitespaces)
            var j = i + 1

            guard j < lines.count else { break }
            let timestamp = lines[j].trimmingCharacters(in: .whitespaces)
            j += 1

            var machine = ""
            var branch: String?
            if j < lines.count {
                let machineLine = lines[j].trimmingCharacters(in: .whitespaces)
                if let sep = machineLine.range(of: " · ") {
                    machine = String(machineLine[..<sep.lowerBound])
                    let b = String(machineLine[sep.upperBound...])
                    branch = b.isEmpty ? nil : b
                } else {
                    machine = machineLine
                }
                j += 1
            }

            // Everything else up to the next "## " block is the prompt.
            var promptLines: [String] = []
            while j < lines.count, !lines[j].hasPrefix("## ") {
                promptLines.append(lines[j])
                j += 1
            }
            while let first = promptLines.first, first.trimmingCharacters(in: .whitespaces).isEmpty {
                promptLines.removeFirst()
            }
            while let last = promptLines.last, last.trimmingCharacters(in: .whitespaces).isEmpty {
                promptLines.removeLast()
            }
            var prompt = promptLines
                .map { $0.hasPrefix("> ") ? String($0.dropFirst(2)) : $0 }
                .joined(separator: "\n")
            if prompt.hasPrefix("\"") { prompt.removeFirst() }
            if prompt.hasSuffix("\"") { prompt.removeLast() }

            if !timestamp.isEmpty, !isMachineNoise(prompt) {
                entries.append(PromptLogEntry(repo: repo, timestamp: timestamp, machine: machine, branch: branch, prompt: prompt))
            }
            i = j
        }

        return entries
    }

    /// Harness/agent-injected noise — `<task-notification>` dumps, relay's
    /// bracketed "[cross-agent dependency drift — informational, ...]" notes,
    /// `<ide_opened_file>`, `<system-reminder>`, etc. — never something typed
    /// by hand. CLIO's own hook-side `PROMPT_LOG_EXCLUDE` only catches a
    /// couple of relay-specific phrases; this catches the whole class by
    /// shape (starts with `<` or `[`) rather than chasing every new wrapper.
    private static func isMachineNoise(_ prompt: String) -> Bool {
        let trimmed = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.hasPrefix("<") || trimmed.hasPrefix("[")
    }

    /// Reads and parses the file at `url`, bounded so a large log can never
    /// freeze the panel or grow memory without limit. Returns nil (does not
    /// throw) on a missing/unreadable file — the caller surfaces that as a load
    /// error. The read is capped at `byteCeiling` bytes and the result at
    /// `rowCap` entries; since CLIO writes newest-first directly below the marker
    /// (near the top of the file), both caps keep the *newest* prompts and drop
    /// the oldest tail. Both bounds are injectable for testing.
    static func load(from url: URL,
                     byteCeiling: Int = FileLoad.markdownByteCeiling,
                     rowCap: Int = FileLoad.feedRowCap) -> [PromptLogEntry]? {
        guard let (text, _) = FileLoad.boundedText(url, byteCeiling: byteCeiling) else {
            return nil
        }
        return Array(parse(text).prefix(rowCap))
    }
}
