"""Forward-only schema migration runner.

The baseline schema (version ``BASELINE_SCHEMA_VERSION``) is created by the
``ensure_*_schema`` functions in :mod:`rebalance.ingest.db.schema`. Every schema
change from the next version onward is a numbered SQL file in ``db/migrations/``
(``NNNN_description.sql``); ``schema.py`` stays frozen at the baseline.

:func:`run_migrations` stamps a database at the baseline version, then applies
any migration files newer than the recorded version, in order. It is idempotent
— a database already at the latest version is a cheap no-op.

See ``db/migrations/README.md`` for the authoring discipline.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from rebalance.ingest.db.schema import (
    BASELINE_SCHEMA_VERSION,
    ensure_baseline_schema,
    ensure_schema_version_table,
)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def current_schema_version(conn: sqlite3.Connection) -> int:
    """Return the highest recorded schema version, or 0 if none is recorded."""
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def discover_migrations() -> list[tuple[int, Path]]:
    """Return ``(version, path)`` for every ``NNNN_*.sql`` file, ascending.

    Files whose name does not start with an integer are ignored.
    """
    found: list[tuple[int, Path]] = []
    if not MIGRATIONS_DIR.is_dir():
        return found
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        prefix = path.name.split("_", 1)[0]
        try:
            version = int(prefix)
        except ValueError:
            continue
        found.append((version, path))
    found.sort()
    return found


def _stamp(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
        (version, datetime.now(timezone.utc).isoformat()),
    )


def run_migrations(conn: sqlite3.Connection) -> int:
    """Bring *conn*'s database up to the latest schema version; return that version.

    Ensures the baseline schema exists first (so migrations always have their
    tables), then applies migration files newer than the recorded version, in
    order. A database with no ``schema_version`` row is treated as being at the
    baseline — it is either a fresh install or one that predates migrations, and
    both are at the baseline shape.
    """
    ensure_baseline_schema(conn)
    ensure_schema_version_table(conn)
    version = current_schema_version(conn)
    if version == 0:
        _stamp(conn, BASELINE_SCHEMA_VERSION)
        version = BASELINE_SCHEMA_VERSION

    for mig_version, path in discover_migrations():
        if mig_version <= version:
            continue
        script = path.read_text(encoding="utf-8")
        try:
            # The runner owns the transaction, so atomicity never depends on a
            # migration file wrapping itself in BEGIN ... COMMIT. executescript()
            # issues an implicit COMMIT first (flushing the baseline stamp), then
            # runs the wrapped script as one explicit transaction. If any
            # statement fails mid-script the transaction is left open and the
            # except below rolls the whole migration back — the database stays at
            # the prior version with the original tables intact, never
            # half-applied. Migration files therefore MUST NOT contain their own
            # transaction control (see migrations/README.md); a nested BEGIN
            # would raise and the migration would roll back rather than apply.
            conn.executescript(f"BEGIN;\n{script}\nCOMMIT;")
            _stamp(conn, mig_version)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        version = mig_version

    conn.commit()  # flush the baseline stamp when no migrations were pending
    return version
