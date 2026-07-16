import Foundation

/// Per-column alignment declared by a GFM delimiter cell (`:--` / `--:` / `:-:` / `--`).
enum MarkdownTableAlignment: Equatable {
    case leading, center, trailing
}

/// A parsed GFM pipe table — header cells, one alignment per column, and data
/// rows (each padded/truncated to the header's column count by the parser).
struct MarkdownTable: Equatable {
    let header: [String]
    let alignments: [MarkdownTableAlignment]
    let rows: [[String]]
}

/// One block of parsed markdown source: a detected table, or an opaque source
/// line to fall through to the existing line-by-line renderer (MarkdownLine).
enum MarkdownBlock: Equatable {
    case table(MarkdownTable)
    case line(String)
}

/// Detects GFM-style pipe tables — a header row, a `---|:--|--:` delimiter row,
/// then data rows — inside markdown source and splits the text into blocks, so
/// the renderer can draw a real table instead of literal `|` characters. Any
/// line that isn't part of a recognized table passes through unchanged.
enum MarkdownTableParser {
    static func parse(_ content: String) -> [MarkdownBlock] {
        let lines = content.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
        var blocks: [MarkdownBlock] = []
        var i = 0
        while i < lines.count {
            let headerCells = cells(of: lines[i])
            if i + 1 < lines.count,
               isPipeRow(lines[i]),
               let alignments = delimiterAlignments(lines[i + 1]),
               alignments.count == headerCells.count {
                var rows: [[String]] = []
                var j = i + 2
                while j < lines.count, isPipeRow(lines[j]) {
                    rows.append(pad(cells(of: lines[j]), to: headerCells.count))
                    j += 1
                }
                blocks.append(.table(MarkdownTable(header: headerCells, alignments: alignments, rows: rows)))
                i = j
            } else {
                blocks.append(.line(lines[i]))
                i += 1
            }
        }
        return blocks
    }

    private static func isPipeRow(_ line: String) -> Bool {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        return !trimmed.isEmpty && trimmed.contains("|")
    }

    /// Splits a pipe row into trimmed cells, dropping the empty cell produced by
    /// a leading/trailing `|` (the common `| a | b |` style).
    private static func cells(of line: String) -> [String] {
        var trimmed = line.trimmingCharacters(in: .whitespaces)
        if trimmed.hasPrefix("|") { trimmed.removeFirst() }
        if trimmed.hasSuffix("|") { trimmed.removeLast() }
        return trimmed.split(separator: "|", omittingEmptySubsequences: false)
            .map { $0.trimmingCharacters(in: .whitespaces) }
    }

    private static func pad(_ row: [String], to count: Int) -> [String] {
        if row.count == count { return row }
        if row.count > count { return Array(row.prefix(count)) }
        return row + Array(repeating: "", count: count - row.count)
    }

    /// Nil unless every cell is a valid GFM delimiter cell (only `-`/`:`, at
    /// least one `-`) — otherwise the row is ordinary text, not a table.
    private static func delimiterAlignments(_ line: String) -> [MarkdownTableAlignment]? {
        guard isPipeRow(line) else { return nil }
        let parts = cells(of: line)
        guard !parts.isEmpty else { return nil }
        var alignments: [MarkdownTableAlignment] = []
        for part in parts {
            guard !part.isEmpty, part.allSatisfy({ $0 == "-" || $0 == ":" }), part.contains("-") else {
                return nil
            }
            switch (part.hasPrefix(":"), part.hasSuffix(":")) {
            case (true, true):  alignments.append(.center)
            case (false, true): alignments.append(.trailing)
            default:            alignments.append(.leading)
            }
        }
        return alignments
    }
}
