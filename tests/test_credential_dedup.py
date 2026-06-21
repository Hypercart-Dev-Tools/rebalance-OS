"""Phase 3 — credential I/O dedup regression tests.

Covers the shared helpers introduced when the per-secret get/set/clear dance and
the Calendar/Gmail OAuth loaders were collapsed:

  - ``config._set/_clear/_get_secret_dual_store`` (GitHub/Figma/Sleuth backbone)
  - ``config._set_google_oauth_token_json`` (Calendar/Gmail setter backbone)
  - ``oauth_common.load_credentials`` (Calendar/Gmail loader backbone)

The trust-boundary invariants these protect: keyring + rbos.config stay in
lockstep, the config-only path works when the keyring is unavailable (launchd),
logging failures never abort a credential write, and an access-token refresh
persists to BOTH stores.
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from rebalance.ingest import config, oauth_common


def _mem_config(cfg: dict):
    """Patch config's keyring + rbos.config I/O to in-memory dicts."""
    kr: dict = {}
    return (
        patch.object(config, "_keyring_set", side_effect=lambda k, v: kr.__setitem__(k, v) or True),
        patch.object(config, "_keyring_get", side_effect=lambda k: kr.get(k)),
        patch.object(config, "_keyring_delete", side_effect=lambda k: kr.pop(k, None) is not None),
        patch.object(config, "_read_config", side_effect=lambda: dict(cfg)),
        patch.object(config, "_write_config", side_effect=lambda c: (cfg.clear(), cfg.update(c))),
        kr,
    )


class DualStoreSecretTests(unittest.TestCase):
    def test_set_writes_keyring_and_secret_store(self) -> None:
        from rebalance.ingest import secret_store
        cfg: dict = {}
        ms, mg, md, mr, mw, kr = _mem_config(cfg)
        with ms, mg, md, mr, mw:
            config._set_secret_dual_store("k", "v")
        self.assertEqual(kr.get("k"), "v")                         # keyring (primary)
        self.assertEqual(secret_store.read_secret_file("k"), "v")  # durable fallback
        self.assertNotIn("k", cfg)                                 # Phase 2: NOT rbos.config

    def test_durable_fallback_when_keyring_unavailable(self) -> None:
        # keyring write fails → secret persists to the out-of-repo secret store
        # (Phase 2: rbos.config is NOT written) and resolves from the store.
        cfg: dict = {}
        with patch.object(config, "_keyring_set", return_value=False), \
             patch.object(config, "_keyring_get", return_value=None), \
             patch.object(config, "_read_config", side_effect=lambda: dict(cfg)), \
             patch.object(config, "_write_config", side_effect=lambda c: (cfg.clear(), cfg.update(c))):
            config._set_secret_dual_store("github_token", "ghp_x")
            self.assertNotIn("github_token", cfg)  # Phase 2: config no longer written
            value, source = config._get_secret_dual_store("github_token")
        self.assertEqual(value, "ghp_x")
        self.assertEqual(source, "secret-store")

    def test_clear_removes_from_both(self) -> None:
        cfg: dict = {"k": "v"}
        ms, mg, md, mr, mw, kr = _mem_config(cfg)
        kr["k"] = "v"
        with ms, mg, md, mr, mw:
            config._clear_secret_dual_store("k")
        self.assertNotIn("k", kr)
        self.assertNotIn("k", cfg)


class CallbackIsolationTests(unittest.TestCase):
    def test_set_github_token_survives_logging_failure(self) -> None:
        from rebalance.ingest import secret_store
        cfg: dict = {}
        with patch.object(config, "_keyring_set", return_value=False), \
             patch.object(config, "_read_config", side_effect=lambda: dict(cfg)), \
             patch.object(config, "_write_config", side_effect=lambda c: (cfg.clear(), cfg.update(c))), \
             patch("rebalance.ingest.auth_log.log_github_token_set", side_effect=RuntimeError("boom")), \
             patch("rebalance.ingest.token_meta.record_token_set"):
            config.set_github_token("ghp_y")  # must not raise
        # keyring down + logging blew up, but the secret store still persisted it.
        self.assertEqual(secret_store.read_secret_file("github_token"), "ghp_y")

    def test_google_oauth_set_survives_logging_failure(self) -> None:
        blob = '{"refresh_token": "rt"}'
        with patch.object(config, "_keyring_set", return_value=True), \
             patch("rebalance.ingest.auth_log.log_calendar_token_set", side_effect=RuntimeError("boom")), \
             patch("rebalance.ingest.token_meta.record_token_set"):
            ok = config.set_calendar_oauth_token_json(blob, source="manual", record=True)
        self.assertTrue(ok)  # write succeeded despite the logging blow-up


