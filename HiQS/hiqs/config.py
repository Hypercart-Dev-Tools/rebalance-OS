"""Read HiQS configuration and resolve secrets without writing either store."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
from typing import Any


# Adding a setting must also add the code that consumes it. Unknown settings
# remain available through Config and are surfaced through config_status.
DEFAULT_CONFIG: dict[str, Any] = {
    "projects": [],
    "search": {"mode": "hybrid"},
}
KNOWN_CONFIG_KEYS = frozenset(DEFAULT_CONFIG)
KEYRING_SERVICE = "hiqs"


class ConfigError(ValueError):
    """Raised when JSON configuration cannot be read safely."""


class SecretFilePermissionError(PermissionError):
    """Raised when the optional on-disk secret store is not private."""


def config_path() -> Path:
    """Return the canonical user configuration path without creating it."""
    return Path.home() / ".config" / "hiqs" / "config.json"


def secret_file_path() -> Path:
    """Return the optional, private secret-file path without creating it."""
    return config_path().with_name("secrets.json")


@dataclass(frozen=True)
class Config(Mapping[str, Any]):
    """The complete configuration plus safe metadata for a status surface."""

    _values: Mapping[str, Any]
    path: Path
    loaded: bool
    unknown_keys: tuple[str, ...]

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    @property
    def status(self) -> dict[str, Any]:
        """Return status metadata only; configuration values are never echoed."""
        return {
            "path": str(self.path),
            "loaded": self.loaded,
            "unknown_keys": list(self.unknown_keys),
            "state": "warn" if self.unknown_keys else "ok",
        }


def load_config(path: str | Path | None = None) -> Config:
    """Read the whole JSON config, preserving unrecognised top-level keys.

    A missing file is a normal first-run state and returns DEFAULT_CONFIG.
    Malformed JSON or a non-object document is an explicit error, rather than a
    quiet empty configuration that turns intended settings into no-ops.
    """
    resolved_path = config_path() if path is None else Path(path)
    if not resolved_path.exists():
        return Config(deepcopy(DEFAULT_CONFIG), resolved_path, False, ())

    try:
        with resolved_path.open(encoding="utf-8") as config_file:
            raw_values = json.load(config_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError("HiQS configuration could not be read") from error

    if not isinstance(raw_values, dict):
        raise ConfigError("HiQS configuration must be a JSON object")

    values = deepcopy(DEFAULT_CONFIG)
    values.update(raw_values)
    unknown_keys = tuple(sorted(str(key) for key in raw_values.keys() - KNOWN_CONFIG_KEYS))
    return Config(values, resolved_path, True, unknown_keys)


def config_status(config: Config | None = None) -> dict[str, Any]:
    """Expose config health for the shared status surface without values."""
    return (load_config() if config is None else config).status


def _read_secret_file(path: Path, name: str) -> str | None:
    """Read a named secret from a private JSON object, if the file exists."""
    try:
        file_stat = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ConfigError("HiQS secret file could not be inspected") from error

    if not stat.S_ISREG(file_stat.st_mode) or stat.S_IMODE(file_stat.st_mode) != 0o600:
        raise SecretFilePermissionError("HiQS secret file must be a regular 0600 file")

    try:
        with path.open(encoding="utf-8") as secret_file:
            values = json.load(secret_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError("HiQS secret file could not be read") from error

    if not isinstance(values, dict):
        raise ConfigError("HiQS secret file must be a JSON object")
    value = values.get(name)
    return value if isinstance(value, str) and value else None


def _keyring_secret(name: str) -> str | None:
    """Read a secret from keyring, treating an unavailable backend as no hit."""
    try:
        import keyring

        value = keyring.get_password(KEYRING_SERVICE, name)
    except Exception:  # An unavailable OS keyring must not block fallback.
        return None
    return value if value else None


def secret(
    name: str,
    *,
    secret_file: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    keyring_getter: Callable[[str], str | None] | None = None,
) -> str | None:
    """Resolve name through keyring, a private file, then the environment.

    The first non-empty value wins. This read-only helper neither creates files
    nor writes keyring entries, and no exception includes a secret value.
    """
    keyring_value = _keyring_secret(name) if keyring_getter is None else keyring_getter(name)
    if keyring_value:
        return keyring_value

    file_value = _read_secret_file(
        secret_file_path() if secret_file is None else Path(secret_file), name
    )
    if file_value:
        return file_value

    environment = os.environ if environ is None else environ
    value = environment.get(name)
    return value if value else None
