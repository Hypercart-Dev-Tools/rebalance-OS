from __future__ import annotations

import base64
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from rebalance import web


def _basic_auth(secret: str, username: str = "zapier") -> dict[str, str]:
    token = base64.b64encode(f"{username}:{secret}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


class ZapierWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.secret_path = Path(self.tmp.name) / web.ZAPIER_SECRET_NAME
        self.secret_path.write_text("super-secret\n", encoding="utf-8")
        web._ZAPIER_RATE_LIMIT_BUCKETS.clear()
        if hasattr(web.app.state, "zapier_webhook_secret"):
            web.app.state.zapier_webhook_secret = None

    def _client(self) -> TestClient:
        patcher = mock.patch("rebalance.web.resolve_secret_path", return_value=self.secret_path)
        self.addCleanup(patcher.stop)
        patcher.start()
        client = TestClient(web.app)
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        return client

    def test_basic_auth_rejects_before_body_parse(self) -> None:
        resp = self._client().post(
            "/api/zapier/ingest",
            headers=_basic_auth("wrong-secret"),
            content="{not-json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["error"], "forbidden")

    def test_basic_auth_accepts_and_reaches_stub(self) -> None:
        resp = self._client().post(
            "/api/zapier/ingest",
            headers=_basic_auth("super-secret"),
            json={"source": "email", "event_id": "evt-1"},
        )
        self.assertEqual(resp.status_code, 501)
        self.assertEqual(resp.json()["error"], "not_implemented")
        self.assertEqual(resp.json()["source"], "email")

    def test_query_param_secret_fallback_is_accepted(self) -> None:
        resp = self._client().post(
            "/api/zapier/ingest?zapier_secret=super-secret",
            json={"source": "calendar", "event_id": "evt-2"},
        )
        self.assertEqual(resp.status_code, 501)
        self.assertEqual(resp.json()["error"], "not_implemented")
        self.assertEqual(resp.json()["source"], "calendar")

    def test_unknown_source_is_400(self) -> None:
        resp = self._client().post(
            "/api/zapier/ingest",
            headers=_basic_auth("super-secret"),
            json={"source": "notes"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "unknown_source")

    def test_routes_email_source_to_email_handler(self) -> None:
        with mock.patch(
            "rebalance.web.zapier_email.handle_email_event",
            side_effect=NotImplementedError("email stub"),
        ) as email_handler, mock.patch(
            "rebalance.web.zapier_calendar.handle_calendar_event",
        ) as calendar_handler:
            resp = self._client().post(
                "/api/zapier/ingest",
                headers=_basic_auth("super-secret"),
                json={"source": "email", "message_id": "msg-1"},
            )

        self.assertEqual(resp.status_code, 501)
        email_handler.assert_called_once_with({"source": "email", "message_id": "msg-1"})
        calendar_handler.assert_not_called()

    def test_dry_run_validates_without_calling_handler(self) -> None:
        with mock.patch("rebalance.web.zapier_email.handle_email_event") as email_handler:
            resp = self._client().post(
                "/api/zapier/ingest?dry_run=true",
                headers=_basic_auth("super-secret"),
                json={"source": "email", "message_id": "msg-2"},
            )

        body = resp.json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            body,
            {
                "ok": True,
                "request_id": body["request_id"],
                "source": "email",
                "dry_run": True,
            },
        )
        email_handler.assert_not_called()

    def test_database_locked_maps_to_503(self) -> None:
        with mock.patch(
            "rebalance.web.zapier_email.handle_email_event",
            side_effect=sqlite3.OperationalError("database is locked"),
        ):
            resp = self._client().post(
                "/api/zapier/ingest",
                headers=_basic_auth("super-secret"),
                json={"source": "email", "message_id": "msg-3"},
            )

        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["error"], "database_locked")

    def test_health_reports_secret_configured(self) -> None:
        resp = self._client().get("/api/zapier/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True, "secret_configured": True})


if __name__ == "__main__":
    unittest.main()
