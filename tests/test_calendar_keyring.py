"""Tests for keyring-backed Google Calendar OAuth (set_calendar_oauth_token_json)."""

import json
import unittest
from unittest.mock import patch

from rebalance.ingest import config

_BLOB = json.dumps({
    "token": "access",
    "refresh_token": "rt_xyz",
    "client_id": "c",
    "client_secret": "s",
    "scopes": ["https://www.googleapis.com/auth/calendar"],
})


class CalendarKeyringTests(unittest.TestCase):
    def test_explicit_auth_logs_and_records_sidecar(self) -> None:
        with patch.object(config, "_keyring_set", return_value=True), \
             patch("rebalance.ingest.auth_log.log_calendar_token_set") as logev, \
             patch("rebalance.ingest.token_meta.record_token_set") as sidecar:
            ok = config.set_calendar_oauth_token_json(_BLOB, source="manual", record=True)
        self.assertTrue(ok)
        logev.assert_called_once()
        sidecar.assert_called_once()
        # Sidecar is keyed on the stable refresh_token, not the rotating access token.
        self.assertEqual(sidecar.call_args.args[0], "calendar")
        self.assertEqual(sidecar.call_args.args[1], "rt_xyz")

    def test_refresh_persist_does_not_log_or_record(self) -> None:
        # An access-token refresh (record=False) is not a re-authorization.
        with patch.object(config, "_keyring_set", return_value=True), \
             patch("rebalance.ingest.auth_log.log_calendar_token_set") as logev, \
             patch("rebalance.ingest.token_meta.record_token_set") as sidecar:
            config.set_calendar_oauth_token_json(_BLOB, source="refresh", record=False)
        logev.assert_not_called()
        sidecar.assert_not_called()

    def test_keyring_failure_skips_recording(self) -> None:
        with patch.object(config, "_keyring_set", return_value=False), \
             patch("rebalance.ingest.auth_log.log_calendar_token_set") as logev:
            ok = config.set_calendar_oauth_token_json(_BLOB, record=True)
        self.assertFalse(ok)
        logev.assert_not_called()


if __name__ == "__main__":
    unittest.main()
