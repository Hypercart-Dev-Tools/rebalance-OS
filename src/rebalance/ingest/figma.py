"""Figma comment ingestion.

The Figma REST API exposes comments per file, not as a global feed. This
collector therefore takes a configured list of file keys, fetches each file's
comments, and upserts by ``file_key:comment_id``. Rows are retained as history;
new comments are reported as inserts and changed/resolved comments as updates.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Protocol

from rebalance.ingest.db import db_connection, run_migrations
from rebalance.lib.time_ops import _now
from rebalance.lib.json_ops import _json_dumps

if TYPE_CHECKING:  # import-cycle / mlx-free: only for type checkers
    from rebalance.ingest.semantic_index import SemanticDoc

FIGMA_API_BASE = "https://api.figma.com"
USER_AGENT = "rebalance-os/0.31"

logger = logging.getLogger(__name__)


class FigmaAPIError(RuntimeError):
    """Raised when Figma returns a non-success response."""

    def __init__(self, message: str, *, status: int = 0, url: str = "", body: str = ""):
        super().__init__(message)
        self.status = status
        self.url = url
        self.body = body


class FigmaClientProtocol(Protocol):
    def get_comments(self, file_key: str, *, as_md: bool = True) -> list[dict[str, Any]]:
        """Return comments for one Figma file key."""


class FigmaClient:
    """Small urllib-based client for the Figma comments endpoint."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = FIGMA_API_BASE,
        timeout: int = 30,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.token = token.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self.token:
            headers["X-Figma-Token"] = self.token
        return headers

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8") if exc.fp else ""
            except Exception:  # noqa: BLE001 - response stream may already be closed
                body = ""
            raise FigmaAPIError(
                f"Figma API request failed: {exc.code} {url}",
                status=exc.code,
                url=url,
                body=body,
            ) from exc
        except urllib.error.URLError as exc:
            raise FigmaAPIError(f"Figma API request failed: {exc.reason}", url=url) from exc

    def get_comments(self, file_key: str, *, as_md: bool = True) -> list[dict[str, Any]]:
        data = self._get_json(
            f"/v1/files/{urllib.parse.quote(file_key, safe='')}/comments",
            params={"as_md": "true" if as_md else "false"},
        )
        comments = data.get("comments") if isinstance(data, dict) else None
        if not isinstance(comments, list):
            raise FigmaAPIError("Figma comments response did not include a comments list")
        return [item for item in comments if isinstance(item, dict)]


@dataclass(frozen=True)
class FigmaSyncResult:
    files_requested: int
    files_synced: int
    comments_fetched: int
    comments_inserted: int
    comments_updated: int
    comments_unchanged: int
    errors: list[dict[str, str]]
    elapsed_seconds: float


def _user_name(user: Any) -> str:
    if not isinstance(user, dict):
        return ""
    return str(user.get("handle") or user.get("name") or "").strip()


def _user_id(user: Any) -> str:
    if not isinstance(user, dict):
        return ""
    return str(user.get("id") or "").strip()


def _comment_record(file_key: str, raw: dict[str, Any], synced_at: str) -> dict[str, Any]:
    comment_id = str(raw.get("id") or "").strip()
    message = str(raw.get("message") or "").strip()
    created_at = str(raw.get("created_at") or "").strip()
    resolved_at = str(raw.get("resolved_at") or "").strip()
    parent_id = str(raw.get("parent_id") or "").strip()
    user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    client_meta = raw.get("client_meta") if isinstance(raw.get("client_meta"), dict) else {}
    reactions = raw.get("reactions") if isinstance(raw.get("reactions"), list) else []
    order_id = raw.get("order_id")
    return {
        "comment_key": f"{file_key}:{comment_id}",
        "file_key": file_key,
        "comment_id": comment_id,
        "parent_id": parent_id,
        "message": message,
        "user_id": _user_id(user),
        "user_handle": _user_name(user),
        "created_at": created_at,
        "resolved_at": resolved_at,
        "order_id": order_id if isinstance(order_id, (int, float)) else None,
        "client_meta_json": _json_dumps(client_meta),
        "reactions_json": _json_dumps(reactions),
        "raw_json": _json_dumps(raw),
        "synced_at": synced_at,
    }


