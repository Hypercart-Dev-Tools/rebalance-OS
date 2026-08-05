# rebalance.db Vector Bloat Reclaim Runbook (GH-250)

This runbook details the procedure to reclaim ~10.2 GB of disk space from `rebalance.db` by deleting orphaned vectors in the `vec0` virtual table.

It must be executed inside a maintenance window where no writers are active.

## 1. Preconditions & Verification

Before proceeding, ensure all of these conditions are met:

### 1.1 GH-250 R1 Confirmed
Confirm the orphan count is flat across at least 3 `github_sync` cycles. Reclaiming before the writer fix is verified will result in re-orphaned vectors.
```bash
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
```
*Wait for a few sync cycles and verify this number does not increase.*

### 1.2 Stop and Fence Writers
No background tasks or other writers can be active during this operation. Run the fencing script and confirm the output:
```bash
./utils/gh250/fence-writers.sh
```
*Expected: The script must output success indicating all writers are fenced.*

### 1.3 Disk Space Headroom
You must have sufficient free space for the database, backup, and the vacuum rebuild copy.
**Formula:** `Free Space > (DB Size * 2.5) + 10 GB` (margin).
Check DB size and free space:
```bash
ls -lh rebalance.db
df -h .
```
*(Reference: For a 13.43 GB DB, you need at least ~40 GB free space. Verify against your `df -h` output.)*

### 1.4 Baseline Measurements
Record these numbers before starting. They will be used to verify the procedure worked correctly.
```bash
# 1. Total database size
ls -lh rebalance.db

# 2. Total vectors
sqlite3 rebalance.db "SELECT count(*) FROM vec0;"

# 3. Live vectors (MUST remain unchanged at the end)
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"

# 4. Orphaned vectors
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"

# 5. Integrity check
sqlite3 rebalance.db "PRAGMA integrity_check;"
```

### 1.5 Backup and Restore Rehearsal
Take a backup and **rehearse the restore**.
```bash
# Take the backup
cp rebalance.db rebalance.db.backup

# Rehearse the restore by copying it to a test file
cp rebalance.db.backup rebalance.db.restore_test

# Verify the test file is readable and identical
sqlite3 rebalance.db.restore_test "PRAGMA integrity_check;"
rm rebalance.db.restore_test
```
*Do not proceed if the backup cannot be read.*

---

## 2. Execution

The deletion is batched to prevent holding the writer lock for too long and to avoid unbounded WAL inflation.
The database must be in WAL mode. Verify with:
```bash
sqlite3 rebalance.db "PRAGMA journal_mode;"
```
*(Expected output: `wal`)*

### 2.1 Batch Deletion
Run the following script to delete orphaned vectors in batches of 10,000. This uses `NOT EXISTS` which correctly handles missing or NULL `doc_id`s.

Save this to a temporary script `delete_orphans.sh` (outside the repo if necessary, e.g. in `/tmp`) or run it directly in your shell:

```bash
#!/bin/bash

BATCH_SIZE=10000
DB="rebalance.db"

while true; do
  # Delete a batch of orphans
  sqlite3 "$DB" "DELETE FROM vec0 WHERE rowid IN (SELECT rowid FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id) LIMIT $BATCH_SIZE);"
  
  # Check if any rows were deleted
  CHANGES=$(sqlite3 "$DB" "SELECT changes();")
  
  if [ "$CHANGES" -eq 0 ]; then
    echo "No more orphans to delete."
    break
  fi
  
  # Checkpoint WAL
  sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);"
  
  # Print progress
  REMAINING=$(sqlite3 "$DB" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);")
  echo "Deleted $CHANGES orphans. $REMAINING orphans remaining."
done
```
*Wait for this script to finish. It will print progress after every batch.*

### 2.2 Reclaim Space (VACUUM INTO)
Once all orphans are deleted, reclaim space. We use `VACUUM INTO` because it is safer. It writes the rebuilt database to a new file, ensuring the original database is untouched until the swap.
*Note: `VACUUM` needs exclusive access. No concurrent readers (including `rebalance doctor`) are allowed.*

```bash
# Vacuum into a new file
sqlite3 rebalance.db "VACUUM INTO 'rebalance.db.vacuumed';"

# Verify the vacuumed database
sqlite3 rebalance.db.vacuumed "PRAGMA integrity_check;"

# Atomic swap (replace old db with new db)
mv rebalance.db.vacuumed rebalance.db
```

---

## 3. Abort and Resume

If things go wrong, follow these guidelines:

### Abort Conditions
Abort the procedure and evaluate if:
- The initial orphan count is different than expected (e.g., increasing).
- `PRAGMA integrity_check` returns anything other than `ok`.
- Free disk space is below the required threshold.
- Any background writer process is detected.
- The batch deletion script returns an error.

### Resumability
- **Batch Deletions:** Safe to resume. Each batch is a committed transaction. Just run the script again.
- **Interrupted VACUUM:** NOT resumable. If `VACUUM INTO` fails or is killed, simply delete the partial `rebalance.db.vacuumed` file. The original `rebalance.db` is untouched. If a standard `VACUUM` was used and interrupted, the database might be corrupt, and you MUST restore from backup.

---

## 4. Post-checks

Run these checks to verify the cleanup. **All must pass before unfencing writers.**

```bash
# 1. Integrity check
sqlite3 rebalance.db "PRAGMA integrity_check;"
# Expected: ok

# 2. Orphan count
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: 0

# 3. Live vector count (MUST match baseline from step 1.4)
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: [Your recorded live vector count, e.g., 9292]

# 4. Database size
ls -lh rebalance.db
# Expected: Should have dropped significantly (e.g., near ~1.2 GB)

# 5. Doctor checks
rebalance doctor
# Expected: clean output
```

### 4.1 Unfence and Verify
If all post-checks pass, unfence the writers and verify the next sync works:
```bash
# Unfence writers
./utils/gh250/unfence-writers.sh

# Re-enable launchd schedules (specific to your setup)
# Monitor the next github_sync to ensure it completes normally.
```

---

## 5. Rollback

If you made a mistake (e.g. live vectors count dropped) or the database is corrupted, restore from the backup immediately.

```bash
# 1. Ensure no SQLite processes are touching the DB
# (Kill them if necessary)

# 2. Move the broken DB aside
mv rebalance.db rebalance.db.broken

# 3. Restore the backup
cp rebalance.db.backup rebalance.db

# 4. Verify the restore
sqlite3 rebalance.db "PRAGMA integrity_check;"
```
*Do not forget to keep writers fenced until the root cause is resolved.*
