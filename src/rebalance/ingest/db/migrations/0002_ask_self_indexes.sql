-- Device-local inventory of ask_self RAG indexes.
-- Populated by the "ask_self" collector (rebalance.ingest.ask_self_scan).
-- One row per (device, repo): the bridge from ask_self's filesystem footprint
-- to Rebalance's GitHub-identity watched set is repo_full_name (owner/repo).
CREATE TABLE IF NOT EXISTS ask_self_indexes (
    device_id        TEXT    NOT NULL,
    local_path       TEXT    NOT NULL,
    repo_full_name   TEXT,
    repo_label       TEXT,
    repo_kind        TEXT,
    harness_path     TEXT    NOT NULL,
    index_db_path    TEXT,
    index_built      INTEGER NOT NULL DEFAULT 0,
    branch           TEXT,
    head_sha         TEXT,
    last_commit_at   TEXT,
    file_count       INTEGER,
    total_chunks     INTEGER,
    embed_model      TEXT,
    embed_dim        INTEGER,
    index_size_bytes INTEGER,
    ingested_at      TEXT,
    remote_url       TEXT,
    scanned_at       TEXT    NOT NULL,
    PRIMARY KEY (device_id, local_path)
);

CREATE INDEX IF NOT EXISTS idx_ask_self_repo ON ask_self_indexes(repo_full_name);
CREATE INDEX IF NOT EXISTS idx_ask_self_device ON ask_self_indexes(device_id);
