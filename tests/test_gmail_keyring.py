"""Tests for keyring-backed Gmail OAuth (set_gmail_oauth_token_json).

Mirrors test_calendar_keyring.py — the Gmail credential model is the Calendar
model applied to gmail.readonly.
"""

import json
import unittest
from unittest.mock import patch

from rebalance.ingest import config

_BLOB = json.dumps({
    "token": "access",
    "refresh_token": "rt_gmail",
    "client_id": "c",
    "client_secret": "s",
    "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
})


class GmailKeyringTests(unittest.TestCase):
    def test_explicit_auth_logs_and_records_sidecar(self) -> None:
        with patch.object(config, "_keyring_set", return_value=True), \
             patch("rebalance.ingest.auth_log.log_gmail_token_set") as logev, \
             patch("rebalance.ingest.token_meta.record_token_set") as sidecar:
            ok = config.set_gmail_oauth_token_json(_BLOB, source="manual", record=True)
        self.assertTrue(ok)
        logev.assert_called_once()
        sidecar.assert_called_once()
        # Sidecar is keyed on the stable refresh_token, not the rotating access token.
        self.assertEqual(sidecar.call_args.args[0], "gmail")
        self.assertEqual(sidecar.call_args.args[1], "rt_gmail")

    def test_refresh_persist_does_not_log_or_record(self) -> None:
        # An access-token refresh (record=False) is not a re-authorization.
        with patch.object(config, "_keyring_set", return_value=True), \
             patch("rebalance.ingest.auth_log.log_gmail_token_set") as logev, \
             patch("rebalance.ingest.token_meta.record_token_set") as sidecar:
            config.set_gmail_oauth_token_json(_BLOB, source="refresh", record=False)
        logev.assert_not_called()
        sidecar.assert_not_called()

    def test_keyring_failure_skips_recording(self) -> None:
        with patch.object(config, "_keyring_set", return_value=False), \
             patch("rebalance.ingest.auth_log.log_gmail_token_set") as logev:
            ok = config.set_gmail_oauth_token_json(_BLOB, record=True)
        self.assertFalse(ok)
        logev.assert_not_called()


class GmailLoadCredentialsTests(unittest.TestCase):
    """_load_credentials resolves keyring first, then the pickle fallback."""

    def test_keyring_blob_is_preferred_over_pickle(self) -> None:
        from rebalance.ingest import gmail

        fake_creds = type("Creds", (), {
            "expired": False,
            "refresh_token": "rt_gmail",
            "scopes": [gmail.GMAIL_READONLY_SCOPE],
        })()

        with patch("rebalance.ingest.config.get_gmail_oauth_token_json", return_value=_BLOB), \
             patch("google.oauth2.credentials.Credentials.from_authorized_user_info",
                   return_value=fake_creds) as from_info:
            creds = gmail._load_credentials(required_scopes=[gmail.GMAIL_READONLY_SCOPE])
        from_info.assert_called_once()
        self.assertIs(creds, fake_creds)

    def test_missing_everywhere_raises_gmail_auth_error(self) -> None:
        from rebalance.ingest import gmail

        with patch("rebalance.ingest.config.get_gmail_oauth_token_json", return_value=None), \
             patch("pathlib.Path.exists", return_value=False):
            with self.assertRaises(gmail.GmailAuthError) as ctx:
                gmail._load_credentials(required_scopes=[gmail.GMAIL_READONLY_SCOPE])
        self.assertIn("setup_gmail_oauth.py", str(ctx.exception))

    def test_missing_required_scope_raises(self) -> None:
        from rebalance.ingest import gmail

        narrow = type("Creds", (), {
            "expired": False,
            "refresh_token": "rt_gmail",
            "scopes": ["https://www.googleapis.com/auth/userinfo.email"],
        })()
        with patch("rebalance.ingest.config.get_gmail_oauth_token_json", return_value=_BLOB), \
             patch("google.oauth2.credentials.Credentials.from_authorized_user_info",
                   return_value=narrow):
            with self.assertRaises(gmail.GmailAuthError):
                gmail._load_credentials(required_scopes=[gmail.GMAIL_READONLY_SCOPE])


if __name__ == "__main__":
    unittest.main()
