"""Tests for the Collector registry in index_ops."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from rebalance.ingest.index_ops import (
    COLLECTORS,
    Collector,
    _all_scope_names,
    _scope_values,
    refresh_index,
    register_collector,
)


class CollectorRegistryTests(unittest.TestCase):
    def test_builtin_collectors_registered(self) -> None:
        for name in ("vault", "github", "calendar", "sleuth", "email", "semantic", "sync"):
            self.assertIn(name, COLLECTORS, f"missing built-in collector {name}")

    def test_scope_values_includes_all(self) -> None:
        values = _scope_values()
        self.assertIn("all", values)
        for name in ("vault", "github", "calendar", "sync"):
            self.assertIn(name, values)

    def test_all_scope_is_raw_sources_only(self) -> None:
        # `all` token narrowed to raw incoming sources (Decision A / Phase 1b).
        self.assertEqual(
            sorted(_all_scope_names()),
            sorted(["vault", "github", "calendar", "sleuth", "email"]),
        )

    def test_default_refresh_recipe_includes_follow_on_stages(self) -> None:
        # The no-scope default still runs raw sources + code/semantic/sync.
        from rebalance.ingest.index_ops import _default_refresh_scopes
        self.assertEqual(
            sorted(_default_refresh_scopes()),
            sorted(["vault", "github", "calendar", "sleuth", "email", "code", "semantic", "sync"]),
        )

    def test_register_new_collector_then_unregister(self) -> None:
        calls: list[dict[str, Any]] = []

        def _refresh(db: Path, **opts: Any) -> dict[str, Any]:
            calls.append(opts)
            return {"scope": "linear_test", "dry_run": opts.get("dry_run", False)}

        try:
            register_collector(Collector("linear_test", _refresh, included_in_all=False))
            self.assertIn("linear_test", COLLECTORS)
            # included_in_all=False keeps it OUT of the "all" expansion
            self.assertNotIn("linear_test", _all_scope_names())
            # But it shows up in the full scope-values list
            self.assertIn("linear_test", _scope_values())
            # And calling its refresh works
            result = COLLECTORS["linear_test"].refresh(Path("/tmp/x"), dry_run=True)
            self.assertEqual(result, {"scope": "linear_test", "dry_run": True})
        finally:
            COLLECTORS.pop("linear_test", None)

    def test_duplicate_registration_raises(self) -> None:
        def _refresh(db: Path, **opts: Any) -> dict[str, Any]:
            return {"scope": "vault"}

        with self.assertRaises(ValueError):
            register_collector(Collector("vault", _refresh))

    def test_reserved_name_rejected(self) -> None:
        def _refresh(db: Path, **opts: Any) -> dict[str, Any]:
            return {"scope": "all"}

        with self.assertRaises(ValueError):
            register_collector(Collector("all", _refresh))

    def test_refresh_index_dispatches_through_registry(self) -> None:
        """refresh_index must route scope keys through COLLECTORS, not legacy code."""
        calls: list[tuple[Path, dict[str, Any]]] = []

        def _mock_refresh(db: Path, **opts: Any) -> dict[str, Any]:
            calls.append((db, opts))
            return {"scope": "smoke_test", "synced": 1}

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            try:
                register_collector(
                    Collector("smoke_test", _mock_refresh, included_in_all=False)
                )
                result = refresh_index(
                    db_path,
                    scope=["smoke_test"],
                    dry_run=False,
                    update_dashboard_note=False,
                )
                # The dispatcher must have called our collector exactly once.
                self.assertEqual(len(calls), 1, "collector was not called by refresh_index")
                called_db, called_opts = calls[0]
                self.assertEqual(called_db, db_path.resolve())
                # Result envelope must include our collector's return value.
                scopes_in_result = [r.get("scope") for r in result.get("results", [])]
                self.assertIn("smoke_test", scopes_in_result)
            finally:
                COLLECTORS.pop("smoke_test", None)


if __name__ == "__main__":
    unittest.main()
