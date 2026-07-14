"""Round-trip tests for querier.ask — pins the QueryResult field contract.

Risk-table mitigation: a renamed QueryResult field breaks retrieval.py and
cli/query.py silently (both re-serialize by field name with no shared helper).
These tests must pass before any field rename.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest.db import db_connection, ensure_schema, ensure_calendar_schema
from rebalance.ingest.querier import ask, QueryResult


_FAKE_GITHUB_ROW = {
    "project_name": "acme/widget",
    "total_commits": 3,
    "prs_opened": 1,
    "prs_merged": 1,
    "issues_opened": 0,
    "is_idle": False,
}

_FAKE_VAULT_HIT = {
    "title": "Planning Note",
    "heading": "Q2",
    "body_preview": "some body",
    "similarity_score": 0.88,
    "source_type": "vault",
}


def _minimal_db(tmp_dir: str) -> Path:
    db_path = Path(tmp_dir) / "rebalance.db"
    with db_connection(db_path, ensure_schema) as conn:
        ensure_calendar_schema(conn)
    return db_path


class QueryResultContractTests(unittest.TestCase):
    """Structural contract: every field on QueryResult must be present and typed."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._db = _minimal_db(self._tmp.name)

    def _ask(self, **overrides):
        defaults = dict(
            query="what is the status",
            database_path=self._db,
            skip_synthesis=True,
        )
        defaults.update(overrides)
        return ask(**defaults)

    def test_returns_query_result_instance(self) -> None:
        result = self._ask()
        self.assertIsInstance(result, QueryResult)

    def test_query_field_echoed(self) -> None:
        result = self._ask(query="ping")
        self.assertEqual(result.query, "ping")

    def test_skip_synthesis_leaves_synthesis_empty(self) -> None:
        result = self._ask()
        self.assertEqual(result.synthesis, "")
        self.assertEqual(result.model_used, "")

    def test_elapsed_seconds_non_negative(self) -> None:
        result = self._ask()
        self.assertGreaterEqual(result.elapsed_seconds, 0)

    def test_temporal_context_top_level_keys(self) -> None:
        """temporal_context must have 'today' and 'tomorrow' — keys MCP serializer reads."""
        result = self._ask()
        self.assertIn("today", result.temporal_context)
        self.assertIn("tomorrow", result.temporal_context)

    def test_temporal_context_today_field_shape(self) -> None:
        """today dict must carry date, day_name, day_type, is_weekend, is_vacation, vacation_event."""
        result = self._ask()
        today = result.temporal_context["today"]
        for key in ("date", "day_name", "day_type", "is_weekend", "is_vacation", "vacation_event"):
            self.assertIn(key, today, msg=f"today is missing key '{key}'")

    def test_temporal_context_tomorrow_field_shape(self) -> None:
        result = self._ask()
        tomorrow = result.temporal_context["tomorrow"]
        for key in ("date", "day_name", "day_type", "is_weekend", "is_vacation", "vacation_event"):
            self.assertIn(key, tomorrow, msg=f"tomorrow is missing key '{key}'")

    def test_temporal_context_day_type_is_valid_string(self) -> None:
        result = self._ask()
        valid = {"workday", "off", "vacation"}
        self.assertIn(result.temporal_context["today"]["day_type"], valid)
        self.assertIn(result.temporal_context["tomorrow"]["day_type"], valid)

    def test_list_fields_are_lists(self) -> None:
        result = self._ask()
        for field in (
            "vault_context",
            "github_context",
            "github_semantic_context",
            "project_context",
            "vault_activity",
        ):
            self.assertIsInstance(getattr(result, field), list, msg=f"{field} should be list")

    def test_calendar_context_is_dict_with_upcoming_and_recent(self) -> None:
        result = self._ask()
        self.assertIsInstance(result.calendar_context, dict)
        self.assertIn("upcoming", result.calendar_context)
        self.assertIn("recent", result.calendar_context)


