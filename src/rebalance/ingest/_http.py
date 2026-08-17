"""
Shared GitHub HTTP client.

Replaces three near-duplicate helpers that grew up in parallel:

* ``github_scan._headers`` + ``github_scan._get``
  — used "Authorization: token X" (v3 syntax), returned ``(status, data | None)``.
* ``github_knowledge._github_headers`` + ``github_knowledge._http_get_json``
  — used "Authorization: Bearer X" (GitHub's current syntax), raised
    RuntimeError on HTTP error.
* ``github_knowledge._paginate_list``
  — paginated list endpoints with optional ``stop_updated_before`` cutoff.

The two header forms are interchangeable at the API level (GitHub accepts both),
but the duplication meant a fix to one path (rate-limit handling, retry logic,
new audit fields) never reached the other. ``GitHubClient`` is the single home.

Two response modes are offered so the existing call sites don't need behavior
changes during migration:

* :meth:`GitHubClient.get` — returns ``(status, data | None)``. Mirrors
  github_scan's contract. Use when the caller wants to branch on status (e.g.
  treat 422 as "no more pages").
* :meth:`GitHubClient.get_json` — raises :class:`GitHubHTTPError` on any
  non-2xx. Mirrors github_knowledge's contract.

Retries: 429 / 5xx are retried with exponential backoff up to ``retries``
attempts (jittered, honoring ``Retry-After`` when present). 4xx other than
429 are not retried. Default ``retries=3`` matches the CLAUDE.md "respect
GitHub 5000/hr PAT limits; sleep/retry" guidance. Tests pass ``retries=1``
to keep them deterministic.
"""

from __future__ import annotations

import atexit
from collections import Counter
import json
import logging
import os
import random
import threading
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlencode, urlsplit

GITHUB_API = "https://api.github.com"
USER_AGENT = "rebalance-os/0.30"
_API_VERSION = "2022-11-28"

logger = logging.getLogger(__name__)

_PROCESS_RUN_ID = f"pid-{os.getpid()}-{time.time_ns()}"
_ATTRIBUTION_LOCK = threading.Lock()


def _endpoint_path(url: str) -> str:
    """Return a low-cardinality GitHub route name, without query parameters."""
    path = urlsplit(url).path or "/"
    parts = path.strip("/").split("/")
    if parts[:1] == ["repos"] and len(parts) >= 3:
        parts[1:3] = ["{owner}", "{repo}"]
    # GitHub endpoint identifiers (PR, issue, milestone, etc.) are numeric.
    # Normalising them makes the fan-out visible instead of producing one row
    # for every individual resource.
    parts = ["{id}" if part.isdigit() else part for part in parts]
    return "/" + "/".join(part for part in parts if part)


class _RequestAttribution:
    """Thread-safe, process-local attribution shared by clients in one job."""

    def __init__(self, job_label: str, run_id: str) -> None:
        self.job_label = job_label
        self.run_id = run_id
        self.endpoint_counts: Counter[str] = Counter()
        self.endpoint_attempt_counts: Counter[str] = Counter()
        self.logical_requests = 0
        self.attempts = 0
        self.rate_limit_first: dict[str, str | int] | None = None
        self.rate_limit_last: dict[str, str | int] | None = None
        self.rate_limit_reset_epochs: set[str] = set()
        self._emitted_attempts = 0

    def record_request(self, url: str) -> None:
        with _ATTRIBUTION_LOCK:
            self.logical_requests += 1
            self.endpoint_counts[_endpoint_path(url)] += 1

    def record_attempt(self, url: str) -> None:
        with _ATTRIBUTION_LOCK:
            self.attempts += 1
            self.endpoint_attempt_counts[_endpoint_path(url)] += 1

    def record_headers(self, status: int, attempt: int, headers: dict[str, str]) -> None:
        if not any(key.startswith("x-ratelimit-") for key in headers):
            return
        # Do not derive a per-job quota delta: this PAT can be shared and a
        # run can cross an hourly reset. Every retained sample carries reset.
        sample: dict[str, str | int] = {
            "status": status,
            "attempt": attempt,
            "limit": headers.get("x-ratelimit-limit", ""),
            "remaining": headers.get("x-ratelimit-remaining", ""),
            "used": headers.get("x-ratelimit-used", ""),
            "reset": headers.get("x-ratelimit-reset", ""),
        }
        with _ATTRIBUTION_LOCK:
            if self.rate_limit_first is None:
                self.rate_limit_first = sample
            self.rate_limit_last = sample
            if reset := str(sample["reset"]):
                self.rate_limit_reset_epochs.add(reset)

    def snapshot(self) -> dict[str, Any]:
        with _ATTRIBUTION_LOCK:
            return {
                "job_label": self.job_label,
                "run_id": self.run_id,
                "logical_requests": self.logical_requests,
                "attempts": self.attempts,
                "endpoint_counts": dict(sorted(self.endpoint_counts.items())),
                "endpoint_attempt_counts": dict(sorted(self.endpoint_attempt_counts.items())),
                "rate_limit_headers": {
                    "first": self.rate_limit_first,
                    "last": self.rate_limit_last,
                    "reset_epochs": sorted(self.rate_limit_reset_epochs),
                },
                "rate_limit_note": "Header values are samples, not a per-job quota delta.",
            }

    def emit_summary(self) -> None:
        with _ATTRIBUTION_LOCK:
            if not self.attempts or self._emitted_attempts == self.attempts:
                return
            self._emitted_attempts = self.attempts
        logger.info("github_http_job_summary %s", json.dumps(self.snapshot(), sort_keys=True))


