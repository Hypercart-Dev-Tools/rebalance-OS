import Foundation
import GRDB

// Resolves the rebalance SQLite path mirroring Python's paths.py chain:
//   1. REBALANCE_DB environment variable
//   2. Canonical app-data path
//      (~/Library/Application Support/rebalance-os/rebalance.db on macOS) —
//      NOT TCC-protected, so the dashboard reads it without an Allow-prompt.
//   3. ~/.config/rebalance-os/config.json → database_path (legacy override)
// The Python resolver also walks up from cwd for a project marker, but a
// Mac GUI app launched from Finder has no meaningful cwd, so that layer is
// intentionally skipped here.
enum RebalanceDatabaseResolveError: Error, LocalizedError
{
    case notFound(triedPaths: [String])

    var errorDescription: String?
    {
        switch self
        {
        case .notFound(let paths):
            return "Could not resolve rebalance.db. Tried:\n" + paths.map { "  - \($0)" }.joined(separator: "\n")
        }
    }
}

struct RebalanceDatabaseResolver
{
    static func canonicalPath() -> URL
    {
        let home = FileManager.default.homeDirectoryForCurrentUser
        return home
            .appendingPathComponent("Library")
            .appendingPathComponent("Application Support")
            .appendingPathComponent("rebalance-os")
            .appendingPathComponent("rebalance.db")
    }

    static func resolve() throws -> URL
    {
        var tried: [String] = []

        if let envPath = ProcessInfo.processInfo.environment["REBALANCE_DB"], !envPath.isEmpty
        {
            let url = URL(fileURLWithPath: (envPath as NSString).expandingTildeInPath)
            tried.append("\(url.path) (REBALANCE_DB env)")
            if FileManager.default.fileExists(atPath: url.path) { return url }
        }

        let canonical = canonicalPath()
        tried.append("\(canonical.path) (canonical app-data path)")
        if FileManager.default.fileExists(atPath: canonical.path) { return canonical }

        let configPath = ("~/.config/rebalance-os/config.json" as NSString).expandingTildeInPath
        if let data = try? Data(contentsOf: URL(fileURLWithPath: configPath)),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let dbPath = json["database_path"] as? String,
           !dbPath.isEmpty
        {
            let url = URL(fileURLWithPath: (dbPath as NSString).expandingTildeInPath)
            tried.append("\(url.path) (user config)")
            if FileManager.default.fileExists(atPath: url.path) { return url }
        }
        else
        {
            tried.append("\(configPath) (user config — missing or unreadable)")
        }

        throw RebalanceDatabaseResolveError.notFound(triedPaths: tried)
    }
}

struct GitHubBalanceRow: FetchableRecord, Decodable, Identifiable, Hashable
{
    var repoFullName: String
    var commits: Int
    var pushes: Int
    var prsOpened: Int
    var prsMerged: Int
    var issuesOpened: Int
    var issueComments: Int
    var reviews: Int
    var lastActiveAt: String?

    var id: String { repoFullName }

    enum CodingKeys: String, CodingKey
    {
        case repoFullName = "repo_full_name"
        case commits
        case pushes
        case prsOpened = "prs_opened"
        case prsMerged = "prs_merged"
        case issuesOpened = "issues_opened"
        case issueComments = "issue_comments"
        case reviews
        case lastActiveAt = "last_active_at"
    }

    var totalEvents: Int { commits + prsOpened + prsMerged + issuesOpened + issueComments + reviews }
}

actor RebalanceDatabase
{
    static let shared = RebalanceDatabase()

    private var queue: DatabaseQueue?
    private var dbURL: URL?

    func gitHubBalance(sinceDays: Int = 14) async throws -> [GitHubBalanceRow]
    {
        _diag("gitHubBalance: about to open()")
        let queue = try open()
        _diag("gitHubBalance: open() returned, building since-date")

        let sinceDate: String = {
            let now = Date()
            let cutoff = Calendar.current.date(byAdding: .day, value: -sinceDays, to: now) ?? now
            let fmt = ISO8601DateFormatter()
            fmt.formatOptions = [.withFullDate]
            return fmt.string(from: cutoff)
        }()

        _diag("gitHubBalance: awaiting queue.read")
        let rows = try await queue.read { db in
            try GitHubBalanceRow.fetchAll(db, sql: """
                SELECT repo_full_name,
                       COALESCE(SUM(commits), 0)        AS commits,
                       COALESCE(SUM(pushes), 0)         AS pushes,
                       COALESCE(SUM(prs_opened), 0)     AS prs_opened,
                       COALESCE(SUM(prs_merged), 0)     AS prs_merged,
                       COALESCE(SUM(issues_opened), 0)  AS issues_opened,
                       COALESCE(SUM(issue_comments), 0) AS issue_comments,
                       COALESCE(SUM(reviews), 0)        AS reviews,
                       MAX(last_active_at)              AS last_active_at
                FROM github_activity
                WHERE scan_date >= ?
                GROUP BY repo_full_name
                ORDER BY commits DESC
                """, arguments: [sinceDate])
        }
        _diag("gitHubBalance: queue.read returned \(rows.count) rows")
        return rows
    }

    func resolvedDBPath() -> URL? { dbURL }

    private func open() throws -> DatabaseQueue
    {
        if let queue { return queue }

        _diag("open: resolving DB path")
        let url = try RebalanceDatabaseResolver.resolve()
        _diag("open: resolved to \(url.path)")
        var config = Configuration()
        config.readonly = true
        _diag("open: constructing DatabaseQueue")
        let queue = try DatabaseQueue(path: url.path, configuration: config)
        _diag("open: DatabaseQueue ready")

        self.queue = queue
        self.dbURL = url
        return queue
    }
}

private func _diag(_ line: String)
{
    let path = "/tmp/rebalance-dashboard.diag.log"
    let data = ("[db] " + line + "\n").data(using: .utf8) ?? Data()
    if FileManager.default.fileExists(atPath: path),
       let handle = try? FileHandle(forWritingTo: URL(fileURLWithPath: path))
    {
        defer { try? handle.close() }
        _ = try? handle.seekToEnd()
        try? handle.write(contentsOf: data)
    }
    else
    {
        try? data.write(to: URL(fileURLWithPath: path))
    }
}
