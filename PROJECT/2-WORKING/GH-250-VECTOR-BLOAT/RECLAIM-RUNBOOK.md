# Reclaim Runbook for GH-250 Vector Bloat

This runbook outlines the exact procedure for a human to reclaim space from the database by deleting orphaned vectors accumulated from GH-250 vector bloat. This procedure must be executed inside a maintenance window.

## 0. Pre-Flight Measurements

First, set the absolute environment variables to be used in all subsequent commands:
```bash
export REPO_ROOT="/Users/noelsaw/Documents/rebalance-OS"
export DB_PATH="${REPO_ROOT}/rebalance.db"
export FENCE_SCRIPT="${REPO_ROOT}/utils/gh250/fence-writers.sh"
export PYTHONPATH="${REPO_ROOT}/src"
export PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
```

Before beginning the operation, measure the current database state. The orphan count will have drifted from the reference run due to syncs happening before the R1 fix landed. The reference metrics (measured 2026-08-04) are:
- `rebalance.db` size: 13.43 GB
- Total vectors: 2,687,606
- Orphaned vectors: 2,678,314 (99.65%)
- Live vectors: 9,292
- `freelist_count`: 0
- Expected reclaim: ~10.2 GB → db lands near ~1.2 GB
- Free space on volume: 319 GB

Run a pre-delete integrity check:
```bash
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
```
*(Expect output: `ok`. If it says anything else, **ABORT**).*

Measure the database size:
```bash
ls -lh "$DB_PATH"
```

Measure the `freelist_count`:
```bash
sqlite3 "$DB_PATH" "PRAGMA freelist_count;"
```

Measure the total vector count:
```bash
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0;"
```

Measure the live vector count:
```bash
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```

Measure the current orphan count:
```bash
export START_ORPHAN_COUNT=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);")
echo "Execution start orphan count: $START_ORPHAN_COUNT"
```

Record these numbers. The live vector count **must** match exactly in the post-checks to prove no valid data was destroyed.

## 1. Preconditions

All of the following conditions act as gates. Do not proceed if any step fails.

### [ ] 1.1. Confirm R1 Fix (Orphan Count Flat)
Ensure the orphan count has remained flat across at least 3 `github_sync` cycles. Wait for three `github_sync` cycles to complete, recording the orphan count after each:

```bash
# Wait for github_sync cycle 1 to complete...
export SAMPLE_1=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);")
# Wait for github_sync cycle 2 to complete...
export SAMPLE_2=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);")
# Wait for github_sync cycle 3 to complete...
export SAMPLE_3=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);")

echo "Sample 1: $SAMPLE_1, Sample 2: $SAMPLE_2, Sample 3: $SAMPLE_3, Start: $START_ORPHAN_COUNT"

if [ "$SAMPLE_1" != "$SAMPLE_2" ] || [ "$SAMPLE_2" != "$SAMPLE_3" ] || [ "$SAMPLE_3" != "$START_ORPHAN_COUNT" ]; then
    echo "ERROR: Orphan count is drifting. R1 fix is not confirmed. ABORT."
    exit 1
else
    echo "SUCCESS: Orphan count is flat."
fi
```
If the script exits with an error, **ABORT**.

### [ ] 1.2. Writers Fenced
Fencing writers prevents new records or concurrent updates.
```bash
"$FENCE_SCRIPT" fence
"$FENCE_SCRIPT" verify
```
*Verify the output of the `verify` command confirms writers are fenced. Paste the verification output into your operational log.*

### [ ] 1.3. Backup Taken and Restore Rehearsed
Take a snapshot backup and perform a mock restore to confirm it works. Use a timestamped path.

