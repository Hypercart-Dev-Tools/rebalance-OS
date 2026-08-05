# rebalance.db Vector Bloat Reclaim Runbook (GH-250)

This runbook details the procedure to reclaim ~10.2 GB of disk space from `rebalance.db` by deleting orphaned vectors in the `vec0` virtual table.

It must be executed inside a maintenance window where no writers are active.

## 0. Operator Record

Create a dated file (e.g., `reclaim-2026-08-04.log`) to record the following required values during this procedure. Do not proceed if any value violates the stated bounds.

```text
Date/Operator:
Free bytes (df -k . | awk 'NR==2 {print $4 * 1024}'):
Database bytes (stat -f %z rebalance.db):

github_sync 1 timestamp:
Orphan count immediately after github_sync 1:
github_sync 2 timestamp:
Orphan count immediately after github_sync 2:
github_sync 3 timestamp:
Orphan count immediately after github_sync 3:
(Must be 3 identical counts. If they differ, ABORT. R1 is not confirmed.)

Journal Mode (must be 'wal'):
Integrity Check (must be 'ok'):

Baseline Total Vectors:
Baseline Live Vectors:
Baseline Orphan Vectors (post-fencing, MUST exactly equal sample 3 above, else ABORT):

Fence Verification Output:
(Paste successful `./utils/gh250/fence-writers.sh verify` output here)

Checkpoint Output:
(Paste exact 0|0|0 checkpoint verification output here)

Batch execution log:
(Paste the output of each batch here, including fence verification and progress lines)
```

## 1. Preconditions & Verification

Before proceeding with any destructive action, ensure all preconditions are met.

### 1.1 GH-250 R1 Confirmed
Confirm the orphan count is strictly flat across 3 `github_sync` cycles. For each cycle, first verify it completed, then sample the orphan count.

Command to verify a sync cycle completed (run and wait for a new timestamp):
```bash
grep -a "github_sync" ~/Library/Logs/rebalance/3eyes.log | grep "completed" | tail -n 1
```

Record the timestamp, then immediately run:
```bash
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
```
*Record the 3 identical samples and their sync completion timestamps in your Operator Record. If the counts differ in any way, ABORT.*

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

Before ANY destructive action, you must assert no processes hold handles to the database. Use this **Executable Reader/Writer Gate**:
```bash
./utils/gh250/fence-writers.sh verify
if lsof rebalance.db rebalance.db-wal rebalance.db-shm 2>/dev/null; then echo "ABORT: Processes holding handles detected!"; exit 1; else echo "OK: No handles"; fi
```
*If this gate fails or outputs anything other than `OK: No handles` and a clean verify, ABORT. Do not manually kill processes; investigate why the fence failed.*
*Paste the successful verify output into your Operator Record.*

**CRITICAL POST-FENCING GATE:** Re-run the orphan count. It MUST exactly equal sample 3 from Step 1.1.
```bash
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
```
*Record this as "Baseline Orphan Vectors" in your Operator Record. If it does not match exactly, ABORT.*

### 1.5 Consistent Backup and Restore Rehearsal
Take a consistent backup using SQLite's backup facility, then rehearse the restore command in a disposable location.

```bash
# 0. Ensure no backup destination exists
if [ -f "rebalance.db.backup" ]; then echo "ABORT: Backup already exists"; exit 1; fi

# 1. Run the Executable Reader/Writer Gate
./utils/gh250/fence-writers.sh verify
if lsof rebalance.db rebalance.db-wal rebalance.db-shm 2>/dev/null; then echo "ABORT: Handles open"; exit 1; fi

# 2. Checkpoint WAL before backup
sqlite3 rebalance.db "PRAGMA wal_checkpoint(TRUNCATE);"
# EXPECTED EXACT OUTPUT: 0|0|0
# If the result is NOT exactly 0|0|0, ABORT. Record the checkpoint output in your Operator Record.

# 3. Take a consistent SQLite backup
sqlite3 rebalance.db ".backup 'rebalance.db.backup'"

# 4. Rehearse the restore using the exact sidecar-aware rollback steps
RESTORE_DIR=$(mktemp -d -t rebalance_restore_test.XXXXXX)
# Simulate the failure state by copying the current files
cp rebalance.db "$RESTORE_DIR/rebalance.db"
[ -f rebalance.db-wal ] && cp rebalance.db-wal "$RESTORE_DIR/rebalance.db-wal"
[ -f rebalance.db-shm ] && cp rebalance.db-shm "$RESTORE_DIR/rebalance.db-shm"

# Execute sidecar-aware restore
cp rebalance.db.backup "$RESTORE_DIR/rebalance.db"
rm -f "$RESTORE_DIR/rebalance.db-wal" "$RESTORE_DIR/rebalance.db-shm"

# 5. Verify integrity and live vectors on the restored rehearsal
sqlite3 "$RESTORE_DIR/rebalance.db" "PRAGMA integrity_check;"
sqlite3 "$RESTORE_DIR/rebalance.db" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Verify integrity is 'ok' and live vectors exactly match Baseline Live Vectors.

# 6. Constrained cleanup of rehearsal
rm -f "$RESTORE_DIR/rebalance.db" "$RESTORE_DIR/rebalance.db-wal" "$RESTORE_DIR/rebalance.db-shm"
rmdir "$RESTORE_DIR"
```
*Do not proceed if the backup cannot be verified or live vectors do not match.*

