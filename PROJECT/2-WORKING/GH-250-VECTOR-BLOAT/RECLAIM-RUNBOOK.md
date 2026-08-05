# rebalance.db Vector Bloat Reclaim Runbook (GH-250)

This runbook details the procedure to reclaim ~10.2 GB of disk space from `rebalance.db` by deleting orphaned vectors in the `vec0` virtual table.

It must be executed inside a maintenance window where no writers are active.

> ## ⚠️ DRAFT — reviewed but NOT approved. Read before running anything.
>
> This runbook was rejected by its reviewer four times and never reached approval. Two defects found
> afterwards are fixed here, but it has had **no** approving review since:
>
> 1. **Its queries named tables that do not exist.** Every count used `vec0` / `items` — sqlite-vec's
>    *documentation example* names, not this database's. The baseline query failed outright with
>    `no such table: vec0`. Corrected throughout to `github_embeddings` / `github_documents`.
> 2. **It reimplemented the batch delete inline**, in untested shell, duplicating
>    `utils/gh250/reclaim.py` — which has 13 tests against a production-shaped schema and is verified
>    working against the real database. **Prefer the script.** Any inline SQL below is illustrative;
>    the script is the sanctioned path.
>
> Outstanding reviewer objections (valid, unaddressed): make every fence/handle assertion a real
> shell gate rather than a command followed by prose; capture `wal_checkpoint` output and require
> exactly `0|0|0`; do not discard `verify` output with `>/dev/null` when the record must show every
> gate result; guard every `mv`/`rm` with sidecar-aware preconditions; state a recomputable post-size
> range rather than "~1.2 GB".
>
> **Do not execute this against production until those are closed and it has been approved.**

## 0. Set Operator Environment & Record

Define an environment variable for your operator record to ensure all checks append to it rather than relying on manual copy-pasting.

```bash
export RECORD_FILE="reclaim-$(date +%F-%H%M%S).log"
echo "--- Reclaim Runbook Started ---" | tee -a "$RECORD_FILE"
```

Do not proceed past Section 1 if any value violates the stated bounds.

## 1. Preconditions & Verification

Before proceeding with any destructive action, ensure all preconditions are met.

### 1.1 GH-250 R1 Confirmed

Confirm the orphan count is strictly flat across 3 `github_sync` cycles. For each cycle, capture a marker, wait for the sync to complete, and immediately sample the orphan count. 

**Repeat this process 3 times:**
```bash
# 1. Get a log marker before the sync
MARKER=$(wc -l < ~/Library/Logs/rebalance/3eyes.log)

# 2. Wait for the sync to complete (or trigger it in another terminal)
tail -n +$MARKER -f ~/Library/Logs/rebalance/3eyes.log | grep -m 1 "github_sync completed" | tee -a "$RECORD_FILE"

# 3. Immediately query the orphan count
sqlite3 rebalance.db "SELECT count(*) FROM github_embeddings WHERE NOT EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" | tee -a "$RECORD_FILE"
```
*If the 3 counts recorded are not identical, ABORT.*

### 1.2 Baseline Measurements

Record baseline values in your Operator Record.

```bash
echo -n "Total DB Bytes: " | tee -a "$RECORD_FILE"
stat -f %z rebalance.db | tee -a "$RECORD_FILE"

echo -n "Total Vectors: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "SELECT count(*) FROM github_embeddings;" | tee -a "$RECORD_FILE"

echo -n "Live Vectors: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "SELECT count(*) FROM github_embeddings WHERE EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" | tee -a "$RECORD_FILE"

echo -n "Journal Mode (Must be 'wal'): " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "PRAGMA journal_mode;" | tee -a "$RECORD_FILE"

echo -n "Integrity Check (Must be 'ok'): " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "PRAGMA integrity_check;" | tee -a "$RECORD_FILE"
```

### 1.3 Disk Space Headroom

