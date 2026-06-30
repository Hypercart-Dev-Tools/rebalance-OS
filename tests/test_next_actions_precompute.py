"""STAGE D — refresh_index precomputes the P2 v0.5 ranked "what next" list.

The NETWORK-ALLOWED side of the precompute->SQLite decision: after the data
collectors refresh, ``refresh_index`` calls ``next_actions.rank_next_actions``
(live Gemini synthesis) and persists the result to the ``ranked_next_actions``
cache the dashboard route + static panel read via ``load_ranked_next_actions``.

These tests monkeypatch ``rank_next_actions`` to return a deterministic
``RankedNextActions`` (no network), and assert:
  - a full/network refresh persists a ranked result that ``load_*`` returns;
  - a ``rank_next_actions`` exception does NOT break refresh_index — it logs,
    records a non-fatal note, and continues.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from rebalance.ingest import next_actions
from rebalance.ingest.index_ops import (
    COLLECTORS,
    Collector,
    refresh_index,
    register_collector,
)
from rebalance.ingest.next_actions import (
    RankedAction,
    RankedNextActions,
    load_ranked_next_actions,
)


def _deterministic_ranked() -> RankedNextActions:
    return RankedNextActions(
        ranked=[
            RankedAction(
                rank=1,
                title="Ship the ranked-next-actions cache",
                person=None,
                source="github",
                project="example/repo",
                evidence=["https://example/pr/1"],
                why="open PR you own",
            )
        ],
        synthesis="1. Ship the ranked-next-actions cache | person=operator | source=github",
        model_used="gemini-test",
        blended=True,
        weights_used={"min_team_events": 3},
        note="deterministic test fixture",
        elapsed_seconds=0.01,
        computed_at="2026-06-17T00:00:00+00:00",
    )


class NextActionsPrecomputeTests(unittest.TestCase):
    def _register_noop_full_refresh_collector(self) -> None:
        """A harmless raw_source collector that `all` expands to, so a full
        refresh runs without real network/tokens."""

        def _noop(db: Path, **opts: Any) -> dict[str, Any]:
            return {"scope": "precompute_probe", "synced": 0}

        register_collector(
            Collector("precompute_probe", _noop, included_in_all=False)
        )

    def test_full_refresh_persists_ranked_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            try:
                self._register_noop_full_refresh_collector()
                with (
                    patch(
                        "rebalance.ingest.index_ops._all_scope_names",
                        return_value=["precompute_probe"],
                    ),
                    patch.object(
                        next_actions,
                        "rank_next_actions",
                        return_value=_deterministic_ranked(),
                    ) as mock_rank,
                ):
                    result = refresh_index(
                        db_path,
                        scope=["all"],
                        dry_run=False,
                        update_dashboard_note=False,
                    )

                # rank_next_actions was invoked on the full/network path with the
                # blend_team + synthesize contract.
                mock_rank.assert_called_once()
                _, kwargs = mock_rank.call_args
                self.assertTrue(kwargs.get("blend_team"))
                self.assertTrue(kwargs.get("synthesize"))

                # A success result is recorded with the structured fields.
                na = next(
                    r for r in result["results"] if r.get("scope") == "next_actions"
                )
                self.assertEqual(na["model_used"], "gemini-test")
                self.assertTrue(na["blended"])
                self.assertEqual(na["count"], 1)

                # The cache the dashboard reads now returns the persisted result.
                loaded = load_ranked_next_actions(db_path)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(loaded.model_used, "gemini-test")
                self.assertEqual(len(loaded.ranked), 1)
                self.assertEqual(
                    loaded.ranked[0].title, "Ship the ranked-next-actions cache"
                )
            finally:
                COLLECTORS.pop("precompute_probe", None)

    def test_precompute_failure_does_not_break_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            try:
                self._register_noop_full_refresh_collector()
                with (
                    patch(
                        "rebalance.ingest.index_ops._all_scope_names",
                        return_value=["precompute_probe"],
                    ),
                    patch.object(
                        next_actions,
                        "rank_next_actions",
                        side_effect=RuntimeError("Gemini 503 / network down"),
                    ),
                ):
                    # Must NOT raise.
                    result = refresh_index(
                        db_path,
                        scope=["all"],
                        dry_run=False,
                        update_dashboard_note=False,
                    )

                # The upstream collector still ran and refresh completed.
                scopes = [r.get("scope") for r in result["results"]]
                self.assertIn("precompute_probe", scopes)

                # The failure is recorded as a non-fatal skipped result, NOT a
                # top-level error (so it never cascades into the dashboard gate).
                na = next(
                    r for r in result["results"] if r.get("scope") == "next_actions"
                )
                self.assertTrue(na.get("skipped"))
                self.assertIn("network down", na.get("error", ""))
                self.assertNotIn(
                    "next_actions",
                    [e.get("scope") for e in result["errors"]],
                )

                # Nothing was persisted to the cache.
                self.assertIsNone(load_ranked_next_actions(db_path))
            finally:
                COLLECTORS.pop("precompute_probe", None)

    def test_full_refresh_writes_vault_file_when_enabled(self) -> None:
        """With update_dashboard_note=True and a vault scope, the precompute
        renders the ranked list to the fixed vault file (vault_path passed
        through to the writer)."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            vault = Path(tmp) / "vault"
            vault.mkdir()
            try:
                self._register_noop_full_refresh_collector()
                with (
                    patch(
                        "rebalance.ingest.index_ops._all_scope_names",
                        return_value=["precompute_probe", "vault"],
                    ),
                    patch(
                        "rebalance.ingest.index_ops.get_vault_path",
                        return_value=str(vault),
                    ),
                    patch.object(
                        next_actions, "rank_next_actions",
                        return_value=_deterministic_ranked(),
                    ),
                ):
                    result = refresh_index(
                        db_path,
                        scope=["all"],
                        dry_run=False,
                        update_dashboard_note=True,
                    )
                target = vault / next_actions.VAULT_NEXT_ACTIONS_RELPATH
                self.assertTrue(target.exists())
                self.assertIn("Ship the ranked-next-actions cache",
                              target.read_text(encoding="utf-8"))
                na = next(r for r in result["results"] if r.get("scope") == "next_actions")
                self.assertIsNotNone(na.get("vault_file"))
                # resolved_vault is .resolve()'d (/tmp -> /private/tmp on macOS).
                self.assertEqual(Path(na["vault_file"]).resolve(), target.resolve())
            finally:
                COLLECTORS.pop("precompute_probe", None)

    def test_vault_write_skipped_when_dashboard_note_disabled(self) -> None:
        """update_dashboard_note=False suppresses the vault write (so the suite
        never clobbers a real vault), while the cache is still persisted."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            vault = Path(tmp) / "vault"
            vault.mkdir()
            try:
                self._register_noop_full_refresh_collector()
                with (
                    patch(
                        "rebalance.ingest.index_ops._all_scope_names",
                        return_value=["precompute_probe", "vault"],
                    ),
                    patch(
                        "rebalance.ingest.index_ops.get_vault_path",
                        return_value=str(vault),
                    ),
                    patch.object(
                        next_actions, "rank_next_actions",
                        return_value=_deterministic_ranked(),
                    ),
                ):
                    refresh_index(
                        db_path,
                        scope=["all"],
                        dry_run=False,
                        update_dashboard_note=False,
                    )
                self.assertFalse((vault / next_actions.VAULT_NEXT_ACTIONS_RELPATH).exists())
                # Cache still written (precompute itself does not gate on the note).
                self.assertIsNotNone(load_ranked_next_actions(db_path))
            finally:
                COLLECTORS.pop("precompute_probe", None)

    def test_dry_run_does_not_precompute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            try:
                self._register_noop_full_refresh_collector()
                with (
                    patch(
                        "rebalance.ingest.index_ops._all_scope_names",
                        return_value=["precompute_probe"],
                    ),
                    patch.object(
                        next_actions, "rank_next_actions"
                    ) as mock_rank,
                ):
                    refresh_index(
                        db_path,
                        scope=["all"],
                        dry_run=True,
                        update_dashboard_note=False,
                    )
                mock_rank.assert_not_called()
            finally:
                COLLECTORS.pop("precompute_probe", None)

    def test_named_scope_does_not_precompute(self) -> None:
        """A read-only/named-scope refresh (not full) must NOT precompute."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            try:
                self._register_noop_full_refresh_collector()
                with patch.object(
                    next_actions, "rank_next_actions"
                ) as mock_rank:
                    refresh_index(
                        db_path,
                        scope=["precompute_probe"],
                        dry_run=False,
                        update_dashboard_note=False,
                    )
                mock_rank.assert_not_called()
            finally:
                COLLECTORS.pop("precompute_probe", None)


if __name__ == "__main__":
    unittest.main()
