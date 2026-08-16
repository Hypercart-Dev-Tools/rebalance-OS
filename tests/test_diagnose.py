"""Tests for the repo diagnostics module (diagnose_repo + live PAT probes).

The live probes route through the shared GitHub client (GH-293): these tests
pin the backwards-stable probe envelopes and the offline funnel verdicts with
an injected fake client — no network.
"""

from __future__ import annotations

import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest import diagnose
from rebalance.ingest._http import GitHubHTTPError


def _client_cls(result=None, exc: Exception | None = None) -> type:
    """Build a GitHubClient stand-in returning *result* or raising *exc*."""

    class _FakeClient:
        def __init__(self, token: str, **_: object) -> None:
            pass

        def get_json(self, path: str):
            if exc is not None:
                raise exc
            return result

    return _FakeClient


class LiveProbeTests(unittest.TestCase):
    def test_repo_probe_success(self) -> None:
        fake = _client_cls(result={"default_branch": "development", "private": True})
        with patch.object(diagnose, "GitHubClient", fake):
            out = diagnose._live_probe_repo("someone/repo", "tok")
        self.assertTrue(out["can_see"])
        self.assertEqual(out["status"], 200)
        self.assertEqual(out["default_branch"], "development")
        self.assertTrue(out["private"])

    def test_repo_probe_http_error_maps_status(self) -> None:
        exc = GitHubHTTPError("GitHub API request failed: 404", status=404)
        with patch.object(diagnose, "GitHubClient", _client_cls(exc=exc)):
            out = diagnose._live_probe_repo("someone/repo", "tok")
        self.assertFalse(out["can_see"])
        self.assertEqual(out["status"], 404)
        self.assertIn("404", out["error"])

    def test_repo_probe_network_error_maps_null_status(self) -> None:
        exc = urllib.error.URLError("connection refused")
        with patch.object(diagnose, "GitHubClient", _client_cls(exc=exc)):
            out = diagnose._live_probe_repo("someone/repo", "tok")
        self.assertFalse(out["can_see"])
        self.assertIsNone(out["status"])
        self.assertIn("connection refused", out["error"])

    def test_commit_probe_shape(self) -> None:
        fake = _client_cls(
            result={
                "sha": "abc123",
                "commit": {
                    "message": "first line\nsecond line",
                    "committer": {"date": "2026-08-15T10:00:00Z"},
                },
            },
        )
        with patch.object(diagnose, "GitHubClient", fake):
            out = diagnose._live_probe_commit("someone/repo", "abc123", "tok")
        self.assertTrue(out["exists"])
        self.assertEqual(out["sha"], "abc123")
        self.assertEqual(out["committed_at"], "2026-08-15T10:00:00Z")
        self.assertEqual(out["message_first_line"], "first line")

    def test_pr_probe_shape(self) -> None:
        fake = _client_cls(result={"state": "open", "merged": False, "updated_at": "t", "title": "T"})
        with patch.object(diagnose, "GitHubClient", fake):
            out = diagnose._live_probe_pr("someone/repo", 7, "tok")
        self.assertTrue(out["exists"])
        self.assertFalse(out["merged"])
        self.assertEqual(out["title"], "T")


class DiagnoseRepoFunnelTests(unittest.TestCase):
    """Offline verdicts against an empty temporary database."""

    def test_unknown_repo_is_not_watched_with_registry_next_action(self) -> None:
        result = diagnose.diagnose_repo(self._empty_db(), repo="someone/unknown-repo")
        self.assertEqual(result["verdict"], "not_watched_no_signal")
        self.assertFalse(result["monitoring"]["watched"])
        self.assertFalse(result["monitoring"]["ignored"])
        self.assertTrue(any("registry" in action for action in result["next_actions"]))
        self.assertFalse(result["pat"]["checked"])

    def test_invalid_repo_name_short_circuits(self) -> None:
        result = diagnose.diagnose_repo(self._empty_db(), repo="not-a-repo-name")
        self.assertEqual(result["verdict"], "invalid_input")
        self.assertEqual(result["next_actions"], [])

    def test_live_pat_failure_surfaces_first_next_action(self) -> None:
        probe = {"can_see": False, "status": 404, "error": "Not Found"}
        with patch.object(diagnose, "get_github_token", return_value="tok"), \
             patch.object(diagnose, "_live_probe_repo", return_value=probe):
            result = diagnose.diagnose_repo(self._empty_db(), repo="someone/unknown-repo", live=True)
        self.assertTrue(result["pat"]["checked"])
        self.assertFalse(result["pat"]["can_see"])
        self.assertIn("PAT", result["next_actions"][0])

    def test_live_without_token_reports_missing_token(self) -> None:
        with patch.object(diagnose, "get_github_token", return_value=None):
            result = diagnose.diagnose_repo(self._empty_db(), repo="someone/unknown-repo", live=True)
        self.assertTrue(result["pat"]["checked"])
        self.assertIn("token", result["pat"]["error"])

    def _empty_db(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "diagnose.db"
        from rebalance.ingest.db import db_connection

        with db_connection(path):  # create the empty DB file
            pass
        return path


if __name__ == "__main__":
    unittest.main()
