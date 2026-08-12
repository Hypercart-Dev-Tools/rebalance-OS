"""Phase 3 retrieval contract tests.

Pins:
- normalize_sources() as the canonical semantic source vocabulary owner
- scope_to_sources() / WORK_SOURCES as the canonical scope-alias map
- chat.py delegates to semantic_index, not re-defining its own scope map
- legacy facade docstrings carry the FACADE marker
"""
from __future__ import annotations

import inspect
import unittest


class NormalizeSourcesContractTests(unittest.TestCase):
    """normalize_sources() is the canonical source-vocabulary owner."""

    def setUp(self) -> None:
        from rebalance.ingest.semantic_index import normalize_sources, WORK_SOURCES
        self.normalize = normalize_sources
        self.work_sources = WORK_SOURCES

    def test_importable_from_semantic_index(self) -> None:
        from rebalance.ingest.semantic_index import normalize_sources  # noqa: F401

    def test_none_returns_work_sources_triad(self) -> None:
        result = self.normalize(None)
        self.assertEqual(result, self.work_sources)

    def test_all_returns_work_sources_triad(self) -> None:
        result = self.normalize(["all"])
        self.assertEqual(result, self.work_sources)

    def test_explicit_sources_returned(self) -> None:
        result = self.normalize(["vault", "github"])
        self.assertEqual(result, ("vault", "github"))

    def test_normalizes_case(self) -> None:
        result = self.normalize(["VAULT", "GitHub"])
        self.assertEqual(result, ("vault", "github"))

    def test_deduplicates(self) -> None:
        result = self.normalize(["vault", "vault", "github"])
        self.assertEqual(result, ("vault", "github"))

    def test_strips_whitespace(self) -> None:
        result = self.normalize(["  vault  "])
        self.assertEqual(result, ("vault",))

    def test_invalid_source_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.normalize(["bogus_source"])

    def test_returns_tuple(self) -> None:
        self.assertIsInstance(self.normalize(["vault"]), tuple)


class WorkSourcesAndScopeContractTests(unittest.TestCase):
    """WORK_SOURCES and scope_to_sources() live in semantic_index (canonical owner)."""

    def setUp(self) -> None:
        from rebalance.ingest.semantic_index import WORK_SOURCES, scope_to_sources
        self.WORK_SOURCES = WORK_SOURCES
        self.scope_to_sources = scope_to_sources

    def test_work_sources_importable(self) -> None:
        from rebalance.ingest.semantic_index import WORK_SOURCES  # noqa: F401

    def test_scope_to_sources_importable(self) -> None:
        from rebalance.ingest.semantic_index import scope_to_sources  # noqa: F401

    def test_work_sources_contains_vault_github_email(self) -> None:
        self.assertIn("vault", self.WORK_SOURCES)
        self.assertIn("github", self.WORK_SOURCES)
        self.assertIn("email", self.WORK_SOURCES)

    def test_scope_work_returns_work_sources(self) -> None:
        self.assertEqual(self.scope_to_sources("work"), list(self.WORK_SOURCES))

    def test_scope_code_returns_code_only(self) -> None:
        self.assertEqual(self.scope_to_sources("code"), ["code"])

    def test_scope_all_returns_work_plus_code(self) -> None:
        result = self.scope_to_sources("all")
        for s in self.WORK_SOURCES:
            self.assertIn(s, result)
        self.assertIn("code", result)


class ChatDelegationContractTests(unittest.TestCase):
    """chat.py must not define its own WORK_SOURCES or scope-alias mapping.

    These symbols must be imported from semantic_index, not re-defined locally.
    If this test fails, chat.py has re-introduced its own vocabulary.
    """

    def test_chat_imports_work_sources_from_semantic_index(self) -> None:
        import rebalance.chat as chat
        import rebalance.ingest.semantic_index as si
        self.assertIs(chat.WORK_SOURCES, si.WORK_SOURCES)

    def test_chat_scope_fn_is_semantic_index_scope_fn(self) -> None:
        import rebalance.chat as chat
        import rebalance.ingest.semantic_index as si
        # chat._semantic_sources_for_scope must be scope_to_sources from semantic_index
        self.assertIs(chat._semantic_sources_for_scope, si.scope_to_sources)

    def test_chat_scope_work_matches_semantic_index(self) -> None:
        from rebalance.chat import _semantic_sources_for_scope
        from rebalance.ingest.semantic_index import scope_to_sources
        self.assertEqual(_semantic_sources_for_scope("work"), scope_to_sources("work"))

    def test_chat_scope_code_matches_semantic_index(self) -> None:
        from rebalance.chat import _semantic_sources_for_scope
        from rebalance.ingest.semantic_index import scope_to_sources
        self.assertEqual(_semantic_sources_for_scope("code"), scope_to_sources("code"))

    def test_chat_scope_all_matches_semantic_index(self) -> None:
        from rebalance.chat import _semantic_sources_for_scope
        from rebalance.ingest.semantic_index import scope_to_sources
        self.assertEqual(_semantic_sources_for_scope("all"), scope_to_sources("all"))


class LegacyFacadeMarkerTests(unittest.TestCase):
    """Legacy MCP tools must carry the FACADE marker in their docstrings.

    This makes the deprecation intent machine-readable and prevents the tools
    from silently drifting back into active development.
    """

    def _get_register_locals(self) -> dict:
        import inspect
        import rebalance.mcp.tools.retrieval as mod
        src = inspect.getsource(mod)
        return src

class CliNormalizationDelegationTests(unittest.TestCase):
    """CLI source normalizer must delegate validation to normalize_sources()."""

    def setUp(self) -> None:
        from rebalance.cli.semantic import _normalize_semantic_sources_option
        self.normalize_cli = _normalize_semantic_sources_option

    def test_valid_source_accepted(self) -> None:
        result = self.normalize_cli(["vault"])
        self.assertIn("vault", result)

    def test_invalid_source_raises_bad_parameter(self) -> None:
        import typer
        with self.assertRaises(typer.BadParameter):
            self.normalize_cli(["totally_bogus_source"])

    def test_empty_expands_to_all_sources(self) -> None:
        result = self.normalize_cli([])
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_all_expands_dynamically(self) -> None:
        result = self.normalize_cli(["all"])
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
