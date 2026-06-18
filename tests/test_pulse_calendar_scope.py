"""The pulse 'Upcoming Meetings' section is committed and pushed off-machine, so
_query_calendar_upcoming must surface ONLY the operator's own ('primary')
calendar — a teammate event leaking here would be an off-machine export of
teammate data (P2 decision #3, the highest-stakes filter site)."""

import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from rebalance.ingest.pulse import _query_calendar_upcoming

_TABLE = """
    CREATE TABLE calendar_events (
        id TEXT PRIMARY KEY, summary TEXT, start_time TEXT NOT NULL,
        end_time TEXT, location TEXT, attendees_json TEXT,
        calendar_id TEXT NOT NULL DEFAULT 'primary',
        status TEXT, description TEXT, fetched_at TEXT NOT NULL,
        person TEXT
    )
"""


def _event(id_: str, cal: str, summary: str, person: str | None = None) -> tuple:
    # 14:00 UTC today — after `now` (09:00) so it counts as upcoming.
    return (id_, summary, "2026-06-15T14:00:00+00:00", "2026-06-15T15:00:00+00:00",
            None, None, cal, "confirmed", None, "2026-06-01T00:00:00Z", person)


class TestPulseUpcomingScope(unittest.TestCase):
    def test_only_primary_upcoming_is_returned(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(_TABLE)
        conn.executemany(
            "INSERT INTO calendar_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [_event("p", "primary", "Mine"),
             _event("t", "teammate@group.calendar.google.com", "Theirs")])
        conn.commit()

        now = datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc)
        today_start = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
        tomorrow_start = today_start + timedelta(days=1)

        out = _query_calendar_upcoming(
            conn, today_start=today_start, tomorrow_start=tomorrow_start, now=now)
        summaries = [e["summary"] for e in out]
        conn.close()

        self.assertIn("Mine", summaries)
        self.assertNotIn("Theirs", summaries)

    def test_person_label_never_in_upcoming(self) -> None:
        # The pushed pulse render must never carry the `person` teammate label.
        # _query_calendar_upcoming does not SELECT person; this locks that the
        # render query never widens to include it.
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(_TABLE)
        conn.executemany(
            "INSERT INTO calendar_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [_event("p", "primary", "Mine", person="OPERATOR_LABEL"),
             _event("t", "teammate@group.calendar.google.com", "Theirs",
                    person="matthew")])
        conn.commit()

        now = datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc)
        today_start = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
        tomorrow_start = today_start + timedelta(days=1)

        out = _query_calendar_upcoming(
            conn, today_start=today_start, tomorrow_start=tomorrow_start, now=now)
        conn.close()

        for e in out:
            self.assertNotIn("person", e)
        # Defense in depth: no person label survives anywhere in the output.
        blob = repr(out)
        self.assertNotIn("OPERATOR_LABEL", blob)
        self.assertNotIn("matthew", blob)


if __name__ == "__main__":
    unittest.main()
