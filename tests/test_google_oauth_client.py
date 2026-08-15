"""Contract tests for the operator-supplied Google OAuth client module.

Rewritten for GH-276: rebalance no longer ships a Google OAuth client. The
credentials are read from a file the operator downloads from their own Google
Cloud project, so the contract under test changed from "reproduces the embedded
constants" to "resolves the operator's file, or fails loudly naming every path
it tried".

The old golden-constant assertions were deleted rather than adapted — they
pinned a bundled secret whose whole point was that it no longer exists.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _write_client(directory: Path, *, key: str = "installed", **overrides) -> Path:
    payload = {
        key: {
            "client_id": "test-client.apps.googleusercontent.com",
            "client_secret": "test-secret",
            **overrides,
        }
    }
    path = directory / "google_oauth_client.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class OperatorSuppliedClientTests(unittest.TestCase):
    """build_google_oauth_client_config() reads the operator's own file."""

    def _build(self):
        from rebalance.ingest.google_oauth_client import build_google_oauth_client_config
        return build_google_oauth_client_config()

    def test_reads_client_from_env_pointed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_client(Path(tmp))
            with mock.patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_FILE": str(path)}):
                cfg = self._build()
        self.assertEqual(cfg["installed"]["client_id"], "test-client.apps.googleusercontent.com")
        self.assertEqual(cfg["installed"]["client_secret"], "test-secret")

    def test_defaults_are_filled_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_client(Path(tmp))
            with mock.patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_FILE": str(path)}):
                cfg = self._build()
        self.assertEqual(cfg["installed"]["auth_uri"], "https://accounts.google.com/o/oauth2/auth")
        self.assertEqual(cfg["installed"]["token_uri"], "https://oauth2.googleapis.com/token")
        self.assertIn("http://localhost", cfg["installed"]["redirect_uris"])

    def test_missing_file_raises_naming_every_candidate(self) -> None:
        """The error has to be actionable: silence here is a support ticket."""
        from rebalance.ingest.google_oauth_client import (
            GoogleOAuthClientNotConfigured,
            client_file_candidates,
        )
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "GOOGLE_OAUTH_CLIENT_FILE": str(Path(tmp) / "absent.json"),
                "REBALANCE_SECRETS_DIR": str(Path(tmp) / "secrets"),
            }
            with mock.patch.dict(os.environ, env):
                candidates = client_file_candidates()
                with self.assertRaises(GoogleOAuthClientNotConfigured) as ctx:
                    self._build()
        message = str(ctx.exception)
        for candidate in candidates:
            self.assertIn(str(candidate), message)

    def test_web_client_is_rejected_by_name(self) -> None:
        """A Web client fails later with an opaque redirect_uri mismatch — say it now."""
        from rebalance.ingest.google_oauth_client import GoogleOAuthClientNotConfigured
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_client(Path(tmp), key="web")
            with mock.patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_FILE": str(path)}):
                with self.assertRaises(GoogleOAuthClientNotConfigured) as ctx:
                    self._build()
        self.assertIn("Desktop app", str(ctx.exception))

    def test_malformed_json_raises_configured_error_not_json_error(self) -> None:
        from rebalance.ingest.google_oauth_client import GoogleOAuthClientNotConfigured
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "google_oauth_client.json"
            path.write_text("{ not json", encoding="utf-8")
            with mock.patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_FILE": str(path)}):
                with self.assertRaises(GoogleOAuthClientNotConfigured):
                    self._build()

    def test_no_credential_is_embedded_in_the_module(self) -> None:
        """The regression that matters: a real client must never come back."""
        import rebalance.ingest.google_oauth_client as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("apps.googleusercontent.com\"", source)
        self.assertNotIn("GOCSPX-", source)
        self.assertNotIn("base64", source)


class ShippedTemplateTests(unittest.TestCase):
    """The committed template must stay a template."""

    def _template(self) -> Path:
        from rebalance.paths import find_project_root
        root = find_project_root(Path(__file__))
        assert root is not None
        return root / "google_oauth_client.example.json"

    def test_template_exists_and_parses(self) -> None:
        data = json.loads(self._template().read_text(encoding="utf-8"))
        self.assertIn("installed", data)

    def test_template_holds_no_real_credential(self) -> None:
        data = json.loads(self._template().read_text(encoding="utf-8"))
        self.assertIn("REPLACE-ME", data["installed"]["client_id"])
        self.assertEqual(data["installed"]["client_secret"], "REPLACE-ME")


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
