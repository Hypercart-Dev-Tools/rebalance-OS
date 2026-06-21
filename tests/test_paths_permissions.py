"""Phase 1: ~/.config/rebalance-os permission hardening.

The user config dir holds OAuth token files and the secret store; the audit
found it at 0755 with config.json at 0644. `_save_user_config` now forces the
dir to 0700 and the file to 0600 on every write.
"""

import json
import stat

from rebalance import paths


def test_save_user_config_hardens_modes(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "rebalance-os"
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr(paths, "USER_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(paths, "USER_CONFIG_FILE", cfg_file)

    paths._save_user_config({"theme": "dark"})

    assert stat.S_IMODE(cfg_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(cfg_file.stat().st_mode) == 0o600
    assert json.loads(cfg_file.read_text())["theme"] == "dark"


def test_save_user_config_corrects_preexisting_broad_modes(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "rebalance-os"
    cfg_dir.mkdir()
    cfg_dir.chmod(0o755)  # the audit's observed dir posture
    f = cfg_dir / "config.json"
    f.write_text("{}")
    f.chmod(0o644)  # the audit's observed file posture
    monkeypatch.setattr(paths, "USER_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(paths, "USER_CONFIG_FILE", f)

    paths._save_user_config({"k": "v"})

    assert stat.S_IMODE(cfg_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
