"""GH-250 R4: tests for utils/gh250/reclaim.py.

These fixtures build the REAL schema: a sqlite-vec ``vec0`` virtual table named
``github_embeddings`` plus a ``github_documents`` table.

The first draft of this suite created plain tables called ``vec0`` and ``items``
— sqlite-vec's own documentation example names — so all 10 of its tests passed
against a schema this project does not have, while the script could not run
against the real database at all (``no such table: vec0``). A green suite over a
fictional schema is worse than no suite: it reports readiness for a script that
cannot execute. Hence the two guard tests below that pin the real names and the
real production path.
"""

from __future__ import annotations

import os
import sqlite3
import struct
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "utils" / "gh250" / "reclaim.py"
DIM = 1024


def _vec(seed: int = 1) -> bytes:
    """A float32 blob of the production dimension."""
    return struct.pack(f"{DIM}f", *([float(seed)] * DIM))


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.enable_load_extension(True)
    import sqlite_vec

    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def make_db(path: Path, live: int = 3, orphans: int = 5) -> Path:
    """Build a production-shaped database: real vec0 table, real doc table."""
    conn = _connect(path)
    conn.execute(
        """
        CREATE TABLE github_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name TEXT,
            source_key TEXT
        )
        """
    )
    conn.execute(
        f"""
        CREATE VIRTUAL TABLE github_embeddings USING vec0(
            doc_id INTEGER PRIMARY KEY,
            embedding float[{DIM}]
        )
        """
    )
    for i in range(1, live + 1):
        conn.execute(
            "INSERT INTO github_documents (id, repo_full_name, source_key) VALUES (?,?,?)",
            (i, "o/r", f"k{i}"),
        )
        conn.execute(
            "INSERT INTO github_embeddings (doc_id, embedding) VALUES (?,?)", (i, _vec(i))
        )
    # Orphans: vectors whose doc_id has no document (ids well clear of live ones).
    for j in range(1000, 1000 + orphans):
        conn.execute(
            "INSERT INTO github_embeddings (doc_id, embedding) VALUES (?,?)", (j, _vec(j))
        )
    conn.commit()
    conn.close()
    return path


def run(db: Path, *args: str, env: dict | None = None):
    e = dict(os.environ)
    e.setdefault("REBALANCE_ASSUME_NO_METAL", "1")
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--database", str(db), *args],
        capture_output=True,
        text=True,
        env=e,
    )


def counts(db: Path) -> tuple[int, int]:
    """(total vectors, orphaned vectors) via the real predicate."""
    conn = _connect(db)
    total = conn.execute("SELECT count(*) FROM github_embeddings").fetchone()[0]
    orph = conn.execute(
        """SELECT count(*) FROM github_embeddings
           WHERE NOT EXISTS (SELECT 1 FROM github_documents d
                             WHERE d.id = github_embeddings.doc_id)"""
    ).fetchone()[0]
    conn.close()
    return total, orph


# ---------------------------------------------------------------------------
# Guard tests — the two the original suite most needed and did not have
# ---------------------------------------------------------------------------
def test_operates_on_the_real_production_table_names(tmp_path):
    src = SCRIPT.read_text()
    assert "github_embeddings" in src and "github_documents" in src
    assert "FROM vec0" not in src, "reverted to sqlite-vec's doc-example table name"
    assert "FROM items" not in src, "reverted to sqlite-vec's doc-example table name"
    db = make_db(tmp_path / "real.db")
    r = run(db)
    assert r.returncode == 0, r.stderr
    assert "orphaned" in r.stdout


def test_production_path_guard_uses_the_real_location(tmp_path):
    """The guard must name Application Support, not a repo-relative path.

    The first draft compared against <repo>/rebalance.db, which does not exist,
    so it could never fire on the database it existed to protect.
    """
    src = SCRIPT.read_text()
    assert "Application Support" in src
    assert "rebalance-os" in src


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------
def test_dry_run_changes_nothing(tmp_path):
    db = make_db(tmp_path / "d.db")
    before = counts(db)
    mtime = db.stat().st_mtime_ns
    r = run(db)
    assert r.returncode == 0, r.stderr
    assert "DRY RUN" in r.stdout
    assert counts(db) == before
    assert db.stat().st_mtime_ns == mtime


