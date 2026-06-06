-- Focus 5 dashboard: device-local repo activity + the persisted top-5 roster.
-- Populated by the "focus5" collector (rebalance.ingest.focus5_scan).
--
-- Two tables, deliberately split (see PROJECT/2-WORKING/FOCUS-5.md):
--
--   focus5_repo_signals — RAW, mode-agnostic signals for EVERY discovered repo.
--     This is the load-bearing decision from the Phase 0 spike: we persist the
--     raw signals a repo exposes, NOT a pre-computed rank/score. That lets the
--     roster be re-ranked under a different ranking mode WITHOUT re-probing git,
--     and it doubles as the cache that feeds off-roster "hidden attention"
--     warnings (so the page never live-sweeps every repo on each request).
--     NOTE: index_mtime_ts is captured for diagnostics ONLY. The spike proved
--     `.git/index` mtime is polluted by clone/fetch/checkout and must never be a
--     ranking input on its own.
--
--   focus5_roster — the stable top-5 snapshot: which repos, in what order, why,
--     under which ranking mode, computed when. `computed_at` drives the 24h TTL.
--     Re-ranking rewrites this table only; the signals cache is untouched.

CREATE TABLE IF NOT EXISTS focus5_repo_signals (
    device_id         TEXT    NOT NULL,
    local_path        TEXT    NOT NULL,
    repo_name         TEXT    NOT NULL,   -- basename; may collide across roots
    repo_full_name    TEXT,               -- owner/repo bridge to the GitHub corpus
    branch            TEXT,
    upstream          TEXT,
    has_upstream      INTEGER NOT NULL DEFAULT 0,
    ahead             INTEGER NOT NULL DEFAULT 0,
    behind            INTEGER NOT NULL DEFAULT 0,
    modified_count    INTEGER NOT NULL DEFAULT 0,
    untracked_count   INTEGER NOT NULL DEFAULT 0,
    is_dirty          INTEGER NOT NULL DEFAULT 0,
    last_commit_at    TEXT,               -- ISO-8601 of the newest commit (any author)
    last_commit_ts    INTEGER,            -- epoch of the newest commit (any author)
    my_last_commit_ts INTEGER,            -- epoch of newest commit by THIS repo's user.email
    head_reflog_ts    INTEGER,            -- mtime of .git/logs/HEAD (local HEAD moves)
    index_mtime_ts    INTEGER,            -- diagnostics ONLY — never a ranking input
    remote_url        TEXT,
    probed_at         TEXT    NOT NULL,   -- when these signals were captured (freshness)
    PRIMARY KEY (device_id, local_path)
);

CREATE INDEX IF NOT EXISTS idx_focus5_signals_repo  ON focus5_repo_signals(repo_full_name);
CREATE INDEX IF NOT EXISTS idx_focus5_signals_dirty ON focus5_repo_signals(device_id, is_dirty);

CREATE TABLE IF NOT EXISTS focus5_roster (
    device_id     TEXT    NOT NULL,
    local_path    TEXT    NOT NULL,       -- joins to focus5_repo_signals
    position      INTEGER NOT NULL,       -- 1-based rank within the snapshot
    rank_reason   TEXT,                   -- human "why it's here" (dirty / unpushed / commit age)
    ranking_mode  TEXT    NOT NULL,       -- which strategy produced this snapshot
    computed_at   TEXT    NOT NULL,       -- snapshot time; drives the 24h TTL
    PRIMARY KEY (device_id, local_path)
);

CREATE INDEX IF NOT EXISTS idx_focus5_roster_pos ON focus5_roster(device_id, position);
