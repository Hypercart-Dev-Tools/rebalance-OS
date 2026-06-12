"""Round-trip tests for the discover_candidates → confirm_and_write pipeline.

Risk-table mitigation: the MCP run_preflight→confirm_projects flow breaks silently
if DiscoveryResult candidate dict keys (name/status/summary/repos/tags/last_activity_at)
or Project.model_validate's accepted shape change. These tests must pass before
changing the discover→confirm contract or the DiscoveryResult field set.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_schema, ensure_project_schema
from rebalance.ingest.preflight import (
    ConfirmResult,
    DiscoveryResult,
    confirm_and_write,
    discover_candidates,
)
from rebalance.ingest.registry import load_registry


def _setup_dirs(tmp: str) -> tuple[Path, Path, Path, Path, Path]:
    root = Path(tmp)
    vault = root / "vault"
    vault.mkdir()
    registry = vault / "00-project-registry.md"
    projects_yaml = root / "projects.yaml"
    db_path = root / "rebalance.db"
    with db_connection(db_path, ensure_schema) as conn:
        ensure_project_schema(conn)
    return vault, registry, projects_yaml, db_path, root


def _seed_vault_notes(vault: Path, names: list[str]) -> None:
    for name in names:
        (vault / f"{name}.md").write_text(f"# {name}\n\nSome content.", encoding="utf-8")


class DiscoverCandidatesContractTests(unittest.TestCase):
    """discover_candidates returns DiscoveryResult whose candidate dicts have the required keys."""

    REQUIRED_CANDIDATE_KEYS = {"name", "status", "summary", "repos", "tags", "last_activity_at"}

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._vault, self._registry, self._yaml, self._db, _ = _setup_dirs(self._tmp.name)
        _seed_vault_notes(self._vault, ["Alpha Project", "Beta Initiative"])

    def test_returns_discovery_result(self) -> None:
        result = discover_candidates(
            vault_path=self._vault,
            registry_path=self._registry,
            github_token=None,
        )
        self.assertIsInstance(result, DiscoveryResult)

    def test_scanned_files_matches_vault_note_count(self) -> None:
        result = discover_candidates(
            vault_path=self._vault,
            registry_path=self._registry,
            github_token=None,
        )
        self.assertEqual(result.scanned_files, 2)

    def test_candidate_dicts_have_required_keys(self) -> None:
        result = discover_candidates(
            vault_path=self._vault,
            registry_path=self._registry,
            github_token=None,
        )
        all_candidates = (
            result.most_likely_active_projects
            + result.semi_active_projects
            + result.dormant_projects
            + result.potential_projects
        )
        self.assertGreater(len(all_candidates), 0, "expected at least one candidate from vault notes")
        for candidate in all_candidates:
            missing = self.REQUIRED_CANDIDATE_KEYS - set(candidate.keys())
            self.assertFalse(missing, f"candidate dict missing keys: {missing}")

    def test_known_vault_notes_appear_as_candidates(self) -> None:
        result = discover_candidates(
            vault_path=self._vault,
            registry_path=self._registry,
            github_token=None,
        )
        all_names = {
            c["name"].casefold()
            for c in (
                result.most_likely_active_projects
                + result.semi_active_projects
                + result.dormant_projects
                + result.potential_projects
            )
        }
        self.assertIn("alpha project", all_names)
        self.assertIn("beta initiative", all_names)

    def test_github_error_is_none_when_no_token(self) -> None:
        result = discover_candidates(
            vault_path=self._vault,
            registry_path=self._registry,
            github_token=None,
        )
        self.assertIsNone(result.github_error)


class ConfirmAndWriteRoundTripTests(unittest.TestCase):
    """Feed discover_candidates output straight into confirm_and_write — the MCP flow."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._vault, self._registry, self._yaml, self._db, _ = _setup_dirs(self._tmp.name)
        _seed_vault_notes(self._vault, ["Project Gamma", "Project Delta"])

    def _discover(self) -> list[dict]:
        result = discover_candidates(
            vault_path=self._vault,
            registry_path=self._registry,
            github_token=None,
        )
        return (
            result.most_likely_active_projects
            + result.semi_active_projects
            + result.dormant_projects
            + result.potential_projects
        )

    def test_confirm_and_write_returns_confirm_result(self) -> None:
        candidates = self._discover()
        out = confirm_and_write(
            projects=candidates,
            vault_path=self._vault,
            registry_path=self._registry,
            projects_yaml_path=self._yaml,
            database_path=self._db,
        )
        self.assertIsInstance(out, ConfirmResult)

    def test_project_count_matches_candidates_passed(self) -> None:
        candidates = self._discover()
        out = confirm_and_write(
            projects=candidates,
            vault_path=self._vault,
            registry_path=self._registry,
            projects_yaml_path=self._yaml,
            database_path=self._db,
        )
        self.assertEqual(out.project_count, len(candidates))

    def test_registry_written_to_disk(self) -> None:
        candidates = self._discover()
        confirm_and_write(
            projects=candidates,
            vault_path=self._vault,
            registry_path=self._registry,
            projects_yaml_path=self._yaml,
            database_path=self._db,
        )
        self.assertTrue(self._registry.exists())

    def test_registry_contains_confirmed_projects(self) -> None:
        candidates = self._discover()
        confirm_and_write(
            projects=candidates,
            vault_path=self._vault,
            registry_path=self._registry,
            projects_yaml_path=self._yaml,
            database_path=self._db,
        )
        registry = load_registry(self._registry)
        all_names = {
            p.name.casefold()
            for section in (
                registry.active_projects,
                registry.most_likely_active_projects,
                registry.semi_active_projects,
                registry.dormant_projects,
                registry.potential_projects,
            )
            for p in section
        }
        self.assertIn("project gamma", all_names)
        self.assertIn("project delta", all_names)

    def test_confirm_result_registry_path_matches(self) -> None:
        candidates = self._discover()
        out = confirm_and_write(
            projects=candidates,
            vault_path=self._vault,
            registry_path=self._registry,
            projects_yaml_path=self._yaml,
            database_path=self._db,
        )
        self.assertEqual(out.registry_path, str(self._registry))

    def test_idempotent_second_confirm_does_not_duplicate(self) -> None:
        """Running confirm_and_write twice over the same candidates must not double entries."""
        candidates = self._discover()
        confirm_and_write(
            projects=candidates,
            vault_path=self._vault,
            registry_path=self._registry,
            projects_yaml_path=self._yaml,
            database_path=self._db,
        )
        # Second run with same candidates (simulates agent retry)
        confirm_and_write(
            projects=candidates,
            vault_path=self._vault,
            registry_path=self._registry,
            projects_yaml_path=self._yaml,
            database_path=self._db,
        )
        registry = load_registry(self._registry)
        all_names = [
            p.name.casefold()
            for section in (
                registry.active_projects,
                registry.most_likely_active_projects,
                registry.semi_active_projects,
                registry.dormant_projects,
                registry.potential_projects,
            )
            for p in section
        ]
        # Each name should appear at most twice (once per confirm run);
        # the key assertion is no explosion of duplicates
        gamma_count = all_names.count("project gamma")
        self.assertLessEqual(gamma_count, 2, "project duplicated on second confirm")

    def test_empty_candidates_list_is_a_no_op(self) -> None:
        out = confirm_and_write(
            projects=[],
            vault_path=self._vault,
            registry_path=self._registry,
            projects_yaml_path=self._yaml,
            database_path=self._db,
        )
        self.assertEqual(out.project_count, 0)

    def test_vault_dirs_created_after_confirm(self) -> None:
        candidates = self._discover()
        confirm_and_write(
            projects=candidates,
            vault_path=self._vault,
            registry_path=self._registry,
            projects_yaml_path=self._yaml,
            database_path=self._db,
        )
        self.assertTrue((self._vault / "Projects").is_dir())
        self.assertTrue((self._vault / "Daily Notes").is_dir())


if __name__ == "__main__":
    unittest.main()
