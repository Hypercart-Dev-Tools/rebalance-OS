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
        # Patch the key-file step out too — on a real machine the default key
        # file may exist and would resolve before gcloud.
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(cfg, "_gemini_key_from_file", return_value=None), \
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


class PickApiKeyTests(unittest.TestCase):
    def test_extracts_aiza_from_multiline_file(self) -> None:
        # The console-download shape: a project/client id line + the AIza key line.
        aiza = "AIza" + "B" * 35
        self.assertEqual(cfg._pick_api_key(f"gen-lang-client-0383065432\n{aiza}\n"), aiza)

    def test_falls_back_to_first_nonempty_line_for_bare_key(self) -> None:
        self.assertEqual(cfg._pick_api_key("\n  my-bare-key  \nsecond\n"), "my-bare-key")

    def test_none_for_empty_or_blank(self) -> None:
        self.assertIsNone(cfg._pick_api_key(""))
        self.assertIsNone(cfg._pick_api_key("   \n\t\n"))


class KeyFileResolverTests(unittest.TestCase):
    """The key-file step: env path -> config path -> default; AIza extraction."""

    def _write(self, content: str) -> str:
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_reads_key_from_env_path(self) -> None:
        path = self._write("KEYFROMFILE\n")
        with patch.dict(os.environ, {"GEMINI_API_KEY_FILE": path}, clear=True), \
             patch.object(cfg, "get_pulse_config", return_value={}):
            self.assertEqual(cfg._gemini_key_from_file(), "KEYFROMFILE")

    def test_multiline_file_extracts_aiza_key(self) -> None:
        aiza = "AIza" + "C" * 35
        path = self._write(f"gen-lang-client-1\n{aiza}\n")
        with patch.dict(os.environ, {"GEMINI_API_KEY_FILE": path}, clear=True), \
             patch.object(cfg, "get_pulse_config", return_value={}):
            self.assertEqual(cfg._gemini_key_from_file(), aiza)

    def test_uses_config_path_when_no_env(self) -> None:
        path = self._write("CFGKEY\n")
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(cfg, "get_pulse_config", return_value={"gemini_key_file": path}), \
             patch.object(cfg, "DEFAULT_GEMINI_KEY_FILE", "/nonexistent/never.txt"):
            self.assertEqual(cfg._gemini_key_from_file(), "CFGKEY")

    def test_none_when_no_file_resolves(self) -> None:
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(cfg, "get_pulse_config", return_value={}), \
             patch.object(cfg, "DEFAULT_GEMINI_KEY_FILE", "/nonexistent/never.txt"):
            self.assertIsNone(cfg._gemini_key_from_file())

    def test_get_key_uses_file_after_env_before_gcloud(self) -> None:
        path = self._write("FILEKEY\n")
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(cfg, "get_pulse_config", return_value={"gemini_key_file": path}), \
             patch.object(cfg, "DEFAULT_GEMINI_KEY_FILE", "/nonexistent/never.txt"), \
             patch.object(cfg, "_gemini_key_via_gcloud", return_value="GC") as gc:
            self.assertEqual(cfg.get_gemini_api_key(), "FILEKEY")
            gc.assert_not_called()

    def test_env_var_wins_over_key_file(self) -> None:
        path = self._write("FILEKEY\n")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "ENV", "GEMINI_API_KEY_FILE": path}, clear=True):
            self.assertEqual(cfg.get_gemini_api_key(), "ENV")


if __name__ == "__main__":
    unittest.main()
