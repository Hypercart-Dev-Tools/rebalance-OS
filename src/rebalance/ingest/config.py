"""
Configuration loader for rebalance — secrets, API credentials, etc.

Storage path: temp/rbos.config (gitignored, at workspace root)
Format: JSON

Future: Migrate sensitive fields to keyring library when multi-user or compliance required.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


# Resolve to repo root: __file__ is src/rebalance/ingest/config.py
# Parent chain: config.py -> ingest -> rebalance -> src -> rebalance-OS (root)
CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "temp" / "rbos.config"
_GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


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


def normalize_github_repo_name(repo: str) -> str:
    """Normalize one GitHub repo identifier to exact lowercased owner/name form."""
    normalized = repo.strip().strip("/")
    if not normalized or not _GITHUB_REPO_RE.fullmatch(normalized):
        raise ValueError(f"Invalid GitHub repo '{repo}'. Expected owner/name.")
    return normalized.lower()


def _normalize_github_repo_list(repos: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    normalized: list[str] = []
    for repo in repos:
        item = normalize_github_repo_name(repo)
        if item not in normalized:
            normalized.append(item)
    return sorted(normalized)


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


def get_github_ignored_repos() -> list[str]:
    """Return the locally configured GitHub repos to skip across ingest."""
    config = _read_config()
    value = config.get("github_ignored_repos")
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        try:
            repo = normalize_github_repo_name(item)
        except ValueError:
            continue
        if repo not in normalized:
            normalized.append(repo)
    return sorted(normalized)


def set_github_ignored_repos(repos: list[str]) -> None:
    """Store the canonical operator-local GitHub ignore list."""
    config = _read_config()
    config["github_ignored_repos"] = _normalize_github_repo_list(repos)
    _write_config(config)


def add_github_ignored_repo(repo: str) -> bool:
    """Add one repo to the operator-local GitHub ignore list."""
    normalized = normalize_github_repo_name(repo)
    existing = get_github_ignored_repos()
    if normalized in existing:
        return False
    existing.append(normalized)
    set_github_ignored_repos(existing)
    return True


def remove_github_ignored_repo(repo: str) -> bool:
    """Remove one repo from the operator-local GitHub ignore list."""
    normalized = normalize_github_repo_name(repo)
    existing = get_github_ignored_repos()
    if normalized not in existing:
        return False
    set_github_ignored_repos([item for item in existing if item != normalized])
    return True


def is_github_repo_ignored(repo: str) -> bool:
    """Return True when the exact repo is in the operator-local ignore list."""
    normalized = normalize_github_repo_name(repo)
    return normalized in set(get_github_ignored_repos())


def get_config_path() -> Path:
    """Return the config file path (for user reference)."""
    return CONFIG_PATH
