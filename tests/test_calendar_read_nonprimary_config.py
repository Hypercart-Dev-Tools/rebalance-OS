"""Operator read sites must filter on the canonical 'primary' storage key.

Regression for the write/read asymmetry: index_ops + refresh_calendar_source
canonicalise the operator's stored rows to calendar_id='primary', but three
read sites still filtered WHERE calendar_id = config.calendar_id. An operator
whose config.calendar_id is a non-'primary' value (their email — a documented,
supported config) got ZERO rows from the timesheet/daily/weekly report and
project inference, even though the events exist in the DB.

Covers all three fixed sites: daily_report.get_day_data,
project_inference._load_calendar_events, note_builder._load_recent_calendar_activity.
"""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest.calendar_config import CalendarConfig

# A non-'primary' calendar_id the operator might legitimately set in config.
NON_PRIMARY = "noel@neochro.me"


def _config() -> CalendarConfig:
    return CalendarConfig(
        calendar_id=NON_PRIMARY,
        exclude_titles=[],
        aggregator_skip_words=[],
        timezone="UTC",
        projects=[],
        hours_format="decimal",
        team_calendars=[],
    )


def _seed_operator_event(db: Path, summary: str) -> str:
    """Migrate the DB and insert one operator event stored as calendar_id='primary'."""
    from rebalance.ingest.db.connection import get_connection
    from rebalance.ingest.db.migrate import run_migrations

    conn = get_connection(db)
    run_migrations(conn)
    today = datetime.now(timezone.utc).date()
    start = f"{today.isoformat()}T10:00:00+00:00"
    end = f"{today.isoformat()}T11:00:00+00:00"
    conn.execute(
        """INSERT OR REPLACE INTO calendar_events
           (id, summary, start_time, end_time, location, attendees_json,
            calendar_id, status, description, fetched_at, person)
           VALUES (?, ?, ?, ?, '', '[]', 'primary', 'confirmed', '', ?, NULL)""",
        ("evt-op", summary, start, end, start),
    )
    conn.commit()
    conn.close()
    return summary


class TestNonPrimaryConfigStillReadsOperatorEvents(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "rebalance.db"
        self.summary = _seed_operator_event(self.db, "Regression Standup ABC")
        self.config = _config()
        self.today = datetime.now(timezone.utc).date()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_baseline_event_is_stored_under_primary(self) -> None:
        # Sanity: the row really is keyed 'primary', != the config value.
        conn = sqlite3.connect(self.db)
        try:
            stored = conn.execute(
                "SELECT calendar_id FROM calendar_events WHERE id = 'evt-op'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(stored, "primary")
        self.assertNotEqual(stored, self.config.calendar_id)

    def test_get_day_data_returns_operator_event(self) -> None:
        from rebalance.ingest import daily_report

        with patch.object(daily_report, "load_review_decisions", return_value={}):
            day = daily_report.get_day_data(self.db, self.today, self.config)

        summaries = [e.get("summary") for e in day.filtered_events]
        self.assertIn(self.summary, summaries, "non-'primary' config must not hide operator events")
        self.assertGreater(day.total_minutes, 0)

    def test_project_inference_loads_operator_event(self) -> None:
        from rebalance.ingest.project_inference import _load_calendar_events

        events = _load_calendar_events(self.db, config=self.config, days_back=7, days_forward=7)
        summaries = [e.get("summary") for e in events]
        self.assertIn(self.summary, summaries)

    def test_note_builder_loads_operator_event(self) -> None:
        from rebalance.ingest import note_builder

        with patch.object(note_builder, "load_review_decisions", return_value={}):
            _stats, needs_review = note_builder._load_recent_calendar_activity(
                self.db, target_date=self.today, since_days=7, config=self.config
            )
        # No project matcher is configured, so the event surfaces as needs_review
        # (entries are date-prefixed, e.g. "2026-06-13 — Regression Standup ABC").
        self.assertTrue(
            any(self.summary in item for item in needs_review),
            f"operator event missing from needs_review: {needs_review}",
        )


if __name__ == "__main__":
    unittest.main()
