CREATE TABLE IF NOT EXISTS figma_comments (
    comment_key      TEXT PRIMARY KEY,
    file_key         TEXT NOT NULL,
    comment_id       TEXT NOT NULL,
    parent_id        TEXT,
    message          TEXT,
    user_id          TEXT,
    user_handle      TEXT,
    created_at       TEXT,
    resolved_at      TEXT,
    order_id         REAL,
    client_meta_json TEXT,
    reactions_json   TEXT,
    raw_json         TEXT NOT NULL,
    synced_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_figma_comments_file_created
ON figma_comments(file_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_figma_comments_synced
ON figma_comments(synced_at DESC);
