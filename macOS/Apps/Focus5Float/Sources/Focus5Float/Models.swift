import Foundation

// Wire models for GET /focus-5.json — frozen in macOS/Apps/Focus5Float/CONTRACT.md.
// Decode with JSONDecoder().keyDecodingStrategy = .convertFromSnakeCase (see
// SampleData / Focus5Client). Optionals reflect fields that are legitimately
// absent/null in real payloads (no PR, no upstream, non-GitHub/local-only repo,
// empty DB). Unknown wire keys (device_id, head_reflog_ts, index_mtime_ts) are
// intentionally not modeled — Codable ignores them.

struct Focus5Response: Codable {
    let roster: [RepoCard]
    let offRosterWarnings: [OffRosterWarning]
    let computedAt: String?          // ISO-8601; nil when roster empty
    let rankingMode: String?         // "recent_activity" | "dirty_first" | nil
    let summary: Summary

    struct Summary: Codable {
        let discovered: Int
        let rosterSize: Int
        let offRosterAttention: Int
    }
}

struct RepoCard: Codable, Identifiable {
    var id: String { localPath }     // stable per machine

    let position: Int
    let repoName: String
    let repoFullName: String?        // nil for non-GitHub / local-only
    let localPath: String            // LOCAL-ONLY
    let remoteUrl: String?           // SENSITIVE
    let vscodeUrl: String            // LOCAL-ONLY
    let rankReason: String
    let rankingMode: String
    let computedAt: String

    // Tree health (live re-probe folded over the cached signals)
    let branch: String?
    let upstream: String?
    let hasUpstream: Bool?
    let ahead: Int
    let behind: Int
    let modifiedCount: Int
    let untrackedCount: Int
    let isDirty: Bool
    let healthAvailable: Bool
    let healthProbedAt: String?

    // Activity timestamps (any may be nil)
    let lastCommitAt: String?
    let lastCommitTs: Int?
    let myLastCommitTs: Int?
    let probedAt: String?

    let newestPr: NewestPR?
    let recentActivity: [Commit]
}

struct NewestPR: Codable {
    let number: Int
    let title: String
    let state: String                // "open" | "closed" | "merged"
    let htmlUrl: String
    let isDraft: Bool
    let isMerged: Bool
}

struct Commit: Codable, Identifiable {
    var id: String { sha }
    let sha: String
    let subject: String
    let committedAt: String          // ISO-8601
    let authorEmail: String          // SENSITIVE (PII) — never re-export
}

struct OffRosterWarning: Codable, Identifiable {
    var id: String { localPath }
    let repoName: String
    let localPath: String            // LOCAL-ONLY
    let repoFullName: String?
    let branch: String?
    let ahead: Int
    let modifiedCount: Int
    let untrackedCount: Int
    let isDirty: Bool
    let probedAt: String?
}

struct Focus5GoalsResponse: Codable {
    let exists: Bool
    let items: [ObsidianReminder]
    let path: String?
    let totalOpen: Int
    let reason: String?
    let message: String?
}

struct Focus5GoalCompleteResponse: Codable {
    let ok: Bool
    let title: String
    let lineIndex: Int
    let exists: Bool
    let items: [ObsidianReminder]
    let path: String?
    let totalOpen: Int
    let reason: String?
    let message: String?
}

struct ObsidianReminder: Codable, Identifiable {
    var id: Int { lineIndex }
    let title: String
    let description: String
    let lineIndex: Int
}