```bash
export TIMESTAMP=$(date +%s)
export BACKUP_PATH="${DB_PATH}.backup_${TIMESTAMP}"
export TEST_DB_PATH="${DB_PATH}.restore_test_${TIMESTAMP}"

# Prove destinations do not exist
ls -la "$BACKUP_PATH" "$TEST_DB_PATH" 2>/dev/null && { echo "ERROR: Backup paths already exist. ABORT."; exit 1; } || echo "Paths are clear."

# Take backup
sqlite3 "$DB_PATH" ".backup '${BACKUP_PATH}'"

# Verify backup integrity directly
sqlite3 "$BACKUP_PATH" "PRAGMA integrity_check;"

# Rehearse restore
sqlite3 "$TEST_DB_PATH" ".restore '${BACKUP_PATH}'"
sqlite3 "$TEST_DB_PATH" "PRAGMA integrity_check;"

# Verify counts in restored DB match the baseline
export TEST_TOTAL=$(sqlite3 "$TEST_DB_PATH" "SELECT count(*) FROM vec0;")
export TEST_LIVE=$(sqlite3 "$TEST_DB_PATH" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);")
export TEST_ORPHANS=$(sqlite3 "$TEST_DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);")

echo "Restored Test DB - Total: $TEST_TOTAL, Live: $TEST_LIVE, Orphans: $TEST_ORPHANS"
```
*(Expect `integrity_check` to be `ok`, and the counts to match your baseline precisely. If any step fails or counts mismatch, **ABORT**).*

Instead of blindly removing the test database, retain it unless disk space is critically constrained. If you must remove it, verify its path first:
```bash
ls -la "$TEST_DB_PATH"
# rm "$TEST_DB_PATH"
```

### [ ] 1.4. Free Space Go/No-Go
Verify there is enough free space on the volume.
**Formula:** `Current DB size + Backup + VACUUM rebuild copy + Margin`.
Using the reference 13.43 GB: `13.43 GB (db) + 13.43 GB (backup) + 1.2 GB (compacted copy) + 11.94 GB (margin) = ~40 GB required`.

Run this command to calculate and verify free space:
```bash
export REQUIRED_KB=$((40 * 1024 * 1024))
export AVAILABLE_KB=$(df -k $(dirname "$DB_PATH") | awk 'NR==2 {print $4}')

echo "Required: $REQUIRED_KB KB, Available: $AVAILABLE_KB KB"

if [ "$AVAILABLE_KB" -lt "$REQUIRED_KB" ]; then
    echo "ERROR: Insufficient free space. ABORT."
    exit 1
else
    echo "SUCCESS: Sufficient disk space available."
fi
```
If the script exits with an error, **ABORT**.

## 2. Execution

### 2.1. Confirm Journal Mode
We assume WAL mode for these operations. Confirm the database is in WAL mode:
```bash
sqlite3 "$DB_PATH" "PRAGMA journal_mode;"
```
*(Expect output: `wal`. If it is not, the checkpoint commands below will fail).*

### 2.2. Batched Delete
A single monolithic delete transaction will hold the writer lock for too long and inflate the WAL unboundedly. We perform deletes in batches of 50,000 using `NOT EXISTS`.

Run this self-contained script block in your shell:
```bash
set -euo pipefail

export BATCH_SIZE=50000

while true; do
  BEFORE=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);")
  if [ "$BEFORE" -eq 0 ]; then
    echo "Deletion complete. 0 orphans remain."
    break
  fi
  
  echo "Before batch: $BEFORE orphans."
  
  DELETED=$(sqlite3 "$DB_PATH" "
    BEGIN IMMEDIATE;
    DELETE FROM vec0 WHERE rowid IN (
        SELECT rowid FROM vec0
        WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id)
        LIMIT $BATCH_SIZE
    );
    SELECT changes();
    COMMIT;
  ")
  
  if ! [[ "$DELETED" =~ ^[0-9]+$ ]] || [ "$DELETED" -eq 0 ]; then
    echo "ERROR: Expected to delete vectors but changes() returned '$DELETED'. Aborting."
    exit 1
  fi
  
  REMAINING=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);")
  
  echo "Deleted: $DELETED, Remaining: $REMAINING."

  # Checkpoint WAL
  CHECKPOINT_RESULT=$(sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint(TRUNCATE);")
  CHECKPOINT_BUSY=$(echo "$CHECKPOINT_RESULT" | awk -F'|' '{print $1}')
  
  if [ "$CHECKPOINT_BUSY" != "0" ]; then
    echo "ERROR: WAL checkpoint returned busy lock ($CHECKPOINT_RESULT). Aborting."
    exit 1
  fi
done
```

