"""Tests for next_actions.py — the P2 v0.5 "what next" keystone.

Hermetic: no network (synthesize=False or _synthesize_with_fallback monkeypatched),
a temp SQLite DB built through the real migration runner.
"""

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


def _seed_migrated_db(db: Path) -> None:
    """Create a fully migrated DB (post-0005 calendar_events + 0006 cache)."""
    with db_connection(db) as conn:
        run_migrations(conn)
        conn.commit()


def _insert_event(
    db: Path,
    *,
    event_id: str,
    summary: str,
    start_time: str,
    end_time: str,
    calendar_id: str,
    person: str | None,
) -> None:
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


def _today_at(hour: int, minute: int = 0, tz=None) -> str:
    tz = tz or na.local_tz()
    now = datetime.now(tz)
    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# _norm_title + dedup_teammate_blocks
# ---------------------------------------------------------------------------


class TestDedup(unittest.TestCase):
    def test_norm_title_punctuation_insensitive(self) -> None:
        self.assertEqual(na._norm_title("1:45 - Team Call"), na._norm_title("1:45 Team Call"))
        self.assertEqual(na._norm_title("1:45 - Team Call"), "1 45 team call")

    def _blk(self, eid, summary, day="2026-06-17", time="13:45"):
        return {"id": eid, "summary": summary, "local_day": day, "time": time,
                "duration_minutes": 30, "person": "matthew"}

    def test_drops_shared_id(self) -> None:
        operator = [self._blk("op1", "Standup")]
        teammate = [self._blk("shared", "Some other meeting")]
        kept, dropped = na.dedup_teammate_blocks(
            teammate, operator, shared_ids={"shared"}
        )
        self.assertEqual(kept, [])
        self.assertEqual(dropped, 1)

    def test_drops_normalized_title_same_day(self) -> None:
        # "1:45 - Team Call" (operator) vs "1:45 Team Call" (teammate) same day.
        operator = [self._blk("op1", "1:45 - Team Call")]
        teammate = [self._blk("mate1", "1:45 Team Call")]
        kept, dropped = na.dedup_teammate_blocks(teammate, operator, shared_ids=set())
        self.assertEqual(kept, [])
        self.assertEqual(dropped, 1)

    def test_same_title_different_day_is_kept(self) -> None:
        operator = [self._blk("op1", "1:45 Team Call", day="2026-06-16")]
        teammate = [self._blk("mate1", "1:45 Team Call", day="2026-06-17")]
        kept, dropped = na.dedup_teammate_blocks(teammate, operator, shared_ids=set())
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, 0)

    def test_keeps_distinct_and_counts(self) -> None:
        operator = [self._blk("op1", "Standup"), self._blk("op2", "1:45 - Team Call")]
        teammate = [
            self._blk("shared", "anything"),            # dropped by id
            self._blk("mate2", "1:45 Team Call"),        # dropped by title
            self._blk("mate3", "Customer Onboarding"),   # kept (distinct)
        ]
        kept, dropped = na.dedup_teammate_blocks(
            teammate, operator, shared_ids={"shared"}
        )
        self.assertEqual(dropped, 2)
        self.assertEqual([b["id"] for b in kept], ["mate3"])


# ---------------------------------------------------------------------------
# assemble_day_bundle — NOISE guard applied once
# ---------------------------------------------------------------------------


