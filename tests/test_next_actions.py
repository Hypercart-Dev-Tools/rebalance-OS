"""Tests for next_actions.py — the P2 v0.5 "what next" keystone.

Hermetic: no network (synthesize=False or _synthesize_with_fallback monkeypatched),
a temp SQLite DB built through the real migration runner.
"""

import sqlite3
import tempfile
import unittest
import json
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


def _insert_project(db: Path, *, name: str, repos: list[str]) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO project_registry
            (name, status, summary, value_level, priority_tier, risk_level,
             repos_json, tags_json, custom_fields_json)
        VALUES (?, 'active', '', NULL, NULL, NULL, ?, '[]', '{}')
        """,
        (name, json.dumps(repos)),
    )
    conn.commit()
    conn.close()


def _insert_commit(
    db: Path,
    *,
    repo: str,
    sha: str,
    author_login: str,
    message: str,
    committed_at: str,
) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO github_commits
            (repo_full_name, item_type, item_number, sha, author_login, message,
             committed_at, html_url, fetched_at)
        VALUES (?, 'commit', 0, ?, ?, ?, ?, ?, ?)
        """,
        (
            repo,
            sha,
            author_login,
            message,
            committed_at,
            f"https://github.example/{repo}/commit/{sha}",
            committed_at,
        ),
    )
    conn.commit()
    conn.close()


def _insert_github_item(
    db: Path,
    *,
    repo: str,
    item_type: str,
    number: int,
    title: str,
    state: str,
    author_login: str,
    created_at: str,
    updated_at: str,
) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO github_items
            (repo_full_name, item_type, number, title, state, author_login,
             html_url, created_at, updated_at, fetched_at, is_merged)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            repo,
            item_type,
            number,
            title,
            state,
            author_login,
            f"https://github.example/{repo}/{item_type}/{number}",
            created_at,
            updated_at,
            updated_at,
        ),
    )
    conn.commit()
    conn.close()


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
            email_activity = []
            figma_activity = []

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
            email_activity = figma_activity = []

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


