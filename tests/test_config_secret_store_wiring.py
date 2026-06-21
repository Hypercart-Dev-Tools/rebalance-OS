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


def test_config_no_longer_receives_secret(seams):
    # Phase 2: the secret goes to keyring + secret store, NOT rbos.config.
    config_module._set_secret_dual_store("github_token", "ghp_abc")
    assert "github_token" not in config_module._read_config()
    assert secret_store.read_secret_file("github_token") == "ghp_abc"


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


# --- Sleuth (JSON-blob credential, separate from the dual-store helpers) -----

_SLEUTH_CREDS = {
    "SLEUTH_WEB_API_BASE_URL": "https://sleuth.example",
    "SLEUTH_WEB_API_TOKEN": "tok_abc",
    "SLEUTH_WORKSPACE_NAME": "neochrome",
}


def test_sleuth_set_writes_creds_to_secret_store_at_0600(seams, monkeypatch):
    # Logging is best-effort in set_sleuth_credentials; stub it for a hermetic test.
    monkeypatch.setattr("rebalance.ingest.auth_log.log_sleuth_credentials_set", lambda **kw: None)
    monkeypatch.setattr("rebalance.ingest.token_meta.record_token_set", lambda *a, **kw: None)

    config_module.set_sleuth_credentials(
        _SLEUTH_CREDS["SLEUTH_WEB_API_BASE_URL"],
        _SLEUTH_CREDS["SLEUTH_WEB_API_TOKEN"],
        _SLEUTH_CREDS["SLEUTH_WORKSPACE_NAME"],
    )
    assert secret_store.read_secret_json("sleuth_web_api") == _SLEUTH_CREDS
    f = seams / "secrets" / "sleuth_web_api"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_sleuth_resolves_from_secret_store_when_keyring_down(seams):
    secret_store.write_secret_json("sleuth_web_api", _SLEUTH_CREDS)
    creds = config_module.get_sleuth_credentials()
    assert creds == _SLEUTH_CREDS


def test_sleuth_clear_removes_from_secret_store(seams, monkeypatch):
    monkeypatch.setattr("rebalance.ingest.auth_log.log_sleuth_credentials_set", lambda **kw: None)
    monkeypatch.setattr("rebalance.ingest.token_meta.record_token_set", lambda *a, **kw: None)
    config_module.set_sleuth_credentials(
        _SLEUTH_CREDS["SLEUTH_WEB_API_BASE_URL"],
        _SLEUTH_CREDS["SLEUTH_WEB_API_TOKEN"],
        _SLEUTH_CREDS["SLEUTH_WORKSPACE_NAME"],
    )
    config_module.clear_sleuth_credentials()
    assert secret_store.read_secret_json("sleuth_web_api") is None


# --- rbos.config permission hardening (still secret-bearing until Phase 2) ---

def test_write_config_hardens_to_0600(seams):
    config_module._write_config({"github_token": "ghp_x", "figma_file_keys": ["a"]})
    cfg = seams / "rbos.config"
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o600
    assert config_module._read_config()["github_token"] == "ghp_x"


def test_write_config_corrects_preexisting_broad_mode(seams):
    cfg = seams / "rbos.config"
    cfg.write_text("{}")
    cfg.chmod(0o644)  # the audit's observed posture
    config_module._write_config({"x": 1})
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o600
