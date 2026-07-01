import Foundation
import Clibgit2

/// The typed "minimum facts" Focus 5 needs from a repo — the fact set the
/// Phase 0-R QA gate "Structured facts, not raw text" requires, extracted
/// IN-PROCESS via libgit2 (no `Process`, no raw `git status` text dump).
public struct RepoFacts: Codable, CustomStringConvertible {
    public var branch: String?
    public var detachedHead: Bool
    public var ahead: Int
    public var behind: Int
    public var modified: Int      // tracked, changed
    public var untracked: Int     // new, not tracked
    public var dirty: Bool
    public var lastCommitUnix: Int64?  // last local commit timestamp (epoch seconds)

    public var description: String {
        let ts = lastCommitUnix.map { String($0) } ?? "nil"
        return "branch=\(branch ?? "-") detached=\(detachedHead) ahead=\(ahead) behind=\(behind) modified=\(modified) untracked=\(untracked) dirty=\(dirty) lastCommitUnix=\(ts)"
    }
}

public enum GitProbeError: Error, CustomStringConvertible {
    case open(Int32)
    case libgit2(String)
    public var description: String {
        switch self {
        case .open(let c): return "git_repository_open failed (code \(c))"
        case .libgit2(let m): return "libgit2 error: \(m)"
        }
    }
}

/// In-process libgit2 probe. Proves the embedded path returns the full fact set
/// for a real repo without shelling out.
public enum GitProbe {

    public static func libgit2Version() -> String {
        git_libgit2_init()
        var major: Int32 = 0, minor: Int32 = 0, rev: Int32 = 0
        _ = git_libgit2_version(&major, &minor, &rev)
        return "\(major).\(minor).\(rev)"
    }

    public static func probe(path: String) throws -> RepoFacts {
        git_libgit2_init()
        defer { git_libgit2_shutdown() }

        var repo: OpaquePointer? = nil
        let rc = git_repository_open(&repo, path)
        guard rc == 0, let repo = repo else { throw GitProbeError.open(rc) }
        defer { git_repository_free(repo) }

        var facts = RepoFacts(branch: nil, detachedHead: false, ahead: 0, behind: 0,
                              modified: 0, untracked: 0, dirty: false, lastCommitUnix: nil)

        // branch / detached
        facts.detachedHead = (git_repository_head_detached(repo) == 1)
        var headRef: OpaquePointer? = nil
        if git_repository_head(&headRef, repo) == 0, let headRef = headRef {
            if let shp = git_reference_shorthand(headRef) {
                facts.branch = String(cString: shp)
            }
            git_reference_free(headRef)
        }

        // last-commit timestamp: HEAD -> oid -> commit -> time
        var headOid = git_oid()
        if git_reference_name_to_id(&headOid, repo, "HEAD") == 0 {
            var commit: OpaquePointer? = nil
            if git_commit_lookup(&commit, repo, &headOid) == 0, let commit = commit {
                facts.lastCommitUnix = Int64(git_commit_time(commit))
                git_commit_free(commit)
            }

            // ahead/behind vs upstream (branch@{upstream}); best-effort
            if let branch = facts.branch {
                var upOid = git_oid()
                let upRef = "refs/remotes/origin/\(branch)"
                if git_reference_name_to_id(&upOid, repo, upRef) == 0 {
                    var ahead = 0, behind = 0
                    if git_graph_ahead_behind(&ahead, &behind, repo, &headOid, &upOid) == 0 {
                        facts.ahead = ahead
                        facts.behind = behind
                    }
                }
            }
        }

        // status: modified vs untracked
        var opts = git_status_options()
        opts.version = UInt32(GIT_STATUS_OPTIONS_VERSION)
        opts.flags = GIT_STATUS_OPT_INCLUDE_UNTRACKED
        var list: OpaquePointer? = nil
        if git_status_list_new(&list, repo, &opts) == 0, let list = list {
            let n = git_status_list_entrycount(list)
            var modified = 0, untracked = 0
            var i = 0
            while i < n {
                if let e = git_status_byindex(list, i) {
                    let s = e.pointee.status
                    if (s & (GIT_STATUS_WT_NEW | GIT_STATUS_INDEX_NEW)) != 0 {
                        untracked += 1
                    } else if s != 0 {
                        modified += 1
                    }
                }
                i += 1
            }
            facts.modified = modified
            facts.untracked = untracked
            facts.dirty = (modified + untracked) > 0
            git_status_list_free(list)
        }

        return facts
    }
}
