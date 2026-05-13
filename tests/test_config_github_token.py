"""Tests for GitHub token resolution: config first, gh CLI fallback."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest import config as config_module
from rebalance.ingest.config import (
    add_github_ignored_repo,
    add_github_related_repo,
    clear_github_token,
    get_github_related_repos,
    get_github_token,
    get_github_token_with_source,
    get_github_ignored_repos,
    get_project_priority_rules,
    is_github_repo_ignored,
    remove_github_related_repo,
    remove_github_ignored_repo,
    remove_project_priority_rule,
    set_github_related_repos,
    set_github_token,
    set_github_ignored_repos,
    set_project_priority_rule,
)


class GitHubTokenResolutionTests(unittest.TestCase):
    """Cover the four resolution paths: config-set, gh-fallback, neither, explicit-clear."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # Redirect CONFIG_PATH at the module level so reads/writes hit a scratch file.
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_config_token_wins_when_present(self) -> None:
        set_github_token("ghp_fromconfig0000")
        with patch.object(config_module, "_try_gh_cli_token", return_value="gho_fromcli0000"):
            token, source = get_github_token_with_source()
        self.assertEqual(token, "ghp_fromconfig0000")
        self.assertEqual(source, "config")

    def test_falls_back_to_gh_cli_when_config_missing(self) -> None:
        with patch.object(config_module, "_try_gh_cli_token", return_value="gho_fromcli0000"):
            token, source = get_github_token_with_source()
        self.assertEqual(token, "gho_fromcli0000")
        self.assertEqual(source, "gh-cli")

    def test_returns_none_when_neither_present(self) -> None:
        with patch.object(config_module, "_try_gh_cli_token", return_value=None):
            token, source = get_github_token_with_source()
        self.assertIsNone(token)
        self.assertIsNone(source)

    def test_clear_token_makes_gh_cli_take_over(self) -> None:
        set_github_token("ghp_fromconfig0000")
        clear_github_token()
        with patch.object(config_module, "_try_gh_cli_token", return_value="gho_fromcli0000"):
            token, source = get_github_token_with_source()
        self.assertEqual(token, "gho_fromcli0000")
        self.assertEqual(source, "gh-cli")

    def test_get_github_token_returns_only_token_for_backward_compat(self) -> None:
        set_github_token("ghp_fromconfig0000")
        self.assertEqual(get_github_token(), "ghp_fromconfig0000")


class GhCliFallbackErrorHandlingTests(unittest.TestCase):
    """The fallback must never raise — it has to return None on every failure mode."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"
        # No config token in any of these tests.

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_returns_none_when_gh_not_installed(self) -> None:
        with patch.object(config_module.subprocess, "run", side_effect=FileNotFoundError):
            self.assertIsNone(config_module._try_gh_cli_token())

    def test_returns_none_when_gh_not_authenticated(self) -> None:
        err = subprocess.CalledProcessError(1, ["gh"], stderr="not logged in")
        with patch.object(config_module.subprocess, "run", side_effect=err):
            self.assertIsNone(config_module._try_gh_cli_token())

    def test_returns_none_when_gh_times_out(self) -> None:
        err = subprocess.TimeoutExpired(cmd=["gh"], timeout=5)
        with patch.object(config_module.subprocess, "run", side_effect=err):
            self.assertIsNone(config_module._try_gh_cli_token())

    def test_returns_none_when_gh_outputs_empty_string(self) -> None:
        completed = subprocess.CompletedProcess(args=["gh"], returncode=0, stdout="\n", stderr="")
        with patch.object(config_module.subprocess, "run", return_value=completed):
            self.assertIsNone(config_module._try_gh_cli_token())

    def test_strips_trailing_whitespace(self) -> None:
        completed = subprocess.CompletedProcess(args=["gh"], returncode=0, stdout="ghu_abc123\n", stderr="")
        with patch.object(config_module.subprocess, "run", return_value=completed):
            self.assertEqual(config_module._try_gh_cli_token(), "ghu_abc123")


class GitHubIgnoredReposTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_round_trip_normalizes_dedupes_and_sorts(self) -> None:
        set_github_ignored_repos(["DLT-HUB/dlt", "example/repo", "dlt-hub/dlt"])
        self.assertEqual(get_github_ignored_repos(), ["dlt-hub/dlt", "example/repo"])

    def test_add_remove_and_membership_are_case_insensitive(self) -> None:
        self.assertTrue(add_github_ignored_repo("DLT-HUB/dlt"))
        self.assertFalse(add_github_ignored_repo("dlt-hub/dlt"))
        self.assertTrue(is_github_repo_ignored("dlt-hub/DLT"))
        self.assertTrue(remove_github_ignored_repo("DLT-HUB/dlt"))
        self.assertFalse(is_github_repo_ignored("dlt-hub/dlt"))


class GitHubRelatedReposTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_round_trip_normalizes_dedupes_sorts_and_excludes_self(self) -> None:
        set_github_related_repos(
            "AcmeOrg/sample-child-theme-oct-2024",
            [
                "kissplugins/KISS-woo-order-monitoring-alerts",
                "AcmeOrg/sample-child-theme-oct-2024",
                "KISSPLUGINS/kiss-woo-order-monitoring-alerts",
            ],
        )
        # Lowercase query verifies case-insensitive lookup against the
        # mixed-case stored key.
        self.assertEqual(
            get_github_related_repos("acmeorg/sample-child-theme-oct-2024"),
            ["kissplugins/kiss-woo-order-monitoring-alerts"],
        )

    def test_add_remove_related_repo(self) -> None:
        central = "AcmeOrg/sample-child-theme-oct-2024"
        related = "kissplugins/KISS-woo-fast-search"

        self.assertTrue(add_github_related_repo(central, related))
        self.assertFalse(add_github_related_repo(central, related))
        self.assertEqual(
            get_github_related_repos(central),
            ["kissplugins/kiss-woo-fast-search"],
        )

        self.assertTrue(remove_github_related_repo(central, related))
        self.assertFalse(remove_github_related_repo(central, related))
        self.assertEqual(get_github_related_repos(central), [])


class ProjectPriorityRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_set_list_and_remove_project_priority_rule(self) -> None:
        rule = set_project_priority_rule(
            name="Client Alpha",
            aliases=["Alpha Site", "Alpha Site"],
            client="Alpha",
            priority_tier=1,
            value_score=10,
            value_level="strategic",
            risk_level="high",
        )

        self.assertEqual(rule["aliases"], ["Alpha Site"])
        self.assertEqual(get_project_priority_rules(), [rule])

        self.assertTrue(remove_project_priority_rule("Client Alpha"))
        self.assertFalse(remove_project_priority_rule("Client Alpha"))
        self.assertEqual(get_project_priority_rules(), [])

    def test_invalid_priority_values_raise(self) -> None:
        with self.assertRaises(ValueError):
            set_project_priority_rule(name="Client Alpha", priority_tier=6)
        with self.assertRaises(ValueError):
            set_project_priority_rule(name="Client Alpha", value_score=11)


if __name__ == "__main__":
    unittest.main()
