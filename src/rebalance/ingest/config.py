"""
Configuration loader for rebalance — secrets, API credentials, etc.

Storage path: temp/rbos.config (gitignored, at workspace root)
Format: JSON

Future: Migrate sensitive fields to keyring library when multi-user or compliance required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Resolve to repo root: __file__ is src/rebalance/ingest/config.py
# Parent chain: config.py -> ingest -> rebalance -> src -> rebalance-OS (root)
CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "temp" / "rbos.config"


def _ensure_config_dir() -> None:
    """Create temp/ dir if missing."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _read_config() -> dict[str, Any]:
    """Load config from disk; return {} if missing."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}


def _write_config(config: dict[str, Any]) -> None:
    """Write config to disk with .gitignore safety."""
    _ensure_config_dir()
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_github_token() -> str | None:
    """
    Get GitHub PAT from config. Returns None if not set.

    Config key: github_token
    """
    config = _read_config()
    return config.get("github_token")


def set_github_token(token: str) -> None:
    """Store GitHub PAT in config."""
    config = _read_config()
    config["github_token"] = token.strip()
    _write_config(config)


def get_config_path() -> Path:
    """Return the config file path (for user reference)."""
    return CONFIG_PATH
