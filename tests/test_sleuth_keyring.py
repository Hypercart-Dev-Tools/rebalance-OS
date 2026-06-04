"""Tests for keyring-backed Sleuth credentials (config.set/get_sleuth_credentials)."""

import unittest
from unittest.mock import patch

from rebalance.ingest import config


class SleuthKeyringTests(unittest.TestCase):
    def test_set_then_get_resolves_from_keyring(self) -> None:
        store: dict = {}
        with patch.object(config, "_keyring_set", side_effect=lambda k, v: store.__setitem__(k, v) or True), \
             patch.object(config, "_keyring_get", side_effect=lambda k: store.get(k)), \
             patch.object(config, "_read_config", return_value={}), \
             patch.object(config, "_write_config"), \
             patch("rebalance.ingest.auth_log.log_sleuth_credentials_set"), \
             patch("rebalance.ingest.token_meta.record_token_set"):
            config.set_sleuth_credentials("http://104.0.0.1:2020", "tok_123", "ws-dev", source="manual")
            creds = config.get_sleuth_credentials()
        self.assertEqual(creds["SLEUTH_WEB_API_BASE_URL"], "http://104.0.0.1:2020")
        self.assertEqual(creds["SLEUTH_WEB_API_TOKEN"], "tok_123")
        self.assertEqual(creds["SLEUTH_WORKSPACE_NAME"], "ws-dev")

    def test_set_logs_and_records_sidecar(self) -> None:
        store: dict = {}
        with patch.object(config, "_keyring_set", side_effect=lambda k, v: store.__setitem__(k, v) or True), \
             patch.object(config, "_read_config", return_value={}), \
             patch.object(config, "_write_config"), \
             patch("rebalance.ingest.auth_log.log_sleuth_credentials_set") as logev, \
             patch("rebalance.ingest.token_meta.record_token_set") as sidecar:
            config.set_sleuth_credentials("http://x:2020", "tok_abc", "neochrome-dev")
        logev.assert_called_once()
        self.assertEqual(logev.call_args.kwargs.get("workspace"), "neochrome-dev")
        sidecar.assert_called_once()
        self.assertEqual(sidecar.call_args.args[0], "sleuth")

    def test_get_falls_back_to_config_copy_when_keyring_empty(self) -> None:
        creds = {
            "SLEUTH_WEB_API_BASE_URL": "http://x:2020",
            "SLEUTH_WEB_API_TOKEN": "t",
            "SLEUTH_WORKSPACE_NAME": "w",
        }
        with patch.object(config, "_keyring_get", return_value=None), \
             patch.object(config, "_read_config", return_value={config.SLEUTH_KEYRING_KEY: creds}):
            out = config.get_sleuth_credentials()
        self.assertEqual(out, creds)

    def test_incomplete_keyring_blob_falls_through(self) -> None:
        import json
        # keyring has a partial blob (missing token) → must not be returned; falls to config.
        partial = json.dumps({"SLEUTH_WEB_API_BASE_URL": "http://x", "SLEUTH_WORKSPACE_NAME": "w"})
        good = {
            "SLEUTH_WEB_API_BASE_URL": "http://x",
            "SLEUTH_WEB_API_TOKEN": "t",
            "SLEUTH_WORKSPACE_NAME": "w",
        }
        with patch.object(config, "_keyring_get", return_value=partial), \
             patch.object(config, "_read_config", return_value={config.SLEUTH_KEYRING_KEY: good}):
            out = config.get_sleuth_credentials()
        self.assertEqual(out, good)


if __name__ == "__main__":
    unittest.main()
