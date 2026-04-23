"""
Sleuth reminders ingestor — pulls the Slack-reminders feed exposed by the
Sleuth Web API and mirrors it into SQLite.

HTTP layer mirrors github_scan.py: stdlib urllib, Bearer auth, a 30s timeout,
single attempt (no retries).  Sleuth returns HTTP 200 even on auth/workspace
errors — payload["success"] is the source of truth.

Rows are upserted by reminder_id.  Rows that disappear from the server
response are NOT deleted: we want history, and activeOnly=true responses
omit completed reminders that we still want to keep.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HTTP_TIMEOUT_SECONDS = 30
USER_AGENT = "rebalance-os/0.1"


class SleuthApiError(Exception):
    """Raised when the Sleuth API is unreachable or returns success=false."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SleuthReminder:
    reminder_id: str
    state: str
    is_active: bool
    created_on: datetime | None
    should_post_on: datetime | None
    reminder_message_text: str
    ignore_snooze: bool
    assignee_id: str | None
    original_sender_id: str | None
    target_channel_id: str | None
    original_channel_id: str | None
    original_channel_name: str | None
    original_message_id: str | None
    original_thread_ts: str | None
    github_urls: tuple[str, ...]


@dataclass
class SleuthSyncResult:
    workspace_name: str
    fetched_at: str
    total_reminder_count: int
    returned_reminder_count: int
    inserted_count: int
    updated_count: int
    unchanged_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace_name": self.workspace_name,
            "fetched_at": self.fetched_at,
            "total_reminder_count": self.total_reminder_count,
            "returned_reminder_count": self.returned_reminder_count,
            "inserted_count": self.inserted_count,
            "updated_count": self.updated_count,
            "unchanged_count": self.unchanged_count,
        }


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    # datetime.fromisoformat doesn't accept the trailing "Z" before Python 3.11.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_reminder(data: dict[str, Any]) -> SleuthReminder:
    raw_urls = data.get("githubUrls") or []
    urls: tuple[str, ...]
    if isinstance(raw_urls, list):
        urls = tuple(str(u) for u in raw_urls if isinstance(u, str) and u.strip())
    else:
        urls = ()
    return SleuthReminder(
        reminder_id=str(data["reminderId"]),
        state=str(data.get("state", "")),
        is_active=bool(data.get("isActive", False)),
        created_on=_parse_datetime(data.get("createdOn")),
        should_post_on=_parse_datetime(data.get("shouldPostOn")),
        reminder_message_text=str(data.get("reminderMessageText", "")),
        ignore_snooze=bool(data.get("ignoreSnooze", False)),
        assignee_id=_optional_str(data.get("assigneeId")),
        original_sender_id=_optional_str(data.get("originalSenderId")),
        target_channel_id=_optional_str(data.get("targetChannelId")),
        original_channel_id=_optional_str(data.get("originalChannelId")),
        original_channel_name=_optional_str(data.get("originalChannelName")),
        original_message_id=_optional_str(data.get("originalMessageId")),
        original_thread_ts=_optional_str(data.get("originalThreadTs")),
        github_urls=urls,
    )


