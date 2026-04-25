"""
Configuration loader for rebalance — secrets, API credentials, etc.

Storage path: temp/rbos.config (gitignored, at workspace root)
Format: JSON

Future: Migrate sensitive fields to keyring library when multi-user or compliance required.
"""

from __future__ import annotations

import json
import subprocess
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


def _try_gh_cli_token() -> str | None:
    """Return the OAuth token gh CLI is currently using, or None if unavailable."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    token = result.stdout.strip()
    return token or None


def get_github_token_with_source() -> tuple[str | None, str | None]:
    """
    Resolve a GitHub token. Returns (token, source) where source is one of:
      "config"  — token came from temp/rbos.config
      "gh-cli"  — fell back to `gh auth token`
      None      — neither available

    Resolution order is config first, then gh CLI. This keeps explicit
    PATs authoritative when both are present, so a user who set a token
    deliberately won't be silently overridden by an ambient gh login.
    """
    config = _read_config()
    token = config.get("github_token")
    if token:
        return token, "config"
    token = _try_gh_cli_token()
    if token:
        return token, "gh-cli"
    return None, None


def get_github_token() -> str | None:
    """
    Get GitHub token. Falls back to `gh auth token` if no PAT is in config.

    Config key: github_token
    """
    token, _source = get_github_token_with_source()
    return token


def set_github_token(token: str) -> None:
    """Store GitHub PAT in config."""
    config = _read_config()
    config["github_token"] = token.strip()
    _write_config(config)


def clear_github_token() -> None:
    """Remove the stored GitHub PAT from config (e.g. to switch to `gh auth token`)."""
    config = _read_config()
    if "github_token" in config:
        del config["github_token"]
        _write_config(config)


def get_vault_path() -> str | None:
    """
    Get Obsidian vault path from config. Returns None if not set.

    Config key: vault_path
    """
    config = _read_config()
    return config.get("vault_path")


def set_vault_path(path: str) -> None:
    """Store Obsidian vault path in config."""
    config = _read_config()
    config["vault_path"] = path.strip()
    _write_config(config)


def get_config_path() -> Path:
    """Return the config file path (for user reference)."""
    return CONFIG_PATH