class GoogleOAuthSetterTests(unittest.TestCase):
    def test_sidecar_keyed_on_refresh_token_per_service(self) -> None:
        blob = '{"refresh_token": "rt_g"}'
        with patch.object(config, "_keyring_set", return_value=True), \
             patch("rebalance.ingest.auth_log.log_gmail_token_set") as logev, \
             patch("rebalance.ingest.token_meta.record_token_set") as sidecar:
            config.set_gmail_oauth_token_json(blob, source="manual", record=True)
        logev.assert_called_once()
        self.assertEqual(sidecar.call_args.args[0], "gmail")
        self.assertEqual(sidecar.call_args.args[1], "rt_g")

    def test_record_false_skips_logging(self) -> None:
        blob = '{"refresh_token": "rt_g"}'
        with patch.object(config, "_keyring_set", return_value=True), \
             patch("rebalance.ingest.auth_log.log_gmail_token_set") as logev, \
             patch("rebalance.ingest.token_meta.record_token_set") as sidecar:
            config.set_gmail_oauth_token_json(blob, source="refresh", record=False)
        logev.assert_not_called()
        sidecar.assert_not_called()


class OAuthCommonLoaderTests(unittest.TestCase):
    def _svc(self, **over):
        base = dict(
            name="calendar",
            token_path=Path("/tmp/rbos-test-token"),
            get_token_json=lambda: None,
            set_token_json=MagicMock(return_value=True),
            has_scopes=lambda c, r: True,
            missing_error=lambda p: ValueError(f"missing:{p}"),
            scope_error=lambda c, r: RuntimeError("bad-scope"),
        )
        base.update(over)
        return oauth_common.OAuthService(**base)

    def test_refresh_persists_to_both_stores(self) -> None:
        class Creds:
            expired = True
            refresh_token = "rt"
            scopes = ["s"]
            expiry = None

            def refresh(self, _request):
                self.expired = False

            def to_json(self):
                return '{"refresh_token": "rt"}'

        creds = Creds()
        set_token = MagicMock(return_value=True)
        # keyring returns a blob → reconstructed via _creds_from_json (seamed).
        svc = self._svc(get_token_json=lambda: '{"refresh_token": "rt"}', set_token_json=set_token)

        with patch("rebalance.ingest.oauth_common._creds_from_json", return_value=creds), \
             patch("rebalance.ingest.secret_store.write_secret_file") as wsf, \
             patch("google.auth.transport.requests.Request"), \
             patch("rebalance.ingest.auth_log.log_token_refreshed"):
            out = oauth_common.load_credentials(svc, required_scopes=["s"])

        self.assertIs(out, creds)
        # keyring store written as a refresh (not a re-auth)...
        set_token.assert_called_once()
        self.assertEqual(set_token.call_args.kwargs.get("record"), False)
        self.assertEqual(set_token.call_args.kwargs.get("source"), "refresh")
        # ...and the JSON fallback written to the secret store (not pickle).
        wsf.assert_called_once()
        self.assertEqual(wsf.call_args.args[0], "google-calendar-oauth")

    def test_missing_token_raises_service_error(self) -> None:
        svc = self._svc(missing_error=lambda p: ValueError("missing"))
        with patch("pathlib.Path.exists", return_value=False), \
             patch("rebalance.ingest.auth_log.log_token_missing"):
            with self.assertRaises(ValueError):
                oauth_common.load_credentials(svc, required_scopes=["s"])

    def test_insufficient_scope_raises_service_error(self) -> None:
        creds = type("C", (), {"expired": False, "refresh_token": "rt", "scopes": ["narrow"]})()
        svc = self._svc(
            get_token_json=lambda: '{"refresh_token": "rt"}',
            has_scopes=lambda c, r: False,
            scope_error=lambda c, r: RuntimeError("bad-scope"),
        )
        with patch("google.oauth2.credentials.Credentials.from_authorized_user_info", return_value=creds):
            with self.assertRaises(RuntimeError):
                oauth_common.load_credentials(svc, required_scopes=["wide"])


if __name__ == "__main__":
    unittest.main()
