"""Contract: semantic-maintenance CLI source vocabulary == runtime stage set.

Phase 1 (runtime contract closure) requires that the source set accepted by the
``semantic-*`` maintenance commands match exactly what the runtime ``semantic``
stage actually projects into the unified index — no stage/CLI drift. These tests
pin that invariant so a future hand-edit to one side fails fast.
"""

from __future__ import annotations

import unittest

from rebalance.cli.semantic import _normalize_semantic_sources_option
from rebalance.ingest.index_ops import _all_semantic_sources
from rebalance.ingest.semantic_index import normalize_sources


class SemanticSourceContractTests(unittest.TestCase):
    def test_legal_set_matches_runtime_stage(self) -> None:
        """Every source the runtime stage processes is accepted by the CLI
        validator, and the validator accepts nothing the stage cannot project."""
        stage_sources = set(_all_semantic_sources())
        # Each runtime source individually passes validation.
        accepted = set(normalize_sources(sorted(stage_sources)))
        self.assertEqual(accepted, stage_sources)

    def test_non_semantic_sources_rejected(self) -> None:
        """calendar/sleuth are raw sources the semantic stage does not project,
        so the maintenance CLI must reject them rather than silently no-op."""
        for bogus in ("calendar", "sleuth"):
            with self.assertRaises(ValueError):
                normalize_sources([bogus])

    def test_cli_all_expansion_equals_runtime_stage(self) -> None:
        """``--source all`` resolves to exactly the runtime stage's source set."""
        self.assertEqual(
            _normalize_semantic_sources_option(["all"]),
            _all_semantic_sources(),
        )
        # Empty selection behaves like "all".
        self.assertEqual(
            _normalize_semantic_sources_option([]),
            _all_semantic_sources(),
        )


if __name__ == "__main__":
    unittest.main()
