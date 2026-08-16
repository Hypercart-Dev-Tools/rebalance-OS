"""Tests for the pulse renderer's assigned-issues GitHub search (GH-293).

fetch_assigned_issues routes through the shared GitHub client; these tests pin
the row mapping and the rate-limit error contract with an injected fake —
no network.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from rebalance.ingest import pulse
from rebalance.ingest._http import GitHubHTTPError


def _client_cls(result=None, exc: Exception | None = None) -> type:
    class _FakeClient:
        def __init__(self, token: str, **_: object) -> None:
            pass

        def get_json(self, url: str):
            if exc is not None:
                raise exc
            return result

    return _FakeClient


class FetchAssignedIssuesTests(unittest.TestCase):
    def _since(self) -> datetime:
        return datetime(2026, 8, 15, tzinfo=timezone.utc)

    def test_maps_search_rows_to_pulse_shape(self) -> None:
        payload = {
            "items": [
                {
                    "number": 42,
                    "title": "Fix the thing",
                    "state": "open",
                    "html_url": "https://github.com/someone/repo/issues/42",
                    "created_at": "2026-08-10T00:00:00Z",
                    "updated_at": "2026-08-14T00:00:00Z",
                    "labels": [{"name": "bug"}, {}],
                    "repository_url": "https://api.github.com/repos/someone/repo",
                }
            ]
        }
        fake = _client_cls(result=payload)
        with patch.object(pulse, "GitHubClient", fake):
            rows = pulse.fetch_assigned_issues(github_login="someone", token="tok", since_date=self._since())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["repo"], "someone/repo")
        self.assertEqual(row["number"], 42)
        self.assertEqual(row["title"], "Fix the thing")
        self.assertEqual(row["labels"], ["bug"])

    def test_rate_limit_error_keeps_runtime_error_contract(self) -> None:
        exc = GitHubHTTPError(
            "GitHub API request failed: 403",
            status=403,
            is_rate_limit=True,
        )
        with patch.object(pulse, "GitHubClient", _client_cls(exc=exc)):
            with self.assertRaises(RuntimeError) as ctx:
                pulse.fetch_assigned_issues(github_login="someone", token="tok", since_date=self._since())
        self.assertIn("rate limit", str(ctx.exception))

    def test_non_rate_limit_http_error_propagates(self) -> None:
        exc = GitHubHTTPError("GitHub API request failed: 422", status=422)
        with patch.object(pulse, "GitHubClient", _client_cls(exc=exc)):
            with self.assertRaises(GitHubHTTPError):
                pulse.fetch_assigned_issues(github_login="someone", token="tok", since_date=self._since())

    def test_empty_items_yield_empty_list(self) -> None:
        with patch.object(pulse, "GitHubClient", _client_cls(result={"items": []})):
            rows = pulse.fetch_assigned_issues(github_login="someone", token="tok", since_date=self._since())
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