You must have sufficient free space for the live database + backup + `VACUUM INTO` rebuild copy **plus a 10 GB margin**.
**Formula:** `Free Space Bytes > Live DB Bytes + Backup DB Bytes (same size) + 1.2 GB (estimated vacuumed size) + 10 GB (margin)`

```bash
echo -n "Free Bytes: " | tee -a "$RECORD_FILE"
df -k . | awk 'NR==2 {print $4 * 1024}' | tee -a "$RECORD_FILE"
```
*(Reference: For a 13.43 GB DB, you need: 13.43 (live) + 13.43 (backup) + ~1.2 (vacuum target) + 10 GB margin = ~38.06 GB free space. Verify your free space is greater than this.)*
*If you do not have enough disk space, ABORT.*

### 1.4 Stop and Fence Writers

Run the fencing script to ensure no background tasks or other writers are active:
```bash
./utils/gh250/fence-writers.sh fence | tee -a "$RECORD_FILE"
```

**Executable Reader/Writer Gate** (run this before every destructive step):
```bash
if ! FENCE_OUT=$(./utils/gh250/fence-writers.sh verify); then 
  echo "ABORT: Fence verification failed. Output: $FENCE_OUT" | tee -a "$RECORD_FILE"; exit 1
fi
echo "$FENCE_OUT" | tee -a "$RECORD_FILE"
if lsof rebalance.db rebalance.db-wal rebalance.db-shm >/dev/null 2>&1; then 
  echo "ABORT: Processes holding handles detected!" | tee -a "$RECORD_FILE"; exit 1
else 
  echo "OK: No handles" | tee -a "$RECORD_FILE"
fi
```
*If this gate fails, ABORT. Investigate the cause rather than killing processes.*

**CRITICAL POST-FENCING GATE:** Re-run the orphan count. It MUST exactly equal the samples from Step 1.1.
```bash
echo -n "Post-fencing Orphan Count: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "SELECT count(*) FROM github_embeddings WHERE NOT EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" | tee -a "$RECORD_FILE"
```
*If this count does not exactly match the counts from 1.1, ABORT.*

### 1.5 Consistent Backup and Restore Rehearsal

Take a consistent backup and rehearse the restore process in a uniquely named location.

```bash
# 0. Ensure no backup destination exists
if [ -f "rebalance.db.backup" ]; then echo "ABORT: Backup already exists" | tee -a "$RECORD_FILE"; exit 1; fi

# 1. Executable Reader/Writer Gate
if ! FENCE_OUT=$(./utils/gh250/fence-writers.sh verify); then echo "ABORT: Fence verification failed. Output: $FENCE_OUT" | tee -a "$RECORD_FILE"; exit 1; fi
echo "$FENCE_OUT" | tee -a "$RECORD_FILE"
if lsof rebalance.db rebalance.db-wal rebalance.db-shm >/dev/null 2>&1; then echo "ABORT: Processes holding handles detected!" | tee -a "$RECORD_FILE"; exit 1; fi

# 2. Checkpoint WAL before backup
echo -n "Backup Checkpoint Result: " | tee -a "$RECORD_FILE"
CP_RESULT=$(sqlite3 rebalance.db "PRAGMA wal_checkpoint(TRUNCATE);" 2>&1)
echo "$CP_RESULT" | tee -a "$RECORD_FILE"
if [ "$CP_RESULT" != "0|0|0" ]; then echo "ABORT: WAL checkpoint failed or not clean" | tee -a "$RECORD_FILE"; exit 1; fi

# 3. Take a consistent SQLite backup
sqlite3 rebalance.db ".backup 'rebalance.db.backup'" | tee -a "$RECORD_FILE"

# 4. Rehearse restore steps in a unique directory
RESTORE_DIR=$(mktemp -d -t rebalance_restore_test.XXXXXX)
# Simulate failure state
cp rebalance.db "$RESTORE_DIR/rebalance.db"
[ -f rebalance.db-wal ] && cp rebalance.db-wal "$RESTORE_DIR/rebalance.db-wal"
[ -f rebalance.db-shm ] && cp rebalance.db-shm "$RESTORE_DIR/rebalance.db-shm"

# Execute sidecar-aware restore command
cp rebalance.db.backup "$RESTORE_DIR/rebalance.db"
rm -f "$RESTORE_DIR/rebalance.db-wal" "$RESTORE_DIR/rebalance.db-shm"

# 5. Verify integrity and baseline on the restored DB
echo -n "Rehearsal Integrity: " | tee -a "$RECORD_FILE"
sqlite3 "$RESTORE_DIR/rebalance.db" "PRAGMA integrity_check;" | tee -a "$RECORD_FILE"
echo -n "Rehearsal Live Vectors: " | tee -a "$RECORD_FILE"
sqlite3 "$RESTORE_DIR/rebalance.db" "SELECT count(*) FROM github_embeddings WHERE EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" | tee -a "$RECORD_FILE"

# 6. Approve cleanup (Only proceed if rehearsal counts matched exactly)
rm -f "$RESTORE_DIR/rebalance.db"
rmdir "$RESTORE_DIR"
```

