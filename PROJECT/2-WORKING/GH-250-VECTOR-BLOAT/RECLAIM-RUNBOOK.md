# rebalance.db Vector Bloat Reclaim Runbook (GH-250)

This runbook details the procedure to reclaim ~10.2 GB of disk space from `rebalance.db` by deleting orphaned vectors in the `vec0` virtual table.

It must be executed inside a maintenance window where no writers are active.

## 0. Operator Record
Create a dated file (e.g., `reclaim-2026-08-04.log`) to record the following required values during this procedure. Do not proceed if any value violates the stated bounds.

```text
Date/Operator:
Free bytes (df -B1 .):
Database bytes (ls -l rebalance.db):

Orphan count sync sample 1:
Orphan count sync sample 2:
Orphan count sync sample 3:
(Must be flat. If increasing, ABORT. R1 is not confirmed.)

Journal Mode (must be 'wal'):
Integrity Check (must be 'ok'):

Baseline Total Vectors:
Baseline Live Vectors:
Baseline Orphan Vectors:

Fence Verification Output:
(Paste successful output here)
```

## 1. Preconditions & Verification

Before proceeding with any destructive action, ensure all preconditions are met.

### 1.1 GH-250 R1 Confirmed
Confirm the orphan count is flat across at least 3 `github_sync` cycles. 
```bash
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
```
*Wait for a few sync cycles. Record the samples in your Operator Record. If the count increases, ABORT.*

### 1.2 Baseline Measurements
Record these numbers in your Operator Record.
```bash
# Total database bytes
ls -l rebalance.db

# Total vectors
sqlite3 rebalance.db "SELECT count(*) FROM vec0;"

# Live vectors (MUST remain unchanged at the end)
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"

# Orphaned vectors
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"

# Journal mode
sqlite3 rebalance.db "PRAGMA journal_mode;"

# Integrity check
sqlite3 rebalance.db "PRAGMA integrity_check;"
```

### 1.3 Disk Space Headroom
You must have sufficient free space for the live database + backup + `VACUUM INTO` rebuild copy **plus a 10 GB margin**.
**Formula:** `Free Space Bytes > (Database Bytes * 2) + 1.2 GB (estimated vacuumed size) + 10 GB`
Record the bytes and recomputable comparison in your Operator Record.
```bash
df -B1 .
ls -l rebalance.db
```
*(Reference: For a 13.43 GB DB, you need: 13.43 (live) + 13.43 (backup) + ~1.2 (vacuum target) = ~28.06 GB. With a 10 GB margin, you need ~38.06 GB free space. The reference system had 319 GB available.)*

### 1.4 Stop and Fence Writers
No background tasks or other writers can be active during this operation. Run the fencing script and paste the successful output into your Operator Record.
```bash
./utils/gh250/fence-writers.sh
```
*Check for any rogue processes still holding open file handles. Ensure no output is returned for the db file:*
```bash
lsof rebalance.db
```

### 1.5 Consistent Backup and Restore Rehearsal
Take a consistent backup using SQLite's backup facility, then rehearse the restore command in a disposable location.
```bash
# 1. Checkpoint WAL before backup to ensure all data is in the main file
sqlite3 rebalance.db "PRAGMA wal_checkpoint(TRUNCATE);"
# Expected output begins with "0|" (e.g., 0|0|0). If not, abort.

# 2. Take a consistent SQLite backup
sqlite3 rebalance.db ".backup 'rebalance.db.backup'"

# 3. Rehearse the restore in a temporary location
mkdir -p /tmp/rebalance_restore_test
cp rebalance.db.backup /tmp/rebalance_restore_test/rebalance.db
sqlite3 /tmp/rebalance_restore_test/rebalance.db "PRAGMA integrity_check;"
sqlite3 /tmp/rebalance_restore_test/rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Verify integrity is 'ok' and live vectors match baseline.

# 4. Clean up rehearsal
rm -rf /tmp/rebalance_restore_test
```
*Do not proceed if the backup cannot be read or live vectors do not match.*

---

## 2. Execution

The database must be in WAL mode. Delete operations are batched to prevent holding the writer lock for too long and to avoid unbounded WAL inflation.

