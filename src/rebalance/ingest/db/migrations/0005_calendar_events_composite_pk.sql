-- 0005: calendar_events composite primary key (id, calendar_id) + person column.
--
-- The single-column PK (id) overwrote a shared invite when the same Google event
-- id appeared on two calendars, flipping its calendar_id. A teammate's calendar
-- must coexist with the operator's own, so the row identity becomes
-- (id, calendar_id). This also adds `person` (a friendly owner label) and an
-- index on (calendar_id, start_time) for per-calendar day-window queries.
--
-- SQLite cannot ALTER a primary key in place, so the table is rebuilt
-- (create -> copy -> drop -> rename). ATOMICITY: the runner (migrate.py) wraps
-- every migration in a single transaction and rolls back on any error, so a
-- crash mid-rebuild leaves the ORIGINAL calendar_events fully intact and the
-- migration simply re-runs next time — there is no window where the only copy
-- of the data lives in the scratch table. This file therefore carries NO BEGIN/
-- COMMIT of its own (a nested BEGIN would error under the runner's transaction).
--
-- Notes:
--   * The old PK guaranteed `id` was unique, so (id, calendar_id) is trivially
--     unique — the copy cannot violate the new composite PK.
--   * `id` and `calendar_id` are declared NOT NULL explicitly: SQLite allows
--     NULLs in non-INTEGER PRIMARY KEY columns unless told otherwise.
--   * Explicit column lists (not SELECT *) so the new `person` column defaults
--     to NULL on copy.

DROP TABLE IF EXISTS calendar_events_new;

CREATE TABLE calendar_events_new (
    id              TEXT NOT NULL,
    summary         TEXT,
    start_time      TEXT NOT NULL,
    end_time        TEXT,
    location        TEXT,
    attendees_json  TEXT,
    calendar_id     TEXT NOT NULL DEFAULT 'primary',
    status          TEXT,
    description     TEXT,
    fetched_at      TEXT NOT NULL,
    person          TEXT,
    PRIMARY KEY (id, calendar_id)
);

INSERT INTO calendar_events_new
    (id, summary, start_time, end_time, location, attendees_json,
     calendar_id, status, description, fetched_at)
SELECT
    id, summary, start_time, end_time, location, attendees_json,
    calendar_id, status, description, fetched_at
FROM calendar_events;

DROP TABLE calendar_events;
ALTER TABLE calendar_events_new RENAME TO calendar_events;

CREATE INDEX IF NOT EXISTS idx_calendar_start
    ON calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_calendar_id_start
    ON calendar_events(calendar_id, start_time);
