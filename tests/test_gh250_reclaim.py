import os
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

def setup_db(db_path, num_live=5, num_orphans=5, corrupt=False):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE items (id INTEGER PRIMARY KEY);")
    cursor.execute("CREATE TABLE vec0 (doc_id INTEGER, vec BLOB);")
    
    # insert live vectors
    for i in range(num_live):
        cursor.execute(f"INSERT INTO items (id) VALUES ({i});")
        cursor.execute(f"INSERT INTO vec0 (doc_id, vec) VALUES ({i}, ?);", (b'live',))
        
    # insert orphaned vectors
    for i in range(num_live, num_live + num_orphans):
        cursor.execute(f"INSERT INTO vec0 (doc_id, vec) VALUES ({i}, ?);", (b'orphan',))
        
    conn.commit()
    
    if corrupt:
        # To simulate integrity failure, we'll write junk to the db file.
        conn.close()
        with open(db_path, "r+b") as f:
            f.seek(100)
            f.write(b'JUNK DATA FOR CORRUPTION TEST')
    else:
        conn.close()

def run_reclaim(*args, env=None):
    cmd = ["python", "utils/gh250/reclaim.py"] + list(args)
    return subprocess.run(cmd, env=env, capture_output=True, text=True)

def test_dry_run_changes_nothing(tmp_path):
    db_path = tmp_path / "test.db"
    setup_db(db_path, num_live=10, num_orphans=10)
    
    mtime_before = db_path.stat().st_mtime
    
    # dry-run
    res = run_reclaim("--database", str(db_path))
    assert res.returncode == 0
    assert "DRY RUN:" in res.stdout
    
    mtime_after = db_path.stat().st_mtime
    assert mtime_before == mtime_after
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM vec0;")
    assert cursor.fetchone()[0] == 20
    conn.close()

def test_execute_deletes_orphans(tmp_path):
    db_path = tmp_path / "test.db"
    setup_db(db_path, num_live=10, num_orphans=10)
    
    res = run_reclaim("--database", str(db_path), "--execute")
    assert res.returncode == 0
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM vec0;")
    assert cursor.fetchone()[0] == 10
    
    cursor.execute("SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);")
    assert cursor.fetchone()[0] == 10
    conn.close()

def test_production_path_guard(tmp_path):
    prod_path = Path("rebalance.db")
    # Backup original if it exists, though it shouldn't in this test environment
    # Actually, we shouldn't touch the real production db! We can just assert the script refuses it without creating it.
    
    # Check if prod db exists, but we can just run dry-run against it, it should fail before even checking if it exists.
    res = run_reclaim("--database", "rebalance.db")
    assert res.returncode != 0
    assert "ERROR: Refusing to run on production database" in res.stderr
    
    # Make sure we didn't write a file
    # We shouldn't write to rebalance.db in this test. We just rely on the script refusing it.

def test_batching_correctness(tmp_path):
    db_path = tmp_path / "test.db"
    setup_db(db_path, num_live=10, num_orphans=25)
    
    # run with batch size 10
    res = run_reclaim("--database", str(db_path), "--execute", "--batch-size", "10")
    assert res.returncode == 0
    
    assert "Batch 1: Deleted 10" in res.stdout
    assert "Batch 2: Deleted 10" in res.stdout
    assert "Batch 3: Deleted 5" in res.stdout
    
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT count(*) FROM vec0;").fetchone()[0] == 10
    conn.close()

def test_resume_after_interrupt(tmp_path):
    db_path = tmp_path / "test.db"
    setup_db(db_path, num_live=10, num_orphans=25)
    
    env = os.environ.copy()
    env["_CRASH_AFTER_BATCH"] = "1"
    
    # run with batch size 10, will crash after 1st batch
    res = run_reclaim("--database", str(db_path), "--execute", "--batch-size", "10", env=env)
    assert res.returncode != 0
    assert "CRASHING FOR TEST" in res.stderr
    
    # Check intermediate state: 10 deleted, 15 orphans left
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);").fetchone()[0] == 15
    conn.close()
    
    # Resume normally
    res2 = run_reclaim("--database", str(db_path), "--execute", "--batch-size", "10")
    assert res2.returncode == 0
    
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT count(*) FROM vec0;").fetchone()[0] == 10
    conn.close()

def test_zero_orphans_noop(tmp_path):
    db_path = tmp_path / "test.db"
    setup_db(db_path, num_live=10, num_orphans=0)
    
    res = run_reclaim("--database", str(db_path), "--execute")
    assert res.returncode == 0
    assert "No more orphans to delete." in res.stdout
    
def test_integrity_check_failure(tmp_path):
    db_path = tmp_path / "test.db"
    setup_db(db_path, num_live=10, num_orphans=10, corrupt=True)
    
    res = run_reclaim("--database", str(db_path), "--execute")
    assert res.returncode != 0
    assert "malformed" in res.stderr