### 2.1 Batch Deletion
Verify no remaining writer/reader processes exist (`lsof rebalance.db`), then run the following script. The script enables fail-fast (`set -e`) and captures the deleted row count in the same transaction.

Save this to a temporary script `delete_orphans.sh` (outside the repo if necessary, e.g. in `/tmp`) and execute it:

```bash
#!/bin/bash
set -e

BATCH_SIZE=10000
DB="rebalance.db"

while true; do
  # Execute DELETE and SELECT changes() in the same connection
  OUTPUT=$(sqlite3 "$DB" "DELETE FROM vec0 WHERE rowid IN (SELECT rowid FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id) LIMIT $BATCH_SIZE); SELECT changes();")
  
  CHANGES=$(echo "$OUTPUT" | tail -n 1)
  
  if [ "$CHANGES" -eq 0 ]; then
    echo "No more orphans to delete."
    break
  fi
  
  # Checkpoint WAL explicitly and abort if it fails
  CP_RESULT=$(sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);")
  if [[ "$CP_RESULT" != 0|* ]]; then
    echo "ERROR: WAL checkpoint failed with result: $CP_RESULT"
    exit 1
  fi
  
  echo "Deleted $CHANGES orphans. Checkpoint result: $CP_RESULT"
done
```

### 2.2 Reclaim Space (VACUUM INTO)
Once all orphans are deleted, reclaim space using `VACUUM INTO`. 
Verify there is no pre-existing vacuum target before running:
```bash
rm -f rebalance.db.vacuumed

# Vacuum into a new file
sqlite3 rebalance.db "VACUUM INTO 'rebalance.db.vacuumed';"

# Verify the vacuumed database
sqlite3 rebalance.db.vacuumed "PRAGMA integrity_check;"

# Atomic swap (replace old db with new db)
mv rebalance.db.vacuumed rebalance.db
```

---

## 3. Abort and Resume

If things go wrong, evaluate the state based on the following conditions:

### Abort Conditions
Abort the procedure before or during execution if:
- Orphan count increases during the R1 confirmation (sync sample).
- `PRAGMA integrity_check` returns anything other than `ok`.
- Free disk space is below the calculated formula threshold.
- Any background writer process is detected.
- WAL checkpoint fails (result does not start with `0|`).
- The batch deletion script returns a batch error.

### Resumability
- **Batch Error:** If the script errors, resolve the cause (e.g., killed process, disk full). Run `PRAGMA integrity_check;` and verify baseline live vectors. If they pass, you may resume by running the script again.
- **Interrupted `VACUUM INTO`:** Safe. If `VACUUM INTO` fails or is interrupted, the original database is untouched. Simply delete the partial target (`rm -f rebalance.db.vacuumed`) and restart the vacuum command.
- **Failed/Interrupted Swap:** Unsafe. If the `mv` command is interrupted, you must perform a full restore from backup.

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

# 3. Live vector count (MUST exactly match baseline from Operator Record)
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: [Your recorded live vector count, e.g., 9292]

# 4. Database size
ls -lh rebalance.db
# Expected: Near the predicted ~1.2 GB
```

### 4.1 Unfence and Verify
If all post-checks pass, unfence the writers and verify the next sync works:
```bash
# Unfence writers
./utils/gh250/unfence-writers.sh

# Force or wait for the next sync to run (e.g., via launchctl if scheduled)
# Verify the sync completed successfully:
# Expected evidence: recent logs showing successful github_sync without errors
```

---

## 5. Rollback

If you made a mistake (e.g. live vectors count dropped) or the database is corrupted, restore from the backup.

```bash
# 1. Ensure no SQLite processes are touching the DB. Check for any locking processes:
lsof rebalance.db

# 2. Move the broken DB and its WAL/SHM files aside to preserve them for debugging
mv rebalance.db rebalance.db.broken
mv rebalance.db-wal rebalance.db.broken-wal 2>/dev/null || true
mv rebalance.db-shm rebalance.db.broken-shm 2>/dev/null || true

# 3. Restore the backup (with exact commands to handle -wal/-shm)
cp rebalance.db.backup rebalance.db
rm -f rebalance.db-wal rebalance.db-shm

# 4. Verify the restore
sqlite3 rebalance.db "PRAGMA integrity_check;"
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Must be 'ok' and match baseline live vectors.
```
