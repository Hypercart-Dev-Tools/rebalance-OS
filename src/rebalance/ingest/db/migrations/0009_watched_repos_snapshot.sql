-- 0009: persist a canonical snapshot of the watched-repos set each GitHub sync.
--
-- The watched set (get_watched_repos) is a recomputed union with no history, so a
-- repo held only by a rolling window (activity 14d / pushed) drops off the roster
-- with no trace — the BinoidCBD/LTVera-Pandas "fell out" report. This table gives
-- the set a memory: one row per (snapshot_ts, repo), with the resolving bucket(s)
-- recorded so a later reduction can name WHAT KIND of coverage was lost. The
-- watchlist_guard writer diffs the newest two snapshots and emits a
-- watched_repos_reduced event (auth_log) on a concerning drop; it prunes rows
-- older than 30 days. See PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md.
--
-- snapshot_ts is a UTC epoch (seconds). buckets is a comma-separated subset of
-- {project,activity,pushed,external} — the buckets that held the repo at snapshot
-- time. Additive + idempotent (IF NOT EXISTS). No BEGIN/COMMIT (the runner owns
-- the transaction; see migrations/README.md).

CREATE TABLE IF NOT EXISTS watched_repos_snapshot (
    snapshot_ts INTEGER NOT NULL,
    repo        TEXT    NOT NULL,
    buckets     TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (snapshot_ts, repo)
);

CREATE INDEX IF NOT EXISTS idx_watched_repos_snapshot_ts
    ON watched_repos_snapshot (snapshot_ts);