---

## 2. Execution

### 2.1 Batch Deletion

Save this script to `delete_orphans.sh` (outside the repo) and execute it. It enforces the no-reader gate and explicit transaction checkpointing for each batch.

```bash
#!/bin/bash
set -euo pipefail

BATCH_SIZE=10000
DB="rebalance.db"
BATCH_NUM=1

while true; do
  # Executable Reader/Writer Gate per batch
  ./utils/gh250/fence-writers.sh verify >/dev/null
  if lsof "$DB" "$DB-wal" "$DB-shm" 2>/dev/null; then
    echo "ERROR: Processes holding handles detected before batch $BATCH_NUM!"
    exit 1
  fi
  
  # Checkpoint WAL before batch
  CP_RESULT=$(sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);" 2>&1)
  if [ "$CP_RESULT" != "0|0|0" ]; then
    echo "ERROR: WAL checkpoint failed before batch $BATCH_NUM. Result: $CP_RESULT"
    exit 1
  fi

  # Execute DELETE and SELECT changes() in the same explicit connection transaction
  OUTPUT=$(sqlite3 "$DB" "BEGIN IMMEDIATE; DELETE FROM vec0 WHERE rowid IN (SELECT rowid FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id) LIMIT $BATCH_SIZE); SELECT changes(); COMMIT;" 2>&1)
  
  # Robust numeric extraction
  CHANGES=$(echo "$OUTPUT" | grep -Eo '^[0-9]+$' | tail -n 1 || echo "ERROR")
  if [[ "$CHANGES" == "ERROR" ]] || ! [[ "$CHANGES" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Could not parse changes output in batch $BATCH_NUM: $OUTPUT"
    exit 1
  fi
  
  if [ "$CHANGES" -eq 0 ]; then
    echo "No more orphans to delete."
    break
  fi
  
  REMAINING=$(sqlite3 "$DB" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);" 2>&1)
  
  echo "Batch $BATCH_NUM: Deleted $CHANGES orphans. Remaining: $REMAINING. Checkpoint: $CP_RESULT"
  ((BATCH_NUM++))
done
```
*Record the script output (or final lines) and the fence verifications in your Operator Record.*

### 2.2 Reclaim Space (VACUUM INTO)

**1. Assert target absent:**
```bash
if [ -f "rebalance.db.vacuumed" ]; then echo "ABORT: Target already exists"; exit 1; fi
```

**2. Executable Reader/Writer Gate:**
```bash
./utils/gh250/fence-writers.sh verify
if lsof rebalance.db rebalance.db-wal rebalance.db-shm 2>/dev/null; then echo "ABORT: Handles open"; exit 1; fi
```

**3. Vacuum into the new file:**
```bash
sqlite3 rebalance.db "VACUUM INTO 'rebalance.db.vacuumed';"
```

**4. CRITICAL: Verify the vacuum target BEFORE swap:**
```bash
sqlite3 rebalance.db.vacuumed "PRAGMA integrity_check;"
# Expected: ok

sqlite3 rebalance.db.vacuumed "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: 0

sqlite3 rebalance.db.vacuumed "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: Exactly matches Baseline Live Vectors

stat -f %z rebalance.db.vacuumed
# Record target bytes in Operator Record
```

