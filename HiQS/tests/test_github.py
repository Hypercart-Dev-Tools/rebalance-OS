"""Tests for the GitHub source's bounded, idempotent sync contract."""

from __future__ import annotations

import inspect
import json

from hiqs.db import db_connection
from hiqs.sources import github


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _item(updated_at="2026-08-01T12:00:00Z"):
    return {
        "number": 7,
        "title": "Ship the important change",
        "body": "Implementation details.",
        "state": "open",
        "html_url": "https://example.test/org/repo/issues/7",
        "user": {"login": "author"},
        "assignee": {"login": "owner"},
        "updated_at": updated_at,
        "created_at": "2026-07-30T10:00:00Z",
    }


def _stubbed_urlopen(payloads):
    def fake_urlopen(request, *, timeout):
        assert timeout == github.NETWORK_TIMEOUT_SECONDS
        url = request.full_url
        for fragment, payload in payloads.items():
            if fragment in url:
                return _Response(payload)
        raise AssertionError(f"unexpected URL: {url}")

    return fake_urlopen


def test_github_fetch_idempotence_activity_time_and_watermark(tmp_path, monkeypatch):
    """A label-only source update changes the watermark but not ranker- or docs-facing activity time."""
    conn = db_connection(tmp_path / "hiqs.db")
    monkeypatch.setattr(github.hiqs_config, "secret", lambda _name: None)
    monkeypatch.setattr(github, "log_event", lambda *_args: None)
    payloads = {
        "/users/operator/events": [{"repo": {"name": "org/repo"}, "created_at": "2026-08-01T08:00:00Z", "type": "PushEvent"}],
        "/repos/org/repo/issues?": [_item()],
        "/repos/org/repo/issues/events?": [{"event": "commented", "created_at": "2026-08-01T09:00:00Z", "issue": {"number": 7}}],
    }
    monkeypatch.setattr(github, "urlopen", _stubbed_urlopen(payloads))
    watermark = {}
    config = {"github": {"login": "operator", "repos": ["org/repo"], "api_url": "https://example.test"}, "watermark": watermark}
    try:
        first = github.SOURCE.fetch(conn, config)
        second = github.SOURCE.fetch(conn, config)
        assert first.counts["inserted"] == 2
        assert second.counts["inserted"] == second.counts["updated"] == 0
        assert second.counts["unchanged"] == 2
        assert watermark["github"] == "2026-08-01T12:00:00Z"
        row = conn.execute("SELECT author, assignee, updated_at, activity_at FROM github_items").fetchone()
        assert row == ("author", "owner", "2026-08-01T12:00:00Z", "2026-08-01T09:00:00Z")

        payloads["/repos/org/repo/issues?"] = [_item("2026-08-02T12:00:00Z")]
        labelled = github.SOURCE.fetch(conn, config)
        assert labelled.counts["updated"] == 1
        assert conn.execute("SELECT activity_at FROM github_items").fetchone()[0] == "2026-08-01T09:00:00Z"
        assert list(github.docs(conn))[0].ts == "2026-08-01T09:00:00Z"
    finally:
        conn.close()


def test_github_failure_continues_logs_error_and_keeps_watermark(tmp_path, monkeypatch):
    """A mid-walk failure leaves its cursor unchanged while later repos still sync."""
    conn = db_connection(tmp_path / "hiqs.db")
    logged = []
    monkeypatch.setattr(github.hiqs_config, "secret", lambda _name: None)
    monkeypatch.setattr(github, "log_event", lambda *args: logged.append(args))

    def fake_urlopen(request, *, timeout):
        assert timeout == github.NETWORK_TIMEOUT_SECONDS
        if "/repos/org/bad/" in request.full_url:
            raise OSError("network down")
        if "issues/events" in request.full_url:
            return _Response([])
        return _Response([_item()])

    monkeypatch.setattr(github, "urlopen", fake_urlopen)
    watermark = {"github": "old"}
    try:
        report = github.SOURCE.fetch(conn, {"github": {"repos": ["org/bad", "org/good"], "api_url": "https://example.test"}, "watermark": watermark})
        assert report.errors == ["GitHub item request failed"]
        assert report.units_ok == ("org/good",)
        assert watermark == {"github": "old"}
        assert conn.execute("SELECT repo FROM github_items").fetchone()[0] == "org/good"
        assert logged[-1][2] == "error"
    finally:
        conn.close()


def test_github_rejects_contentless_shells_and_every_urlopen_has_timeout(tmp_path, monkeypatch):
    """Quality rejects un-attestable rows and a stalled call cannot hold the writer."""
    conn = db_connection(tmp_path / "hiqs.db")
    monkeypatch.setattr(github.hiqs_config, "secret", lambda _name: None)
    monkeypatch.setattr(github, "log_event", lambda *_args: None)
    monkeypatch.setattr(github, "urlopen", _stubbed_urlopen({"issues?": [{"number": 1}], "issues/events?": []}))
    try:
        report = github.SOURCE.fetch(conn, {"github": {"repos": ["org/repo"], "api_url": "https://example.test"}})
        assert report.counts["rejected"] == 1
        assert conn.execute("SELECT count(*) FROM github_items").fetchone()[0] == 0
        assert report.meta["api_calls"] == 2
        assert "timeout=NETWORK_TIMEOUT_SECONDS" in inspect.getsource(github._request_json)
    finally:
        conn.close()