_JOB_ATTRIBUTION: dict[tuple[str, str], _RequestAttribution] = {}


def _job_attribution(job_label: str, run_id: str) -> _RequestAttribution:
    key = (job_label, run_id)
    with _ATTRIBUTION_LOCK:
        attribution = _JOB_ATTRIBUTION.get(key)
        if attribution is None:
            attribution = _RequestAttribution(job_label, run_id)
            _JOB_ATTRIBUTION[key] = attribution
        return attribution


def _emit_job_summaries() -> None:
    """Emit one structured summary for each process/run job at shutdown."""
    with _ATTRIBUTION_LOCK:
        attributions = list(_JOB_ATTRIBUTION.values())
    for attribution in attributions:
        attribution.emit_summary()


atexit.register(_emit_job_summaries)


class GitHubHTTPError(RuntimeError):
    """Raised by :meth:`GitHubClient.get_json` on non-2xx responses.

    Carries the HTTP status, URL, and body excerpt so callers can build
    structured diagnostics. ``is_rate_limit`` is True for 429 and 403
    rate-limit responses (which GitHub returns interchangeably for PAT
    quota exhaustion).
    """

    def __init__(self, message: str, status: int, *, url: str = "", body: str = "", is_rate_limit: bool = False):
        super().__init__(message)
        self.status = status
        self.url = url
        self.body = body
        self.is_rate_limit = is_rate_limit


def _is_rate_limit(status: int, response_headers: dict[str, str] | None = None) -> bool:
    if status == 429:
        return True
    if status == 403 and response_headers:
        # GitHub signals primary rate limit with x-ratelimit-remaining: 0 and
        # secondary rate limit with retry-after present.
        remaining = response_headers.get("x-ratelimit-remaining")
        if remaining == "0":
            return True
        if "retry-after" in response_headers:
            return True
    return False


def _retry_after_seconds(headers: dict[str, str], attempt: int) -> float:
    """Compute backoff: honor Retry-After header, else exponential w/ jitter."""
    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    # Exponential backoff: 1s, 2s, 4s, capped at 16s; +/- 25% jitter.
    base = min(2.0 ** attempt, 16.0)
    jitter = base * 0.25 * (random.random() * 2 - 1)
    return max(0.5, base + jitter)


