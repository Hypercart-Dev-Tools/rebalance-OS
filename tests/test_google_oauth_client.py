"""Contract tests for the shared Google OAuth client credentials module.

Written BEFORE the credential extraction (Phase 1 QA: contract tests land
before module movement). Verifies the shared module produces the same decoded
values that the original per-script constants produced.
"""

from __future__ import annotations

import base64
import unittest

# The values the two scripts embedded before extraction — golden reference.
_GOLDEN_CID_B64 = "NDA5Mjk4MzQxOTg1LTFrdWI0dTFiMWJkMGxlZWEzYjc0ZDR2bW81Y3F2NzV0LmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29t"
_GOLDEN_CS_B64  = "R09DU1BYLWNxWTA3a0VBZDJTTHM5RWg2MDRqV2NYRGxpQXo="
_GOLDEN_CID     = base64.b64decode(_GOLDEN_CID_B64).decode()
_GOLDEN_CS      = base64.b64decode(_GOLDEN_CS_B64).decode()


class GoogleOAuthCredentialsContractTests(unittest.TestCase):
    """build_google_oauth_client_config() must reproduce the original constants."""

    def _config(self) -> dict:
        from rebalance.ingest.google_oauth_client import build_google_oauth_client_config
        return build_google_oauth_client_config()

    def test_returns_installed_key(self) -> None:
        cfg = self._config()
        self.assertIn("installed", cfg)

    def test_client_id_matches_golden(self) -> None:
        cfg = self._config()
        self.assertEqual(cfg["installed"]["client_id"], _GOLDEN_CID)

    def test_client_secret_matches_golden(self) -> None:
        cfg = self._config()
        self.assertEqual(cfg["installed"]["client_secret"], _GOLDEN_CS)

    def test_auth_uri(self) -> None:
        cfg = self._config()
        self.assertEqual(cfg["installed"]["auth_uri"], "https://accounts.google.com/o/oauth2/auth")

    def test_token_uri(self) -> None:
        cfg = self._config()
        self.assertEqual(cfg["installed"]["token_uri"], "https://oauth2.googleapis.com/token")

    def test_redirect_uris_contains_localhost(self) -> None:
        cfg = self._config()
        self.assertIn("http://localhost", cfg["installed"]["redirect_uris"])

    def test_idempotent_calls_return_equal_dicts(self) -> None:
        from rebalance.ingest.google_oauth_client import build_google_oauth_client_config
        self.assertEqual(build_google_oauth_client_config(), build_google_oauth_client_config())


class AuthLogFlowSourceTests(unittest.TestCase):
    """log_flow_started/succeeded/failed must accept a source kwarg (Phase 1)."""

    def test_log_flow_started_accepts_source_kwarg(self) -> None:
        import inspect
        from rebalance.ingest.auth_log import log_flow_started
        sig = inspect.signature(log_flow_started)
        self.assertIn("source", sig.parameters)

    def test_log_flow_succeeded_accepts_source_kwarg(self) -> None:
        import inspect
        from rebalance.ingest.auth_log import log_flow_succeeded
        sig = inspect.signature(log_flow_succeeded)
        self.assertIn("source", sig.parameters)

    def test_log_flow_failed_accepts_source_kwarg(self) -> None:
        import inspect
        from rebalance.ingest.auth_log import log_flow_failed
        sig = inspect.signature(log_flow_failed)
        self.assertIn("source", sig.parameters)

    def test_default_source_is_calendar(self) -> None:
        import inspect
        from rebalance.ingest.auth_log import log_flow_started
        sig = inspect.signature(log_flow_started)
        default = sig.parameters["source"].default
        self.assertEqual(default, "calendar")

    def test_gmail_setup_emits_gmail_source(self) -> None:
        """setup_gmail_oauth passes source='gmail' — verify the call signature accepts it."""
        import os, tempfile, json
        from rebalance.ingest.auth_log import log_flow_started
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("REBALANCE_AUTH_LOG_DIR")
            os.environ["REBALANCE_AUTH_LOG_DIR"] = tmp
            try:
                log_flow_started(["https://mail.googleapis.com/auth/gmail.readonly"], source="gmail")
                log_path = next(iter(p for p in __import__("pathlib").Path(tmp).glob("*.jsonl")), None)
                if log_path is None:
                    log_path = __import__("pathlib").Path(tmp) / "auth_activity.jsonl"
                entries = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
                self.assertEqual(entries[-1]["source"], "gmail")
                self.assertEqual(entries[-1]["event"], "flow_started")
            finally:
                if old is None:
                    os.environ.pop("REBALANCE_AUTH_LOG_DIR", None)
                else:
                    os.environ["REBALANCE_AUTH_LOG_DIR"] = old


class ProjectRootFindTests(unittest.TestCase):
    """paths.find_project_root() must be public and match old config._project_root_from() semantics."""

    def test_find_project_root_is_importable(self) -> None:
        from rebalance.paths import find_project_root
        self.assertTrue(callable(find_project_root))

    def test_returns_none_for_non_project_dir(self) -> None:
        import tempfile
        from rebalance.paths import find_project_root
        with tempfile.TemporaryDirectory() as tmp:
            result = find_project_root(__import__("pathlib").Path(tmp) / "deep" / "dir")
            self.assertIsNone(result)

    def test_returns_path_for_project_root(self) -> None:
        from rebalance.paths import find_project_root
        from pathlib import Path
        # Start from this file — the repo has .git so should resolve
        result = find_project_root(Path(__file__))
        self.assertIsNotNone(result)
        self.assertTrue((result / ".git").exists() or (result / "pyproject.toml").exists())


if __name__ == "__main__":
    unittest.main()
