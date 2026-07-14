"""
Gmail collector — fetches the newest N messages from the user's inbox via
the Gmail API, persists metadata + snippets to SQLite, and feeds the
unified semantic index alongside vault and GitHub.

Phase 1 scope:
- newest 100 messages, configurable via ``gmail_query_filter`` in
  ``temp/rbos.config`` (default: ``in:inbox``)
- metadata + Gmail-provided snippet only; no MIME body extraction
- upsert keyed on Gmail's ``message_id``

Auth: desktop OAuth (browser consent once via
``scripts/setup_gmail_oauth.py``), stored in the OS keyring with a
pickle-file fallback that launchd can read. This mirrors the Calendar
credential model exactly — keyring primary, file fallback, rotated
access tokens written back to both on refresh. A user's own OAuth
client (Testing mode) can request the restricted ``gmail.readonly``
scope without app verification, which the shared gcloud ADC client
cannot — so this path works for public cloners where ADC did not.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DEFAULT_QUERY_FILTER = "in:inbox"
DEFAULT_MAX_RESULTS = 100

# launchd-reachable fallback for the OAuth token (keychain is unreachable from
# the daily-sync's stripped environment). Mirrors calendar's TOKEN_PATH.
from rebalance.paths import resolve_oauth_token_path
TOKEN_PATH = resolve_oauth_token_path("gmail")

GMAIL_SETUP_HINT = (
    "python scripts/setup_gmail_oauth.py   "
    "(one-time browser consent; then `rebalance config migrate-to-keyring`)"
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
    # Rows REJECTED at the write boundary for carrying no signal (no sender, no
    # subject, no timestamp). Defaulted so existing constructors are unaffected.
    messages_skipped: int = 0


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class GmailAuthError(RuntimeError):
    """Raised when the Gmail OAuth token is missing or lacks the Gmail scope."""


def _credentials_have_scopes(creds: Any, required_scopes: list[str]) -> bool:
    """Return True if the credentials cover every required scope."""
    current = set(getattr(creds, "scopes", []) or [])
    return all(scope in current for scope in required_scopes)


def _load_credentials(required_scopes: list[str] | None = None) -> Any:
    """Load OAuth2 credentials — keyring first, pickle file as the launchd fallback.

    Delegates the keyring→pickle→refresh→persist-both flow to
    :func:`rebalance.ingest.oauth_common.load_credentials`; only the
    Gmail-specific error messages and scope rule live here.
    """
    from rebalance.ingest import oauth_common
    from rebalance.ingest.config import (
        get_gmail_oauth_token_json,
        set_gmail_oauth_token_json,
    )

    def _missing(token_path: str) -> Exception:
        return GmailAuthError(
            f"Gmail OAuth token not found (keyring empty and no file at {token_path}).\n"
            f"  Run: {GMAIL_SETUP_HINT}\n"
            "  Or switch to the Gmail MCP connector: `gmail_ingest_method=mcp`."
        )

    def _scope_error(creds: Any, required: list[str]) -> Exception:
        return GmailAuthError(
            "Gmail OAuth token does not include the required scope "
            f"({', '.join(required)}). Current: {getattr(creds, 'scopes', []) or []}.\n"
            f"  Re-run: {GMAIL_SETUP_HINT}"
        )

    svc = oauth_common.OAuthService(
        name="gmail",
        token_path=TOKEN_PATH,
        get_token_json=get_gmail_oauth_token_json,
        set_token_json=set_gmail_oauth_token_json,
        has_scopes=_credentials_have_scopes,
        missing_error=_missing,
        scope_error=_scope_error,
    )
    return oauth_common.load_credentials(svc, required_scopes)


def _build_service() -> Any:
    """Build a Gmail API v1 service client from the desktop OAuth token."""
    from googleapiclient.discovery import build
    creds = _load_credentials(required_scopes=[GMAIL_READONLY_SCOPE])
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
            from rebalance.ingest import auth_log
            auth_log.log_gmail_scope_insufficient(str(exc))
            raise GmailAuthError(
                "Gmail OAuth token is missing the gmail.readonly scope. Re-run:\n"
                f"  {GMAIL_SETUP_HINT}"
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


def push_email_messages(
    database_path: Path,
    messages: list[dict[str, Any]],
) -> GmailSyncResult:
    """Source-owned entry point for the MCP Gmail push-ingest: upsert the
    caller-provided messages into email_messages. The MCP tool uses this so it
    no longer imports the leaf ingest_email_messages directly
    (COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2). Semantic projection is owned
    by the semantic stage (Phase 3) and runs as a follow-on step.
    """
    return ingest_email_messages(database_path, messages)


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

    CONTENTLESS rows are REJECTED, not stored. A message carrying no sender, no
    subject AND no ``received_at`` is not a message — it is a shell. This path
    takes caller-supplied dicts, so a caller whose payload uses DIFFERENT key
    names (a raw Gmail API resource, another connector's shape) would otherwise
    have every unmatched field silently coerced to ``""`` by the ``or ""``
    defaulting below, and the table would fill with rows that look ingested and
    are unusable. That is not hypothetical: on 2026-06-25 a single push landed
    119 such rows on the primary device — 96% of the table — and they were
    invisible until GH-125 tried to rank email and found nothing to rank. Reject
    at the boundary and TELL the caller (``messages_skipped``), so a wrong payload
    shape surfaces as a number instead of as silent data loss.
    """
    from rebalance.ingest.db import db_connection, ensure_email_schema

    start = time.monotonic()
    synced_at = datetime.now(timezone.utc).isoformat()
    inserted = updated = stored = skipped = 0

    with db_connection(database_path, ensure_email_schema) as conn:
        for m in messages:
            msg_id = str(m.get("message_id") or "").strip()
            if not msg_id:
                skipped += 1
                continue
            # A row needs at least ONE of sender / subject / timestamp to be a
            # message at all. None of the three → nothing to attest with, nothing
            # to rank, nothing to show. Refuse it.
            if not (
                str(m.get("from_address") or "").strip()
                or str(m.get("from_name") or "").strip()
                or str(m.get("subject") or "").strip()
                or str(m.get("received_at") or "").strip()
            ):
                skipped += 1
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

    if skipped:
        # NON-SILENT: a skipped row almost always means the caller's payload uses
        # different key names, not that the mail was empty. Name the likely cause.
        logger.warning(
            "ingest_email_messages: REJECTED %d of %d message(s) carrying no sender, "
            "no subject and no received_at. Expected keys: message_id, thread_id, "
            "from_address, from_name, subject, snippet, received_at, labels — check "
            "the payload's key names.",
            skipped,
            len(messages),
        )

    return GmailSyncResult(
        messages_listed=len(messages),
        messages_stored=stored,
        messages_inserted=inserted,
        messages_updated=updated,
        query_filter="mcp",
        elapsed_seconds=round(time.monotonic() - start, 2),
        messages_skipped=skipped,
    )