### 2.3. VACUUM INTO
The database needs to be compacted to reclaim the disk space. We use `VACUUM INTO` followed by a two-step atomic cutover sequence. This rebuilds the database into a new file without modifying the original in-place.

First, verify that no readers or writers remain and that the current DB is healthy:
```bash
"$FENCE_SCRIPT" verify
lsof "$DB_PATH" || echo "No open file handles (as expected)."
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
```
*(If `lsof` shows processes holding the DB open, **ABORT**).*

Set a unique target for the compact file and ensure it does not exist:
```bash
export COMPACT_TIMESTAMP=$(date +%s)
export COMPACT_PATH="${DB_PATH}.compact_${COMPACT_TIMESTAMP}"

ls -la "$COMPACT_PATH" 2>/dev/null && { echo "ERROR: Target exists. ABORT."; exit 1; } || echo "Target clear."
```

Run the `VACUUM INTO` command (this will take time):
```bash
sqlite3 "$DB_PATH" "VACUUM INTO '${COMPACT_PATH}';"
```

Before swapping, validate the compacted file:
```bash
sqlite3 "$COMPACT_PATH" "PRAGMA integrity_check;"
sqlite3 "$COMPACT_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
sqlite3 "$COMPACT_PATH" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
ls -lh "$COMPACT_PATH"
```
*(Expect `integrity_check` to be `ok`, orphan count to be `0`, live count to match the baseline exactly, and size to be around `1.2 GB`)*. If any of these fail, **ABORT**, retain the compact file for inspection, and retry only to a new unique target path.

Perform the cutover sequence. Repeat the no-open-handles check immediately before cutover:
```bash
lsof "$DB_PATH" || echo "No open file handles (as expected)."
```

Verify source and destination before each `mv`. Note that the first rename is atomic, but the two-rename cutover sequence as a whole is not atomic.
```bash
export RETAINED_PATH="${DB_PATH}.retained_${COMPACT_TIMESTAMP}"
ls -la "$RETAINED_PATH" 2>/dev/null && { echo "ERROR: Retained path already exists. ABORT."; exit 1; } || echo "Retained path is clear."

ls -la "$DB_PATH"
mv "$DB_PATH" "$RETAINED_PATH"

ls -la "$COMPACT_PATH"
mv "$COMPACT_PATH" "$DB_PATH"
```

If WAL and SHM sidecars exist for the original DB, preserve them using unique names rather than blindly removing them:
```bash
[ -f "${DB_PATH}-wal" ] && mv "${DB_PATH}-wal" "${RETAINED_PATH}-wal"
[ -f "${DB_PATH}-shm" ] && mv "${DB_PATH}-shm" "${RETAINED_PATH}-shm"
```

## 3. Abort and Resume

### Abort Conditions
- **Unexpected orphan count at start**: The orphan count does not match the baseline or has changed unexpectedly.
- **`integrity_check` not `ok`**: The database fails its integrity check at any point.
- **Disk headroom below threshold**: Disk space falls below the calculated safety margin.
- **Any writer still live**: The fence script fails or a writer process is detected via `lsof`.
- **Batch error**: Any batch delete command returns an error or a checkpoint error occurs (a busy lock).

### Resume vs. Restore
- **Resumable (Batched Deletes)**: If the batched deletion loop is interrupted cleanly, it is safe to resume. However, before resuming, you MUST re-verify integrity, verify writers are still fenced, and re-check baseline live vector counts.
- **Not Resumable (VACUUM)**: A failed or interrupted `VACUUM INTO` output is corrupt. Do not overwrite it; retain it for inspection and restart `VACUUM INTO` with a new unique output path.
- **Restore Required**: If live vectors are inadvertently deleted or a catastrophic corruption occurs during the swap, you must execute a full restore.

