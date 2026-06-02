"""Append-only auth-activity log, unified across every collector.

One JSON line per auth event, written to ``temp/logs/auth_activity.jsonl``.
Every collector that authenticates against an external service logs here at
its auth boundaries — flow start/success/failure, token missing/refresh,
credential validation, deauthorization — so you can tail one file and
immediately answer "which collector lost access, on which device, when?"

Entry shape:
  {
    "ts":     "2026-06-01T14:23:00.123456+00:00",
    "device": "noels-Mac-Studio.local",
    "source": "calendar",          # which collector / integration
    "event":  "flow_succeeded",
    "detail": { ... }              # event-specific fields
  }

Sources & events
----------------
calendar
  flow_started          — OAuth browser flow was opened
  flow_succeeded        — token written; includes expiry and scopes
  flow_failed           — exception prevented token write; includes error
  token_missing         — _load_credentials found no token file
  token_refreshed       — expired token was refreshed successfully
  token_refresh_failed  — refresh attempt raised an exception
github
  token_validated       — PAT validated against /user; includes login + scopes
  token_invalid         — PAT validation returned non-200 (bad/expired token)
  auth_failed           — a live API call was rejected (401) mid-collection
gmail
  adc_missing           — no Application Default Credentials found
  scope_insufficient    — ADC present but lacks the Gmail readonly scope

The ``FAILURE_EVENTS`` set marks the events that represent a collector losing
(or never having) access — what ``rebalance config doctor`` surfaces as the
"last auth failure" per integration.
"""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Events that mean a collector lost or lacked access. Used by readers (the web
# dashboard, doctor) to surface the most recent failure per source.
FAILURE_EVENTS: frozenset[str] = frozenset({
    # calendar
    "flow_failed", "token_missing", "token_refresh_failed",
    # github
    "token_invalid", "auth_failed",
    # gmail
    "adc_missing", "scope_insufficient",
})


# ---------------------------------------------------------------------------
# Log paths — resolved relative to this file's project root
# ---------------------------------------------------------------------------

def _log_dir() -> Path:
    """Return temp/logs/, creating it if needed."""
    root = Path(__file__).resolve().parents[3]  # …/rebalance-OS/
    log_dir = root / "temp" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _log_path() -> Path:
    """Return the unified JSONL log path, creating parent dirs if needed."""
    return _log_dir() / "auth_activity.jsonl"


def _legacy_calendar_path() -> Path:
    """The pre-unification calendar-only log. Read (never written) so existing
    history still shows up in the dashboard after the cutover."""
    return _log_dir() / "calendar_oauth_activity.jsonl"


# ---------------------------------------------------------------------------
# Core append
# ---------------------------------------------------------------------------

def _append(source: str, event: str, detail: dict[str, Any] | None = None) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "device": socket.gethostname(),
        "source": source,
        "event": event,
        "detail": detail or {},
    }
    try:
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # never let logging break the caller


def log_event(source: str, event: str, detail: dict[str, Any] | None = None) -> None:
    """Generic entry point so new collectors can log without a typed helper."""
    _append(source, event, detail)


# ---------------------------------------------------------------------------
# Calendar helpers — one per event type
# ---------------------------------------------------------------------------

def log_flow_started(scopes: list[str]) -> None:
    _append("calendar", "flow_started", {"scopes": scopes})


def log_flow_succeeded(expiry: str | None, scopes: list[str], token_path: str) -> None:
    _append("calendar", "flow_succeeded", {
        "expiry": expiry,
        "scopes": scopes,
        "token_path": token_path,
    })


def log_flow_failed(error: str) -> None:
    _append("calendar", "flow_failed", {"error": error})


def log_token_missing(token_path: str) -> None:
    _append("calendar", "token_missing", {"token_path": token_path})


def log_token_refreshed(expiry: str | None, token_path: str) -> None:
    _append("calendar", "token_refreshed", {"expiry": expiry, "token_path": token_path})


def log_token_refresh_failed(error: str, token_path: str) -> None:
    _append("calendar", "token_refresh_failed", {"error": error, "token_path": token_path})


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def log_github_token_validated(login: str, scopes: list[str]) -> None:
    _append("github", "token_validated", {"login": login, "scopes": scopes})


def log_github_token_invalid(status: int, error: str = "") -> None:
    _append("github", "token_invalid", {"status": status, "error": error})


def log_github_auth_failed(status: int, endpoint: str = "") -> None:
    """A live API call was rejected for auth reasons (401) mid-collection —
    the PAT was revoked, expired, or lost a required scope."""
    _append("github", "auth_failed", {"status": status, "endpoint": endpoint})


# ---------------------------------------------------------------------------
# Gmail helpers
# ---------------------------------------------------------------------------

def log_gmail_adc_missing(error: str = "") -> None:
    _append("gmail", "adc_missing", {"error": error})


def log_gmail_scope_insufficient(error: str = "") -> None:
    _append("gmail", "scope_insufficient", {"error": error})


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

def _read_file(path: Path, default_source: str | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if default_source is not None and "source" not in entry:
            entry["source"] = default_source
        entries.append(entry)
    return entries


def read_log(limit: int = 200) -> list[dict[str, Any]]:
    """Return the most recent *limit* entries, newest first.

    Merges the unified log with the legacy calendar-only log (backfilling
    ``source="calendar"`` on legacy rows) so pre-unification history is not
    lost. Sorted by timestamp; ties keep insertion order.
    """
    entries = _read_file(_log_path())
    entries += _read_file(_legacy_calendar_path(), default_source="calendar")
    entries.sort(key=lambda e: e.get("ts", ""))
    return list(reversed(entries[-limit:]))


def latest_failure_by_source(sources: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Return the most recent *failure* event per source.

    Used by ``rebalance doctor`` to surface "last auth failure" for each
    integration. Pass *sources* to restrict the result; omit for all.
    """
    wanted = set(sources) if sources else None
    latest: dict[str, dict[str, Any]] = {}
    for entry in read_log(limit=2000):  # newest-first
        if entry.get("event") not in FAILURE_EVENTS:
            continue
        source = entry.get("source", "")
        if wanted is not None and source not in wanted:
            continue
        # newest-first iteration → first seen per source is the most recent
        latest.setdefault(source, entry)
    return latest


def latest_event_by_source(sources: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Return the most recent event (any type) per source.

    Lets a reader tell whether a collector is *currently* in a failed auth
    state (its latest event ∈ :data:`FAILURE_EVENTS`) or has since recovered
    (a later success superseded the failure) — which a failure-only view
    cannot distinguish. Pass *sources* to restrict the result; omit for all.
    """
    wanted = set(sources) if sources else None
    latest: dict[str, dict[str, Any]] = {}
    for entry in read_log(limit=2000):  # newest-first
        source = entry.get("source", "")
        if wanted is not None and source not in wanted:
            continue
        latest.setdefault(source, entry)
    return latest
