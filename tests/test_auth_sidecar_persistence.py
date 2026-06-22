"""Phase 2: auth-activity + token-metadata persistence through the real setter path.

Unit coverage for ``token_meta`` / ``auth_log`` lives elsewhere. This pins the
*integration* contract: calling the actual credential setters (the write paths
operators and auto-heal flows use) produces, together:

  * an auth-log ``token_set`` event for the source, and
  * a token-meta sidecar that stores only a fingerprint (never the raw token),
    preserves ``first_added_at`` across a re-set of the same token, and starts a
    fresh record for a genuinely new token value.

token_meta and the auth log share the ``REBALANCE_AUTH_LOG_DIR`` seam; this test
points it at a per-test tmp dir (overriding conftest's session-wide isolation)
so both sidecars start empty and assertions are exact. ``_keyring_set`` is always
stubbed so no test ever writes a fake token into the operator's real keychain.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rebalance.ingest import auth_log, config as config_mod, token_meta


class AuthSidecarPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._logs = Path(self._tmp.name) / "logs"
        # Fresh, per-test logs dir for BOTH auth_activity.jsonl and token_meta.json.
        env = patch.dict("os.environ", {"REBALANCE_AUTH_LOG_DIR": str(self._logs)})
        env.start()
        self.addCleanup(env.stop)

    def test_setter_emits_auth_event_and_fingerprint_only_sidecar(self) -> None:
        # keyring unavailable (launchd) → dual store writes to the conftest-
        # isolated secret store; github's sidecar write is unconditional.
        with patch.object(config_mod, "_keyring_set", return_value=False):
            config_mod.set_github_token("ghp_AAA_first_value_000000")

        latest = auth_log.latest_event_by_source()
        self.assertIn("github", latest)
        self.assertEqual(latest["github"]["event"], "token_set")

        meta = token_meta.current_token_meta("github")
        self.assertIsNotNone(meta)
        self.assertEqual(
            meta["fingerprint"], token_meta.fingerprint("ghp_AAA_first_value_000000")
        )
        self.assertEqual(meta["set_count"], 1)
        raw = (self._logs / "token_meta.json").read_text(encoding="utf-8")
        self.assertNotIn("ghp_AAA_first_value_000000", raw)  # fingerprint-only
        self.assertIn(
            "fingerprint", json.loads(raw)["github"]["tokens"][meta["fingerprint"]]
        )

    def test_first_added_at_retained_across_reset_then_resets_for_new_token(self) -> None:
        with patch.object(config_mod, "_keyring_set", return_value=False):
            config_mod.set_github_token("ghp_AAA_first_value_000000")
            first = token_meta.current_token_meta("github")["first_added_at"]

            # Re-set the SAME token → first_added_at preserved, count advances.
            config_mod.set_github_token("ghp_AAA_first_value_000000")
            again = token_meta.current_token_meta("github")
            self.assertEqual(again["first_added_at"], first)
            self.assertEqual(again["set_count"], 2)

            # A genuinely NEW token value → fresh record.
            config_mod.set_github_token("ghp_BBB_rotated_value_111111")
        rotated = token_meta.current_token_meta("github")
        self.assertEqual(
            rotated["fingerprint"], token_meta.fingerprint("ghp_BBB_rotated_value_111111")
        )
        self.assertEqual(rotated["set_count"], 1)
        self.assertGreaterEqual(rotated["first_added_at"], first)

    def test_google_refresh_does_not_reset_authorization_age(self) -> None:
        # An automatic access-token refresh (record=False) must NOT log a new
        # token_set nor restamp first_added_at; only an explicit (re)auth does.
        # The Google path is keyring-only and records only when the keyring write
        # succeeds, so stub _keyring_set truthy (no real keychain is touched).
        with patch.object(config_mod, "_keyring_set", return_value=True):
            blob = json.dumps({"refresh_token": "rt_stable_value", "token": "at_1"})
            config_mod.set_calendar_oauth_token_json(blob, source="manual", record=True)
            first = token_meta.current_token_meta("calendar")["first_added_at"]

            refreshed = json.dumps({"refresh_token": "rt_stable_value", "token": "at_2"})
            config_mod.set_calendar_oauth_token_json(refreshed, source="refresh", record=False)
        meta = token_meta.current_token_meta("calendar")
        self.assertEqual(meta["first_added_at"], first)
        self.assertEqual(meta["set_count"], 1)


if __name__ == "__main__":
    unittest.main()
