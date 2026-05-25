"""SQLite connection factory and context manager for rebalance.

Opens connections with WAL mode, foreign keys, a generous busy timeout, and
the sqlite-vec extension loaded when available.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Generator

try:
    import sqlite_vec
except Exception:  # pragma: no cover - import guard for environments without sqlite-vec
    sqlite_vec = None


def get_connection(database_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode, foreign keys, and sqlite-vec loaded.

    Note: sqlite-vec may not load on all Python builds (e.g., system Python without
    extension support). The connection will still work for basic queries.
    """
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(database_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Wait up to 30s for a writer slot before raising "database is locked".
    # Background refreshes from the TUI can briefly overlap launchd jobs;
    # without this they fail instantly. See git history for the 2026-05 incident.
    conn.execute("PRAGMA busy_timeout=30000")

    # Try to load sqlite-vec, but gracefully fall back if unavailable
    try:
        if sqlite_vec is not None and hasattr(conn, 'enable_load_extension'):
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
    except (AttributeError, Exception):
        # sqlite-vec not available on this Python build; continue without it
        pass

    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_connection(
    database_path: Path,
    ensure_fn: Callable[[sqlite3.Connection], None] | None = None,
) -> Generator[sqlite3.Connection, None, None]:
    """Context-managed database connection with optional schema setup.

    Usage::

        with db_connection(db_path, ensure_schema) as conn:
            rows = conn.execute("SELECT ...").fetchall()

    The connection is always closed on exit — even if the caller raises.
    Pass *ensure_fn* to guarantee a specific set of tables exists (e.g.
    ``ensure_schema``, ``ensure_calendar_schema``).  Omit it when you only
    need a bare connection.
    """
    conn = get_connection(database_path)
    if ensure_fn is not None:
        ensure_fn(conn)
    try:
        yield conn
    finally:
        conn.close()
