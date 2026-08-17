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


class RequestAttributionTests(unittest.TestCase):
    """GH-144 regression: per-job request attribution at the client chokepoint.

    One ``github-sync`` run was measured at ~2,292 requests against a 5,000/hr
    PAT ceiling, 63% of it from fetching six sub-resources per PR. Nothing in the
    codebase could say that on-box — the number came from reading call sites by
    hand. ``_request()`` is the single point every GitHub call passes through, so
    the counter lives there and therefore also sees pagination and retries, which
    per-call-site instrumentation would miss.

    These tests pin the properties that make the measurement trustworthy. Each
    uses a unique ``run_id``: attribution is keyed ``(job_label, run_id)`` in a
    module-level registry, so a shared id would leak counts between tests.
    """

    def _client(self, name: str, **kw) -> GitHubClient:
        return GitHubClient("ghp", job_label="test-job", run_id=f"run-{name}", **kw)

    def test_endpoint_paths_are_normalised_so_fan_out_is_visible(self) -> None:
        """Per-resource ids must collapse, or 241 PRs produce 241 rows instead of one."""
        from rebalance.ingest._http import _endpoint_path

        self.assertEqual(
            _endpoint_path("https://api.github.com/repos/acme/widgets/pulls/1234"),
            "/repos/{owner}/{repo}/pulls/{id}",
        )
        self.assertEqual(
            _endpoint_path("https://api.github.com/repos/acme/widgets/pulls/99/reviews?page=2"),
            "/repos/{owner}/{repo}/pulls/{id}/reviews",
            "query parameters must not split one route into many rows",
        )
        self.assertEqual(_endpoint_path("https://api.github.com/user"), "/user")

    def test_counts_logical_requests_per_endpoint(self) -> None:
        client = self._client("counts", retries=1)
        with patch("urllib.request.urlopen", return_value=_ok_response({"ok": True})):
            client.get("/repos/acme/widgets/pulls/1")
            client.get("/repos/acme/widgets/pulls/2")
            client.get("/user")

        summary = client.request_summary()
        self.assertEqual(summary["logical_requests"], 3)
        self.assertEqual(
            summary["endpoint_counts"],
            {"/repos/{owner}/{repo}/pulls/{id}": 2, "/user": 1},
            "two different PRs must aggregate into one normalised route",
        )

    def test_retries_are_counted_as_attempts_not_extra_logical_requests(self) -> None:
        """A retried call is one request that cost three round-trips.

        Conflating the two would make a rate-limited run look like it issued more
        distinct requests than it did — the opposite of the diagnosis this exists
        to support.
        """
        client = self._client("retries", retries=3, sleep=lambda _s: None)
        with patch("urllib.request.urlopen", side_effect=_http_error(500)):
            client.get("/repos/acme/widgets/pulls/7")

        summary = client.request_summary()
        self.assertEqual(summary["logical_requests"], 1)
        self.assertEqual(summary["attempts"], 3)
        self.assertEqual(
            summary["endpoint_attempt_counts"]["/repos/{owner}/{repo}/pulls/{id}"], 3
        )

    def test_pagination_is_captured(self) -> None:
        """paginate() goes through _request(), so every page must be counted."""
        client = self._client("paginate", retries=1)
        pages = [
            _ok_response([{"id": 1}] * 100),  # full page -> keep going
            _ok_response([{"id": 2}]),        # short page -> stop
        ]
        with patch("urllib.request.urlopen", side_effect=pages):
            client.paginate("/repos/acme/widgets/issues")

        summary = client.request_summary()
        self.assertEqual(
            summary["logical_requests"], 2,
            "both pages must appear; per-call-site instrumentation would see one call",
        )

    def test_every_rate_limit_sample_carries_its_reset_epoch(self) -> None:
        """Start/end `used` is not a valid per-job delta without the reset epoch.

        The PAT is shared across machines and a run can cross an hourly reset, so
        a `used` delta with no reset attached is not just imprecise — it is
        unfalsifiable. Codex flagged this explicitly when measuring #140.
        """
        client = self._client("headers", retries=1)
        headers = {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "4991",
            "x-ratelimit-used": "9",
            "x-ratelimit-reset": "1752861600",
        }
        with patch("urllib.request.urlopen", return_value=_ok_response({}, headers)):
            client.get("/user")

        rl = client.request_summary()["rate_limit_headers"]
        self.assertIsNotNone(rl["first"])
        self.assertEqual(rl["first"]["reset"], "1752861600")
        self.assertEqual(rl["last"]["used"], "9")
        self.assertEqual(rl["reset_epochs"], ["1752861600"])

    def test_clients_sharing_a_job_and_run_share_one_attribution(self) -> None:
        """github_scan._get() builds a NEW client per call; those must still sum.

        Attribution is run-scoped rather than client-scoped precisely for this
        case. If it were per-instance, the legacy call path would report ~1
        request per client and the job total would be meaningless.
        """
        run = "run-shared"
        a = GitHubClient("ghp", job_label="github-sync", run_id=run, retries=1)
        b = GitHubClient("ghp", job_label="github-sync", run_id=run, retries=1)

        with patch("urllib.request.urlopen", return_value=_ok_response({})):
            a.get("/user")
            b.get("/repos/acme/widgets")

        self.assertEqual(a.request_summary()["logical_requests"], 2)
        self.assertEqual(
            a.request_summary(), b.request_summary(),
            "both clients must observe the same job-level totals",
        )

    def test_a_different_run_id_does_not_inherit_counts(self) -> None:
        """Runs must not accumulate across a process, or every number inflates."""
        first = GitHubClient("ghp", job_label="github-sync", run_id="run-A", retries=1)
        with patch("urllib.request.urlopen", return_value=_ok_response({})):
            first.get("/user")

        second = GitHubClient("ghp", job_label="github-sync", run_id="run-B", retries=1)
        self.assertEqual(second.request_summary()["logical_requests"], 0)


if __name__ == "__main__":
    unittest.main()