**5. Executable Reader/Writer Gate again before atomic swap:**
```bash
./utils/gh250/fence-writers.sh verify
if lsof rebalance.db rebalance.db-wal rebalance.db-shm rebalance.db.vacuumed 2>/dev/null; then echo "ABORT: Handles open"; exit 1; fi
```

**6. Atomic Swap:**
```bash
mv rebalance.db.vacuumed rebalance.db
```

---

## 3. Abort and Resume

### Abort Conditions
- Baseline measurements do not match exact requirements.
- Any background writer process is detected or verification fails.
- WAL checkpoint fails to return exactly `0|0|0`.
- The batch deletion script errors.
- Target `rebalance.db.vacuumed` exists before `VACUUM INTO`.

### Resumability
- **Batch Error:** Resolve the cause (e.g., disk full, random reader spawned). Run `PRAGMA integrity_check;` and verify baseline live vectors on `rebalance.db`. If they pass, resume by running the script again.
- **Interrupted `VACUUM INTO`:** The original database remains valid. Ensure no SQLite process is hanging (`lsof`). Inspect the incomplete target `rebalance.db.vacuumed` to ensure it is just a partial file, then safely remove it: `rm -f rebalance.db.vacuumed`. Restart step 2.2.
- **Failed/Interrupted Swap:** If the `mv` command fails, DO NOT blindly restore. Inspect `rebalance.db` and `rebalance.db.vacuumed`. If both exist, the swap didn't happen—preserve both, check integrity of `rebalance.db`, and retry the swap. If `rebalance.db` is missing or corrupt, preserve the failed artifacts and execute the full Rollback procedure.

---

## 4. Post-checks

All checks must pass before unfencing writers.

```bash
# 1. Integrity check
sqlite3 rebalance.db "PRAGMA integrity_check;"
# Expected: ok

# 2. Orphan count
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: 0

# 3. Live vector count (MUST exactly match baseline from Operator Record)
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: [Your recorded live vector count]

# 4. Total vector count (MUST exactly match baseline live count)
sqlite3 rebalance.db "SELECT count(*) FROM vec0;"
# Expected: [Your recorded live vector count]

# 5. Database size
TARGET_BYTES=$(grep -A1 "Record target bytes" reclaim-*.log | tail -n1 | grep -Eo '^[0-9]+$' || echo 1)
ACTUAL_BYTES=$(stat -f %z rebalance.db)
if [ "$ACTUAL_BYTES" -eq "$TARGET_BYTES" ]; then echo "OK: Size matches target"; else echo "WARN: Size mismatch"; fi
```

### 4.1 Unfence and Verify
```bash
# Restore schedules using the p4 restoration command
./utils/gh250/fence-writers.sh unfence
```

**Wait for the first scheduled `github_sync` or trigger it manually, then verify completion:**
```bash
grep -a "github_sync completed" ~/Library/Logs/rebalance/3eyes.log | tail -n 1
# Expected evidence: A log entry with a current timestamp indicating successful completion.
```

---

## 5. Rollback

If the database is corrupted or live vectors dropped, restore from backup. 

**1. Executable Reader/Writer Gate before rollback:**
```bash
./utils/gh250/fence-writers.sh verify
if lsof rebalance.db rebalance.db-wal rebalance.db-shm 2>/dev/null; then echo "ABORT: Handles open"; exit 1; fi
```

**2. Preserve failed artifacts (sidecar-aware):**
```bash
[ -f rebalance.db ] && mv rebalance.db rebalance.db.broken
[ -f rebalance.db-wal ] && mv rebalance.db-wal rebalance.db.broken-wal
[ -f rebalance.db-shm ] && mv rebalance.db-shm rebalance.db.broken-shm
[ -f rebalance.db.vacuumed ] && mv rebalance.db.vacuumed rebalance.db.vacuumed.broken
```

**3. Restore from backup:**
```bash
cp rebalance.db.backup rebalance.db
```

**4. Verify the restored state:**
```bash
sqlite3 rebalance.db "PRAGMA integrity_check;"
# Expected: ok

sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: Exactly matches Baseline Live Vectors

sqlite3 rebalance.db "SELECT count(*) FROM vec0;"
# Expected: Exactly matches Baseline Total Vectors

sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);"
# Expected: Exactly matches Baseline Orphan Vectors
```
