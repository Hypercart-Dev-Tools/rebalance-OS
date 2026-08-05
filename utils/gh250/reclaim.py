#!/usr/bin/env python3
"""Reclaim space from orphaned github_embeddings vectors (GH-250 R4).

Deletes vectors whose ``doc_id`` no longer resolves to a ``github_documents`` row,
then rebuilds the database with ``VACUUM INTO``.

Dry-run by default. ``--execute`` is required to delete anything, and the real
production database additionally requires ``--i-know-this-is-production``.

Schema note (this is where the first draft went wrong): the tables are
``github_embeddings`` (a sqlite-vec ``vec0`` VIRTUAL table declared
``vec0(doc_id INTEGER PRIMARY KEY, embedding float[1024])``) and
``github_documents``. They are NOT named ``vec0``/``items`` — those are
sqlite-vec's own documentation examples, and a draft written against them cannot
run here at all. Equally, a ``vec0`` virtual table does NOT expose a bare
``rowid`` column, so every predicate below keys on ``doc_id``.
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

VEC_TABLE = "github_embeddings"
DOC_TABLE = "github_documents"

#: The real database. Not repo-relative — it lives in Application Support.
PROD_DB = (
    Path.home() / "Library" / "Application Support" / "rebalance-os" / "rebalance.db"
)

ORPHAN_PREDICATE = f"""
    NOT EXISTS (SELECT 1 FROM {DOC_TABLE} d WHERE d.id = {VEC_TABLE}.doc_id)
"""


def load_vec_extension(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec so the vec0 virtual table is queryable.

    Without this, every statement against github_embeddings fails with
    "no such module: vec0" on a real database.
    """
    try:
        import sqlite_vec
    except ImportError:
        print(
            "ERROR: sqlite_vec is not importable; cannot open the vector table.",
            file=sys.stderr,
        )
        sys.exit(1)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def get_metrics(conn: sqlite3.Connection, db_path: str) -> dict:
    cur = conn.cursor()
    total = cur.execute(f"SELECT count(*) FROM {VEC_TABLE}").fetchone()[0]
    orphans = cur.execute(
        f"SELECT count(*) FROM {VEC_TABLE} WHERE {ORPHAN_PREDICATE}"
    ).fetchone()[0]
    live = total - orphans
    freelist = cur.execute("PRAGMA freelist_count").fetchone()[0]
    size = Path(db_path).stat().st_size if Path(db_path).exists() else 0
    return {
        "db_size": size,
        "total_vectors": total,
        "orphans": orphans,
        "live_vectors": live,
        "freelist_count": freelist,
    }


def _fmt(b: int) -> str:
    return f"{b / 1024**3:.2f} GB" if b > 1024**3 else f"{b / 1024**2:.2f} MB"


def print_table(before: dict, after: dict) -> None:
    print(f"{'Metric':<20} | {'Before':<15} | {'After':<15}")
    print("-" * 56)
    print(f"{'db size':<20} | {_fmt(before['db_size']):<15} | {_fmt(after['db_size']):<15}")
    for key, label in (
        ("total_vectors", "total vectors"),
        ("orphans", "orphaned"),
        ("live_vectors", "live vectors"),
        ("freelist_count", "freelist_count"),
    ):
        print(f"{label:<20} | {before[key]:<15} | {after[key]:<15}")


