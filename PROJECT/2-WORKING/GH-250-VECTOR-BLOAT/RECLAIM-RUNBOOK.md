# rebalance.db Vector Bloat Reclaim Runbook (GH-250)

This runbook details the procedure to reclaim ~10.2 GB of disk space from `rebalance.db` by deleting orphaned vectors in the `vec0` virtual table.

It must be executed inside a maintenance window where no writers are active.

## 0. Operator Record

Create a dated file (e.g., `reclaim-2026-08-04.log`) to record the following required values during this procedure. Do not proceed if any value violates the stated bounds.

```text
Date/Operator:
Free bytes (df -k . | awk 'NR==2 {print $4 * 1024}'):
Database bytes (stat -f %z rebalance.db):

Orphan count immediately after github_sync 1:
Orphan count immediately after github_sync 2:
Orphan count immediately after github_sync 3:
(Must be flat. If increasing, ABORT. R1 is not confirmed.)

Journal Mode (must be 'wal'):
Integrity Check (must be 'ok'):

Baseline Total Vectors:
Baseline Live Vectors:
Baseline Orphan Vectors (post-fencing, MUST exactly equal the final R1 sample above, else ABORT):

Fence Verification Output:
(Paste successful `./utils/gh250/fence-writers.sh verify` output here)

Checkpoint Output:
(Paste exact 0|0|0 checkpoint verification output here)
```

## 1. Preconditions & Verification

Before proceeding with any destructive action, ensure all preconditions are met.

### 1.1 GH-250 R1 Confirmed
Confirm the orphan count is flat across at least 3 `github_sync` cycles. Record each sample immediately after a named `github_sync` cycle completes.
```bash
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
```
*Record the 3 samples in your Operator Record. If the count increases, ABORT.*

### 1.2 Baseline Measurements
Record these baseline values in your Operator Record.
```bash
# Total database bytes
stat -f %z rebalance.db

# Total vectors
sqlite3 rebalance.db "SELECT count(*) FROM vec0;"

# Live vectors (MUST remain unchanged at the end)
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"

# Journal mode
sqlite3 rebalance.db "PRAGMA journal_mode;"

# Integrity check
sqlite3 rebalance.db "PRAGMA integrity_check;"
```

### 1.3 Disk Space Headroom
You must have sufficient free space for the live database + backup + `VACUUM INTO` rebuild copy **plus a 10 GB margin**.
**Formula:** `Free Space Bytes > Live DB Bytes + Backup DB Bytes (same size) + 1.2 GB (estimated vacuumed size) + 10 GB (margin)`
```bash
# Get Free Bytes:
df -k . | awk 'NR==2 {print $4 * 1024}'

# Get Live DB Bytes:
stat -f %z rebalance.db
```
*(Reference: For a 13.43 GB DB, you need: 13.43 (live) + 13.43 (backup) + ~1.2 (vacuum target) + 10 GB margin = ~38.06 GB free space. The reference system had 319 GB available.)*
*Record the bytes and recomputable comparison in your Operator Record. If not enough space, ABORT.*

### 1.4 Stop and Fence Writers
No background tasks or other writers can be active during this operation. Run the fencing script:
```bash
./utils/gh250/fence-writers.sh fence
```
Verify the fence was successful and paste the output into your Operator Record:
```bash
./utils/gh250/fence-writers.sh verify
```
Check for any rogue processes still holding open file handles. Ensure no output is returned for the db file:
```bash
lsof rebalance.db
```
*If `lsof` returns any output, you MUST kill those processes before continuing.*

**CRITICAL POST-FENCING GATE:** Re-run the orphan count. It MUST exactly equal the final R1 sample from Step 1.1.
```bash
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
```
*Record this as "Baseline Orphan Vectors" in your Operator Record. If it does not match exactly, ABORT.*

### 1.5 Consistent Backup and Restore Rehearsal
Take a consistent backup using SQLite's backup facility, then rehearse the restore command in a disposable location.
```bash
# 0. Ensure no readers/writers
lsof rebalance.db

# 1. Checkpoint WAL before backup to ensure all data is in the main file
sqlite3 rebalance.db "PRAGMA wal_checkpoint(TRUNCATE);"
# EXPECTED: 0|0|0
# If the result is NOT 0|0|0, readers are still active or the checkpoint failed. ABORT.
# Record the checkpoint output in your Operator Record.

# 2. Take a consistent SQLite backup
sqlite3 rebalance.db ".backup 'rebalance.db.backup'"

# 3. Rehearse the restore in a safe temporary directory
RESTORE_DIR=$(mktemp -d -t rebalance_restore_test)
cp rebalance.db.backup "$RESTORE_DIR/rebalance.db"

# 4. Verify integrity and live vectors on the restored rehearsal
sqlite3 "$RESTORE_DIR/rebalance.db" "PRAGMA integrity_check;"
sqlite3 "$RESTORE_DIR/rebalance.db" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Verify integrity is 'ok' and live vectors match the Baseline Live Vectors.

# 5. Clean up rehearsal
rm -rf "$RESTORE_DIR"
```
*Do not proceed if the backup cannot be read or live vectors do not match.*