---

## 2. Execution

### 2.1 Batch Deletion

Save this script to `delete_orphans.sh` and execute it.
```bash
#!/bin/bash
set -euo pipefail
BATCH_SIZE=10000
DB="rebalance.db"
BATCH_NUM=1

while true; do
  # Executable Reader/Writer Gate
  if ! FENCE_OUT=$(./utils/gh250/fence-writers.sh verify); then echo "ERROR: Fence verification failed before batch $BATCH_NUM. Output: $FENCE_OUT" | tee -a "$RECORD_FILE"; exit 1; fi
  echo "Batch $BATCH_NUM Fence: $FENCE_OUT" | tee -a "$RECORD_FILE"
  if lsof "$DB" "$DB-wal" "$DB-shm" >/dev/null 2>&1; then echo "ERROR: Processes holding handles detected before batch $BATCH_NUM!" | tee -a "$RECORD_FILE"; exit 1; fi
  
  # Checkpoint WAL
  CP_RESULT=$(sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);" 2>&1)
  echo "Batch $BATCH_NUM Checkpoint: $CP_RESULT" | tee -a "$RECORD_FILE"
  if [ "$CP_RESULT" != "0|0|0" ]; then echo "ERROR: WAL checkpoint failed before batch $BATCH_NUM. Result: $CP_RESULT" | tee -a "$RECORD_FILE"; exit 1; fi

  # Execute DELETE and SELECT changes() in a single explicit transaction
  OUTPUT=$(sqlite3 "$DB" "BEGIN IMMEDIATE; DELETE FROM github_embeddings WHERE rowid IN (SELECT rowid FROM github_embeddings WHERE NOT EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id) LIMIT $BATCH_SIZE); SELECT changes(); COMMIT;" 2>&1)
  
  CHANGES=$(echo "$OUTPUT" | grep -Eo '^[0-9]+$' | tail -n 1 || true)
  if [[ -z "$CHANGES" ]] || ! [[ "$CHANGES" =~ ^[0-9]+$ ]]; then echo "ERROR: Could not parse changes output: $OUTPUT" | tee -a "$RECORD_FILE"; exit 1; fi
  if [ "$CHANGES" -eq 0 ]; then echo "No more orphans to delete." | tee -a "$RECORD_FILE"; break; fi
  
  # Robust remaining count
  REMAINING=$(sqlite3 "$DB" "SELECT count(*) FROM github_embeddings WHERE NOT EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" 2>&1)
  if ! [[ "$REMAINING" =~ ^[0-9]+$ ]]; then echo "ERROR: Failed to query remaining count: $REMAINING" | tee -a "$RECORD_FILE"; exit 1; fi
  
  echo "Batch $BATCH_NUM: Deleted $CHANGES orphans. Remaining: $REMAINING." | tee -a "$RECORD_FILE"
  ((BATCH_NUM++))
done
```

