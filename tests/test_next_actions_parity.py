"""CROSS-SURFACE PARITY — the dashboard route and ask(team=True) cannot diverge.

The P2 v0.5 keystone is ``next_actions.rank_next_actions``: BOTH consumer
surfaces that produce the ranked "what should we work on next" list must obtain
it from that single function with IDENTICAL arguments, so the two can never show
a different ranking for the same operator/DB.

The two surfaces are:
  - the dashboard route handler ``web.whatsnext_page`` (its ``?refresh`` path is
    the only network-allowed synthesis path; it calls ``rank_next_actions`` then
    persists), and
  - ``querier.ask(team=True)`` (the MCP/CLI surface; stashes the ranked result on
    the QueryResult sidecar).

Both import ``rank_next_actions`` from ``rebalance.ingest.next_actions`` at call
time, so a single patch of that attribute captures EVERY surface's call args with
no network and no DB writes. The test then asserts the captured args are equal:
same ``database_path``, ``blend_team=True``, and the same ``weights`` (neither
surface passes ``weights``, so both default to ``None`` — captured identically).
If a future edit makes one surface pass a different db, drop ``blend_team``, or
sneak in a custom ``weights``, the equality assertion fails.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from rebalance.ingest.db import (
    db_connection,
    ensure_calendar_schema,
    ensure_schema,
)
from rebalance.ingest.next_actions import RankedNextActions
from rebalance.ingest.querier import NEXT_ACTIONS_ATTR, ask
from rebalance.web import whatsnext_page


def _minimal_db(tmpdir: str) -> Path:
    """A schema-only SQLite DB — enough for both surfaces to run end to end."""
    db = Path(tmpdir) / "rebalance.db"
    with db_connection(db) as conn:
        ensure_schema(conn)
        ensure_calendar_schema(conn)
        conn.commit()
    return db


def _normalize(call: Any, db: Path) -> dict[str, Any]:
    """Reduce a captured ``rank_next_actions`` call to its identity-defining args.

    Tolerates ``database_path`` being passed positionally (route: ``rank(db, ...)``)
    or by keyword. The identity is ``(database_path, blend_team, weights)`` — the
    three args that decide WHICH ranking is produced for a DB.
    """
    db_arg = call.kwargs.get("database_path")
    if db_arg is None and call.args:
        db_arg = call.args[0]
    return {
        "database_path": db_arg,
        "blend_team": call.kwargs.get("blend_team"),
        "weights": call.kwargs.get("weights"),
    }


class CrossSurfaceParityTests(unittest.TestCase):
    """Both surfaces must rank from rank_next_actions with identical args."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._db = _minimal_db(self._tmp.name)

    def _capture_ask_call(self) -> dict[str, Any]:
        """Drive ask(team=True) and return its normalized rank_next_actions call."""
        with patch(
            "rebalance.ingest.next_actions.rank_next_actions",
            return_value=RankedNextActions(),
        ) as mock_rank:
            result = ask("status", self._db, skip_synthesis=True, team=True)
        # Sanity: the sidecar surface really did go through rank_next_actions.
        self.assertIsNotNone(getattr(result, NEXT_ACTIONS_ATTR, None))
        mock_rank.assert_called_once()
        return _normalize(mock_rank.call_args, self._db)

    def _capture_route_call(self) -> dict[str, Any]:
        """Drive the dashboard route's refresh (synthesis) path and return its
        normalized rank_next_actions call.

        ``?refresh`` is the network-allowed synthesis path that calls
        rank_next_actions; ``resolve_database_path`` is patched (at its source,
        ``rebalance.paths`` — the route imports it locally) to the test DB and
        ``persist_ranked_next_actions`` to a no-op so nothing touches the network
        or rewrites the cache.
        """
        with patch(
            "rebalance.paths.resolve_database_path", return_value=self._db
        ), patch(
            "rebalance.ingest.next_actions.persist_ranked_next_actions"
        ), patch(
            "rebalance.ingest.next_actions.rank_next_actions",
            return_value=RankedNextActions(),
        ) as mock_rank:
            whatsnext_page(refresh=True)
        mock_rank.assert_called_once()
        return _normalize(mock_rank.call_args, self._db)

    def test_route_and_ask_rank_with_identical_args(self) -> None:
        """The two surfaces obtain their ranked list from rank_next_actions with
        the SAME database_path, blend_team=True, and the same (default) weights —
        so they cannot diverge."""
        ask_call = self._capture_ask_call()
        route_call = self._capture_route_call()

        # Both targeted the test DB.
        self.assertEqual(ask_call["database_path"], self._db)
        self.assertEqual(route_call["database_path"], self._db)
        # Both blended the team arm.
        self.assertTrue(ask_call["blend_team"])
        self.assertTrue(route_call["blend_team"])
        # Neither overrides weights (both default → None), so the same weight set
        # is loaded by the keystone for both surfaces.
        self.assertIsNone(ask_call["weights"])
        self.assertIsNone(route_call["weights"])

        # The load-bearing assertion: the identity-defining arg sets are EQUAL.
        # A future edit that makes one surface pass a different db, drop
        # blend_team, or inject custom weights breaks this.
        self.assertEqual(ask_call, route_call)


if __name__ == "__main__":
    unittest.main()
