"""Append-only telemetry and the shared HiQS health view.

Health is inferred solely from persisted events and table probes.  This keeps
the CLI, MCP, and web surfaces honest when a source has never run or SQLite is
unavailable: neither case is presented as healthy.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

from .db import db_connection


EVENT_STATUSES = frozenset({"ok", "warn", "error", "unknown"})
_COUNTED_TABLES = (
    "vault_files",
    "github_activity",
    "github_items",
    "calendar_events",
    "docs",
    "docs_vec",
    "projects",
    "events",
)
_ERROR_TAIL_LIMIT = 5


def _utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with a stable ``Z`` suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_event(kind: str, source: str, status: str, payload: Mapping[str, Any]) -> None:
    """Append one structured event to the observability spine.

    ``status`` is deliberately checked before SQLite sees it, so callers get a
    clear contract error rather than relying on a schema-specific constraint
    failure.  Payloads must be JSON serialisable; event content is never
    silently discarded.
    """
    if status not in EVENT_STATUSES:
        allowed = ", ".join(sorted(EVENT_STATUSES))
        raise ValueError(f"event status must be one of: {allowed}")

    payload_json = json.dumps(dict(payload), separators=(",", ":"), sort_keys=True)
    with closing(db_connection()) as connection:
        connection.execute(
            "INSERT INTO events(ts, kind, source, status, payload_json) VALUES (?, ?, ?, ?, ?)",
            (_utc_now(), kind, source, status, payload_json),
        )
        connection.commit()


def _empty_status() -> dict[str, Any]:
    """Build the honest status shape used for first run and failed probes."""
    return {
        "sources": {},
        "row_counts": {},
        "last_errors": [],
        "search": {"mode": "unknown", "model": None, "quality": "unknown"},
        "ranking": {"quality": "unknown"},
    }


def _payload(payload_json: str) -> dict[str, Any] | None:
    """Decode a persisted event payload without letting bad history break status."""
    try:
        value = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _quality(connection: sqlite3.Connection, kind: str, source: str | None = None) -> tuple[Any, str | None]:
    """Return the latest valid evaluation payload, annotated with its event time."""
    where = "kind = ?"
    values: tuple[str, ...] = (kind,)
    if source is not None:
        where += " AND source = ?"
        values += (source,)
    row = connection.execute(
        f"SELECT ts, payload_json FROM events WHERE {where} ORDER BY rowid DESC LIMIT 1",
        values,
    ).fetchone()
    if row is None:
        return "unknown", None
    payload = _payload(row[1])
    if payload is None:
        return "unknown", None
    payload["measured_at"] = row[0]
    return payload, row[0]


def _search_mode(connection: sqlite3.Connection) -> tuple[str, str | None]:
    """Derive the active search mode from its most recent attested event."""
    row = connection.execute(
        """
        SELECT kind, payload_json
        FROM events
        WHERE kind IN ('search.degraded', 'search.ready')
           OR (kind = 'eval.completed' AND source = 'search')
        ORDER BY rowid DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return "unknown", None

    kind, payload_json = row
    payload = _payload(payload_json) or {}
    mode = payload.get("mode")
    if mode in {"hybrid", "fts_only", "unknown"}:
        return mode, payload.get("model") if isinstance(payload.get("model"), str) else None
    if kind == "search.degraded":
        return "fts_only", None
    return "hybrid", payload.get("model") if isinstance(payload.get("model"), str) else None


def _freshness(last_success_at: str | None) -> dict[str, Any] | str:
    """Describe the age of a successful event, without guessing on bad data."""
    if last_success_at is None:
        return "unknown"
    try:
        occurred_at = datetime.fromisoformat(last_success_at.replace("Z", "+00:00"))
        if occurred_at.tzinfo is None:
            return "unknown"
        age_seconds = max(0, int((datetime.now(timezone.utc) - occurred_at).total_seconds()))
    except ValueError:
        return "unknown"
    return {"last_success_at": last_success_at, "age_s": age_seconds}


def _source_statuses(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """Aggregate each observed source's latest state and last successful sync."""
    rows = connection.execute(
        "SELECT rowid, ts, source, status FROM events WHERE source <> '' ORDER BY rowid DESC"
    ).fetchall()
    sources: dict[str, dict[str, Any]] = {}
    for _, timestamp, source, event_status in rows:
        state = sources.setdefault(
            source,
            {"status": event_status, "last_event_at": timestamp, "last_success_at": None},
        )
        if event_status == "ok" and state["last_success_at"] is None:
            state["last_success_at"] = timestamp
    for state in sources.values():
        state["freshness"] = _freshness(state["last_success_at"])
    return sources


def _row_counts(connection: sqlite3.Connection) -> dict[str, int]:
    """Count the canonical schema tables without dynamically interpolating names."""
    return {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in _COUNTED_TABLES
    }


def _last_errors(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return a bounded, newest-first error tail for an operator or sentinel."""
    rows = connection.execute(
        """
        SELECT ts, kind, source, payload_json
        FROM events
        WHERE status = 'error'
        ORDER BY rowid DESC
        LIMIT ?
        """,
        (_ERROR_TAIL_LIMIT,),
    ).fetchall()
    return [
        {"ts": timestamp, "kind": kind, "source": source, "payload": _payload(payload_json)}
        for timestamp, kind, source, payload_json in rows
    ]


def status() -> dict[str, Any]:
    """Return the shared health payload, or an explicitly unknown one on probe failure."""
    result = _empty_status()
    try:
        with closing(db_connection()) as connection:
            result["sources"] = _source_statuses(connection)
            result["row_counts"] = _row_counts(connection)
            result["last_errors"] = _last_errors(connection)
            search_quality, _ = _quality(connection, "eval.completed", "search")
            search_mode, search_model = _search_mode(connection)
            if search_model is None and isinstance(search_quality, dict):
                model = search_quality.get("model")
                search_model = model if isinstance(model, str) else None
            result["search"] = {
                "mode": search_mode,
                "model": search_model,
                "quality": search_quality,
            }
            ranking_quality, _ = _quality(connection, "rank.evaluated")
            result["ranking"] = {"quality": ranking_quality}
    except (OSError, sqlite3.Error):
        # A failed probe is itself unknown.  Do not turn a status check into an
        # outage or infer health from process state.
        return _empty_status()
    return result
