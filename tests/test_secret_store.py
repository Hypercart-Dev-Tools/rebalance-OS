"""Contract tests for the Phase-1 secret-storage primitive.

These lock the invariants the hardening plan promises: atomic writes, enforced
``0600``/``0700`` modes (including correction of a pre-existing broad mode),
safe reads that never raise, and the six-field resolver-status object. The root
is redirected to ``tmp_path`` so no test touches the operator's real
``~/.config`` tree (the hermetic-seam requirement).
"""

import json
import stat

import pytest

from rebalance.ingest import secret_store


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def store_root(tmp_path, monkeypatch):
    """Redirect the secret-store root into tmp_path via the module seam."""
    root = tmp_path / "secrets"
    monkeypatch.setattr(secret_store, "SECRET_STORE_DIR", root)
    return root


def test_write_creates_file_0600_under_dir_0700(store_root):
    dest = secret_store.write_secret_file("github_token", "ghp_secret")
    assert dest == store_root / "github_token"
    assert dest.read_text() == "ghp_secret"
    assert _mode(dest) == 0o600
    assert _mode(store_root) == 0o700


def test_write_corrects_preexisting_broad_modes(store_root):
    # Simulate the audit's finding: dir 0755, stale file 0644.
    store_root.mkdir(parents=True)
    store_root.chmod(0o755)
    stale = store_root / "figma_token"
    stale.write_text("old")
    stale.chmod(0o644)

    secret_store.write_secret_file("figma_token", "new")

    assert _mode(store_root) == 0o700
    assert _mode(store_root / "figma_token") == 0o600
    assert (store_root / "figma_token").read_text() == "new"


def test_write_is_atomic_no_tmp_left_behind(store_root):
    secret_store.write_secret_file("sleuth_web_api", "token")
    leftovers = list(store_root.glob("*.tmp"))
    assert leftovers == []


def test_json_roundtrip(store_root):
    blob = {"access_token": "x", "refresh_token": "y", "scopes": ["a", "b"]}
    secret_store.write_secret_json("calendar.json", blob)
    assert secret_store.read_secret_json("calendar.json") == blob
    # Stored as pretty JSON, not pickle.
    raw = (store_root / "calendar.json").read_text()
    assert json.loads(raw) == blob


def test_read_missing_returns_none_not_raise(store_root):
    assert secret_store.read_secret_file("nope") is None
    assert secret_store.read_secret_json("nope") is None


def test_read_corrupt_json_returns_none(store_root):
    secret_store.write_secret_file("bad.json", "{not json")
    assert secret_store.read_secret_json("bad.json") is None
    # Raw text still readable.
    assert secret_store.read_secret_file("bad.json") == "{not json"


def test_delete_secret_file(store_root):
    secret_store.write_secret_file("temp_secret", "v")
    assert secret_store.delete_secret_file("temp_secret") is True
    assert secret_store.read_secret_file("temp_secret") is None
    # Deleting a missing file is a no-op False, not an error.
    assert secret_store.delete_secret_file("temp_secret") is False


def test_permission_ok_flags_broad_mode(store_root):
    dest = secret_store.write_secret_file("k", "v")
    assert secret_store.permission_ok(dest) is True
    dest.chmod(0o644)
    assert secret_store.permission_ok(dest) is False
    assert secret_store.permission_ok(store_root) is True


def test_permission_ok_missing_path_is_false(store_root):
    assert secret_store.permission_ok(store_root / "ghost") is False


def test_env_var_seam_overrides_default(tmp_path, monkeypatch):
    # With no module override, the env var must win over the ~/.config default.
    monkeypatch.setattr(secret_store, "SECRET_STORE_DIR", None)
    target = tmp_path / "env-secrets"
    monkeypatch.setenv(secret_store.SECRET_STORE_DIR_ENV_VAR, str(target))
    assert secret_store.secret_store_root() == target
    dest = secret_store.write_secret_file("t", "v")
    assert dest == target / "t"
    assert _mode(dest) == 0o600


def test_resolver_status_has_all_six_fields():
    status = secret_store.ResolverStatus(
        source="keyring",
        primary_store="keyring",
        fallback_store="secret-store",
        launchd_safe=True,
        last_validated_at=None,
        permission_ok=True,
    )
    d = status.as_dict()
    assert set(d) == {
        "source",
        "primary_store",
        "fallback_store",
        "launchd_safe",
        "last_validated_at",
        "permission_ok",
    }
    assert d["source"] == "keyring"
    assert d["launchd_safe"] is True