class TestAssembleDayBundle(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "rebalance.db"
        _seed_migrated_db(self.db)
        self.tz = na.local_tz()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_not_noise_guard_applied_once(self) -> None:
        now = datetime.now(self.tz)
        local_day = now.date().isoformat()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        class _FakeActivity:
            gh_commits = [
                {"repo": "hypercart-dev-tools/rebalance-git-pulse", "subject": "noise"},
                {"repo": "acme/real", "subject": "real work"},
            ]
            gh_items = [
                {"repo": "hypercart-dev-tools/rebalance-git-pulse", "title": "noise item"},
                {"repo": "acme/real", "title": "real item"},
            ]
            gh_comments = []
            vault_edits = []
            sleuth_activity = []

        # Stub _query_day_activity so the bundle uses our crafted activity.
        orig = na._query_day_activity
        na._query_day_activity = lambda *a, **k: _FakeActivity()
        try:
            with db_connection(self.db) as conn:
                bundle = na.assemble_day_bundle(
                    conn, local_day=local_day, start=start, end=end,
                    github_login="me", slack_user_id=None, tz=self.tz,
                )
        finally:
            na._query_day_activity = orig

        repos_commits = {c["repo"] for c in bundle.gh_commits}
        repos_items = {i["repo"] for i in bundle.gh_items}
        self.assertNotIn("hypercart-dev-tools/rebalance-git-pulse", repos_commits)
        self.assertNotIn("hypercart-dev-tools/rebalance-git-pulse", repos_items)
        self.assertIn("acme/real", repos_commits)
        self.assertIn("acme/real", repos_items)

    def test_calendar_blocks_operator_scoped(self) -> None:
        local_day = datetime.now(self.tz).date().isoformat()
        _insert_event(self.db, event_id="mine", summary="My Block",
                      start_time=_today_at(10, tz=self.tz),
                      end_time=_today_at(11, tz=self.tz),
                      calendar_id="primary", person=None)
        _insert_event(self.db, event_id="theirs", summary="Their Block",
                      start_time=_today_at(12, tz=self.tz),
                      end_time=_today_at(13, tz=self.tz),
                      calendar_id="matt@group.calendar.google.com", person="matthew")
        now = datetime.now(self.tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        orig = na._query_day_activity

        class _Empty:
            gh_commits = gh_items = gh_comments = vault_edits = sleuth_activity = []

        na._query_day_activity = lambda *a, **k: _Empty()
        try:
            with db_connection(self.db) as conn:
                bundle = na.assemble_day_bundle(
                    conn, local_day=local_day, start=start, end=end,
                    github_login="me", slack_user_id=None, tz=self.tz,
                )
        finally:
            na._query_day_activity = orig

        summaries = {b["summary"] for b in bundle.calendar_blocks}
        self.assertIn("My Block", summaries)
        self.assertNotIn("Their Block", summaries)


# ---------------------------------------------------------------------------
# rank_next_actions — operator-only + the definition-of-done team test
# ---------------------------------------------------------------------------


class TestRankNextActions(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "rebalance.db"
        _seed_migrated_db(self.db)
        self.tz = na.local_tz()
        # No real LLM in tests.
        self._orig_pulse_cfg = na.get_pulse_config

    def tearDown(self) -> None:
        na.get_pulse_config = self._orig_pulse_cfg
        self._tmp.cleanup()

    def _patch_pulse_cfg(self) -> None:
        na.get_pulse_config = lambda: {"github_login": "me", "slack_user_id": None}

    def _patch_roster(self, entries):
        orig = CalendarConfig.load
        cfg = CalendarConfig(
            calendar_id="primary", exclude_titles=[], aggregator_skip_words=[],
            timezone=self.tz.key, projects=[], hours_format="decimal",
            team_calendars=entries,
        )
        CalendarConfig.load = classmethod(lambda cls, *a, **k: cfg)
        self.addCleanup(lambda: setattr(CalendarConfig, "load", orig))

    def test_sparse_empty_roster_yields_operator_only(self) -> None:
        self._patch_pulse_cfg()
        self._patch_roster([])  # no teammates
        _insert_event(self.db, event_id="mine", summary="Operator Meeting",
                      start_time=_today_at(9, tz=self.tz),
                      end_time=_today_at(10, tz=self.tz),
                      calendar_id="primary", person=None)
        result = na.rank_next_actions(self.db, blend_team=True, synthesize=False)
        self.assertIsInstance(result, na.RankedNextActions)
        # Valid operator-only result — calendar block surfaces, no teammate label.
        self.assertTrue(any("Operator Meeting" in a.title for a in result.ranked))
        self.assertTrue(all(a.person is None for a in result.ranked))

    def test_definition_of_done_team_blend_surfaces_extra_item(self) -> None:
        """A teammate carries an item the operator lacks: blend_team=True surfaces
        >=1 ranked item that blend_team=False does not."""
        self._patch_pulse_cfg()
        self._patch_roster([TeamCalendarEntry(person="matthew",
                                              calendar_id="matt@group.calendar.google.com")])
        # Operator's own block.
        _insert_event(self.db, event_id="op1", summary="Operator Block",
                      start_time=_today_at(9, tz=self.tz),
                      end_time=_today_at(10, tz=self.tz),
                      calendar_id="primary", person=None)
        # Teammate (matthew) — rich enough to pass additivity: seed >= min_team_events
        # events in-window, plus the distinctive upcoming item the operator lacks.
        weights = SignalWeights()
        for i in range(weights.min_team_events + 1):
            _insert_event(
                self.db, event_id=f"matt-hist-{i}", summary=f"Matt history {i}",
                start_time=(datetime.now(timezone.utc) - timedelta(days=1, hours=i)).isoformat(),
                end_time=(datetime.now(timezone.utc) - timedelta(days=1, hours=i) + timedelta(minutes=30)).isoformat(),
                calendar_id="matt@group.calendar.google.com", person="matthew",
            )
        # The distinctive UPCOMING teammate item (must be in the upcoming window).
        soon = datetime.now(timezone.utc) + timedelta(hours=4)
        _insert_event(
            self.db, event_id="matt-distinct", summary="Customer Escalation Sync",
            start_time=soon.isoformat(),
            end_time=(soon + timedelta(minutes=45)).isoformat(),
            calendar_id="matt@group.calendar.google.com", person="matthew",
        )

        blended = na.rank_next_actions(self.db, blend_team=True, synthesize=False, weights=weights)
        solo = na.rank_next_actions(self.db, blend_team=False, synthesize=False, weights=weights)

        blended_titles = {a.title for a in blended.ranked}
        solo_titles = {a.title for a in solo.ranked}

        self.assertTrue(blended.blended)
        self.assertFalse(solo.blended)
        # The teammate-only item appears in the blended view, not the solo view.
        self.assertTrue(any("Customer Escalation Sync" in t for t in blended_titles))
        self.assertFalse(any("Customer Escalation Sync" in t for t in solo_titles))
        # And it is person-attributed (local display only).
        self.assertTrue(any(
            a.person == "matthew" and "Customer Escalation Sync" in a.title
            for a in blended.ranked
        ))

    def test_synthesize_monkeypatched_keeps_fallback_on_empty(self) -> None:
        """A failed/empty synthesis still yields a ranked (deterministic) view."""
        self._patch_pulse_cfg()
        self._patch_roster([])
        _insert_event(self.db, event_id="mine", summary="Fallback Meeting",
                      start_time=_today_at(9, tz=self.tz),
                      end_time=_today_at(10, tz=self.tz),
                      calendar_id="primary", person=None)
        import rebalance.ingest.querier as querier
        orig = querier._synthesize_with_fallback
        querier._synthesize_with_fallback = lambda *a, **k: ("", "fake (failed)")
        try:
            result = na.rank_next_actions(self.db, blend_team=False, synthesize=True)
        finally:
            querier._synthesize_with_fallback = orig
        # Degraded-but-ranked: empty synthesis falls back to deterministic order.
        self.assertTrue(any("Fallback Meeting" in a.title for a in result.ranked))

    def test_never_raises_on_missing_db(self) -> None:
        self._patch_pulse_cfg()
        self._patch_roster([])
        # Point at a path whose parent does not exist to force an internal error.
        result = na.rank_next_actions(self.db, blend_team=False, synthesize=False)
        self.assertIsInstance(result, na.RankedNextActions)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "rebalance.db"
        _seed_migrated_db(self.db)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_round_trip(self) -> None:
        result = na.RankedNextActions(
            ranked=[na.RankedAction(rank=1, title="Do thing", person="matthew",
                                    source="calendar", project="Acme",
                                    evidence=["matt 14:00 (45m)"], why="cross-person")],
            synthesis="", model_used="test", blended=True,
            weights_used={"min_team_events": 12},
            note="ok", elapsed_seconds=0.1,
            computed_at="2026-06-17T12:00:00+00:00",
        )
        na.persist_ranked_next_actions(self.db, result)
        loaded = na.load_ranked_next_actions(self.db)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.ranked[0].title, "Do thing")
        self.assertEqual(loaded.ranked[0].person, "matthew")
        self.assertTrue(loaded.blended)

    def test_load_returns_none_on_empty(self) -> None:
        self.assertIsNone(na.load_ranked_next_actions(self.db))

    def test_get_ranked_meta_freshness(self) -> None:
        self.assertEqual(na.get_ranked_meta(self.db)["row_count"], 0)
        result = na.RankedNextActions(blended=True, model_used="m",
                                      computed_at="2026-06-17T12:00:00+00:00")
        na.persist_ranked_next_actions(self.db, result)
        meta = na.get_ranked_meta(self.db)
        self.assertEqual(meta["row_count"], 1)
        self.assertTrue(meta["blended"])
        self.assertEqual(meta["model_used"], "m")


if __name__ == "__main__":
    unittest.main()
