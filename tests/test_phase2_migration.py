"""Phase 2: lift secrets out of repo-local rbos.config into the secret store.

Covers the migration command (idempotent), the doctor signal, and the
launchd-safe read proof (with keyring unavailable, a migrated secret must
resolve from the out-of-repo secret store).
"""

import pytest

from rebalance import doctor
from rebalance.ingest import config as config_module
from rebalance.ingest import secret_store


@pytest.fixture
def seams(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "rbos.config")
    monkeypatch.setattr(secret_store, "SECRET_STORE_DIR", tmp_path / "secrets")
    monkeypatch.setattr(config_module, "_keyring_get", lambda k: None)
    monkeypatch.setattr(config_module, "_keyring_set", lambda k, v: False)
    monkeypatch.setattr(config_module, "_keyring_delete", lambda k: False)
    return tmp_path


def test_migrate_moves_github_token_out_of_config(seams):
    config_module._write_config({"github_token": "ghp_legacy", "vault_path": "/x"})
    results = config_module.migrate_repo_local_secrets()
    assert results["github_token"] == "migrated → secret store"
    assert secret_store.read_secret_file("github_token") == "ghp_legacy"
    cfg = config_module._read_config()
    assert "github_token" not in cfg     # secret lifted out
    assert cfg["vault_path"] == "/x"     # non-secret keys untouched


def test_migrate_handles_sleuth_dict(seams):
    creds = {
        "SLEUTH_WEB_API_BASE_URL": "https://x",
        "SLEUTH_WEB_API_TOKEN": "t",
        "SLEUTH_WORKSPACE_NAME": "w",
    }
    config_module._write_config({"sleuth_web_api": creds})
    results = config_module.migrate_repo_local_secrets()
    assert results["sleuth_web_api"] == "migrated → secret store"
    assert secret_store.read_secret_json("sleuth_web_api") == creds
    assert "sleuth_web_api" not in config_module._read_config()


def test_migrate_is_idempotent(seams):
    config_module._write_config({"github_token": "ghp_legacy"})
    config_module.migrate_repo_local_secrets()
    second = config_module.migrate_repo_local_secrets()
    assert second["github_token"] == "already clean"
    assert config_module.repo_local_secret_keys_present() == []


def test_repo_local_secret_keys_present(seams):
    assert config_module.repo_local_secret_keys_present() == []
    config_module._write_config({"github_token": "ghp", "figma_token": "fig", "vault_path": "/x"})
    assert set(config_module.repo_local_secret_keys_present()) == {"github_token", "figma_token"}


def test_launchd_safe_read_after_migration(seams):
    # The Phase 2 gate: with keyring unavailable (launchd), a migrated token
    # resolves from the out-of-repo secret store — not from rbos.config.
    config_module._write_config({"github_token": "ghp_launchd"})
    config_module.migrate_repo_local_secrets()
    value, source = config_module._get_secret_dual_store("github_token")
    assert value == "ghp_launchd"
    assert source == "secret-store"


def test_doctor_flags_secret_in_config(seams):
    config_module._write_config({"github_token": "ghp_legacy"})
    check = doctor._check_repo_local_secrets()
    assert check.status == doctor.WARN
    assert "github_token" in check.detail


def test_doctor_ok_when_config_clean(seams):
    config_module._write_config({"vault_path": "/x"})  # non-secret only
    check = doctor._check_repo_local_secrets()
    assert check.status == doctor.OK


# --- verify-then-cutover gate ------------------------------------------------
# The plan's headline availability risk: migration must NEVER delete a secret
# from rbos.config unless the out-of-repo store provably retained it. Otherwise
# a failed store write would lock launchd out of the only credential it can read.

def test_migrate_keeps_config_when_store_write_raises(seams, monkeypatch):
    config_module._write_config({"github_token": "ghp_legacy"})

    def _boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(secret_store, "write_secret_file", _boom)
    results = config_module.migrate_repo_local_secrets()

    assert "FAILED" in results["github_token"]
    # Secret NOT lifted out — the legacy launchd-safe read survives.
    assert config_module._read_config().get("github_token") == "ghp_legacy"
    assert "github_token" in config_module.repo_local_secret_keys_present()


def test_migrate_verify_gate_keeps_config_when_store_does_not_retain(seams, monkeypatch):
    # Write "succeeds" but a read-back can't confirm the value — the gate must
    # treat that as a failed cutover and leave rbos.config intact.
    config_module._write_config({"github_token": "ghp_legacy"})
    monkeypatch.setattr(secret_store, "read_secret_file", lambda _k: None)
    results = config_module.migrate_repo_local_secrets()

    assert "FAILED" in results["github_token"]
    assert config_module._read_config().get("github_token") == "ghp_legacy"
    assert "github_token" in config_module.repo_local_secret_keys_present()
