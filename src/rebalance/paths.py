"""
Centralized path resolution for rebalance OS.

Every CLI command, MCP tool, and helper that needs to know "where is the
database?" or "where is the calendar env file?" should call into this module
rather than building paths inline. This is the one place to change when adding
new layers of context (e.g., per-machine overrides) or when migrating away
from hardcoded operator paths.

Resolution chains
-----------------

resolve_database_path(explicit) — find rebalance.db:
    1. ``explicit`` argument if non-None (e.g., ``--database /path/to/db``)
    2. ``REBALANCE_DB`` env var (used by launchd jobs, the MCP server, and
       any operator who exports it in their shell rc)
    3. Walk up from the current working directory looking for a project
       marker (``.git`` or ``pyproject.toml``); if found, look for
       ``rebalance.db`` next to it. Lets developers run any command from
       anywhere inside the project tree.
    4. ``database_path`` field in the user-level config at
       ``~/.config/rebalance-os/config.json``. Lets operators run commands
       from any directory on the machine without needing shell-rc edits.

resolve_secret_path(name) — find ``~/secrets/<name>``:
    1. ``REBALANCE_SECRETS_DIR`` env var
    2. ``secrets_dir`` field in the user-level config
    3. ``~/secrets`` (legacy default)

Setting user-level defaults
---------------------------

The user-level config is populated via the ``rebalance config
set-default-database`` and ``rebalance config set-secrets-dir`` CLI
subcommands. The file is gitignored by virtue of living outside the repo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Project markers used by the walk-up step — first match wins.
_PROJECT_MARKERS = (".git", "pyproject.toml")
_WALK_UP_MAX_DEPTH = 12

# User-level config (XDG-compliant; respects $XDG_CONFIG_HOME).
USER_CONFIG_DIR: Path = Path(
    os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
) / "rebalance-os"
USER_CONFIG_FILE: Path = USER_CONFIG_DIR / "config.json"


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _load_user_config() -> dict:
    """Return parsed user config, or {} if missing/invalid. Never raises."""
    if not USER_CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_user_config(data: dict) -> None:
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USER_CONFIG_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _walk_up_for_project_root(start: Path | None = None) -> Path | None:
    """Walk parents looking for a project marker. Return root or None."""
    p = (start or Path.cwd()).resolve()
    for _ in range(_WALK_UP_MAX_DEPTH):
        if any((p / m).exists() for m in _PROJECT_MARKERS):
            return p
        if p.parent == p:
            break
        p = p.parent
    return None


# ---------------------------------------------------------------------------
# Database resolver
# ---------------------------------------------------------------------------

class DatabaseNotFoundError(FileNotFoundError):
    """Raised when the resolver can't locate rebalance.db.

    Carries the list of (path, source) candidates it tried so the caller can
    render a structured error to the user or an orchestrating agent.
    """

    def __init__(self, candidates: list[tuple[Path, str]]):
        self.candidates = candidates
        message = build_database_help_message(candidates)
        super().__init__(message)


def resolve_database_path(explicit: Path | None = None) -> Path:
    """Resolve the rebalance.db path via the layered chain documented above.

    Returns an existing absolute path, or raises ``DatabaseNotFoundError``
    with a message naming every layer that was tried.
    """
    candidates: list[tuple[Path, str]] = []

    if explicit is not None:
        candidates.append((Path(explicit).expanduser().resolve(), "--database flag"))

    env_value = os.environ.get("REBALANCE_DB")
    if env_value:
        candidates.append((Path(env_value).expanduser().resolve(), "REBALANCE_DB env var"))

    project_root = _walk_up_for_project_root()
    if project_root is not None:
        candidates.append((project_root / "rebalance.db", f"project root walk-up ({project_root})"))

    user_cfg = _load_user_config()
    if isinstance(user_cfg.get("database_path"), str) and user_cfg["database_path"]:
        candidates.append((
            Path(user_cfg["database_path"]).expanduser().resolve(),
            f"user config ({USER_CONFIG_FILE})",
        ))

    for path, _source in candidates:
        if path.exists():
            return path

    raise DatabaseNotFoundError(candidates)


def build_database_help_message(candidates: list[tuple[Path, str]]) -> str:
    """Format a user-facing error explaining every route to fix the missing DB."""
    if candidates:
        tried_block = "\n".join(f"  - {p}  ({src})" for p, src in candidates)
    else:
        tried_block = "  (no candidates found at any layer)"
    return (
        "Could not resolve rebalance.db. Tried:\n"
        f"{tried_block}\n"
        "\n"
        "Fix one of these:\n"
        "  1. Pass --database /path/to/rebalance.db on the command line\n"
        "  2. export REBALANCE_DB=/path/to/rebalance.db (e.g., in ~/.zshrc)\n"
        "  3. Run from anywhere inside the project tree (any dir under a .git or pyproject.toml)\n"
        "  4. Set a user-level default once:\n"
        "       rebalance config set-default-database /path/to/rebalance.db\n"
    )


# ---------------------------------------------------------------------------
# Secrets resolver
# ---------------------------------------------------------------------------

def resolve_secrets_dir() -> Path:
    """Resolve the directory holding env-style secret files.

    Order:
      1. REBALANCE_SECRETS_DIR env var
      2. secrets_dir field in user-level config
      3. ~/secrets (legacy default)
    """
    if env_value := os.environ.get("REBALANCE_SECRETS_DIR"):
        return Path(env_value).expanduser().resolve()
    user_cfg = _load_user_config()
    if isinstance(user_cfg.get("secrets_dir"), str) and user_cfg["secrets_dir"]:
        return Path(user_cfg["secrets_dir"]).expanduser().resolve()
    return (Path.home() / "secrets").resolve()


def resolve_secret_path(name: str) -> Path:
    """Return the resolved Path to a named secret file under the secrets dir.

    Example: ``resolve_secret_path("google-calendar.env")`` →
        ``Path("/Users/noelsaw/secrets/google-calendar.env")`` by default,
        respecting REBALANCE_SECRETS_DIR / user config when set.
    """
    return resolve_secrets_dir() / name


# ---------------------------------------------------------------------------
# Setters (used by `rebalance config set-default-database` etc.)
# ---------------------------------------------------------------------------

def set_user_config_value(key: str, value: str) -> Path:
    """Persist key=value to the user-level config and return the file path."""
    cfg = _load_user_config()
    cfg[key] = value
    _save_user_config(cfg)
    return USER_CONFIG_FILE


def get_user_config_summary() -> dict:
    """Return a dict suitable for ``rebalance config show-defaults`` output."""
    cfg = _load_user_config()
    return {
        "user_config_file": str(USER_CONFIG_FILE),
        "user_config_exists": USER_CONFIG_FILE.exists(),
        "database_path": cfg.get("database_path"),
        "secrets_dir": cfg.get("secrets_dir"),
        "env_REBALANCE_DB": os.environ.get("REBALANCE_DB"),
        "env_REBALANCE_SECRETS_DIR": os.environ.get("REBALANCE_SECRETS_DIR"),
        "cwd": str(Path.cwd()),
        "project_root_walk_up": str(_walk_up_for_project_root()) if _walk_up_for_project_root() else None,
    }