def checkpoint(cur: sqlite3.Cursor, when: str) -> None:
    """TRUNCATE-checkpoint the WAL and FAIL if it did not come back clean.

    The result row is (busy, log, checkpointed); busy != 0 means a reader or
    writer blocked it. Reporting success after a blocked checkpoint would let the
    caller believe the WAL was flushed when it was not, so this exits non-zero.
    """
    cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    result = cur.fetchone()
    if os.environ.get("_MOCK_CHECKPOINT_FAIL") == "1":
        result = (1, 1, 1)
    if result is None or result[0] != 0:
        print(
            f"ERROR: WAL checkpoint not clean {when}: {result} "
            "(first column must be 0 — a reader/writer is holding the database)",
            file=sys.stderr,
        )
        sys.exit(1)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--database", required=True, help="Path to the database")
    ap.add_argument("--execute", action="store_true", help="Delete for real (default: dry-run)")
    ap.add_argument(
        "--i-know-this-is-production",
        action="store_true",
        help="Required to touch the real production database",
    )
    ap.add_argument("--batch-size", type=int, default=10000)
    args = ap.parse_args()

    if args.batch_size <= 0:
        print("ERROR: --batch-size must be a positive integer", file=sys.stderr)
        sys.exit(1)

    db_path = Path(args.database).expanduser().resolve()

    # Compare against the REAL production path. An earlier draft computed this
    # as <repo>/rebalance.db, which does not exist — so the guard could never
    # fire on the database it was meant to protect.
    try:
        is_prod = db_path == PROD_DB.resolve()
    except OSError:
        is_prod = db_path == PROD_DB
    if is_prod and not args.i_know_this_is_production:
        print(
            f"ERROR: {db_path} is the production database. Refusing without "
            "--i-know-this-is-production.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.isolation_level = None  # explicit transactions below
    load_vec_extension(conn)

    before = get_metrics(conn, str(db_path))

    if not args.execute:
        print("DRY RUN: nothing will be modified. Pass --execute to act.")
        print_table(before, before)
        sys.exit(0)

    # A clean no-op: with nothing to reclaim, do NOT rewrite the database.
    # Rebuilding a healthy multi-GB file to reclaim zero bytes is pure risk.
    if before["orphans"] == 0:
        print("No orphaned vectors. Nothing to reclaim — leaving the database untouched.")
        print_table(before, before)
        sys.exit(0)

    print(f"Starting reclaim on {db_path} (batch size {args.batch_size})")
    cur = conn.cursor()
    total_deleted = 0
    batch_num = 1

    while True:
        checkpoint(cur, f"before batch {batch_num}")
        cur.execute("BEGIN IMMEDIATE")
        # doc_id, not rowid: a vec0 virtual table exposes no rowid column.
        cur.execute(
            f"""
            DELETE FROM {VEC_TABLE}
            WHERE doc_id IN (
                SELECT doc_id FROM {VEC_TABLE}
                WHERE {ORPHAN_PREDICATE}
                LIMIT {args.batch_size}
            )
            """
        )
        changes = conn.execute("SELECT changes()").fetchone()[0]
        cur.execute("COMMIT")

        if changes == 0:
            break

        total_deleted += changes
        cp = checkpoint(cur, f"after batch {batch_num}")
        remaining = cur.execute(
            f"SELECT count(*) FROM {VEC_TABLE} WHERE {ORPHAN_PREDICATE}"
        ).fetchone()[0]
        print(
            f"Batch {batch_num}: deleted {changes}, remaining {remaining}, "
            f"checkpoint {cp}"
        )

        if os.environ.get("_CRASH_AFTER_BATCH") == str(batch_num):
            print("CRASHING FOR TEST", file=sys.stderr)
            sys.exit(2)
        batch_num += 1

    print(f"Deleted {total_deleted} orphaned vectors. Rebuilding with VACUUM INTO...")
    target = db_path.with_suffix(".vacuum.db")
    if target.exists():
        print(
            f"ERROR: rebuild target {target} already exists. Refusing to overwrite "
            "it — inspect and move it aside first.",
            file=sys.stderr,
        )
        sys.exit(1)
    conn.execute(f"VACUUM INTO '{target}'")

    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        print(f"ERROR: integrity_check returned {integrity!r}", file=sys.stderr)
        sys.exit(1)

    after = get_metrics(conn, str(db_path))
    after["db_size"] = target.stat().st_size
    conn.close()

    print_table(before, after)

    if after["orphans"] != 0:
        print(f"ERROR: {after['orphans']} orphans remain", file=sys.stderr)
        sys.exit(1)
    # The assertion that proves only garbage was deleted.
    if after["live_vectors"] != before["live_vectors"]:
        print(
            f"ERROR: live vector count changed {before['live_vectors']} -> "
            f"{after['live_vectors']}. Over-deletion — restore from backup.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"\nRebuilt database written to {target}")
    print("Swap it in per RECLAIM-RUNBOOK.md; this script does not move it.")


if __name__ == "__main__":
    main()