---

## 2. Execution

The database must be in WAL mode. Delete operations are batched to prevent holding the writer lock for too long and to avoid unbounded WAL inflation.

### 2.1 Batch Deletion
Verify no remaining writer/reader processes exist:
```bash
lsof rebalance.db
./utils/gh250/fence-writers.sh verify
```
Save this to a temporary script `delete_orphans.sh` (outside the repo if necessary, e.g. in `/tmp`) and execute it. It runs in a strict pipeline and explicitly checks for exact WAL checkpoint success.

```bash
#!/bin/bash
set -euo pipefail

BATCH_SIZE=10000
DB="rebalance.db"
BATCH_NUM=1

while true; do
  # Execute DELETE and SELECT changes() in the same explicit connection transaction, capturing stderr
  OUTPUT=$(sqlite3 "$DB" "BEGIN IMMEDIATE; DELETE FROM vec0 WHERE rowid IN (SELECT rowid FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id) LIMIT $BATCH_SIZE); SELECT changes(); COMMIT;" 2>&1)
  
  CHANGES=$(echo "$OUTPUT" | tail -n 1)
  
  if [ "$CHANGES" -eq 0 ]; then
    echo "No more orphans to delete."
    break
  fi
  
  # Checkpoint WAL explicitly and abort if it fails
  CP_RESULT=$(sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);" 2>&1)
  case "$CP_RESULT" in
    0\|0\|0)
      ;;
    *)
      echo "ERROR: WAL checkpoint failed or readers still active. Result: $CP_RESULT"
      exit 1
      ;;
  esac
  
  REMAINING=$(sqlite3 "$DB" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);" 2>&1)
  
  echo "Batch $BATCH_NUM: Deleted $CHANGES orphans. Remaining: $REMAINING. Checkpoint: $CP_RESULT"
  ((BATCH_NUM++))
done
```

### 2.2 Reclaim Space (VACUUM INTO)
Once all orphans are deleted, reclaim space using `VACUUM INTO`. 

Verify no writers/readers are active:
```bash
lsof rebalance.db
./utils/gh250/fence-writers.sh verify
```

Assert the vacuum target does **NOT** exist. If `ls` finds it, **ABORT** and investigate. Do not blindly `rm -f`.
```bash
ls rebalance.db.vacuumed
# Expected: "ls: rebalance.db.vacuumed: No such file or directory"
```

Vacuum into the new file:
```bash
sqlite3 rebalance.db "VACUUM INTO 'rebalance.db.vacuumed';"
```

**CRITICAL:** Verify the vacuum target's integrity, orphan count, and baseline live count **BEFORE** replacing the original. Also record its bytes.
```bash
# Verify integrity
sqlite3 rebalance.db.vacuumed "PRAGMA integrity_check;"
# Expected: ok

# Verify 0 orphans
sqlite3 rebalance.db.vacuumed "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: 0

# Verify baseline live vectors match
sqlite3 rebalance.db.vacuumed "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: [Your recorded live vector count]

# Record target bytes
stat -f %z rebalance.db.vacuumed
```

If all checks pass, perform the atomic swap. `mv` within the same directory on the same filesystem is atomic.
```bash
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
- WAL checkpoint fails (result is not exactly `0|0|0`).
- The batch deletion script returns a batch error.
- The vacuum target `rebalance.db.vacuumed` already exists before `VACUUM INTO`.

### Resumability
- **Batch Error:** If the script errors, resolve the cause (e.g., killed process, disk full). Run `PRAGMA integrity_check;` and verify baseline live vectors on `rebalance.db`. If they pass, you may resume by running the script again.
- **Interrupted `VACUUM INTO`:** Safe. If `VACUUM INTO` fails or is interrupted, the original database is untouched. Ensure no SQLite process is hanging, delete the incomplete partial target (`rm -f rebalance.db.vacuumed`), and restart the vacuum command.
- **Failed/Interrupted Swap:** Needs inspection. If the `mv` command somehow fails, do not blindly restore. Check the state of `rebalance.db` and `rebalance.db.vacuumed`. If `rebalance.db` is missing or corrupted, preserve the failed artifacts (move them aside) and perform the full restore procedure.

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
stat -f %z rebalance.db
# Expected: Within a few MBs of the recorded vacuumed target bytes (~1.2 GB).
```

### 4.1 Unfence and Verify
If all post-checks pass, unfence the writers and verify the next sync works:
```bash
# Unfence writers to restore schedules exactly as they were
./utils/gh250/fence-writers.sh unfence

# Check that schedules are loaded
./utils/gh250/fence-writers.sh verify
# (This should now FAIL to verify zero writers, meaning writers are back)
```

Confirm the first post-unfence sync completes normally. Wait for the scheduled `github_sync` or trigger it, then tail the logs to ensure success:
```bash
# Check the log for a completed sync
grep -a "github_sync" ~/Library/Logs/rebalance/3eyes.log | tail -n 5
# Expected evidence: A log entry indicating a successful sync round completed without errors.
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
