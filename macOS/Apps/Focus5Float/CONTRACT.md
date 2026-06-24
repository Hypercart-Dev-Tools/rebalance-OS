# Focus 5 Float — Data Contract (frozen in Phase 0)

The macOS app is a **read-only projection** of the Focus 5 roster. This file is the
single source of truth for the wire shape it decodes.

- **Endpoint:** `GET http://localhost:8787/focus-5.json`
- **Query:** `?view=dirty` → re-rank to the "Dirty Five" board (read-only, in-memory).
  Omit (or `?view=focus5`) → the persisted `recent_activity` headline board.
- **Method:** GET only. The route is **strictly read-only** — it never runs the device
  git scan (`sync_focus5`) and never rewrites `focus5_roster` (verified by
  `tests/test_focus5_scan.py::WebRouteTests::test_focus5_json_is_read_only_no_scan_no_write`).
- **Scope:** **LOCAL-ONLY.** Binds to localhost; the payload carries operator-local /
  PII fields (see classification). Not safe for a remote/cloud mirror without a
  separate sanitized projection.
- **Source:** `summarize_focus5(db, mode=...)` in
  `src/rebalance/ingest/focus5_scan.py` — the same function the HTML `/focus-5` page uses.
- **Implementation:** `focus5_json()` in `src/rebalance/web.py`.

## Top-level shape

```jsonc
{
  "roster": [ /* ≤ 5 RepoCard, ordered by position */ ],
  "off_roster_warnings": [ /* OffRosterWarning, dirty/unpushed repos outside top-5 */ ],
  "computed_at": "2026-06-23T01:30:00+00:00",   // null when roster empty
  "ranking_mode": "recent_activity",             // or "dirty_first"; null when empty
  "summary": { "discovered": 21, "roster_size": 5, "off_roster_attention": 1 }
}
```

Brand-new machine (no DB) returns this exact shape with `roster: []`, `summary` zeros,
nulls — HTTP 200, never a 404/500. The app decodes one shape always.

## RepoCard fields (real, from live DB)

`ahead, behind, branch, computed_at, device_id, has_upstream, head_reflog_ts,
health_available, health_probed_at, index_mtime_ts, is_dirty, last_commit_at,
last_commit_ts, local_path, modified_count, my_last_commit_ts, newest_pr, position,
probed_at, rank_reason, ranking_mode, recent_activity, remote_url, repo_full_name,
repo_name, untracked_count, upstream, vscode_url`

- `newest_pr`: object or **null** — `{number, title, state, html_url, is_draft, is_merged}`
- `recent_activity`: array (possibly empty) of `{sha, subject, committed_at, author_email}`

## Field classification — local-only/sensitive vs portable

Drives the **render set** (what the desktop app shows) and, critically, the **allowlist**
a future remote mirror must apply. The desktop app may consume all fields (localhost);
a remote projection (`summarize_focus5_public()`, deferred) must **strip the local-only set**.

| Field | Class | Why |
|---|---|---|
| `local_path` | **LOCAL-ONLY** | Absolute filesystem path of the operator's machine. |
| `vscode_url` | **LOCAL-ONLY** | Embeds the absolute path. |
| `device_id` | **LOCAL-ONLY** | Machine identity. |
| `remote_url` | **SENSITIVE** | May be SSH-with-user or reveal private repo URLs. |
| `recent_activity[].author_email` | **SENSITIVE (PII)** | Email address. Strip for any export. |
| `probed_at`, `head_reflog_ts`, `index_mtime_ts`, `health_probed_at` | local-diagnostic | Machine-local timings; low value remotely, not secret. |
| `position`, `rank_reason`, `ranking_mode`, `computed_at` | portable | Ranking metadata. |
| `repo_name`, `repo_full_name` | portable* | `repo_full_name` reveals private repo naming — allowlist deliberately. |
| `branch`, `upstream`, `has_upstream`, `ahead`, `behind`, `modified_count`, `untracked_count`, `is_dirty` | portable | Tree-health signals. |
| `last_commit_at`, `last_commit_ts`, `my_last_commit_ts` | portable | Activity timestamps. |
| `health_available` | portable | Render flag. |
| `newest_pr.*` | portable | `html_url` is a public GitHub URL; title may leak — allowlist per repo visibility. |
| `recent_activity[].{sha,subject,committed_at}` | portable | Commit metadata (email excluded). |

## Rebuild path — DECISION: deferred (no POST in v1 spike)

`?view=dirty` is read-only re-ranking and stays a GET param. A fresh device walk
(`sync_focus5()`, ~30s, rewrites the roster tables) is a **mutation** and is **not**
reachable from `/focus-5.json`. v1 of the app **re-pulls** the current roster on refresh;
it does **not** force a rebuild. If a forced rebuild proves necessary, add a separate
explicit **`POST /focus-5/sync`** in Phase 4 — never folded into the GET. (Plan Open
Question 1.)

## Swift `Codable` contract

Decode with `JSONDecoder().keyDecodingStrategy = .convertFromSnakeCase` and ISO-8601
date parsing on the string timestamps. Optionals reflect fields that are legitimately
absent/null in real payloads (no PR, no upstream, non-GitHub/local-only repo, empty DB).

```swift
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
```

> Note: `device_id`, `head_reflog_ts`, `index_mtime_ts` exist on the wire but are
> intentionally omitted from the Swift model — the app doesn't render them. `Codable`
> ignores unknown keys, so this is safe.