class GithubContextRowShapeTests(unittest.TestCase):
    """When github_context is non-empty, each row must carry the required keys."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._db = _minimal_db(self._tmp.name)

    def test_github_context_row_has_required_keys(self) -> None:
        with patch(
            "rebalance.ingest.querier._gather_github_context",
            return_value=[_FAKE_GITHUB_ROW],
        ):
            result = ask("status", self._db, skip_synthesis=True)

        self.assertEqual(len(result.github_context), 1)
        row = result.github_context[0]
        for key in ("total_commits", "prs_opened", "issues_opened"):
            self.assertIn(key, row, msg=f"github_context row missing key '{key}'")

    def test_github_context_is_idle_flag_present(self) -> None:
        with patch(
            "rebalance.ingest.querier._gather_github_context",
            return_value=[_FAKE_GITHUB_ROW],
        ):
            result = ask("status", self._db, skip_synthesis=True)

        self.assertIn("is_idle", result.github_context[0])


class McpSerializationContractTests(unittest.TestCase):
    """The MCP ask tool re-serializes QueryResult by field name — all keys must survive."""

    # GH-125 (D1): the QueryResult contract was DELIBERATELY BUMPED to carry the
    # first-class `hiqs` field — the persisted HiQS ranked verdict. This replaces
    # the rejected NEXT_ACTIONS_ATTR sidecar.
    EXPECTED_KEYS = {
        "query",
        "synthesis",
        "vault_context",
        "github_context",
        "github_semantic_context",
        "project_context",
        "vault_activity",
        "calendar_context",
        "temporal_context",
        "hiqs",
        "model_used",
        "elapsed_seconds",
    }

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._db = _minimal_db(self._tmp.name)

    def test_mcp_serialization_preserves_all_keys(self) -> None:
        """Replicate exactly what retrieval.py:ask does — any rename breaks MCP at runtime."""
        result = ask("ping", self._db, skip_synthesis=True)
        serialized = {
            "query": result.query,
            "synthesis": result.synthesis,
            "vault_context": result.vault_context,
            "github_context": result.github_context,
            "github_semantic_context": result.github_semantic_context,
            "project_context": result.project_context,
            "vault_activity": result.vault_activity,
            "calendar_context": result.calendar_context,
            "temporal_context": result.temporal_context,
            "hiqs": result.hiqs,
            "model_used": result.model_used,
            "elapsed_seconds": result.elapsed_seconds,
        }
        self.assertEqual(set(serialized.keys()), self.EXPECTED_KEYS)

    def test_idempotent_on_repeated_calls(self) -> None:
        """Running ask twice over the same empty DB must not crash."""
        for _ in range(2):
            result = ask("repeat", self._db, skip_synthesis=True)
            self.assertIsInstance(result, QueryResult)


class HiqsFieldContractTests(unittest.TestCase):
    """GH-125 (D1/D3): `hiqs` is a first-class QueryResult field.

    ``ask()`` reads the PERSISTED ranking via ``load_ranked_next_actions`` (a
    cheap cached read) and exposes it as ``result.hiqs``. It NEVER calls
    ``rank_next_actions`` (no recompute, no Gemini) — the dashboard route is the
    single writer of that cache, so the two surfaces cannot drift.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._db = _minimal_db(self._tmp.name)

    def test_default_path_never_recomputes_the_ranking(self) -> None:
        """Acceptance #5: ask() does NOT recompute the ranking on the default path."""
        with patch("rebalance.ingest.next_actions.rank_next_actions") as mock_rank:
            ask("status", self._db, skip_synthesis=True)
        mock_rank.assert_not_called()

    def test_empty_db_degrades_to_empty_ranking_without_raising(self) -> None:
        """A never-ranked / empty DB → hiqs is an empty ranking, ask() does not raise."""
        result = ask("status", self._db, skip_synthesis=True)
        self.assertIsInstance(result.hiqs, dict)
        self.assertEqual(result.hiqs.get("ranked"), [])

    def test_hiqs_field_carries_the_persisted_verdict(self) -> None:
        """hiqs reflects the persisted ranking read via load_ranked_next_actions."""
        from rebalance.ingest.next_actions import RankedNextActions, RankedAction

        cached = RankedNextActions(
            ranked=[RankedAction(rank=1, title="ship it", person=None, source="github")],
            blended=True,
            note="from-cache",
        )
        with patch(
            "rebalance.ingest.next_actions.load_ranked_next_actions",
            return_value=cached,
        ) as mock_load, patch(
            "rebalance.ingest.next_actions.rank_next_actions",
        ) as mock_rank:
            result = ask("status", self._db, skip_synthesis=True)

        mock_load.assert_called_once()
        mock_rank.assert_not_called()  # cached read only — never a recompute
        self.assertEqual(result.hiqs, cached.as_dict())
        self.assertEqual(result.hiqs["ranked"][0]["title"], "ship it")

    def test_hiqs_read_failure_never_breaks_ask(self) -> None:
        """A failing cached read degrades to an empty ranking; ask() still returns."""
        with patch(
            "rebalance.ingest.next_actions.load_ranked_next_actions",
            side_effect=RuntimeError("boom"),
        ):
            result = ask("status", self._db, skip_synthesis=True)
        self.assertIsInstance(result, QueryResult)
        self.assertEqual(result.hiqs.get("ranked"), [])


if __name__ == "__main__":
    unittest.main()