def _upsert_comment(conn: Any, record: dict[str, Any]) -> str:
    existing = conn.execute(
        """
        SELECT parent_id, message, user_id, user_handle, created_at, resolved_at,
               order_id, client_meta_json, reactions_json, raw_json
        FROM figma_comments
        WHERE comment_key = ?
        """,
        (record["comment_key"],),
    ).fetchone()

    columns = [
        "comment_key",
        "file_key",
        "comment_id",
        "parent_id",
        "message",
        "user_id",
        "user_handle",
        "created_at",
        "resolved_at",
        "order_id",
        "client_meta_json",
        "reactions_json",
        "raw_json",
        "synced_at",
    ]
    values = [record[column] for column in columns]

    if existing is None:
        placeholders = ", ".join("?" for _ in columns)
        conn.execute(
            f"INSERT INTO figma_comments ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return "inserted"

    changed = any(
        (existing[column] or "") != (record[column] or "")
        for column in [
            "parent_id",
            "message",
            "user_id",
            "user_handle",
            "created_at",
            "resolved_at",
            "order_id",
            "client_meta_json",
            "reactions_json",
            "raw_json",
        ]
    )
    if not changed:
        conn.execute(
            "UPDATE figma_comments SET synced_at = ? WHERE comment_key = ?",
            (record["synced_at"], record["comment_key"]),
        )
        return "unchanged"

    assignments = ", ".join(f"{column} = ?" for column in columns[3:])
    conn.execute(
        f"UPDATE figma_comments SET {assignments} WHERE comment_key = ?",
        [record[column] for column in columns[3:]] + [record["comment_key"]],
    )
    return "updated"


def sync_figma_comments(
    database_path: Path,
    *,
    file_keys: list[str],
    token: str,
    client: FigmaClientProtocol | None = None,
) -> FigmaSyncResult:
    """Fetch and upsert comments for configured Figma files."""
    start = time.monotonic()
    unique_file_keys: list[str] = []
    for file_key in file_keys:
        item = str(file_key or "").strip()
        if item and item not in unique_file_keys:
            unique_file_keys.append(item)

    figma = client or FigmaClient(token)
    synced_at = _now()
    files_synced = comments_fetched = inserted = updated = unchanged = 0
    errors: list[dict[str, str]] = []

    with db_connection(database_path) as conn:
        run_migrations(conn)
        for file_key in unique_file_keys:
            try:
                comments = figma.get_comments(file_key, as_md=True)
            except FigmaAPIError as exc:
                logger.warning("Figma comments sync failed for file %s: %s", file_key, exc)
                errors.append({"file_key": file_key, "error": str(exc)})
                continue

            files_synced += 1
            comments_fetched += len(comments)
            for raw in comments:
                if not str(raw.get("id") or "").strip():
                    continue
                state = _upsert_comment(conn, _comment_record(file_key, raw, synced_at))
                if state == "inserted":
                    inserted += 1
                elif state == "updated":
                    updated += 1
                else:
                    unchanged += 1
        conn.commit()

    return FigmaSyncResult(
        files_requested=len(unique_file_keys),
        files_synced=files_synced,
        comments_fetched=comments_fetched,
        comments_inserted=inserted,
        comments_updated=updated,
        comments_unchanged=unchanged,
        errors=errors,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


def figma_semantic_docs(conn: Any) -> "Iterator[SemanticDoc]":
    """Yield one :class:`SemanticDoc` per Figma comment with non-empty body.

    This is the registry-driven SourceModule provider: the flag-gated path in
    ``backfill_semantic_documents`` iterates it (source_table ``figma_comments``)
    instead of an if-ladder branch. Imports of ``SemanticDoc`` and the read
    helper are function-local so this module's top-level imports stay limited to
    ``rebalance.ingest.db`` and never pull in mlx/the embedder.
    """
    from rebalance.ingest.db import semantic as sem  # noqa: PLC0415
    from rebalance.ingest.semantic_index import SemanticDoc  # noqa: PLC0415

    for row in sem.figma_comments_for_semantic(conn):
        message = row["message"] or ""
        if not message.strip():
            continue

        author = row["user_handle"] or row["user_id"] or "Figma user"
        created_at = row["created_at"] or row["synced_at"]
        yield SemanticDoc(
            source_pk=row["comment_key"],
            doc_kind="comment",
            title=f"Figma comment by {author}",
            body=message,
            metadata={
                "file_key": row["file_key"],
                "comment_id": row["comment_id"],
                "parent_id": row["parent_id"] or "",
                "user_id": row["user_id"] or "",
                "user_handle": row["user_handle"] or "",
                "created_at": created_at,
                "resolved_at": row["resolved_at"] or "",
                "client_meta": json.loads(row["client_meta_json"]) if row["client_meta_json"] else {},
                "reactions": json.loads(row["reactions_json"]) if row["reactions_json"] else [],
            },
            created_at=created_at,
            updated_at=row["synced_at"],
        )
