"""CI guard: no secret-bearing write path may leak a live secret into rbos.config.

Phase 2 moved every credential out of repo-local ``temp/rbos.config`` into the
keyring + out-of-repo secret store. These tests pin that invariant so a future
write path that regresses (writing a secret back into rbos.config) fails CI:

  * the real public setters (github / figma / sleuth) leave rbos.config
    secret-free even when the keyring is unavailable (launchd conditions), and
  * the detector that doctor relies on actually flags a planted leak — so the
    guard above is meaningful, not vacuously green.

The secret store and auth/token-meta logs are redirected to tmp dirs by the
autouse fixtures in conftest.py; only rbos.config needs per-test isolation here.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.doctor import WARN, _check_repo_local_secrets
from rebalance.ingest import config as config_mod


class RepoLocalSecretLeakTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_config_path = config_mod.CONFIG_PATH
        config_mod.CONFIG_PATH = Path(self._tmp.name) / "rbos.config"
        self.addCleanup(self._restore_config_path)

    def _restore_config_path(self) -> None:
        config_mod.CONFIG_PATH = self._orig_config_path

    def test_real_setters_never_leak_into_rbos_config_without_keyring(self) -> None:
        # Simulate a launchd run: no keychain access. The dual store must persist
        # to the secret store only — never to repo-local rbos.config.
        with patch.object(config_mod, "_keyring_set", return_value=False), \
             patch.object(config_mod, "_keyring_get", return_value=None):
            config_mod.set_github_token("ghp_FAKETOKEN_github_0123456789")
            config_mod.set_figma_token("figd_FAKETOKEN_figma_0123456789")
            config_mod.set_sleuth_credentials(
                "https://example.test", "FAKE_sleuth_token", "workspace-x"
            )

            # The contract: nothing secret-bearing is in rbos.config.
            self.assertEqual(config_mod.repo_local_secret_keys_present(), [])

            # And the secret is still resolvable launchd-safe (from the store).
            self.assertEqual(
                config_mod.get_github_token(), "ghp_FAKETOKEN_github_0123456789"
            )

        # Belt-and-braces: the raw file (if written at all) holds no secret value.
        cfg_path = config_mod.CONFIG_PATH
        if cfg_path.exists():
            raw = cfg_path.read_text(encoding="utf-8")
            self.assertNotIn("ghp_FAKETOKEN_github_0123456789", raw)
            self.assertNotIn("figd_FAKETOKEN_figma_0123456789", raw)
            self.assertNotIn("FAKE_sleuth_token", raw)

    def test_detector_flags_a_planted_leak(self) -> None:
        # If a regression *did* write a secret into rbos.config, the detector
        # doctor relies on must catch it — otherwise the guard above is hollow.
        config_mod._write_config({"github_token": "ghp_LEAKED_secret_value"})

        self.assertIn("github_token", config_mod.repo_local_secret_keys_present())
        check = _check_repo_local_secrets()
        self.assertEqual(check.status, WARN)


if __name__ == "__main__":
    unittest.main()
