"""Tests for _migrate_google_pickle_to_keyring — the re-auth-aware sync that
backs `rebalance config migrate-to-keyring` for the Google OAuth tokens.

The key behavior under test: a freshly re-authed pickle (different refresh_token
than the keyring copy) must UPDATE keyring, not be skipped as "already set".
"""

import json
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from rebalance.cli.config_cmds import _migrate_google_pickle_to_keyring


def _blob(refresh: str) -> str:
    return json.dumps({
        "token": "access",
        "refresh_token": refresh,
        "client_id": "c",
        "client_secret": "s",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    })


class _FakeCreds:
    """Picklable stand-in for google Credentials with a to_json() method."""

    def __init__(self, refresh: str) -> None:
        self.refresh = refresh

    def to_json(self) -> str:
        return _blob(self.refresh)


def _write_pickle(path: Path, refresh: str) -> None:
    with open(path, "wb") as f:
        pickle.dump(_FakeCreds(refresh), f)


class MigrateGooglePickleTests(unittest.TestCase):
    def _run(self, *, keyring_blob, pickle_refresh):
        set_keyring = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            token_path = Path(tmp) / "token"
            if pickle_refresh is not None:
                _write_pickle(token_path, pickle_refresh)
            _migrate_google_pickle_to_keyring(
                label="gmail",
                token_path=token_path,
                get_keyring=lambda: keyring_blob,
                set_keyring=set_keyring,
                missing_hint="run setup",
            )
        return set_keyring

    def test_empty_keyring_with_pickle_migrates(self) -> None:
        set_keyring = self._run(keyring_blob=None, pickle_refresh="rt_1")
        set_keyring.assert_called_once()
        self.assertEqual(set_keyring.call_args.kwargs.get("source"), "migrate")

    def test_reauth_newer_pickle_refreshes_keyring(self) -> None:
        # keyring has an OLD refresh token; the pickle was just re-authed → update.
        set_keyring = self._run(keyring_blob=_blob("rt_OLD"), pickle_refresh="rt_NEW")
        set_keyring.assert_called_once()
        self.assertEqual(set_keyring.call_args.kwargs.get("source"), "reauth")
        self.assertEqual(json.loads(set_keyring.call_args.args[0])["refresh_token"], "rt_NEW")

    def test_same_refresh_token_is_noop(self) -> None:
        set_keyring = self._run(keyring_blob=_blob("rt_same"), pickle_refresh="rt_same")
        set_keyring.assert_not_called()

    def test_no_pickle_keeps_existing_keyring(self) -> None:
        set_keyring = self._run(keyring_blob=_blob("rt_1"), pickle_refresh=None)
        set_keyring.assert_not_called()


if __name__ == "__main__":
    unittest.main()
