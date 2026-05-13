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
    3. Canonical app-data location for this platform. On macOS that is
       ``~/Library/Application Support/rebalance-os/rebalance.db``; on
       Linux/other it is ``$XDG_DATA_HOME/rebalance-os/rebalance.db`` or
       ``~/.local/share/rebalance-os/rebalance.db``. This is the default
       resting place for the DB and is NOT TCC-protected on macOS, which
       lets GUI clients (e.g., the SwiftUI dashboard) read it without an
       Allow-prompt dance.
    4. ``database_path`` field in the user-level config at
       ``~/.config/rebalance-os/config.json``. Lets operators point at a
       non-canonical location (e.g., legacy ``~/Documents/...`` checkout)
       without shell-rc edits.
    5. Walk up from the current working directory looking for a project
       marker (``.git`` or ``pyproject.toml``); if found, look for
       ``rebalance.db`` next to it. Lets developers run any command from
       anywhere inside the project tree.

Note: ``migrate_database_to_canonical()`` will move an existing DB (plus its
``-wal`` and ``-shm`` sidecars) from any of the legacy fallback layers into
the canonical app-data location. Once moved, layer 3 above takes over and the
other layers exist only for explicit overrides and dev-tree work.

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
import shutil
import sys
from pathlib import Path

# Project markers used by the walk-up step — first match wins.
_PROJECT_MARKERS = (".git", "pyproject.toml")
_WALK_UP_MAX_DEPTH = 12

# User-level config (XDG-compliant; respects $XDG_CONFIG_HOME).
USER_CONFIG_DIR: Path = Path(
    os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
) / "rebalance-os"
USER_CONFIG_FILE: Path = USER_CONFIG_DIR / "config.json"


def canonical_database_dir() -> Path:
    """Return the canonical app-data directory for this platform.

    macOS: ``~/Library/Application Support/rebalance-os`` — NOT TCC-protected
    when an app reads files inside its own bundle's data area, which removes
    the Allow-prompt friction the SwiftUI dashboard hit when the DB lived
    under ``~/Documents``.

    Linux/other: ``$XDG_DATA_HOME/rebalance-os`` if set, else
    ``~/.local/share/rebalance-os``. Matches XDG Base Directory spec.
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "rebalance-os"
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data).expanduser() / "rebalance-os"
    return Path.home() / ".local" / "share" / "rebalance-os"


def canonical_database_path() -> Path:
    """Return the canonical full path to rebalance.db for this platform."""
    return canonical_database_dir() / "rebalance.db"


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

    candidates.append((canonical_database_path().resolve(), "canonical app-data path"))

    user_cfg = _load_user_config()
    if isinstance(user_cfg.get("database_path"), str) and user_cfg["database_path"]:
        candidates.append((
            Path(user_cfg["database_path"]).expanduser().resolve(),
            f"user config ({USER_CONFIG_FILE})",
        ))

    project_root = _walk_up_for_project_root()
    if project_root is not None:
        candidates.append((project_root / "rebalance.db", f"project root walk-up ({project_root})"))

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
        f"  3. Place rebalance.db at the canonical location:\n"
        f"       {canonical_database_path()}\n"
        "     (or run ``python -m rebalance.paths --migrate`` to move an\n"
        "      existing DB there)\n"
        "  4. Set a user-level default once:\n"
        "       rebalance config set-default-database /path/to/rebalance.db\n"
        "  5. Run from anywhere inside the project tree (any dir under a .git or pyproject.toml)\n"
    )


# ---------------------------------------------------------------------------
# Database migration to canonical location
# ---------------------------------------------------------------------------

def migrate_database_to_canonical(*, dry_run: bool = False) -> dict:
    """Move rebalance.db (and its WAL/SHM sidecars) to the canonical app-data
    path returned by :func:`canonical_database_path`.

    Idempotent: if the canonical file already exists, returns a noop result.
    If no DB is resolvable from any layer, returns a noop result.

    After a successful move, clears the user-config ``database_path`` field if
    it pointed at the just-moved source path (so future resolves prefer the
    canonical location rather than chasing a stale absolute path).

    Returns a dict with keys: ``action`` (``moved`` | ``noop``), ``source``,
    ``destination``, ``moved_files`` (list of resolved paths actually moved
    on disk), ``cleared_user_config_key`` (bool), ``reason`` (str, when
    ``action == "noop"``).
    """
    canonical = canonical_database_path().resolve()
    result: dict = {
        "action": "noop",
        "source": None,
        "destination": str(canonical),
        "moved_files": [],
        "cleared_user_config_key": False,
        "reason": "",
        "dry_run": dry_run,
    }

    if canonical.exists():
        result["reason"] = "canonical path already exists"
        return result

    try:
        source = resolve_database_path()
    except DatabaseNotFoundError:
        result["reason"] = "no existing DB to migrate"
        return result

    source = source.resolve()
    result["source"] = str(source)

    if source == canonical:
        result["reason"] = "source already at canonical"
        return result

    moved: list[str] = []
    if not dry_run:
        canonical.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("", "-wal", "-shm"):
            src = source.parent / (source.name + suffix)
            dst = canonical.parent / (canonical.name + suffix)
            if src.exists():
                shutil.move(str(src), str(dst))
                moved.append(str(dst))

        # If the user config explicitly pointed at the source path, clear it
        # so the canonical layer wins on future resolves. Don't touch any
        # other custom user paths.
        user_cfg = _load_user_config()
        cfg_db = user_cfg.get("database_path")
        if isinstance(cfg_db, str) and cfg_db:
            cfg_resolved = Path(cfg_db).expanduser().resolve()
            if cfg_resolved == source:
                user_cfg.pop("database_path", None)
                _save_user_config(user_cfg)
                result["cleared_user_config_key"] = True

    result["action"] = "moved"
    result["moved_files"] = moved
    return result


def _migrate_cli() -> int:
    """Module-level entry: ``python -m rebalance.paths --migrate``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m rebalance.paths",
        description="Move rebalance.db to the canonical app-data location.",
    )
    parser.add_argument("--migrate", action="store_true", help="Run the migration.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would move without moving.")
    args = parser.parse_args()

    if not args.migrate:
        parser.print_help()
        return 2

    result = migrate_database_to_canonical(dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_migrate_cli())


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
