"""
Gmail collector — fetches the newest N messages from the user's inbox via
the Gmail API, persists metadata + snippets to SQLite, and feeds the
unified semantic index alongside vault and GitHub.

Phase 1 scope:
- newest 100 messages, configurable via ``gmail_query_filter`` in
  ``temp/rbos.config`` (default: ``in:inbox``)
- metadata + Gmail-provided snippet only; no MIME body extraction
- upsert keyed on Gmail's ``message_id``

Auth: Application Default Credentials (ADC). Setup is documented in
README. The runtime probe here fails loudly with the exact gcloud
command if the credentials are missing or lack the Gmail scope.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DEFAULT_QUERY_FILTER = "in:inbox"
DEFAULT_MAX_RESULTS = 100

GCLOUD_LOGIN_HINT = (
    "gcloud auth application-default login "
    "--scopes=https://www.googleapis.com/auth/gmail.readonly,"
    "https://www.googleapis.com/auth/cloud-platform"
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class GmailSyncResult:
    messages_listed: int
    messages_stored: int
    messages_inserted: int
    messages_updated: int
    query_filter: str
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class GmailAuthError(RuntimeError):
    """Raised when ADC credentials are missing or lack the Gmail scope."""


def _load_adc_credentials() -> Any:
    """Load Application Default Credentials with the Gmail readonly scope.

    Fails loudly with the exact ``gcloud`` command needed to fix the most
    common failure modes (no ADC at all, or ADC without Gmail scope).
    """
    try:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError as exc:
        raise GmailAuthError(
            "google-auth is required for Gmail ingest. Install with: "
            "pip install 'rebalance-os[calendar]' (the calendar extra "
            "already pulls in google-auth dependencies)."
        ) from exc

    try:
        creds, _project = google.auth.default(scopes=[GMAIL_READONLY_SCOPE])
    except DefaultCredentialsError as exc:
        raise GmailAuthError(
            "No Application Default Credentials found. Run:\n"
            f"  {GCLOUD_LOGIN_HINT}"
        ) from exc

    return creds


def _build_service() -> Any:
    """Build a Gmail API v1 service client using ADC."""
    from googleapiclient.discovery import build
    creds = _load_adc_credentials()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# ---------------------------------------------------------------------------
# Header parsing helpers
# ---------------------------------------------------------------------------


def _headers_to_dict(headers: list[dict[str, str]]) -> dict[str, str]:
    """Lower-case header lookup. Last-write-wins for duplicates."""
    return {h.get("name", "").lower(): h.get("value", "") for h in headers}


def _parse_received_at(headers: dict[str, str], internal_date_ms: str | None) -> str:
    """Return an ISO-8601 UTC timestamp.

    Prefer the ``Date`` header; fall back to Gmail's ``internalDate``
    (ms epoch) which is always present.
    """
    date_header = headers.get("date", "")
    if date_header:
        try:
            dt = parsedate_to_datetime(date_header)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass

    if internal_date_ms:
        try:
            ms = int(internal_date_ms)
            return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass

    return ""


def _parse_from(headers: dict[str, str]) -> tuple[str, str]:
    """Return ``(from_name, from_address)`` parsed from the ``From`` header."""
    raw = headers.get("from", "")
    if not raw:
        return "", ""
    name, address = parseaddr(raw)
    return name.strip(), address.strip().lower()


# ---------------------------------------------------------------------------
# Fetch + persist
# ---------------------------------------------------------------------------


def _is_insufficient_scope_error(exc: Exception) -> bool:
    """Detect Gmail's 403 insufficient-scope response conservatively."""
    status = getattr(getattr(exc, "resp", None), "status", None)
    try:
        status_int = int(status) if status is not None else None
    except (TypeError, ValueError):
        status_int = None
    if status_int != 403:
        return False

    content = getattr(exc, "content", b"")
    if isinstance(content, bytes):
        body = content.decode("utf-8", errors="ignore").lower()
    else:
        body = str(content).lower()

    return any(
        marker in body
        for marker in (
            "insufficient authentication scopes",
            "access_token_scope_insufficient",
            "insufficientpermissions",
        )
    )


