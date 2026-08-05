#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

def get_metrics(conn, db_path):
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM vec0;")
    total_vectors = cursor.fetchone()[0]
    
    cursor.execute("SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);")
    orphans = cursor.fetchone()[0]
    
    cursor.execute("SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);")
    live_vectors = cursor.fetchone()[0]
    
    cursor.execute("PRAGMA freelist_count;")
    freelist_count = cursor.fetchone()[0]
    
    db_size = Path(db_path).stat().st_size if Path(db_path).exists() else 0
    
    return {
        "db_size": db_size,
        "total_vectors": total_vectors,
        "orphans": orphans,
        "live_vectors": live_vectors,
        "freelist_count": freelist_count
    }

def print_table(before, after):
    print(f"{'Metric':<20} | {'Before':<15} | {'After':<15}")
    print("-" * 56)
    
    def format_size(b):
        return f"{b / (1024**3):.2f} GB" if b > 1024**3 else f"{b / (1024**2):.2f} MB"
        
    print(f"{'db size':<20} | {format_size(before['db_size']):<15} | {format_size(after['db_size']):<15}")
    print(f"{'total vectors':<20} | {before['total_vectors']:<15} | {after['total_vectors']:<15}")
    print(f"{'orphaned':<20} | {before['orphans']:<15} | {after['orphans']:<15}")
    print(f"{'live vectors':<20} | {before['live_vectors']:<15} | {after['live_vectors']:<15}")
    print(f"{'freelist_count':<20} | {before['freelist_count']:<15} | {after['freelist_count']:<15}")

def main():
    parser = argparse.ArgumentParser(description="Reclaim space by deleting orphaned vectors")
    parser.add_argument("--database", required=True, help="Path to the database")
    parser.add_argument("--execute", action="store_true", help="Actually delete rows (default is dry-run)")
    parser.add_argument("--i-know-this-is-production", action="store_true", help="Override to allow running on production DB")
    parser.add_argument("--batch-size", type=int, default=10000, help="Batch size for deletion")
    args = parser.parse_args()
    
    db_path = Path(args.database).resolve()
    prod_path = Path("rebalance.db").resolve()
    
    if db_path == prod_path and not args.i_know_this_is_production:
        print("ERROR: Refusing to run on production database without --i-know-this-is-production", file=sys.stderr)
        sys.exit(1)
        
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)
        
    conn = sqlite3.connect(args.database)
    conn.isolation_level = None # Autocommit mode, we will handle transactions explicitly
    
    before_metrics = get_metrics(conn, args.database)
    
    if not args.execute:
        print("DRY RUN: Would delete the following. Pass --execute to actually run.")
        print_table(before_metrics, before_metrics)
        sys.exit(0)
        
    print(f"Starting reclaim on {args.database} (batch size {args.batch_size})")
    
    total_deleted = 0
    batch_num = 1
    
    while True:
        cursor = conn.cursor()
        
        # Explicit transaction
        cursor.execute("BEGIN IMMEDIATE;")
        
        cursor.execute(f"""
            DELETE FROM vec0 
            WHERE rowid IN (
                SELECT rowid FROM vec0 
                WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id) 
                LIMIT {args.batch_size}
            );
        """)
        
        cursor.execute("SELECT changes();")
        changes = cursor.fetchone()[0]
        
        cursor.execute("COMMIT;")
        
        if changes == 0:
            print("No more orphans to delete.")
            break
            
        total_deleted += changes
        
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        cp_result = cursor.fetchone()
        
        cursor.execute("SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);")
        remaining = cursor.fetchone()[0]
        
        print(f"Batch {batch_num}: Deleted {changes} orphans. Remaining: {remaining}. Checkpoint: {cp_result}")
        
        if os.environ.get("_CRASH_AFTER_BATCH") == str(batch_num):
            print("CRASHING FOR TEST", file=sys.stderr)
            sys.exit(2)
            
        batch_num += 1
        
    print("Running integrity check...")
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    integrity = cursor.fetchone()[0]
    
    after_metrics = get_metrics(conn, args.database)
    
    print("\n--- Final Results ---")
    print_table(before_metrics, after_metrics)
    
    if integrity != "ok":
        print(f"\nERROR: Integrity check failed! Result: {integrity}", file=sys.stderr)
        sys.exit(1)
        
    if after_metrics["live_vectors"] != before_metrics["live_vectors"]:
        print(f"\nERROR: Live vectors count changed! Before: {before_metrics['live_vectors']}, After: {after_metrics['live_vectors']}", file=sys.stderr)
        sys.exit(1)
        
    print("\nReclaim completed successfully.")

if __name__ == "__main__":
    main()
