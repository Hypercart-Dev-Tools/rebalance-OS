"""Append-only activity log for Google Calendar OAuth events.

Each entry is one JSON line written to temp/logs/calendar_oauth_activity.jsonl.
Call the helpers at every auth boundary — flow start/success/failure,
token-missing detection, token refresh — so you can tail the file and
immediately answer "did I authorize this device recently?"

Entry shape:
  {
    "ts":     "2026-06-01T14:23:00.123456+00:00",
    "device": "noels-Mac-Studio.local",
    "event":  "flow_succeeded",
    "detail": { ... }   # event-specific fields
  }

Events
------
flow_started          — OAuth browser flow was opened
flow_succeeded        — token written; includes expiry and scopes
flow_failed           — exception prevented token write; includes error string
token_missing         — _load_credentials found no token file
token_refreshed       — expired token was refreshed successfully
token_refresh_failed  — refresh attempt raised an exception
"""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Log path — resolved relative to this file's project root
# ---------------------------------------------------------------------------

def _log_path() -> Path:
    """Return the JSONL log path, creating parent dirs if needed."""
    root = Path(__file__).resolve().parents[3]  # …/rebalance-OS/
    log_dir = root / "temp" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "calendar_oauth_activity.jsonl"


# ---------------------------------------------------------------------------
# Core append
# ---------------------------------------------------------------------------

def _append(event: str, detail: dict[str, Any] | None = None) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "device": socket.gethostname(),
        "event": event,
        "detail": detail or {},
    }
    try:
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # never let logging break the caller


# ---------------------------------------------------------------------------
# Public helpers — one per event type
# ---------------------------------------------------------------------------

def log_flow_started(scopes: list[str]) -> None:
    _append("flow_started", {"scopes": scopes})


def log_flow_succeeded(expiry: str | None, scopes: list[str], token_path: str) -> None:
    _append("flow_succeeded", {
        "expiry": expiry,
        "scopes": scopes,
        "token_path": token_path,
    })


def log_flow_failed(error: str) -> None:
    _append("flow_failed", {"error": error})


def log_token_missing(token_path: str) -> None:
    _append("token_missing", {"token_path": token_path})


def log_token_refreshed(expiry: str | None, token_path: str) -> None:
    _append("token_refreshed", {"expiry": expiry, "token_path": token_path})


def log_token_refresh_failed(error: str, token_path: str) -> None:
    _append("token_refresh_failed", {"error": error, "token_path": token_path})


# ---------------------------------------------------------------------------
# Reader — for the web endpoint
# ---------------------------------------------------------------------------

def read_log(limit: int = 200) -> list[dict[str, Any]]:
    """Return the most recent *limit* entries, newest first."""
    path = _log_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(entries[-limit:]))
