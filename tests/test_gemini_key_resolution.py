"""get_gemini_api_key must resolve the key via the gcloud CLI as documented.

Regression for the locked-design mismatch: the resolver only used the optional
google-cloud-secret-manager Python package. On a machine that can reach the
secret via `gcloud secrets versions access` but lacks the package/env, ask()
silently fell back to local Qwen. A gcloud fallback (the P2-decision-#5 pattern)
now resolves the key — but only as a last resort, so env-var setups pay nothing.
"""

import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rebalance.ingest import config as cfg


class GcloudHelperTests(unittest.TestCase):
    def test_returns_secret_when_gcloud_succeeds(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/gcloud"), \
             patch("subprocess.run", return_value=SimpleNamespace(stdout="KEY123\n")):
            self.assertEqual(cfg._gemini_key_via_gcloud("proj", "gemini-api-key"), "KEY123")

    def test_none_when_gcloud_absent(self) -> None:
        with patch("shutil.which", return_value=None):
            self.assertIsNone(cfg._gemini_key_via_gcloud("proj", "gemini-api-key"))

    def test_none_when_gcloud_errors(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/gcloud"), \
             patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "gcloud")):
            self.assertIsNone(cfg._gemini_key_via_gcloud("proj", "gemini-api-key"))

    def test_none_when_secret_empty(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/gcloud"), \
             patch("subprocess.run", return_value=SimpleNamespace(stdout="  \n")):
            self.assertIsNone(cfg._gemini_key_via_gcloud("proj", "gemini-api-key"))

    def test_project_flag_passed_through(self) -> None:
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return SimpleNamespace(stdout="K\n")

        with patch("shutil.which", return_value="/usr/bin/gcloud"), \
             patch("subprocess.run", side_effect=fake_run):
            cfg._gemini_key_via_gcloud("my-proj", "my-secret")
        self.assertIn("--project", seen["cmd"])
        self.assertIn("my-proj", seen["cmd"])
        self.assertIn("my-secret", seen["cmd"])


class GetGeminiApiKeyOrderTests(unittest.TestCase):
    def test_falls_back_to_gcloud_when_nothing_else_resolves(self) -> None:
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(cfg, "_gemini_key_via_gcloud", return_value="FROM_GCLOUD") as gc:
            self.assertEqual(cfg.get_gemini_api_key(), "FROM_GCLOUD")
            gc.assert_called_once()

    def test_env_var_short_circuits_before_gcloud(self) -> None:
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "ENVKEY"}, clear=True), \
             patch.object(cfg, "_gemini_key_via_gcloud", return_value="SHOULD_NOT_BE_USED") as gc:
            self.assertEqual(cfg.get_gemini_api_key(), "ENVKEY")
            gc.assert_not_called()

    def test_gemini_api_key_env_preferred(self) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "G", "GOOGLE_API_KEY": "GG"}, clear=True), \
             patch.object(cfg, "_gemini_key_via_gcloud", return_value=None):
            self.assertEqual(cfg.get_gemini_api_key(), "G")


if __name__ == "__main__":
    unittest.main()
