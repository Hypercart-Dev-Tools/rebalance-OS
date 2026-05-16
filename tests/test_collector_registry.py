"""Tests for the Collector registry in index_ops."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from rebalance.ingest.index_ops import (
    COLLECTORS,
    Collector,
    _all_scope_names,
    _scope_values,
    register_collector,
)


class CollectorRegistryTests(unittest.TestCase):
    def test_builtin_collectors_registered(self) -> None:
        for name in ("vault", "github", "calendar", "sleuth", "email", "semantic"):
            self.assertIn(name, COLLECTORS, f"missing built-in collector {name}")

    def test_scope_values_includes_all(self) -> None:
        values = _scope_values()
        self.assertIn("all", values)
        for name in ("vault", "github", "calendar"):
            self.assertIn(name, values)

    def test_all_scope_includes_default_built_ins(self) -> None:
        names = _all_scope_names()
        self.assertEqual(
            sorted(names),
            sorted(["vault", "github", "calendar", "sleuth", "email", "semantic"]),
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


if __name__ == "__main__":
    unittest.main()
