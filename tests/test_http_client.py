"""Tests for the shared GitHub HTTP client (src/rebalance/ingest/_http.py)."""

from __future__ import annotations

import io
import json
import unittest
import urllib.error
from typing import Any
from unittest.mock import patch

from rebalance.ingest._http import GitHubClient, GitHubHTTPError


def _ok_response(payload: Any, response_headers: dict[str, str] | None = None):
    """Return a fake context manager mimicking urlopen's response."""
    body = json.dumps(payload).encode()
    hdrs = response_headers or {}

    class _Resp:
        status = 200
        headers = hdrs

        def __enter__(self_inner):
            return self_inner

        def __exit__(self_inner, *_exc):
            return False

        def read(self_inner):
            return body

    return _Resp()


def _http_error(code: int, body: str = "", headers: dict[str, str] | None = None) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://api.github.com/",
        code=code,
        msg="err",
        hdrs=headers or {},
        fp=io.BytesIO(body.encode()),
    )


class GitHubClientHeadersTests(unittest.TestCase):
    def test_uses_bearer_auth_and_api_version(self) -> None:
        client = GitHubClient("ghp_test")
        h = client.headers()
        self.assertEqual(h["Authorization"], "Bearer ghp_test")
        self.assertEqual(h["X-GitHub-Api-Version"], "2022-11-28")
        self.assertIn("rebalance-os", h["User-Agent"])


class GitHubClientGetTests(unittest.TestCase):
    def test_get_returns_status_and_data(self) -> None:
        client = GitHubClient("ghp", retries=1)
        with patch("urllib.request.urlopen", return_value=_ok_response({"login": "alice"})):
            status, data = client.get("/user")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"login": "alice"})

    def test_get_returns_status_none_on_http_error_with_no_retry(self) -> None:
        client = GitHubClient("ghp", retries=1)
        with patch("urllib.request.urlopen", side_effect=_http_error(404)):
            status, data = client.get("/user")
        self.assertEqual(status, 404)
        self.assertIsNone(data)


class GitHubClientGetJsonTests(unittest.TestCase):
    def test_get_json_returns_data_on_2xx(self) -> None:
        client = GitHubClient("ghp", retries=1)
        with patch("urllib.request.urlopen", return_value=_ok_response([1, 2, 3])):
            data = client.get_json("/list")
        self.assertEqual(data, [1, 2, 3])

    def test_get_json_raises_on_4xx(self) -> None:
        client = GitHubClient("ghp", retries=1)
        with patch("urllib.request.urlopen", side_effect=_http_error(404)):
            with self.assertRaises(GitHubHTTPError) as ctx:
                client.get_json("/missing")
        self.assertEqual(ctx.exception.status, 404)
        self.assertFalse(ctx.exception.is_rate_limit)

    def test_get_json_flags_rate_limit_on_429(self) -> None:
        client = GitHubClient("ghp", retries=1)
        with patch("urllib.request.urlopen", side_effect=_http_error(429)):
            with self.assertRaises(GitHubHTTPError) as ctx:
                client.get_json("/x")
        self.assertTrue(ctx.exception.is_rate_limit)

    def test_get_json_flags_rate_limit_on_403_with_zero_remaining(self) -> None:
        client = GitHubClient("ghp", retries=1)
        with patch(
            "urllib.request.urlopen",
            side_effect=_http_error(403, headers={"x-ratelimit-remaining": "0"}),
        ):
            with self.assertRaises(GitHubHTTPError) as ctx:
                client.get_json("/x")
        self.assertTrue(ctx.exception.is_rate_limit)


class GitHubClientRetryTests(unittest.TestCase):
    def test_retries_on_5xx_then_succeeds(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient("ghp", retries=3, sleep=lambda s: sleeps.append(s))
        responses = [_http_error(503), _http_error(503), _ok_response({"ok": True})]

        def _side(*_a, **_k):
            r = responses.pop(0)
            if isinstance(r, urllib.error.HTTPError):
                raise r
            return r

        with patch("urllib.request.urlopen", side_effect=_side):
            data = client.get_json("/flaky")
        self.assertEqual(data, {"ok": True})
        self.assertEqual(len(sleeps), 2)

    def test_does_not_retry_on_4xx(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient("ghp", retries=3, sleep=lambda s: sleeps.append(s))
        with patch("urllib.request.urlopen", side_effect=_http_error(404)):
            with self.assertRaises(GitHubHTTPError):
                client.get_json("/missing")
        self.assertEqual(sleeps, [])

    def test_honors_retry_after_header(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient("ghp", retries=2, sleep=lambda s: sleeps.append(s))
        with patch(
            "urllib.request.urlopen",
            side_effect=_http_error(429, headers={"retry-after": "7"}),
        ):
            with self.assertRaises(GitHubHTTPError):
                client.get_json("/x")
        self.assertEqual(sleeps, [7.0])


class GitHubClientPaginateTests(unittest.TestCase):
    def test_paginate_accumulates_until_short_page(self) -> None:
        client = GitHubClient("ghp", retries=1)
        page1 = [{"id": i, "updated_at": "2024-01-01"} for i in range(100)]
        page2 = [{"id": 100, "updated_at": "2024-01-01"}]  # short page → stop
        responses = [_ok_response(page1), _ok_response(page2)]
        with patch("urllib.request.urlopen", side_effect=lambda *a, **k: responses.pop(0)):
            data = client.paginate("/repos/x/y/issues")
        self.assertEqual(len(data), 101)

    def test_paginate_stops_on_updated_before(self) -> None:
        client = GitHubClient("ghp", retries=1)
        page = [
            {"id": 1, "updated_at": "2024-06-01"},
            {"id": 2, "updated_at": "2023-01-01"},  # below cutoff
        ]
        with patch("urllib.request.urlopen", return_value=_ok_response(page)):
            data = client.paginate("/repos/x/y/issues", stop_updated_before="2024-01-01")
        self.assertEqual([row["id"] for row in data], [1])


if __name__ == "__main__":
    unittest.main()