### 2.2 Reclaim Space (VACUUM INTO)

**1. Verify Target is Absent:**
```bash
if [ -f "rebalance.db.vacuumed" ]; then echo "ABORT: Target already exists" | tee -a "$RECORD_FILE"; exit 1; fi
```

**2. Executable Reader/Writer Gate:**
```bash
if ! FENCE_OUT=$(./utils/gh250/fence-writers.sh verify); then echo "ABORT: Fence verification failed" | tee -a "$RECORD_FILE"; exit 1; fi
echo "$FENCE_OUT" | tee -a "$RECORD_FILE"
if lsof rebalance.db rebalance.db-wal rebalance.db-shm >/dev/null 2>&1; then echo "ABORT: Handles open" | tee -a "$RECORD_FILE"; exit 1; fi
```

**3. VACUUM INTO the new file:**
```bash
sqlite3 rebalance.db "VACUUM INTO 'rebalance.db.vacuumed';"
```

**4. CRITICAL: Verify Target Properties BEFORE Swap:**
```bash
echo -n "Vacuumed Target Integrity: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db.vacuumed "PRAGMA integrity_check;" | tee -a "$RECORD_FILE"
# Expected: ok

echo -n "Vacuumed Target Orphan Count: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db.vacuumed "SELECT count(*) FROM github_embeddings WHERE NOT EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" | tee -a "$RECORD_FILE"
# Expected: 0

echo -n "Vacuumed Target Live Count: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db.vacuumed "SELECT count(*) FROM github_embeddings WHERE EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" | tee -a "$RECORD_FILE"
# Expected: [Your recorded baseline live count]

echo -n "Vacuumed Target Bytes: " | tee -a "$RECORD_FILE"
stat -f %z rebalance.db.vacuumed | tee -a "$RECORD_FILE"
```
*If any of these values are incorrect, DO NOT execute the swap. ABORT and Rollback.*

**5. Executable Reader/Writer Gate before swap:**
```bash
if ! FENCE_OUT=$(./utils/gh250/fence-writers.sh verify); then echo "ABORT: Fence verification failed" | tee -a "$RECORD_FILE"; exit 1; fi
echo "$FENCE_OUT" | tee -a "$RECORD_FILE"
if lsof rebalance.db rebalance.db-wal rebalance.db-shm rebalance.db.vacuumed >/dev/null 2>&1; then echo "ABORT: Handles open" | tee -a "$RECORD_FILE"; exit 1; fi
```

**6. Atomic Swap (Guarded):**
```bash
if ! mv rebalance.db.vacuumed rebalance.db; then
  echo "ERROR: Swap failed. Original files intact." | tee -a "$RECORD_FILE"
  exit 1
fi
```
*(Same-directory `mv` is atomic on POSIX file systems. If it fails midway, `rebalance.db` might still exist intact or neither exists depending on the filesystem. Proceed to Abort/Rollback if it fails.)*

---

## 3. Abort and Resume

### Resume Batch Error
Resolve the cause (e.g. disk space). Re-run the Executable Reader/Writer Gate. Run `PRAGMA integrity_check;`, verify the Live Count exactly matches the baseline, and measure a fresh Orphan Count. If all are successful, restart the batch script.

### Interrupted/Failed `VACUUM INTO`
If `VACUUM INTO` is interrupted, inspect `rebalance.db.vacuumed` manually to confirm it is just incomplete data. Verify `rebalance.db` integrity is still `ok`. After ensuring it is safe, run `rm -i rebalance.db.vacuumed`. Proceed from step 2.2.

### Failed Swap
If `mv` fails, DO NOT blindly restore. Check the state.
If `rebalance.db` exists and `rebalance.db.vacuumed` exists, `mv` didn't happen. Preserve `rebalance.db.vacuumed` by moving it to `rebalance.db.vacuumed.broken`, check `rebalance.db` integrity, and re-attempt. If `rebalance.db` is corrupt, proceed to Rollback.