class GitHubClient:
    """Thin wrapper over ``urllib`` with retries, pagination, and shared headers.

    Parameters
    ----------
    token:
        GitHub PAT or app-installation token. Sent as ``Authorization: Bearer``.
    timeout:
        Per-request timeout in seconds.
    retries:
        Max attempts on 429/5xx (including the first attempt). ``1`` = no retry.
    sleep:
        Test seam for the backoff sleep call.
    job_label:
        Human-readable job name for request attribution. Defaults to
        ``REBALANCE_GITHUB_JOB_LABEL`` or ``github-api``.
    run_id:
        Correlation id for the job. Defaults to ``REBALANCE_GITHUB_RUN_ID`` or
        a process-scoped id. Clients sharing these values share one counter.
    """

    def __init__(
        self,
        token: str,
        *,
        timeout: int = 30,
        retries: int = 3,
        sleep=time.sleep,
        user_agent: str = USER_AGENT,
        job_label: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self.token = token
        self.timeout = timeout
        self.retries = max(1, retries)
        self._sleep = sleep
        self._user_agent = user_agent
        self.job_label = job_label or os.environ.get("REBALANCE_GITHUB_JOB_LABEL", "github-api")
        self.run_id = run_id or os.environ.get("REBALANCE_GITHUB_RUN_ID", _PROCESS_RUN_ID)
        # This is deliberately run-scoped rather than client-scoped: legacy
        # github_scan._get() creates a client per request, and must still be
        # represented in one job total.
        self._attribution = _job_attribution(self.job_label, self.run_id)

    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self._user_agent,
            "X-GitHub-Api-Version": _API_VERSION,
        }
        if self.token.strip():
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, url: str) -> tuple[int, Any, dict[str, str], str]:
        last_status = 0
        last_body = ""
        last_headers: dict[str, str] = {}
        self._attribution.record_request(url)
        for attempt in range(self.retries):
            self._attribution.record_attempt(url)
            req = urllib.request.Request(url, headers=self.headers())
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode()
                    parsed = json.loads(body) if body else None
                    response_headers = {k.lower(): v for k, v in resp.headers.items()}
                    self._attribution.record_headers(resp.status, attempt + 1, response_headers)
                    return resp.status, parsed, response_headers, ""
            except urllib.error.HTTPError as exc:
                last_status = exc.code
                last_headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
                self._attribution.record_headers(last_status, attempt + 1, last_headers)
                try:
                    last_body = exc.read().decode() if exc.fp else ""
                except Exception:  # noqa: BLE001 — body read can fail mid-stream
                    last_body = ""

                retryable = last_status >= 500 or _is_rate_limit(last_status, last_headers)
                if not retryable or attempt + 1 >= self.retries:
                    return last_status, None, last_headers, last_body

                delay = _retry_after_seconds(last_headers, attempt)
                logger.info("GitHub %s -> %s, retrying in %.1fs (attempt %d/%d)", url, last_status, delay, attempt + 1, self.retries)
                self._sleep(delay)
        return last_status, None, last_headers, last_body

    def request_summary(self) -> dict[str, Any]:
        """Return the current structured attribution for this client job."""
        return self._attribution.snapshot()

    def emit_request_summary(self) -> None:
        """Emit the current job summary now; process exit emits any pending one."""
        self._attribution.emit_summary()

    def get(self, path_or_url: str) -> tuple[int, Any]:
        """Return ``(status, parsed_json_or_None)``. Mirrors github_scan._get."""
        url = path_or_url if path_or_url.startswith("http") else f"{GITHUB_API}{path_or_url}"
        status, data, _, _body = self._request(url)
        return status, data

    def get_with_headers(self, path_or_url: str) -> tuple[int, Any, dict[str, str]]:
        """Return ``(status, parsed_json_or_None, response_headers)``.

        Use when the caller needs to read response headers (e.g.
        ``X-OAuth-Scopes`` on ``/user``). Headers are lowercased.
        """
        url = path_or_url if path_or_url.startswith("http") else f"{GITHUB_API}{path_or_url}"
        status, data, headers, _body = self._request(url)
        return status, data, headers

    def get_json(self, path_or_url: str) -> Any:
        """Return parsed JSON or raise :class:`GitHubHTTPError`.

        Mirrors github_knowledge._http_get_json.
        """
        url = path_or_url if path_or_url.startswith("http") else f"{GITHUB_API}{path_or_url}"
        status, data, headers, body = self._request(url)
        if 200 <= status < 300:
            return data
        rate_limit = _is_rate_limit(status, headers)
        raise GitHubHTTPError(
            f"GitHub API request failed: {status} {url}",
            status=status,
            url=url,
            body=body,
            is_rate_limit=rate_limit,
        )

    @staticmethod
    def build_url(base_url: str, **params: Any) -> str:
        cleaned = {key: value for key, value in params.items() if value not in ("", None)}
        if not cleaned:
            return base_url
        return f"{base_url}?{urlencode(cleaned, doseq=True)}"

    def paginate(
        self,
        base_url: str,
        *,
        stop_updated_before: str = "",
        per_page: int = 100,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """Walk a paginated list endpoint, accumulating items.

        Mirrors github_knowledge._paginate_list. Stops at first page with
        ``updated_at < stop_updated_before`` (per row, when the param is set)
        or when a page is short of ``per_page`` items.
        """
        page = 1
        results: list[dict[str, Any]] = []
        while True:
            url = self.build_url(base_url, per_page=per_page, page=page, **params)
            data = self.get_json(url)
            if not isinstance(data, list) or not data:
                break
            stop = False
            for row in data:
                updated_at = str(row.get("updated_at") or "")
                if stop_updated_before and updated_at and updated_at < stop_updated_before:
                    stop = True
                    break
                results.append(row)
            if stop or len(data) < per_page:
                break
            page += 1
        return results