def sync_gmail(
    database_path: Path,
    *,
    query_filter: str | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    service: Any = None,
) -> GmailSyncResult:
    """Fetch newest-N inbox messages and upsert into ``email_messages``.

    Args:
        database_path: SQLite database path.
        query_filter: Gmail search query (e.g. ``in:inbox``). Defaults to
            ``gmail_query_filter`` in ``rbos.config`` then to ``in:inbox``.
        max_results: Cap on messages fetched per run (default 100).
        service: Pre-built Gmail service (test injection point). When
            ``None``, builds via ADC.
    """
    from rebalance.ingest.config import get_gmail_query_filter
    from rebalance.ingest.db import db_connection, ensure_email_schema

    start = time.monotonic()

    if query_filter is None:
        query_filter = get_gmail_query_filter() or DEFAULT_QUERY_FILTER

    if service is None:
        service = _build_service()

    try:
        list_response = service.users().messages().list(
            userId="me",
            q=query_filter,
            maxResults=max_results,
        ).execute()
    except Exception as exc:
        if _is_insufficient_scope_error(exc):
            raise GmailAuthError(
                "ADC token is missing the Gmail readonly scope. Re-run:\n"
                f"  {GCLOUD_LOGIN_HINT}\n"
                "(Adding new scopes requires re-running the login command — "
                "it does not merge with previous scopes silently.)"
            ) from exc
        raise
    message_refs = list_response.get("messages", []) or []

    synced_at = datetime.now(timezone.utc).isoformat()
    metadata_headers = ["From", "To", "Subject", "Date"]

    inserted = 0
    updated = 0
    stored = 0

    with db_connection(database_path, ensure_email_schema) as conn:
        for ref in message_refs:
            msg_id = ref.get("id")
            if not msg_id:
                continue

            msg = service.users().messages().get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=metadata_headers,
            ).execute()

            payload = msg.get("payload", {}) or {}
            headers = _headers_to_dict(payload.get("headers", []) or [])
            from_name, from_address = _parse_from(headers)
            received_at = _parse_received_at(headers, msg.get("internalDate"))
            subject = headers.get("subject", "")
            snippet = msg.get("snippet", "") or ""
            thread_id = msg.get("threadId", "") or ""
            labels = msg.get("labelIds", []) or []

            existed = conn.execute(
                "SELECT 1 FROM email_messages WHERE message_id = ?",
                (msg_id,),
            ).fetchone() is not None

            conn.execute(
                """INSERT OR REPLACE INTO email_messages
                   (message_id, thread_id, from_address, from_name, subject,
                    snippet, received_at, labels_json, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg_id,
                    thread_id,
                    from_address,
                    from_name,
                    subject,
                    snippet,
                    received_at,
                    json.dumps(labels),
                    synced_at,
                ),
            )
            if existed:
                updated += 1
            else:
                inserted += 1
            stored += 1

        conn.commit()

    return GmailSyncResult(
        messages_listed=len(message_refs),
        messages_stored=stored,
        messages_inserted=inserted,
        messages_updated=updated,
        query_filter=query_filter,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


def ingest_email_messages(
    database_path: Path,
    messages: list[dict[str, Any]],
) -> GmailSyncResult:
    """Upsert already-fetched email messages into ``email_messages``.

    The MCP-path counterpart to :func:`sync_gmail`. Instead of fetching from the
    Gmail API via ADC, the caller supplies messages already fetched by some
    other route — e.g. an agent using the Gmail MCP connector. This keeps the
    ``email_messages`` write path identical regardless of how the data arrived.

    Each *message* dict accepts: ``message_id`` (required), ``thread_id``,
    ``from_address``, ``from_name``, ``subject``, ``snippet``, ``received_at``,
    and ``labels`` (list of label strings). Missing keys default to empty.
    Messages without a ``message_id`` are skipped.
    """
    from rebalance.ingest.db import db_connection, ensure_email_schema

    start = time.monotonic()
    synced_at = datetime.now(timezone.utc).isoformat()
    inserted = updated = stored = 0

    with db_connection(database_path, ensure_email_schema) as conn:
        for m in messages:
            msg_id = str(m.get("message_id") or "").strip()
            if not msg_id:
                continue
            existed = conn.execute(
                "SELECT 1 FROM email_messages WHERE message_id = ?", (msg_id,)
            ).fetchone() is not None
            conn.execute(
                """INSERT OR REPLACE INTO email_messages
                   (message_id, thread_id, from_address, from_name, subject,
                    snippet, received_at, labels_json, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg_id,
                    str(m.get("thread_id") or ""),
                    str(m.get("from_address") or ""),
                    str(m.get("from_name") or ""),
                    str(m.get("subject") or ""),
                    str(m.get("snippet") or ""),
                    str(m.get("received_at") or ""),
                    json.dumps(list(m.get("labels") or [])),
                    synced_at,
                ),
            )
            if existed:
                updated += 1
            else:
                inserted += 1
            stored += 1
        conn.commit()

    return GmailSyncResult(
        messages_listed=len(messages),
        messages_stored=stored,
        messages_inserted=inserted,
        messages_updated=updated,
        query_filter="mcp",
        elapsed_seconds=round(time.monotonic() - start, 2),
    )