### Executing a Restore
If a restore is forced, stop all processes and run:

Verify writers are fenced:
```bash
"$FENCE_SCRIPT" verify
```

Check the path and move the damaged DB (and sidecars) out of the way using a unique name:
```bash
export BAD_TIMESTAMP=$(date +%s)
export BAD_PATH="${DB_PATH}.bad_${BAD_TIMESTAMP}"

ls -la "$BAD_PATH" 2>/dev/null && { echo "ERROR: Path exists. ABORT."; exit 1; } || echo "Path is clear."

ls -la "$DB_PATH"
mv "$DB_PATH" "$BAD_PATH"
[ -f "${DB_PATH}-wal" ] && mv "${DB_PATH}-wal" "${BAD_PATH}-wal"
[ -f "${DB_PATH}-shm" ] && mv "${DB_PATH}-shm" "${BAD_PATH}-shm"
```

Restore from the pre-flight backup:
```bash
sqlite3 "$DB_PATH" ".restore '${BACKUP_PATH}'"
```

Verify the restore (integrity + original live/orphan/total counts):
```bash
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0;"
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```
*(Expect `integrity_check` to be `ok`, and the total/live/orphan counts to exactly match your pre-flight baseline).*

Only unfence once restored and verified:
```bash
"$FENCE_SCRIPT" unfence
```

## 4. Post-checks

All post-checks must pass before unfencing writers.

### [ ] 4.1. Integrity Check
```bash
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
```
*(Expect output: `ok`)*

### [ ] 4.2. Orphan Count is 0
```bash
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```
*(Expect output: `0`)*

### [ ] 4.3. Live Vector Count Unchanged
```bash
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```
*(Expect output: Exactly the same as the pre-flight measurement)*

### [ ] 4.4. Database Size Reduced
```bash
ls -lh "$DB_PATH"
```
*(Expect output: Size is near the predicted ~1.2 GB)*

### [ ] 4.5. Rebalance Doctor is Clean
Run the doctor with p2 checks:
```bash
# This must pass fully.
"$PYTHON_BIN" -m rebalance doctor
```

### [ ] 4.6. Unfence Writers and Verify Sync
Once all checks above have passed:
1. Restore the launchd schedules (unfence):
```bash
"$FENCE_SCRIPT" unfence
```
2. Wait for or trigger the next `github_sync`.
3. Confirm the sync completes normally.

## 5. Rollback

If something has gone critically wrong under time pressure and you need to abort the maintenance window quickly:

**1. Halt Execution:**
Press `Ctrl+C` in the terminal to stop any running scripts or `VACUUM`.

**2. Ensure writers are still fenced:**
```bash
"$FENCE_SCRIPT" verify
```

**3. Move the bad database files completely out of the way (never overwrite an existing recovery file):**
```bash
export FAILED_TIMESTAMP=$(date +%s)
export FAILED_PATH="${DB_PATH}.failed_${FAILED_TIMESTAMP}"

ls -la "$FAILED_PATH" 2>/dev/null && { echo "ERROR: Path exists. ABORT."; exit 1; } || echo "Path is clear."

ls -la "$DB_PATH"
mv "$DB_PATH" "$FAILED_PATH"
[ -f "${DB_PATH}-wal" ] && mv "${DB_PATH}-wal" "${FAILED_PATH}-wal"
[ -f "${DB_PATH}-shm" ] && mv "${DB_PATH}-shm" "${FAILED_PATH}-shm"
```

**4. Execute Restore from the pre-flight backup:**
```bash
sqlite3 "$DB_PATH" ".restore '${BACKUP_PATH}'"
```

**5. Verify the restored DB:**
```bash
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0;"
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```
*(Verify integrity is `ok`, and total, live, and orphan counts match the pre-flight original exactly).*

**6. Unfence Writers:**
```bash
"$FENCE_SCRIPT" unfence
```

*(Retain all original, failed, or partial databases for debugging unless disk space is completely exhausted).*