def test_execute_deletes_only_orphans(tmp_path):
    db = make_db(tmp_path / "e.db", live=3, orphans=5)
    r = run(db, "--execute")
    assert r.returncode == 0, r.stderr
    total, orph = counts(db)
    assert orph == 0
    assert total == 3, "live vectors must survive"


def test_live_vector_count_is_unchanged(tmp_path):
    db = make_db(tmp_path / "l.db", live=4, orphans=7)
    r = run(db, "--execute")
    assert r.returncode == 0, r.stderr
    conn = _connect(db)
    live = conn.execute(
        """SELECT count(*) FROM github_embeddings
           WHERE EXISTS (SELECT 1 FROM github_documents d
                         WHERE d.id = github_embeddings.doc_id)"""
    ).fetchone()[0]
    conn.close()
    assert live == 4


def test_batching_matches_single_batch(tmp_path):
    a = make_db(tmp_path / "a.db", live=2, orphans=9)
    b = make_db(tmp_path / "b.db", live=2, orphans=9)
    assert run(a, "--execute", "--batch-size", "2").returncode == 0
    assert run(b, "--execute", "--batch-size", "1000").returncode == 0
    assert counts(a) == counts(b)


def test_zero_orphans_is_a_clean_noop_and_does_not_rewrite(tmp_path):
    """A healthy database must not be rebuilt to reclaim nothing."""
    db = make_db(tmp_path / "z.db", live=3, orphans=0)
    mtime = db.stat().st_mtime_ns
    r = run(db, "--execute")
    assert r.returncode == 0, r.stderr
    assert "Nothing to reclaim" in r.stdout
    assert db.stat().st_mtime_ns == mtime, "database was rewritten despite no orphans"
    assert not (tmp_path / "z.vacuum.db").exists(), "built a rebuild target for a no-op"


def test_batch_size_must_be_positive(tmp_path):
    db = make_db(tmp_path / "bs.db")
    r = run(db, "--execute", "--batch-size", "0")
    assert r.returncode == 1
    assert "positive integer" in r.stderr


def test_missing_database_fails(tmp_path):
    r = run(tmp_path / "nope.db")
    assert r.returncode == 1
    assert "not found" in r.stderr


def test_unclean_checkpoint_aborts(tmp_path):
    db = make_db(tmp_path / "cp.db")
    r = run(db, "--execute", env={"_MOCK_CHECKPOINT_FAIL": "1"})
    assert r.returncode == 1
    assert "checkpoint not clean" in r.stderr


def test_resume_after_interrupt(tmp_path):
    db = make_db(tmp_path / "r.db", live=2, orphans=6)
    r1 = run(db, "--execute", "--batch-size", "2", env={"_CRASH_AFTER_BATCH": "1"})
    assert r1.returncode == 2
    _, mid = counts(db)
    assert 0 < mid < 6, "first batch should have committed durably"
    r2 = run(db, "--execute", "--batch-size", "2")
    assert r2.returncode == 0, r2.stderr
    total, orph = counts(db)
    assert orph == 0 and total == 2


def test_refuses_existing_rebuild_target(tmp_path):
    db = make_db(tmp_path / "t.db", live=1, orphans=2)
    (tmp_path / "t.vacuum.db").write_text("pre-existing evidence")
    r = run(db, "--execute")
    assert r.returncode == 1
    assert "already exists" in r.stderr
    assert (tmp_path / "t.vacuum.db").read_text() == "pre-existing evidence"


def test_rebuild_target_is_written(tmp_path):
    db = make_db(tmp_path / "s.db", live=2, orphans=40)
    r = run(db, "--execute")
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "s.vacuum.db").exists(), "VACUUM INTO target missing"
