-- 0006: ranked_next_actions — local-only precompute cache for the P2 v0.5
-- "what should we work on next" ranked list.
--
-- This is a DEVICE-LOCAL cache, mirroring focus5_roster: the keystone
-- (next_actions.rank_next_actions) computes a flat ranked list and persists it
-- here so the dashboard route can render without recomputing on every request.
--
-- PRIVACY (P2 decision #3): payload_json carries teammate `person` labels (the
-- ranked items are local-display attributed). This table is therefore LOCAL-ONLY
-- and must NEVER be part of export_calendar_snapshot or the pushed pulse. It is
-- never read by any export/sync path.
--
-- Simple CREATE TABLE (low risk). No BEGIN/COMMIT — the runner (migrate.py) owns
-- the transaction; a self-wrapped BEGIN would nest and roll back.

CREATE TABLE IF NOT EXISTS ranked_next_actions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    computed_at   TEXT NOT NULL,
    blended       INTEGER NOT NULL DEFAULT 0,
    model_used    TEXT,
    payload_json  TEXT NOT NULL,
    weights_json  TEXT
);

CREATE INDEX IF NOT EXISTS idx_ranked_next_actions_computed_at
    ON ranked_next_actions(computed_at);