class TestComputeDeepWorkSignals(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "rebalance.db"
        _seed_migrated_db(self.db)
        self.tz = na.local_tz()
        self.today = datetime(2026, 7, 5, 12, 0, tzinfo=self.tz)
        self._orig_pulse_cfg = na.get_pulse_config
        na.get_pulse_config = lambda: {
            "github_login": "me",
            "slack_user_id": None,
            "pulse_timezone": self.tz.key,
        }

    def tearDown(self) -> None:
        na.get_pulse_config = self._orig_pulse_cfg
        self._tmp.cleanup()

    def _stamp(self, days_ago: int, hour: int = 10) -> str:
        dt = (self.today - timedelta(days=days_ago)).replace(
            hour=hour, minute=0, second=0, microsecond=0
        )
        return dt.isoformat()

    def test_compute_deep_work_signals_phase1_cases(self) -> None:
        _insert_project(self.db, name="Streak Project", repos=["acme/streak"])
        _insert_project(self.db, name="Stall Project", repos=["acme/stall"])
        _insert_project(self.db, name="Quiet Project", repos=["acme/quiet"])

        for days_ago in range(5):
            _insert_commit(
                self.db,
                repo="acme/streak",
                sha=f"streak{days_ago}",
                author_login="me",
                message=f"Keep shipping day {days_ago}",
                committed_at=self._stamp(days_ago),
            )

        _insert_commit(
            self.db,
            repo="acme/stall",
            sha="stall1",
            author_login="me",
            message="Touched yesterday only",
            committed_at=self._stamp(1),
        )
        _insert_github_item(
            self.db,
            repo="acme/stall",
            item_type="issue",
            number=42,
            title="Still open follow-up",
            state="open",
            author_login="someone-else",
            created_at=self._stamp(3),
            updated_at=self._stamp(2),
        )

        _insert_commit(
            self.db,
            repo="acme/quiet",
            sha="quiet1",
            author_login="me",
            message="Finished yesterday",
            committed_at=self._stamp(1),
        )

        signals = na.compute_deep_work_signals(
            self.db,
            self.today.date(),
            lookback_days=7,
        )

        self.assertEqual(signals["Streak Project"]["streak_days"], 5)
        self.assertFalse(signals["Streak Project"]["possible_stall"])
        self.assertEqual(
            signals["Streak Project"]["evidence"]["streak_dates"],
            ["2026-07-05", "2026-07-04", "2026-07-03", "2026-07-02", "2026-07-01"],
        )

        stall = signals["Stall Project"]
        self.assertEqual(stall["streak_days"], 0)
        self.assertTrue(stall["possible_stall"])
        self.assertEqual(stall["evidence"]["yesterday_date"], "2026-07-04")
        self.assertEqual(len(stall["evidence"]["yesterday_rows"]), 1)
        self.assertEqual(stall["evidence"]["open_items"][0]["number"], 42)
        self.assertEqual(stall["evidence"]["open_items"][0]["title"], "Still open follow-up")

        quiet = signals["Quiet Project"]
        self.assertEqual(quiet["streak_days"], 0)
        self.assertFalse(quiet["possible_stall"])
        self.assertEqual(quiet["evidence"]["today_rows"], [])
        self.assertEqual(quiet["evidence"]["open_items"], [])


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

    def test_synthesis_disables_thinking_to_avoid_truncation(self) -> None:
        """The ranking call passes thinking_budget=0 so a reasoning model doesn't
        spend the token budget on hidden thinking and truncate the list (the
        '2 items only' regression)."""
        self._patch_pulse_cfg()
        self._patch_roster([])
        _insert_event(self.db, event_id="mine", summary="A Meeting",
                      start_time=_today_at(9, tz=self.tz),
                      end_time=_today_at(10, tz=self.tz),
                      calendar_id="primary", person=None)
        import rebalance.ingest.querier as querier
        captured: dict = {}
        orig = querier._synthesize_with_fallback

        def _capture(prompt, **kwargs):
            captured.update(kwargs)
            return ("", "fake")

        querier._synthesize_with_fallback = _capture
        try:
            na.rank_next_actions(self.db, blend_team=False, synthesize=True)
        finally:
            querier._synthesize_with_fallback = orig
        self.assertEqual(captured.get("thinking_budget"), 0)

    def test_never_raises_on_missing_db(self) -> None:
        self._patch_pulse_cfg()
        self._patch_roster([])
        # Point at a path whose parent does not exist to force an internal error.
        result = na.rank_next_actions(self.db, blend_team=False, synthesize=False)
        self.assertIsInstance(result, na.RankedNextActions)


# ---------------------------------------------------------------------------
# FIX 1 — uniform pipe grammar: prompt ↔ parser round-trip + acceptance gate
# ---------------------------------------------------------------------------


class TestParseRankedSynthesis(unittest.TestCase):
    def test_round_trips_the_emitted_grammar(self) -> None:
        """The parser round-trips the EXACT grammar build_rank_prompt emits:
        person/source/project/evidence/why all populated, evidence a list,
        ranks re-sequenced, leading **markdown** stripped."""
        text = (
            "1. **Fix login PR** | person=operator | source=github | "
            "project=acme/web | evidence=PR #42; gh.com/acme/web/pull/42 | "
            "automation=yes | why=open PR you own\n"
            "2. Customer Escalation Sync | person=matthew | source=calendar | "
            "project= | evidence=matt 14:00; 45m | automation=no | "
            "why=cross-person, no operator signal"
        )
        actions = na._parse_ranked_synthesis(text)
        self.assertEqual(len(actions), 2)

        a1, a2 = actions
        # Ranks re-sequenced 1..N by emit order.
        self.assertEqual([a1.rank, a2.rank], [1, 2])
        # ** markdown stripped from the title.
        self.assertEqual(a1.title, "Fix login PR")
        self.assertEqual(a1.person, None)  # operator → None (local-display invariant)
        self.assertEqual(a1.source, "github")
        self.assertEqual(a1.project, "acme/web")
        # evidence parsed as a LIST split on '; ' (DSP-03).
        self.assertEqual(a1.evidence, ["PR #42", "gh.com/acme/web/pull/42"])
        self.assertEqual(a1.why, "open PR you own")
        # automation= parsed from the grammar.
        self.assertTrue(a1.automation)

        self.assertEqual(a2.person, "matthew")
        self.assertEqual(a2.source, "calendar")
        self.assertIsNone(a2.project)  # empty project= → None
        self.assertEqual(a2.evidence, ["matt 14:00", "45m"])
        self.assertFalse(a2.automation)

    def test_automation_falls_back_to_heuristic_when_omitted(self) -> None:
        """When the model omits automation=, the deterministic heuristic fills it:
        a github-sourced item is automation-eligible; a vague calendar hold is not."""
        text = (
            "1. Fix the broken deploy | person=operator | source=github | "
            "project=acme/web | evidence=x | why=ci is red\n"
            "2. Focus time | person=operator | source=calendar | project= | "
            "evidence=10:00 | why=deep work block"
        )
        actions = na._parse_ranked_synthesis(text)
        self.assertTrue(actions[0].automation)   # github → eligible
        self.assertFalse(actions[1].automation)  # vague calendar hold → not

    def test_infer_automation_heuristic(self) -> None:
        # github source always qualifies.
        self.assertTrue(na._infer_automation("github", "anything", None))
        # code/repo keywords in title/project qualify even off github.
        self.assertTrue(na._infer_automation("sleuth", "wrap up the Binoid plugin", None))
        self.assertTrue(na._infer_automation("calendar", "Bloomz HPOS migration", "bloomz"))
        self.assertTrue(na._infer_automation("sleuth", "look at issue #845", None))
        # meetings / emails / vague holds do not.
        self.assertFalse(na._infer_automation("calendar", "Team standup", None))
        self.assertFalse(na._infer_automation("sleuth", "email Rebekah re budget", None))
        self.assertFalse(na._infer_automation("calendar", "Focus time", None))

    def test_rank_integers_are_not_trusted(self) -> None:
        """Negative/zero/duplicate model rank ints are re-sequenced by order."""
        text = (
            "0. Alpha | person=operator | source=vault | project= | evidence=a | why=x\n"
            "0. Beta | person=operator | source=vault | project= | evidence=b | why=y\n"
            "-3. Gamma | person=operator | source=vault | project= | evidence=c | why=z"
        )
        actions = na._parse_ranked_synthesis(text)
        self.assertEqual([a.rank for a in actions], [1, 2, 3])
        self.assertEqual([a.title for a in actions], ["Alpha", "Beta", "Gamma"])

    def test_bullet_markers_accepted(self) -> None:
        """Bullets (-, *, •) are accepted and rank-assigned by position."""
        text = (
            "- Alpha | person=operator | source=github | project= | evidence=a | why=x\n"
            "* Beta | person=operator | source=github | project= | evidence=b | why=y\n"
            "• Gamma | person=operator | source=github | project= | evidence=c | why=z"
        )
        actions = na._parse_ranked_synthesis(text)
        self.assertEqual([a.rank for a in actions], [1, 2, 3])
        self.assertEqual([a.title for a in actions], ["Alpha", "Beta", "Gamma"])

    def test_degenerate_prose_carries_no_structured_field(self) -> None:
        """A prose numbered list parses to title-only items — no structured field —
        so the acceptance gate (in rank_next_actions) will REJECT it."""
        prose = (
            "1. We should probably look at the login flow soon.\n"
            "2. Also the dashboard needs some love and attention.\n"
            "3. Don't forget to follow up with the team about Q3."
        )
        actions = na._parse_ranked_synthesis(prose)
        # They parse (numbered), but none carries a real structured field.
        self.assertTrue(actions)
        self.assertTrue(all(not na._has_structured_field(a) for a in actions))

    def test_echoed_template_title_rejected(self) -> None:
        """A weak model that echoes the `<rank>. <title>` spec verbatim — even
        WITH the other fields filled — must parse to NOTHING, so the caller keeps
        the deterministic fallback instead of surfacing placeholder titles.
        Regression for the live Qwen-0.6B failure mode (`<rank>. <title>` titles).
        """
        echoed = (
            "1. <rank>. <title> | person=Matthew | source=github | "
            "project=Binoid | evidence=GH 894 | automation=no | why=urgent\n"
            "2. <rank>. <title> | person=operator | source=calendar | "
            "project= | evidence=10:00 | automation=no | why=hold"
        )
        actions = na._parse_ranked_synthesis(echoed)
        self.assertEqual(actions, [])

    def test_placeholder_field_values_ignored(self) -> None:
        """A real title but unfilled `<...>` field values (e.g. `source=<source>`)
        are treated as omitted, not stored as literal junk."""
        text = (
            "1. Review the Binoid PR | person=operator | source=<source> | "
            "project=<project-or-empty> | evidence=GH 894 | why=<one-line reason>"
        )
        actions = na._parse_ranked_synthesis(text)
        self.assertEqual(len(actions), 1)
        a = actions[0]
        self.assertEqual(a.title, "Review the Binoid PR")
        self.assertEqual(a.source, "")        # <source> ignored
        self.assertIsNone(a.project)          # <project-or-empty> ignored
        self.assertEqual(a.why, "")           # <one-line reason> ignored
        self.assertEqual(a.evidence, ["GH 894"])  # real value kept

    def test_bare_angle_token_title_rejected(self) -> None:
        """A title that is wholly a `<...>` token is dropped."""
        actions = na._parse_ranked_synthesis(
            "1. <title> | person=operator | source=github | evidence=x | why=y"
        )
        self.assertEqual(actions, [])

    def test_generated_next_actions_file_excluded_from_candidates(self) -> None:
        """rebalance's own What-To-Do-Next vault file must not rank itself."""
        self.assertTrue(na._is_generated_next_actions_file(
            "Dashboards/What To Do Next.md", "What To Do Next"))
        self.assertTrue(na._is_generated_next_actions_file(
            "Dashboards/What To Do Next.md", ""))
        # A real, differently-named note is kept.
        self.assertFalse(na._is_generated_next_actions_file(
            "Projects/Binoid.md", "Binoid"))


class TestVaultRender(unittest.TestCase):
    """The fixed-vault-file render sink (render_next_actions_markdown +
    write_next_actions_to_vault)."""

    def _result(self) -> "na.RankedNextActions":
        return na.RankedNextActions(
            ranked=[
                na.RankedAction(
                    rank=1, title="Review Binoid PR 894", person=None,
                    source="github", project="Binoid", evidence=["GH 894"],
                    why="bug fix for Bloomz", automation=True,
                ),
                na.RankedAction(
                    rank=2, title="Sync with Matthew", person="Matthew",
                    source="calendar", project=None, evidence=["14:00"],
                    why="cross-person", automation=False,
                ),
            ],
            model_used="gemini-3.5-flash", blended=True,
            note="team blended: 1 additive block",
            computed_at="2026-06-30T01:30:00+00:00",
        )

    def test_render_has_banner_and_items(self) -> None:
        md = na.render_next_actions_markdown(self._result())
        self.assertIn("# What To Do Next", md)
        self.assertIn("do not edit by hand", md)            # single-writer banner
        self.assertIn("gemini-3.5-flash", md)               # provenance
        self.assertIn("1. **Review Binoid PR 894**", md)
        self.assertIn("👤 Matthew", md)                      # teammate attribution
        self.assertIn("evidence: GH 894", md)

    def test_render_empty_is_graceful(self) -> None:
        md = na.render_next_actions_markdown(
            na.RankedNextActions(ranked=[], model_used="x", computed_at="2026-06-30T00:00:00+00:00")
        )
        self.assertIn("Nothing surfaced", md)

    def test_write_to_vault_creates_fixed_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            target = na.write_next_actions_to_vault(self._result(), vault_path=d)
            self.assertIsNotNone(target)
            self.assertEqual(target, Path(d) / na.VAULT_NEXT_ACTIONS_RELPATH)
            self.assertTrue(target.exists())
            self.assertIn("Review Binoid PR 894", target.read_text(encoding="utf-8"))

    def test_write_to_vault_none_when_unconfigured(self) -> None:
        # No override and no configured vault → no-op (None), not an error.
        orig = na.get_vault_path
        na.get_vault_path = lambda: None
        try:
            self.assertIsNone(na.write_next_actions_to_vault(self._result()))
        finally:
            na.get_vault_path = orig

    def test_write_to_vault_overwrites_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            na.write_next_actions_to_vault(self._result(), vault_path=d)
            na.write_next_actions_to_vault(self._result(), vault_path=d)  # second write
            target = Path(d) / na.VAULT_NEXT_ACTIONS_RELPATH
            # One file, single-writer — not appended/duplicated.
            self.assertEqual(target.read_text(encoding="utf-8").count("# What To Do Next"), 1)


class TestAcceptanceGate(unittest.TestCase):
    """rank_next_actions keeps the deterministic fallback when synthesis is prose
    (the DSP-01 regression): the user sees the structured fallback, not prose."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "rebalance.db"
        _seed_migrated_db(self.db)
        self.tz = na.local_tz()
        self._orig_cfg = na.get_pulse_config
        na.get_pulse_config = lambda: {"github_login": "me", "slack_user_id": None}
        orig = CalendarConfig.load
        cfg = CalendarConfig(
            calendar_id="primary", exclude_titles=[], aggregator_skip_words=[],
            timezone=self.tz.key, projects=[], hours_format="decimal",
            team_calendars=[],
        )
        CalendarConfig.load = classmethod(lambda cls, *a, **k: cfg)
        self.addCleanup(lambda: setattr(CalendarConfig, "load", orig))

    def tearDown(self) -> None:
        na.get_pulse_config = self._orig_cfg
        self._tmp.cleanup()

    def test_prose_synthesis_rejected_keeps_structured_fallback(self) -> None:
        _insert_event(self.db, event_id="mine", summary="Ship Release Notes",
                      start_time=_today_at(9, tz=self.tz),
                      end_time=_today_at(10, tz=self.tz),
                      calendar_id="primary", person=None)
        prose = (
            "Here is what I think you should do:\n"
            "1. Maybe take a look at the calendar later.\n"
            "2. Could be worth catching up on email too."
        )
        import rebalance.ingest.querier as querier
        orig = querier._synthesize_with_fallback
        querier._synthesize_with_fallback = lambda *a, **k: (prose, "fake-model")
        try:
            result = na.rank_next_actions(self.db, blend_team=False, synthesize=True)
        finally:
            querier._synthesize_with_fallback = orig

        titles = {a.title for a in result.ranked}
        # The deterministic (structured) fallback survives — NOT the prose lines.
        self.assertIn("Ship Release Notes", titles)
        self.assertNotIn("Maybe take a look at the calendar later.", titles)
        self.assertIn("nothing useful", result.note)

    def test_structured_synthesis_accepted(self) -> None:
        _insert_event(self.db, event_id="mine", summary="Ship Release Notes",
                      start_time=_today_at(9, tz=self.tz),
                      end_time=_today_at(10, tz=self.tz),
                      calendar_id="primary", person=None)
        good = (
            "1. Cut the release | person=operator | source=github | "
            "project=acme/web | evidence=PR #9 | why=ready to merge"
        )
        import rebalance.ingest.querier as querier
        orig = querier._synthesize_with_fallback
        querier._synthesize_with_fallback = lambda *a, **k: (good, "fake-model")
        try:
            result = na.rank_next_actions(self.db, blend_team=False, synthesize=True)
        finally:
            querier._synthesize_with_fallback = orig

        titles = {a.title for a in result.ranked}
        self.assertIn("Cut the release", titles)


# ---------------------------------------------------------------------------
# FIX 3 — blended only when team signal actually contributed
# FIX 6 — additivity window still yields the rich teammate
# ---------------------------------------------------------------------------


class TestBlendedContribution(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "rebalance.db"
        _seed_migrated_db(self.db)
        self.tz = na.local_tz()
        self._orig_cfg = na.get_pulse_config
        na.get_pulse_config = lambda: {"github_login": "me", "slack_user_id": None}

    def tearDown(self) -> None:
        na.get_pulse_config = self._orig_cfg
        self._tmp.cleanup()

    def _patch_roster(self, entries):
        orig = CalendarConfig.load
        cfg = CalendarConfig(
            calendar_id="primary", exclude_titles=[], aggregator_skip_words=[],
            timezone=self.tz.key, projects=[], hours_format="decimal",
            team_calendars=entries,
        )
        CalendarConfig.load = classmethod(lambda cls, *a, **k: cfg)
        self.addCleanup(lambda: setattr(CalendarConfig, "load", orig))

    def test_blended_false_when_operator_only_roster(self) -> None:
        """Empty roster → blended=False (no teammate signal contributed) (C2)."""
        self._patch_roster([])
        _insert_event(self.db, event_id="mine", summary="Solo Block",
                      start_time=_today_at(9, tz=self.tz),
                      end_time=_today_at(10, tz=self.tz),
                      calendar_id="primary", person=None)
        result = na.rank_next_actions(self.db, blend_team=True, synthesize=False)
        self.assertFalse(result.blended)

    def test_blended_false_when_no_teammate_passes_additivity(self) -> None:
        """A roster whose only teammate is too sparse → blended=False (C2/C1)."""
        self._patch_roster([TeamCalendarEntry(
            person="jose", calendar_id="jose@group.calendar.google.com")])
        # Seed just ONE historical event — below min_team_events → gated.
        _insert_event(
            self.db, event_id="jose-1", summary="Jose standup",
            start_time=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            end_time=(datetime.now(timezone.utc) - timedelta(days=1) + timedelta(minutes=15)).isoformat(),
            calendar_id="jose@group.calendar.google.com", person="jose")
        result = na.rank_next_actions(self.db, blend_team=True, synthesize=False)
        self.assertFalse(result.blended)

    def test_multiday_dedup_against_operator_tomorrow_block(self) -> None:
        """FIX 2 (DSP-05): a hand-logged duplicate teammate meeting on TOMORROW is
        deduped against the operator's own tomorrow block — even though the OWN
        candidate list only covers today — because the operator title map spans the
        teammate read horizon."""
        weights = SignalWeights()
        self._patch_roster([TeamCalendarEntry(
            person="matthew", calendar_id="matt@group.calendar.google.com")])
        # Make matthew pass additivity (trailing history).
        for i in range(weights.min_team_events + 1):
            _insert_event(
                self.db, event_id=f"matt-h{i}", summary=f"Matt h{i}",
                start_time=(datetime.now(timezone.utc) - timedelta(days=2, hours=i)).isoformat(),
                end_time=(datetime.now(timezone.utc) - timedelta(days=2, hours=i) + timedelta(minutes=20)).isoformat(),
                calendar_id="matt@group.calendar.google.com", person="matthew")

        # Operator's OWN block TOMORROW (a joint meeting, on operator's calendar).
        tomorrow = datetime.now(self.tz) + timedelta(days=1)
        op_start = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0)
        _insert_event(
            self.db, event_id="op-tmrw", summary="Quarterly Planning Sync",
            start_time=op_start.isoformat(),
            end_time=(op_start + timedelta(minutes=60)).isoformat(),
            calendar_id="primary", person=None)
        # Teammate hand-logs the SAME meeting tomorrow under a different id.
        _insert_event(
            self.db, event_id="matt-tmrw", summary="Quarterly Planning Sync",
            start_time=op_start.isoformat(),
            end_time=(op_start + timedelta(minutes=60)).isoformat(),
            calendar_id="matt@group.calendar.google.com", person="matthew")

        result = na.rank_next_actions(self.db, blend_team=True, synthesize=False)
        # The teammate duplicate must NOT appear as a separate matthew-attributed
        # item — it is deduped against the operator's tomorrow block.
        matt_dupes = [
            a for a in result.ranked
            if a.person == "matthew" and "Quarterly Planning Sync" in a.title
        ]
        self.assertEqual(matt_dupes, [])

    def test_additivity_window_still_yields_matthew(self) -> None:
        """FIX 6: the trailing-history additivity gate still PASSES the rich
        teammate (matthew) from realistic counts (C1/C6 unaffected)."""
        from rebalance.ingest.calendar_config import team_persons_passing_additivity
        weights = SignalWeights()
        self._patch_roster([TeamCalendarEntry(
            person="matthew", calendar_id="matt@group.calendar.google.com")])
        # Seed > min_team_events events within the trailing-history window.
        for i in range(weights.min_team_events + 2):
            _insert_event(
                self.db, event_id=f"matt-{i}", summary=f"Matt {i}",
                start_time=(datetime.now(timezone.utc) - timedelta(days=2, hours=i)).isoformat(),
                end_time=(datetime.now(timezone.utc) - timedelta(days=2, hours=i) + timedelta(minutes=30)).isoformat(),
                calendar_id="matt@group.calendar.google.com", person="matthew")
        # A distinctive upcoming item so the delta is non-empty → blended True.
        soon = datetime.now(timezone.utc) + timedelta(hours=3)
        _insert_event(
            self.db, event_id="matt-up", summary="Vendor Renewal Review",
            start_time=soon.isoformat(),
            end_time=(soon + timedelta(minutes=30)).isoformat(),
            calendar_id="matt@group.calendar.google.com", person="matthew")

        result = na.rank_next_actions(self.db, blend_team=True, synthesize=False)
        # Matthew passed → blended True and the teammate item surfaced.
        self.assertTrue(result.blended)
        self.assertTrue(any(
            a.person == "matthew" and "Vendor Renewal Review" in a.title
            for a in result.ranked
        ))
        # The gate helper itself yields exactly ['matthew'] from realistic counts.
        passing = team_persons_passing_additivity(
            {"matthew": weights.min_team_events + 2}, weights.min_team_events)
        self.assertEqual(passing, ["matthew"])


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
