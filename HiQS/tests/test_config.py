import json
import stat

import pytest

from hiqs.config import (
    DEFAULT_CONFIG,
    SecretFilePermissionError,
    config_status,
    load_config,
    secret,
)


def _write_secret_file(path, values, mode=0o600):
    path.write_text(json.dumps(values), encoding="utf-8")
    path.chmod(mode)


def test_missing_config_uses_documented_defaults(tmp_path):
    config = load_config(tmp_path / "missing.json")

    assert dict(config) == DEFAULT_CONFIG
    assert config.loaded is False
    assert config_status(config) == {
        "path": str(tmp_path / "missing.json"),
        "loaded": False,
        "unknown_keys": [],
        "state": "ok",
    }


def test_config_preserves_unknown_keys_and_surfaces_them_in_status(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"projects": ["HiQS"], "future_feature": {"enabled": True}}),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config["projects"] == ["HiQS"]
    assert config["future_feature"] == {"enabled": True}
    assert config.status["unknown_keys"] == ["future_feature"]
    assert config.status["state"] == "warn"


def test_secret_prefers_keyring_over_file_and_environment(tmp_path):
    secret_path = tmp_path / "secrets.json"
    _write_secret_file(secret_path, {"TOKEN": "from-file"})

    assert secret(
        "TOKEN",
        secret_file=secret_path,
        environ={"TOKEN": "from-environment"},
        keyring_getter=lambda _name: "from-keyring",
    ) == "from-keyring"


def test_secret_uses_private_file_when_keyring_has_no_value(tmp_path):
    secret_path = tmp_path / "secrets.json"
    _write_secret_file(secret_path, {"TOKEN": "from-file"})

    assert secret(
        "TOKEN",
        secret_file=secret_path,
        environ={"TOKEN": "from-environment"},
        keyring_getter=lambda _name: None,
    ) == "from-file"


def test_secret_uses_environment_when_other_rungs_have_no_value(tmp_path):
    assert secret(
        "TOKEN",
        secret_file=tmp_path / "missing.json",
        environ={"TOKEN": "from-environment"},
        keyring_getter=lambda _name: None,
    ) == "from-environment"


def test_secret_returns_none_for_missing_or_empty_values(tmp_path):
    secret_path = tmp_path / "secrets.json"
    _write_secret_file(secret_path, {"TOKEN": ""})

    assert secret(
        "TOKEN",
        secret_file=secret_path,
        environ={"TOKEN": ""},
        keyring_getter=lambda _name: "",
    ) is None


def test_secret_refuses_a_file_that_is_not_0600(tmp_path):
    secret_path = tmp_path / "secrets.json"
    _write_secret_file(secret_path, {"TOKEN": "from-file"}, mode=0o644)

    with pytest.raises(SecretFilePermissionError, match="0600"):
        secret(
            "TOKEN",
            secret_file=secret_path,
            environ={"TOKEN": "from-environment"},
            keyring_getter=lambda _name: None,
        )

    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o644
