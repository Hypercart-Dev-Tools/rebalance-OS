"""Privacy invariant for the v0.5 "what next" team blend.

Hard rule (P2 decision #3): the in-process team blend
(``rank_next_actions(blend_team=True)``) reads teammate ``person`` labels for
LOCAL DISPLAY ONLY. It must never widen the export surface — after a blended
rank, ``export_calendar_snapshot`` must still carry ZERO teammate calendar rows
and ZERO ``person`` labels, and ``sync_snapshot._CALENDAR_COLUMNS`` must still
omit ``person``. Mirrors test_sync_snapshot.test_person_label_never_exported.
"""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rebalance.ingest import next_actions as na
from rebalance.ingest.calendar_config import (
    CalendarConfig,
    SignalWeights,
    TeamCalendarEntry,
)
from rebalance.ingest.db import db_connection, run_migrations
from rebalance.ingest.sync_snapshot import _CALENDAR_COLUMNS, export_calendar_snapshot


def _seed_migrated_db(db: Path) -> None:
    with db_connection(db) as conn:
        run_migrations(conn)
        conn.commit()


def _insert_event(db, *, event_id, summary, start_time, end_time, calendar_id, person):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT OR REPLACE INTO calendar_events "
        "(id, summary, start_time, end_time, location, attendees_json, "
        " calendar_id, status, description, fetched_at, person) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (event_id, summary, start_time, end_time, None, None, calendar_id,
         "confirmed", None, "2026-06-01T00:00:00Z", person),
    )
    conn.commit()
    conn.close()


class TestNextActionsPrivacy(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "rebalance.db"
        self.sync_dir = self.tmp / "sync"
        _seed_migrated_db(self.db)
        self.tz = na.local_tz()

        self._orig_pulse_cfg = na.get_pulse_config
        na.get_pulse_config = lambda: {"github_login": "me", "slack_user_id": None}
        orig_load = CalendarConfig.load
        cfg = CalendarConfig(
            calendar_id="primary", exclude_titles=[], aggregator_skip_words=[],
            timezone=self.tz.key, projects=[], hours_format="decimal",
            team_calendars=[TeamCalendarEntry(
                person="matthew", calendar_id="matt@group.calendar.google.com")],
        )
        CalendarConfig.load = classmethod(lambda cls, *a, **k: cfg)
        self.addCleanup(lambda: setattr(CalendarConfig, "load", orig_load))

    def tearDown(self) -> None:
        na.get_pulse_config = self._orig_pulse_cfg
        self._tmp.cleanup()

    def test_columns_omit_person(self) -> None:
        # The export column tuple itself must never include `person`.
        self.assertNotIn("person", _CALENDAR_COLUMNS)

    def test_blended_rank_does_not_leak_to_export(self) -> None:
        # Operator's own block.
        _insert_event(self.db, event_id="op1", summary="Operator Block",
                      start_time=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                      end_time=(datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
                      calendar_id="primary", person=None)
        # Rich teammate history (passes additivity) + a distinctive upcoming item.
        weights = SignalWeights()
        for i in range(weights.min_team_events + 1):
            _insert_event(
                self.db, event_id=f"matt-hist-{i}", summary=f"Matt history {i}",
                start_time=(datetime.now(timezone.utc) - timedelta(days=1, hours=i)).isoformat(),
                end_time=(datetime.now(timezone.utc) - timedelta(days=1, hours=i) + timedelta(minutes=30)).isoformat(),
                calendar_id="matt@group.calendar.google.com", person="matthew",
            )
        soon = datetime.now(timezone.utc) + timedelta(hours=4)
        _insert_event(
            self.db, event_id="matt-distinct", summary="SECRET Teammate Sync",
            start_time=soon.isoformat(),
            end_time=(soon + timedelta(minutes=45)).isoformat(),
            calendar_id="matt@group.calendar.google.com", person="matthew",
        )

        # Run a blended rank — this reads the `person` column in-process.
        result = na.rank_next_actions(self.db, blend_team=True, synthesize=False, weights=weights)
        self.assertTrue(result.blended)
        self.assertTrue(any("SECRET Teammate Sync" in a.title for a in result.ranked))

        # Export must still be operator-only with zero person labels.
        out = export_calendar_snapshot(self.db, self.sync_dir, device_id="mac")
        raw = out.read_text()
        data = json.loads(raw)

        self.assertEqual({r["calendar_id"] for r in data["rows"]}, {"primary"})
        self.assertNotIn("SECRET Teammate Sync", [r["summary"] for r in data["rows"]])
        for row in data["rows"]:
            self.assertNotIn("person", row)
        # Defense in depth: the teammate label / teammate event never appears
        # anywhere in the serialized export payload.
        self.assertNotIn("matthew", raw)
        self.assertNotIn("SECRET Teammate Sync", raw)
        self.assertNotIn("matt@group.calendar.google.com", raw)


if __name__ == "__main__":
    unittest.main()