---

## 4. Post-checks

All checks must pass before unfencing writers.

```bash
# 1. Rebalance Doctor
rebalance doctor | tee -a "$RECORD_FILE"
# Expected: Clean result with no errors

# 2. Database Checks
echo -n "Final Integrity: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "PRAGMA integrity_check;" | tee -a "$RECORD_FILE"

echo -n "Final Orphan Count: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "SELECT count(*) FROM github_embeddings WHERE NOT EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" | tee -a "$RECORD_FILE"

echo -n "Final Live Count: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "SELECT count(*) FROM github_embeddings WHERE EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" | tee -a "$RECORD_FILE"

echo -n "Final Total Count: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "SELECT count(*) FROM github_embeddings;" | tee -a "$RECORD_FILE"

# 3. Size Comparison
TARGET_BYTES=$(grep -A1 "Vacuumed Target Bytes:" "$RECORD_FILE" | tail -n1 | grep -Eo '^[0-9]+$' || echo 1)
ACTUAL_BYTES=$(stat -f %z rebalance.db)
if [ "$ACTUAL_BYTES" -eq "$TARGET_BYTES" ]; then echo "OK: Final DB size matches target." | tee -a "$RECORD_FILE"; else echo "WARN: Size mismatch" | tee -a "$RECORD_FILE"; fi
```

### 4.1 Unfence and Verify
Restore the schedules:
```bash
./utils/gh250/fence-writers.sh unfence | tee -a "$RECORD_FILE"
```

**Verify the first normal `github_sync`:**
```bash
# Get marker
MARKER=$(wc -l < ~/Library/Logs/rebalance/3eyes.log)
# Wait for the sync completion confirmation in logs
tail -n +$MARKER -f ~/Library/Logs/rebalance/3eyes.log | grep -m 1 "github_sync completed" | tee -a "$RECORD_FILE"
```

---

## 5. Rollback

**1. Executable Reader/Writer Gate:**
```bash
if ! FENCE_OUT=$(./utils/gh250/fence-writers.sh verify); then echo "ABORT: Fence verification failed" | tee -a "$RECORD_FILE"; exit 1; fi
echo "$FENCE_OUT" | tee -a "$RECORD_FILE"
if lsof rebalance.db rebalance.db-wal rebalance.db-shm >/dev/null 2>&1; then echo "ABORT: Handles open" | tee -a "$RECORD_FILE"; exit 1; fi
```

**2. Guarded Preservation of Broken Artifacts:**
```bash
BROKEN_PREFIX="rebalance.db.broken.$(date +%s)"
[ -f rebalance.db ] && mv rebalance.db "$BROKEN_PREFIX"
[ -f rebalance.db-wal ] && mv rebalance.db-wal "$BROKEN_PREFIX-wal"
[ -f rebalance.db-shm ] && mv rebalance.db-shm "$BROKEN_PREFIX-shm"
[ -f rebalance.db.vacuumed ] && mv rebalance.db.vacuumed "$BROKEN_PREFIX.vacuumed"
```

**3. Restore from Backup:**
```bash
cp rebalance.db.backup rebalance.db
```

**4. Verify the Restored DB:**
```bash
echo -n "Restored Integrity: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "PRAGMA integrity_check;" | tee -a "$RECORD_FILE"

echo -n "Restored Live Count: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "SELECT count(*) FROM github_embeddings WHERE EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" | tee -a "$RECORD_FILE"

echo -n "Restored Total Count: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "SELECT count(*) FROM github_embeddings;" | tee -a "$RECORD_FILE"

echo -n "Restored Orphan Count: " | tee -a "$RECORD_FILE"
sqlite3 rebalance.db "SELECT count(*) FROM github_embeddings WHERE NOT EXISTS (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id);" | tee -a "$RECORD_FILE"
```
