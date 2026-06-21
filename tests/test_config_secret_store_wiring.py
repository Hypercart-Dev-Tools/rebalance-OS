"""Phase 1 wiring: the shared GitHub/Figma dual-store helpers now use the
out-of-repo `secret_store` as the durable launchd-safe fallback.

Additive contract — `rbos.config` is still written so existing unattended jobs
keep working; Phase 2 removes that repo-local write. These tests lock both the
new behavior (secret store preferred, 0600, out of repo) and the additive
safety net (config-only machines still resolve).
"""

import stat

import pytest

from rebalance.ingest import config as config_module
from rebalance.ingest import secret_store


@pytest.fixture
def seams(tmp_path, monkeypatch):
    """Redirect config + secret store into tmp and force keyring unavailable."""
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "rbos.config")
    monkeypatch.setattr(secret_store, "SECRET_STORE_DIR", tmp_path / "secrets")
    monkeypatch.setattr(config_module, "_keyring_get", lambda k: None)
    monkeypatch.setattr(config_module, "_keyring_set", lambda k, v: False)
    monkeypatch.setattr(config_module, "_keyring_delete", lambda k: False)
    return tmp_path


def test_set_writes_to_secret_store_at_0600_out_of_repo(seams):
    config_module._set_secret_dual_store("github_token", "ghp_abc")
    f = seams / "secrets" / "github_token"
    assert f.read_text() == "ghp_abc"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert stat.S_IMODE((seams / "secrets").stat().st_mode) == 0o700


def test_get_resolves_from_secret_store_when_keyring_down(seams):
    config_module._set_secret_dual_store("github_token", "ghp_abc")
    assert config_module._get_secret_dual_store("github_token") == ("ghp_abc", "secret-store")


def test_secret_store_preferred_over_config(seams):
    # Stale value in config, live value in the secret store → store wins.
    config_module._write_config({"github_token": "STALE_from_config"})
    secret_store.write_secret_file("github_token", "LIVE_from_store")
    assert config_module._get_secret_dual_store("github_token") == ("LIVE_from_store", "secret-store")


def test_config_still_written_additive(seams):
    # Phase 1 is additive — rbos.config still receives the secret (Phase 2 removes it).
    config_module._set_secret_dual_store("github_token", "ghp_abc")
    assert config_module._read_config().get("github_token") == "ghp_abc"


def test_config_only_machine_still_resolves(seams):
    # Existing machine: token only in rbos.config, nothing in the store yet.
    config_module._write_config({"github_token": "ghp_legacy"})
    assert config_module._get_secret_dual_store("github_token") == ("ghp_legacy", "config")


def test_clear_removes_from_store_and_config(seams):
    config_module._set_secret_dual_store("github_token", "ghp_abc")
    config_module._clear_secret_dual_store("github_token")
    assert secret_store.read_secret_file("github_token") is None
    assert "github_token" not in config_module._read_config()
    assert config_module._get_secret_dual_store("github_token") == (None, None)
