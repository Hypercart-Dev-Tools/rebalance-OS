"""Phase 3: Google OAuth fallback is JSON (secret store), not pickle.

Covers the keyring → secret-store-JSON → legacy-pickle resolution chain, the
migrate-on-read pickle→JSON conversion (idempotent, retires the pickle), and the
refresh path persisting JSON to both stores. `_creds_from_json` is seamed to a
fake so these don't depend on google's Credentials internals.
"""

import json
import pickle

import pytest

from rebalance.ingest import oauth_common
from rebalance.ingest import secret_store


class FakeCreds:
    """Minimal stand-in for google.oauth2.credentials.Credentials."""

    def __init__(self, token="t", expired=False, refresh_token="rt"):
        self._json = json.dumps({"token": token, "refresh_token": refresh_token})
        self.expired = expired
        self.refresh_token = refresh_token
        self.expiry = None
        self.refreshed = False

    def to_json(self):
        return self._json

    def refresh(self, request):
        self.refreshed = True
        self.expired = False


def _make_svc(tmp_path, name="calendar"):
    keyring: dict = {}

    def get_token_json():
        return keyring.get("blob")

    def set_token_json(blob, *, source, record):
        keyring["blob"] = blob
        return True

    svc = oauth_common.OAuthService(
        name=name,
        token_path=tmp_path / f"google-{name}-oauth",
        get_token_json=get_token_json,
        set_token_json=set_token_json,
        has_scopes=lambda creds, scopes: True,
        missing_error=lambda p: FileNotFoundError(p),
        scope_error=lambda c, s: PermissionError("scope"),
    )
    return svc, keyring


@pytest.fixture(autouse=True)
def _seam(tmp_path, monkeypatch):
    monkeypatch.setattr(secret_store, "SECRET_STORE_DIR", tmp_path / "secrets")

    def from_json(blob):
        data = json.loads(blob)
        return FakeCreds(
            token=data.get("token", "t"),
            expired=data.get("expired", False),
            refresh_token=data.get("refresh_token", "rt"),
        )

    monkeypatch.setattr(oauth_common, "_creds_from_json", from_json)


def test_secret_store_key(tmp_path):
    svc, _ = _make_svc(tmp_path)
    assert oauth_common.secret_store_key(svc) == "google-calendar-oauth"
    gmail_svc, _ = _make_svc(tmp_path, name="gmail")
    assert oauth_common.secret_store_key(gmail_svc) == "google-gmail-oauth"


def test_loads_from_keyring(tmp_path):
    svc, kr = _make_svc(tmp_path)
    kr["blob"] = json.dumps({"token": "from_keyring"})
    creds = oauth_common.load_credentials(svc)
    assert json.loads(creds.to_json())["token"] == "from_keyring"


def test_loads_from_secret_store_when_keyring_empty(tmp_path):
    svc, kr = _make_svc(tmp_path)
    secret_store.write_secret_file("google-calendar-oauth", json.dumps({"token": "from_store"}))
    creds = oauth_common.load_credentials(svc)
    assert json.loads(creds.to_json())["token"] == "from_store"


def test_migrates_legacy_pickle_to_json_and_retires_it(tmp_path):
    svc, kr = _make_svc(tmp_path)
    with open(svc.token_path, "wb") as f:
        pickle.dump(FakeCreds(token="from_pickle"), f)

    creds = oauth_common.load_credentials(svc)

    assert json.loads(creds.to_json())["token"] == "from_pickle"
    # Persisted as JSON to keyring + secret store, and the pickle is retired.
    assert kr.get("blob") is not None
    assert secret_store.read_secret_file("google-calendar-oauth") is not None
    assert not svc.token_path.exists()


def test_refresh_persists_json_to_both_stores(tmp_path):
    svc, kr = _make_svc(tmp_path)
    kr["blob"] = json.dumps({"token": "old", "expired": True, "refresh_token": "rt"})

    creds = oauth_common.load_credentials(svc)

    assert creds.refreshed is True
    assert secret_store.read_secret_file("google-calendar-oauth") is not None  # JSON fallback written
    assert not svc.token_path.exists()  # no pickle created on refresh


def test_missing_everywhere_raises(tmp_path):
    svc, kr = _make_svc(tmp_path)
    with pytest.raises(FileNotFoundError):
        oauth_common.load_credentials(svc)


def test_migrate_oauth_pickles_from_keyring_retires_pickle(tmp_path, monkeypatch):
    # keyring holds the JSON, a legacy pickle exists → JSON fallback written, pickle retired.
    from rebalance.ingest import config as config_module
    import rebalance.paths as paths_mod

    monkeypatch.setattr(config_module, "get_calendar_oauth_token_json", lambda: '{"token": "cal"}')
    monkeypatch.setattr(config_module, "get_gmail_oauth_token_json", lambda: None)
    monkeypatch.setattr(paths_mod, "resolve_oauth_token_path", lambda s: tmp_path / f"google-{s}-oauth")
    (tmp_path / "google-calendar-oauth").write_bytes(b"legacy-pickle")

    results = config_module.migrate_oauth_pickles()

    assert "retired" in results["calendar"]
    assert secret_store.read_secret_file("google-calendar-oauth") == '{"token": "cal"}'
    assert not (tmp_path / "google-calendar-oauth").exists()
    assert results["gmail"] == "already clean"  # keyring empty, no pickle
