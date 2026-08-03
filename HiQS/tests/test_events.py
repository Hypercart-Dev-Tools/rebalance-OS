import inspect
import sqlite3

import pytest

from hiqs import events
from hiqs.db import db_connection


@pytest.fixture
def event_database(tmp_path, monkeypatch):
    path = tmp_path / "hiqs.db"
    monkeypatch.setattr(events, "db_connection", lambda: db_connection(path))
    return path


def test_log_event_round_trips_through_status(event_database):
    events.log_event(
        "sync.completed",
        "vault",
        "ok",
        {"counts": {"inserted": 1}, "peak_rss_mb": 42},
    )

    connection = db_connection(event_database)
    try:
        row = connection.execute(
            "SELECT kind, source, status, payload_json FROM events"
        ).fetchone()
        assert row[:3] == ("sync.completed", "vault", "ok")
        assert '"inserted":1' in row[3]
    finally:
        connection.close()

    state = events.status()
    assert state["sources"]["vault"]["status"] == "ok"
    assert state["sources"]["vault"]["last_success_at"] is not None
    assert state["sources"]["vault"]["freshness"]["age_s"] >= 0
    assert state["row_counts"]["events"] == 1


def test_empty_database_never_reports_search_or_ranking_as_healthy(event_database):
    state = events.status()

    assert state["search"] == {"mode": "unknown", "model": None, "quality": "unknown"}
    assert state["ranking"]["quality"] == "unknown"
    assert state["sources"] == {}


def test_unreadable_probe_returns_unknown(monkeypatch):
    def unreadable_database():
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(events, "db_connection", unreadable_database)

    assert events.status() == {
        "sources": {},
        "row_counts": {},
        "last_errors": [],
        "search": {"mode": "unknown", "model": None, "quality": "unknown"},
        "ranking": {"quality": "unknown"},
    }


@pytest.mark.parametrize("invalid_status", ["healthy", "failed", "OK", ""])
def test_log_event_rejects_status_outside_the_closed_vocabulary(event_database, invalid_status):
    with pytest.raises(ValueError, match="event status"):
        events.log_event("sync.completed", "vault", invalid_status, {})


def test_events_has_one_pinned_writer():
    source = inspect.getsource(events)

    assert source.count("INSERT INTO events") == 1
    assert "def log_event" in source


def test_status_reads_latest_measured_quality_and_search_degradation(event_database):
    events.log_event(
        "eval.completed",
        "search",
        "ok",
        {"model": "all-MiniLM-L6-v2", "recall_at_10": 0.83, "mrr_at_10": 0.71, "n_queries": 34},
    )
    events.log_event("rank.evaluated", "ranking", "ok", {"top_5_overlap": 0.8})
    events.log_event("search.degraded", "search", "warn", {"mode": "fts_only"})

    state = events.status()

    assert state["search"]["mode"] == "fts_only"
    assert state["search"]["model"] == "all-MiniLM-L6-v2"
    assert state["search"]["quality"] == {
        "model": "all-MiniLM-L6-v2",
        "recall_at_10": 0.83,
        "mrr_at_10": 0.71,
        "n_queries": 34,
        "measured_at": state["search"]["quality"]["measured_at"],
    }
    assert state["ranking"]["quality"]["top_5_overlap"] == 0.8
    assert state["ranking"]["quality"]["measured_at"]
