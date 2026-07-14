"""CROSS-SURFACE PARITY — the dashboard route and ask() cannot diverge.

The P2 v0.5 keystone is ``next_actions.rank_next_actions``, persisted to the
local ``ranked_next_actions`` cache. GH-125 makes the parity STRUCTURAL: there
is ONE cache, ONE writer, ONE reader.

  - The dashboard route ``web.whatsnext_page`` (its ``?refresh`` path is the only
    network-allowed synthesis path) is the WRITER: it calls ``rank_next_actions``
    then ``persist_ranked_next_actions``.
  - ``querier.ask()`` is the READER: it reads the persisted verdict via
    ``load_ranked_next_actions`` and exposes it as the first-class ``hiqs`` field.
    It NEVER calls ``rank_next_actions`` — no recompute, no second Gemini call.

Because the reader consumes exactly what the writer persisted, the two surfaces
are structurally incapable of showing a different ranking for the same DB. If a
future edit makes ``ask()`` recompute, or makes the route target a different DB
or drop ``blend_team``, the assertions below fail.
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
from rebalance.ingest.querier import ask
from rebalance.web import whatsnext_page


def _minimal_db(tmpdir: str) -> Path:
    """A schema-only SQLite DB — enough for both surfaces to run end to end."""
    db = Path(tmpdir) / "rebalance.db"
    with db_connection(db) as conn:
        ensure_schema(conn)
        ensure_calendar_schema(conn)
        conn.commit()
    return db


class CrossSurfaceParityTests(unittest.TestCase):
    """The route WRITES the ranked cache; ask() READS it — they cannot drift."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._db = _minimal_db(self._tmp.name)

    def test_route_writes_ranked_cache_with_blend_team(self) -> None:
        """The dashboard ``?refresh`` path ranks with blend_team=True then persists.

        ``resolve_database_path`` is patched (at its source, ``rebalance.paths``)
        to the test DB and ``persist_ranked_next_actions`` to a no-op so nothing
        touches the network or rewrites the cache.
        """
        with patch(
            "rebalance.paths.resolve_database_path", return_value=self._db
        ), patch(
            "rebalance.ingest.next_actions.persist_ranked_next_actions"
        ) as mock_persist, patch(
            "rebalance.ingest.next_actions.rank_next_actions",
            return_value=RankedNextActions(),
        ) as mock_rank:
            whatsnext_page(refresh=True)

        mock_rank.assert_called_once()
        call = mock_rank.call_args
        db_arg = call.kwargs.get("database_path")
        if db_arg is None and call.args:
            db_arg = call.args[0]
        self.assertEqual(db_arg, self._db)
        self.assertTrue(call.kwargs.get("blend_team"))
        mock_persist.assert_called_once()  # the route is the cache WRITER

    def test_ask_reads_persisted_cache_and_never_recomputes(self) -> None:
        """ask() reads the persisted verdict via load_ranked_next_actions ONLY.

        It must target the SAME DB and must NOT call rank_next_actions — the
        reader consumes exactly what the route wrote, so no drift is possible.
        """
        sentinel = RankedNextActions(note="persisted", blended=True)
        with patch(
            "rebalance.ingest.next_actions.load_ranked_next_actions",
            return_value=sentinel,
        ) as mock_load, patch(
            "rebalance.ingest.next_actions.rank_next_actions",
        ) as mock_rank:
            result = ask("status", self._db, skip_synthesis=True)

        mock_load.assert_called_once()
        load_call: Any = mock_load.call_args
        db_arg = load_call.args[0] if load_call.args else load_call.kwargs.get("database_path")
        self.assertEqual(db_arg, self._db)
        mock_rank.assert_not_called()  # READER never recomputes
        self.assertEqual(result.hiqs, sentinel.as_dict())


if __name__ == "__main__":
    unittest.main()
