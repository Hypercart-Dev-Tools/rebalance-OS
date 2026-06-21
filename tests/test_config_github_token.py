"""Tests for GitHub token resolution: config first, gh CLI fallback."""

import json
import os
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


def _no_keyring(test_case: unittest.TestCase) -> None:
    """Patch keyring helpers to simulate unavailable keyring (file-only path)."""
    test_case.addCleanup(patch.stopall)
    patch.object(config_module, "_keyring_get", return_value=None).start()
    patch.object(config_module, "_keyring_set", return_value=False).start()
    patch.object(config_module, "_keyring_delete", return_value=False).start()


class GitHubTokenResolutionTests(unittest.TestCase):
    """Cover the four resolution paths: config-set, gh-fallback, neither, explicit-clear."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"
        # Simulate keyring unavailable so these tests exercise the rbos.config path.
        _no_keyring(self)

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_stored_token_wins_over_gh_cli(self) -> None:
        # With keyring unavailable, a set token now resolves from the durable
        # out-of-repo secret store (the preferred launchd-safe fallback), ahead
        # of the gh CLI. Resolution order: keyring → secret-store → config → gh-cli.
        set_github_token("ghp_stored0000")
        with patch.object(config_module, "_try_gh_cli_token", return_value="gho_fromcli0000"):
            token, source = get_github_token_with_source()
        self.assertEqual(token, "ghp_stored0000")
        self.assertEqual(source, "secret-store")

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


class GitHubTokenKeyringTests(unittest.TestCase):
    """Cover the keyring-backed resolution path."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_path = config_module.CONFIG_PATH
        config_module.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path

    def test_keyring_token_wins_over_config(self) -> None:
        """Keyring takes priority over rbos.config."""
        with patch.object(config_module, "_keyring_get", return_value="ghp_fromkeyring"), \
             patch.object(config_module, "_keyring_set", return_value=True), \
             patch.object(config_module, "_keyring_delete", return_value=True):
            token, source = get_github_token_with_source()
        self.assertEqual(token, "ghp_fromkeyring")
        self.assertEqual(source, "keyring")

    def test_set_token_writes_to_keyring_and_secret_store_not_config(self) -> None:
        """Phase 2: set_github_token writes keyring + secret store; rbos.config is
        never written. A pre-existing config token is left untouched by `set`
        (it's removed by `migrate_repo_local_secrets`, not by setters).
        """
        from rebalance.ingest import secret_store
        # Pre-seed rbos.config with a legacy token; `set` must NOT touch it.
        cfg_path = config_module.CONFIG_PATH
        cfg_path.write_text('{"github_token": "ghp_legacy"}', encoding="utf-8")

        stored: dict = {}
        def fake_set(key: str, value: str) -> bool:
            stored[key] = value
            return True

        with patch.object(config_module, "_keyring_set", side_effect=fake_set), \
             patch.object(config_module, "_keyring_get", return_value=None):
            set_github_token("ghp_new")

        self.assertEqual(stored.get("github_token"), "ghp_new")              # keyring
        self.assertEqual(secret_store.read_secret_file("github_token"), "ghp_new")  # secret store
        # rbos.config is not written by `set`; the legacy value is left for migration.
        import json as _json
        self.assertEqual(_json.loads(cfg_path.read_text()).get("github_token"), "ghp_legacy")

    def test_auto_migration_moves_token_from_config_to_keyring(self) -> None:
        """On first read, a token in rbos.config is silently migrated to keyring."""
        cfg_path = config_module.CONFIG_PATH
        cfg_path.write_text('{"github_token": "ghp_legacy"}', encoding="utf-8")

        stored: dict = {}
        def fake_set(key: str, value: str) -> bool:
            stored[key] = value
            return True

        with patch.object(config_module, "_keyring_get", return_value=None), \
             patch.object(config_module, "_keyring_set", side_effect=fake_set):
            token, source = get_github_token_with_source()

        self.assertEqual(token, "ghp_legacy")
        self.assertEqual(source, "config")
        self.assertEqual(stored.get("github_token"), "ghp_legacy")


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


class ConfigPathResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_path = config_module.CONFIG_PATH
        self._orig_env = os.environ.get("REBALANCE_CONFIG")
        config_module.CONFIG_PATH = None

    def tearDown(self) -> None:
        config_module.CONFIG_PATH = self._orig_path
        if self._orig_env is None:
            os.environ.pop("REBALANCE_CONFIG", None)
        else:
            os.environ["REBALANCE_CONFIG"] = self._orig_env

    def test_env_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            override = Path(tmpdir) / "override.json"
            os.environ["REBALANCE_CONFIG"] = str(override)
            self.assertEqual(config_module.get_config_path(), override.resolve())

    def test_repo_root_is_discovered_from_cwd(self) -> None:
        os.environ.pop("REBALANCE_CONFIG", None)
        repo_root = Path(__file__).resolve().parents[1]
        expected = repo_root / "temp" / "rbos.config"
        original_cwd = Path.cwd()
        os.chdir(repo_root)
        try:
            self.assertEqual(config_module.get_config_path(), expected.resolve())
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()


class TokenVisibilityWarningTests(unittest.TestCase):
    """The docs' nonexistent `repo:read` scope steered users to public-only
    tokens; setup now warns when a valid token likely can't see private repos."""

    def test_classic_repo_scope_is_clean(self):
        from rebalance.ingest.github_scan import token_visibility_warning

        self.assertIsNone(token_visibility_warning("ghp_x", ["repo", "read:org"]))

    def test_classic_public_only_warns(self):
        from rebalance.ingest.github_scan import token_visibility_warning

        warning = token_visibility_warning("ghp_x", ["public_repo"])
        self.assertIn("INVISIBLE", warning)
        self.assertIn("public_repo", warning)

    def test_fine_grained_gets_default_trap_advisory(self):
        from rebalance.ingest.github_scan import token_visibility_warning

        warning = token_visibility_warning("github_pat_x", [])
        self.assertIn("Public repositories", warning)

    def test_ambient_tokens_without_scopes_get_no_verdict(self):
        from rebalance.ingest.github_scan import token_visibility_warning

        self.assertIsNone(token_visibility_warning("gho_x", []))
