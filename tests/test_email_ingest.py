"""Tests for Phase 1 Gmail ingest: schema, sync, semantic backfill, and orchestration wiring."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from rebalance.ingest.db import db_connection, ensure_email_schema, ensure_semantic_schema
from rebalance.ingest.gmail import (
    DEFAULT_QUERY_FILTER,
    GmailAuthError,
    _parse_from,
    _parse_received_at,
    sync_gmail,
)
from rebalance.ingest.index_ops import SCOPE_VALUES, _normalize_scope, _refresh_email, get_index_status
from rebalance.ingest.semantic_index import (
    _normalize_sources,
    backfill_semantic_documents,
)


# ---------------------------------------------------------------------------
# Fake Gmail service — implements the chain users().messages().list/get used
# by sync_gmail with no network calls.
# ---------------------------------------------------------------------------


class _FakeRequest:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def execute(self) -> Any:
        return self._payload


class _FakeMessages:
    def __init__(self, list_payload: Any, message_map: dict[str, Any]) -> None:
        self._list_payload = list_payload
        self._message_map = message_map
        self.list_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []

    def list(self, **kwargs: Any) -> _FakeRequest:
        self.list_calls.append(kwargs)
        return _FakeRequest(self._list_payload)

    def get(self, **kwargs: Any) -> _FakeRequest:
        self.get_calls.append(kwargs)
        msg_id = kwargs.get("id")
        return _FakeRequest(self._message_map[msg_id])


class _FakeUsers:
    def __init__(self, messages_obj: _FakeMessages) -> None:
        self._messages_obj = messages_obj

    def messages(self) -> _FakeMessages:
        return self._messages_obj


class _FakeService:
    def __init__(self, list_payload: Any, message_map: dict[str, Any]) -> None:
        self._messages_obj = _FakeMessages(list_payload, message_map)

    def users(self) -> _FakeUsers:
        return _FakeUsers(self._messages_obj)

    @property
    def messages_obj(self) -> _FakeMessages:
        return self._messages_obj


def _make_message(
    msg_id: str,
    *,
    thread_id: str = "t1",
    from_header: str = '"Alice Example" <alice@example.com>',
    subject: str = "Hello",
    snippet: str = "preview text",
    date_header: str = "Mon, 04 May 2026 12:00:00 +0000",
    internal_date_ms: str = "1746360000000",
    labels: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": msg_id,
        "threadId": thread_id,
        "snippet": snippet,
        "internalDate": internal_date_ms,
        "labelIds": labels if labels is not None else ["INBOX", "UNREAD"],
        "payload": {
            "headers": [
                {"name": "From", "value": from_header},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": date_header},
                {"name": "To", "value": "noel@neochro.me"},
            ]
        },
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class EmailSchemaTests(unittest.TestCase):
    def test_ensure_email_schema_creates_table_with_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with db_connection(db_path, ensure_email_schema) as conn:
                cols = {row[1] for row in conn.execute("PRAGMA table_info(email_messages)").fetchall()}
        expected = {
            "message_id", "thread_id", "from_address", "from_name",
            "subject", "snippet", "received_at", "labels_json", "synced_at",
        }
        self.assertTrue(expected.issubset(cols), f"Missing columns: {expected - cols}")


# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------


class HeaderParsingTests(unittest.TestCase):
    def test_parse_from_extracts_name_and_address(self) -> None:
        name, addr = _parse_from({"from": '"Alice Example" <alice@example.com>'})
        self.assertEqual(name, "Alice Example")
        self.assertEqual(addr, "alice@example.com")

    def test_parse_from_lowercases_address(self) -> None:
        _, addr = _parse_from({"from": "Bob <BOB@EXAMPLE.COM>"})
        self.assertEqual(addr, "bob@example.com")

    def test_parse_from_empty(self) -> None:
        self.assertEqual(_parse_from({}), ("", ""))

    def test_parse_received_at_prefers_date_header(self) -> None:
        result = _parse_received_at(
            {"date": "Mon, 04 May 2026 12:00:00 +0000"},
            internal_date_ms="999",
        )
        self.assertTrue(result.startswith("2026-05-04T12:00:00"))

    def test_parse_received_at_falls_back_to_internal_date(self) -> None:
        result = _parse_received_at({}, internal_date_ms="1778241600000")
        # ISO-8601 UTC; exact value verified by round-trip
        self.assertEqual(result, "2026-05-08T12:00:00+00:00")

    def test_parse_received_at_returns_empty_when_both_missing(self) -> None:
        self.assertEqual(_parse_received_at({}, internal_date_ms=None), "")


# ---------------------------------------------------------------------------
# sync_gmail upsert behavior
# ---------------------------------------------------------------------------


class SyncGmailTests(unittest.TestCase):
    def test_first_sync_inserts_all_messages(self) -> None:
        service = _FakeService(
            list_payload={"messages": [{"id": "m1"}, {"id": "m2"}]},
            message_map={
                "m1": _make_message("m1", subject="First"),
                "m2": _make_message("m2", subject="Second"),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            result = sync_gmail(db_path, query_filter="in:inbox", service=service)

            self.assertEqual(result.messages_listed, 2)
            self.assertEqual(result.messages_inserted, 2)
            self.assertEqual(result.messages_updated, 0)

            with db_connection(db_path) as conn:
                rows = conn.execute(
                    "SELECT message_id, subject, from_address FROM email_messages ORDER BY message_id"
                ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["from_address"], "alice@example.com")

    def test_repeat_sync_with_label_change_upserts_existing(self) -> None:
        first = _FakeService(
            list_payload={"messages": [{"id": "m1"}]},
            message_map={"m1": _make_message("m1", labels=["INBOX", "UNREAD"])},
        )
        second = _FakeService(
            list_payload={"messages": [{"id": "m1"}]},
            message_map={"m1": _make_message("m1", labels=["INBOX"])},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            r1 = sync_gmail(db_path, query_filter="in:inbox", service=first)
            r2 = sync_gmail(db_path, query_filter="in:inbox", service=second)

            self.assertEqual(r1.messages_inserted, 1)
            self.assertEqual(r2.messages_inserted, 0)
            self.assertEqual(r2.messages_updated, 1)

            with db_connection(db_path) as conn:
                row = conn.execute(
                    "SELECT labels_json FROM email_messages WHERE message_id = 'm1'"
                ).fetchone()
            self.assertEqual(json.loads(row["labels_json"]), ["INBOX"])

    def test_query_filter_is_passed_through_to_list(self) -> None:
        service = _FakeService(list_payload={"messages": []}, message_map={})
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            sync_gmail(db_path, query_filter="in:inbox -category:promotions", service=service)
        self.assertEqual(
            service.messages_obj.list_calls[0]["q"],
            "in:inbox -category:promotions",
        )

    def test_default_filter_used_when_caller_passes_none_and_no_config(self) -> None:
        service = _FakeService(list_payload={"messages": []}, message_map={})
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("rebalance.ingest.config.get_gmail_query_filter", return_value=None):
            db_path = Path(tmpdir) / "rebalance.db"
            result = sync_gmail(db_path, service=service)
        self.assertEqual(result.query_filter, DEFAULT_QUERY_FILTER)

    def test_403_insufficient_scope_raises_gmail_auth_error(self) -> None:
        class _FakeResp:
            status = 403

        class _Http403Error(Exception):
            resp = _FakeResp()

        class _FailingMessages:
            def list(self, **_kwargs):
                class _Req:
                    def execute(self_inner):
                        raise _Http403Error("insufficient scopes")
                return _Req()

        class _FailingUsers:
            def messages(self):
                return _FailingMessages()

        class _FailingService:
            def users(self):
                return _FailingUsers()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            with self.assertRaises(GmailAuthError) as ctx:
                sync_gmail(db_path, query_filter="in:inbox", service=_FailingService())
        message = str(ctx.exception)
        self.assertIn("gcloud auth application-default login", message)
        self.assertIn("gmail.readonly", message)


# ---------------------------------------------------------------------------
# Semantic backfill — email rows become semantic_documents
# ---------------------------------------------------------------------------


class EmailSemanticBackfillTests(unittest.TestCase):
    def test_backfill_creates_email_semantic_documents(self) -> None:
        service = _FakeService(
            list_payload={"messages": [{"id": "m1"}]},
            message_map={
                "m1": _make_message("m1", subject="Q2 plan", snippet="Need to align on..."),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            sync_gmail(db_path, query_filter="in:inbox", service=service)

            result = backfill_semantic_documents(db_path, source_types=["email"])
            self.assertEqual(result.total_documents, 1)
            self.assertEqual(result.inserted_count, 1)

            with db_connection(db_path) as conn:
                ensure_semantic_schema(conn)
                doc = conn.execute(
                    "SELECT title, body, source_type FROM semantic_documents WHERE source_pk = 'm1'"
                ).fetchone()
        self.assertEqual(doc["source_type"], "email")
        self.assertEqual(doc["title"], "Q2 plan")
        self.assertIn("Q2 plan", doc["body"])
        self.assertIn("Need to align on", doc["body"])


# ---------------------------------------------------------------------------
# Source allowlist and scope wiring
# ---------------------------------------------------------------------------


class EmailScopeWiringTests(unittest.TestCase):
    def test_normalize_sources_includes_email_in_default(self) -> None:
        self.assertIn("email", _normalize_sources(None))

    def test_normalize_sources_accepts_explicit_email(self) -> None:
        self.assertEqual(_normalize_sources(["email"]), ("email",))

    def test_normalize_sources_all_includes_email(self) -> None:
        self.assertIn("email", _normalize_sources(["all"]))

    def test_scope_values_includes_email(self) -> None:
        self.assertIn("email", SCOPE_VALUES)

    def test_normalize_scope_all_expands_to_include_email(self) -> None:
        self.assertIn("email", _normalize_scope(["all"]))

    def test_normalize_scope_accepts_email(self) -> None:
        self.assertEqual(_normalize_scope(["email"]), ["email"])


# ---------------------------------------------------------------------------
# index_status surfaces email source block
# ---------------------------------------------------------------------------


class EmailIndexStatusTests(unittest.TestCase):
    def test_index_status_reports_email_source(self) -> None:
        service = _FakeService(
            list_payload={"messages": [{"id": "m1"}]},
            message_map={"m1": _make_message("m1")},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "rebalance.db"
            sync_gmail(db_path, query_filter="in:inbox", service=service)

            status = get_index_status(db_path)
        self.assertIn("email", status["sources"])
        self.assertEqual(status["sources"]["email"]["messages"], 1)
        self.assertIsNotNone(status["sources"]["email"]["last_synced_at"])


# ---------------------------------------------------------------------------
# _refresh_email dry-run
# ---------------------------------------------------------------------------


class RefreshEmailDryRunTests(unittest.TestCase):
    def test_dry_run_lists_steps_without_touching_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _refresh_email(Path(tmpdir) / "rebalance.db", dry_run=True)
        self.assertEqual(result["scope"], "email")
        self.assertTrue(result["dry_run"])
        self.assertIn("sync_gmail()", result["steps"])
        self.assertIn("semantic_backfill(email)", result["steps"])


if __name__ == "__main__":
    unittest.main()
