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
import pickle
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DEFAULT_QUERY_FILTER = "in:inbox"
DEFAULT_MAX_RESULTS = 100

# launchd-reachable fallback for the OAuth token (keychain is unreachable from
# the daily-sync's stripped environment). Mirrors calendar's TOKEN_PATH.
TOKEN_PATH = Path.home() / ".config" / "rebalance-os" / "google-gmail-oauth"

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

    Mirrors :func:`rebalance.ingest.calendar._load_credentials`: keyring
    (interactive primary) ↔ the pickle file (launchd reads this; the keychain
    is unreachable from the daily-sync's stripped environment). On refresh, the
    rotated access token is written back to BOTH so each stays current.
    """
    import json as _json

    from rebalance.ingest.auth_log import (
        log_token_missing,
        log_token_refresh_failed,
        log_token_refreshed,
    )
    from rebalance.ingest.config import (
        get_gmail_oauth_token_json,
        set_gmail_oauth_token_json,
    )

    creds = None
    blob = get_gmail_oauth_token_json()
    if blob:
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_info(_json.loads(blob))
        except Exception:  # noqa: BLE001 — corrupt/legacy blob → fall back to pickle
            creds = None

    if creds is None:
        if not TOKEN_PATH.exists():
            log_token_missing(str(TOKEN_PATH), source="gmail")
            raise GmailAuthError(
                f"Gmail OAuth token not found (keyring empty and no file at {TOKEN_PATH}).\n"
                f"  Run: {GMAIL_SETUP_HINT}\n"
                "  Or switch to the Gmail MCP connector: `gmail_ingest_method=mcp`."
            )
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    # Refresh if expired — persist the rotated access token to both stores.
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        try:
            creds.refresh(Request())
            # record=False: an access-token refresh is not a re-authorization.
            set_gmail_oauth_token_json(creds.to_json(), source="refresh", record=False)
            try:
                with open(TOKEN_PATH, "wb") as f:
                    pickle.dump(creds, f)
            except OSError:
                pass
            log_token_refreshed(
                expiry=creds.expiry.isoformat() if creds.expiry else None,
                token_path=str(TOKEN_PATH),
                source="gmail",
            )
        except Exception as exc:
            log_token_refresh_failed(error=str(exc), token_path=str(TOKEN_PATH), source="gmail")
            raise

    if required_scopes and not _credentials_have_scopes(creds, required_scopes):
        raise GmailAuthError(
            "Gmail OAuth token does not include the required scope "
            f"({', '.join(required_scopes)}). Current: {getattr(creds, 'scopes', []) or []}.\n"
            f"  Re-run: {GMAIL_SETUP_HINT}"
        )

    return creds


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
