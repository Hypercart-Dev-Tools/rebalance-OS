"""Candidate receipts from the GitHub source."""

from __future__ import annotations

from hiqs.db import db_connection
from hiqs.sources import github


def _item(*, assignee, requested_reviewer, milestone, updated_at="2026-08-01T12:00:00Z"):
    return {
        "number": 42,
        "title": "Ship candidate receipts",
        "body": "Body",
        "state": "open",
        "html_url": "https://example.test/org/repo/pull/42",
        "user": {"login": "author"},
        "assignee": {"login": assignee} if assignee else None,
        "requested_reviewers": [{"login": requested_reviewer}] if requested_reviewer else [],
        "milestone": milestone,
        "updated_at": updated_at,
        "created_at": "2026-07-30T10:00:00Z",
        "pull_request": {},
    }


def _stub_fetch(monkeypatch, item):
    monkeypatch.setattr(github.hiqs_config, "secret", lambda _name: None)
    monkeypatch.setattr(github, "log_event", lambda *_args: None)

    def request_json(url, _token, _api_calls):
        _api_calls[0] += 1
        if "issues/events" in url:
            return [{"event": "reviewed", "created_at": "2026-08-01T09:00:00Z", "issue": {"number": 42}}]
        return [item]

    monkeypatch.setattr(github, "_request_json", request_json)


def _fetch(connection):
    return github.SOURCE.fetch(
        connection,
        {"github": {"repos": ["org/repo"], "api_url": "https://example.test"}},
    )


def test_github_candidates_are_attested_and_preserve_activity_time(tmp_path, monkeypatch):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        item = _item(
            assignee="owner",
            requested_reviewer="reviewer",
            milestone={"due_on": "2026-08-15T00:00:00Z", "title": "v1.0"},
        )
        _stub_fetch(monkeypatch, item)
        _fetch(connection)
        first = list(github.SOURCE.candidates(connection, {}))

        # A label-only API edit advances updated_at but never ranker-facing activity_at.
        _stub_fetch(
            monkeypatch,
            _item(
                assignee="owner",
                requested_reviewer="reviewer",
                milestone={"due_on": "2026-08-15T00:00:00Z", "title": "v1.0"},
                updated_at="2026-08-02T12:00:00Z",
            ),
        )
        _fetch(connection)
        labelled = list(github.SOURCE.candidates(connection, {}))
    finally:
        connection.close()

    assert len(first) == len(labelled) == 1
    candidate = first[0]
    assert candidate.ts == labelled[0].ts == "2026-08-01T09:00:00Z"
    assert all(item.source and item.evidence and item.why for item in first)
    assert candidate.owed_by == "owner"
    assert candidate.due == "2026-08-15T00:00:00Z"
    assert candidate.evidence == "PR #42, assigned to owner, last activity 2026-08-01T09:00:00Z, due 2026-08-15T00:00:00Z"


def test_github_candidates_use_requested_reviewer_and_leave_unknown_obligations_blank(tmp_path, monkeypatch):
    connection = db_connection(tmp_path / "hiqs.db")
    try:
        _stub_fetch(
            monkeypatch,
            _item(assignee="", requested_reviewer="reviewer", milestone=None),
        )
        _fetch(connection)
        reviewer_candidate = list(github.SOURCE.candidates(connection, {}))[0]

        _stub_fetch(
            monkeypatch,
            _item(assignee="", requested_reviewer="", milestone=None, updated_at="2026-08-02T12:00:00Z"),
        )
        _fetch(connection)
        unassigned_candidate = list(github.SOURCE.candidates(connection, {}))[0]
    finally:
        connection.close()

    assert reviewer_candidate.owed_by == "reviewer"
    assert "review requested from reviewer" in reviewer_candidate.evidence
    assert (unassigned_candidate.owed_by, unassigned_candidate.due) == ("", "")