def _iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _fetch_payload(
    base_url: str,
    token: str,
    workspace_name: str,
    active_only: bool,
) -> dict[str, Any]:
    active_param = "true" if active_only else "false"
    url = (
        f"{base_url.rstrip('/')}"
        f"/workspace/{urllib.parse.quote(workspace_name, safe='')}"
        f"/reminders?format=rebalance&activeOnly={active_param}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise SleuthApiError(
            f"Sleuth API returned HTTP {exc.code}",
            status=exc.code,
            body=err_body,
        ) from exc
    except urllib.error.URLError as exc:
        raise SleuthApiError(f"Sleuth API unreachable: {exc.reason}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SleuthApiError(f"Sleuth API returned invalid JSON: {exc}") from exc

    if not isinstance(payload, dict) or not payload.get("success"):
        error_data = payload.get("data") if isinstance(payload, dict) else None
        raise SleuthApiError(
            f"Sleuth API error: {error_data or 'unknown'}",
            status=200,
            body=body,
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise SleuthApiError(
            "Sleuth API response missing 'data' object",
            status=200,
            body=body,
        )
    return data


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------


def ensure_sleuth_schema(conn: sqlite3.Connection) -> None:
    """Create sleuth_reminders table and indexes if they don't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sleuth_reminders (
            reminder_id             TEXT PRIMARY KEY,
            workspace_name          TEXT NOT NULL,
            state                   TEXT NOT NULL,
            is_active               INTEGER NOT NULL,
            created_on              TEXT,
            should_post_on          TEXT,
            reminder_message_text   TEXT NOT NULL,
            ignore_snooze           INTEGER NOT NULL,
            assignee_id             TEXT,
            original_sender_id      TEXT,
            target_channel_id       TEXT,
            original_channel_id     TEXT,
            original_channel_name   TEXT,
            original_message_id     TEXT,
            original_thread_ts      TEXT,
            github_urls_json        TEXT NOT NULL,
            first_seen_at           TEXT NOT NULL,
            last_seen_at            TEXT NOT NULL,
            last_synced_at          TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sleuth_reminders_state "
        "ON sleuth_reminders(state)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sleuth_reminders_active "
        "ON sleuth_reminders(is_active)"
    )
    conn.commit()


_UPDATE_FIELDS = (
    "state",
    "is_active",
    "created_on",
    "should_post_on",
    "reminder_message_text",
    "ignore_snooze",
    "assignee_id",
    "original_sender_id",
    "target_channel_id",
    "original_channel_id",
    "original_channel_name",
    "original_message_id",
    "original_thread_ts",
    "github_urls_json",
)


def _row_values(r: SleuthReminder, github_urls_json: str) -> dict[str, Any]:
    return {
        "state": r.state,
        "is_active": 1 if r.is_active else 0,
        "created_on": _iso_or_none(r.created_on),
        "should_post_on": _iso_or_none(r.should_post_on),
        "reminder_message_text": r.reminder_message_text,
        "ignore_snooze": 1 if r.ignore_snooze else 0,
        "assignee_id": r.assignee_id,
        "original_sender_id": r.original_sender_id,
        "target_channel_id": r.target_channel_id,
        "original_channel_id": r.original_channel_id,
        "original_channel_name": r.original_channel_name,
        "original_message_id": r.original_message_id,
        "original_thread_ts": r.original_thread_ts,
        "github_urls_json": github_urls_json,
    }


def _row_differs(existing: sqlite3.Row, desired: dict[str, Any]) -> bool:
    for field_name in _UPDATE_FIELDS:
        if existing[field_name] != desired[field_name]:
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync_sleuth_reminders(
    base_url: str,
    token: str,
    workspace_name: str,
    database_path: Path,
    *,
    active_only: bool = False,
) -> SleuthSyncResult:
    """Fetch reminders from Sleuth and upsert them into sleuth_reminders."""
    from rebalance.ingest.db import db_connection

    data = _fetch_payload(base_url, token, workspace_name, active_only)

    reminders_raw = data.get("reminders") or []
    if not isinstance(reminders_raw, list):
        raise SleuthApiError("Sleuth API response 'reminders' is not a list")

    reminders = [_to_reminder(item) for item in reminders_raw if isinstance(item, dict)]

    now_iso = datetime.now(timezone.utc).isoformat()
    inserted = updated = unchanged = 0

    with db_connection(database_path, ensure_sleuth_schema) as conn:
        for r in reminders:
            github_urls_json = json.dumps(list(r.github_urls), ensure_ascii=False)
            desired = _row_values(r, github_urls_json)

            row = conn.execute(
                """
                SELECT state, is_active, created_on, should_post_on,
                       reminder_message_text, ignore_snooze, assignee_id,
                       original_sender_id, target_channel_id, original_channel_id,
                       original_channel_name, original_message_id,
                       original_thread_ts, github_urls_json
                FROM sleuth_reminders WHERE reminder_id = ?
                """,
                (r.reminder_id,),
            ).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO sleuth_reminders (
                        reminder_id, workspace_name, state, is_active,
                        created_on, should_post_on, reminder_message_text,
                        ignore_snooze, assignee_id, original_sender_id,
                        target_channel_id, original_channel_id,
                        original_channel_name, original_message_id,
                        original_thread_ts, github_urls_json,
                        first_seen_at, last_seen_at, last_synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.reminder_id,
                        workspace_name,
                        desired["state"],
                        desired["is_active"],
                        desired["created_on"],
                        desired["should_post_on"],
                        desired["reminder_message_text"],
                        desired["ignore_snooze"],
                        desired["assignee_id"],
                        desired["original_sender_id"],
                        desired["target_channel_id"],
                        desired["original_channel_id"],
                        desired["original_channel_name"],
                        desired["original_message_id"],
                        desired["original_thread_ts"],
                        desired["github_urls_json"],
                        now_iso,
                        now_iso,
                        now_iso,
                    ),
                )
                inserted += 1
                continue

            if _row_differs(row, desired):
                conn.execute(
                    """
                    UPDATE sleuth_reminders SET
                        workspace_name = ?,
                        state = ?,
                        is_active = ?,
                        created_on = ?,
                        should_post_on = ?,
                        reminder_message_text = ?,
                        ignore_snooze = ?,
                        assignee_id = ?,
                        original_sender_id = ?,
                        target_channel_id = ?,
                        original_channel_id = ?,
                        original_channel_name = ?,
                        original_message_id = ?,
                        original_thread_ts = ?,
                        github_urls_json = ?,
                        last_seen_at = ?,
                        last_synced_at = ?
                    WHERE reminder_id = ?
                    """,
                    (
                        workspace_name,
                        desired["state"],
                        desired["is_active"],
                        desired["created_on"],
                        desired["should_post_on"],
                        desired["reminder_message_text"],
                        desired["ignore_snooze"],
                        desired["assignee_id"],
                        desired["original_sender_id"],
                        desired["target_channel_id"],
                        desired["original_channel_id"],
                        desired["original_channel_name"],
                        desired["original_message_id"],
                        desired["original_thread_ts"],
                        desired["github_urls_json"],
                        now_iso,
                        now_iso,
                        r.reminder_id,
                    ),
                )
                updated += 1
            else:
                conn.execute(
                    "UPDATE sleuth_reminders SET last_seen_at = ?, last_synced_at = ? "
                    "WHERE reminder_id = ?",
                    (now_iso, now_iso, r.reminder_id),
                )
                unchanged += 1
        conn.commit()

    return SleuthSyncResult(
        workspace_name=str(data.get("workspaceName") or workspace_name),
        fetched_at=str(data.get("fetchedAt") or ""),
        total_reminder_count=int(data.get("totalReminderCount") or 0),
        returned_reminder_count=int(
            data.get("returnedReminderCount")
            if data.get("returnedReminderCount") is not None
            else len(reminders)
        ),
        inserted_count=inserted,
        updated_count=updated,
        unchanged_count=unchanged,
    )
