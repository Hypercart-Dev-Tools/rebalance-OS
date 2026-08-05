# Reclaim Runbook for GH-250 Vector Bloat

This runbook outlines the exact procedure for a human to reclaim space from the database by deleting orphaned vectors accumulated from GH-250 vector bloat. This procedure must be executed inside a maintenance window.

## 0. Pre-Flight Measurements

First, set the absolute database path as an environment variable to be used in all subsequent commands:
```bash
export DB_PATH="/Users/noelsaw/Documents/rebalance-OS/rebalance.db"
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
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```

Record these numbers. The live vector count **must** match exactly in the post-checks to prove no valid data was destroyed.

## 1. Preconditions

All of the following conditions act as gates. Do not proceed if any step fails.

### [ ] 1.1. Confirm R1 Fix (Orphan Count Flat)
Ensure the orphan count has remained flat across at least 3 `github_sync` cycles. Capture and compare three samples:
```bash
# Wait for github_sync cycle 1...
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
# Wait for github_sync cycle 2...
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
# Wait for github_sync cycle 3...
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```
If the count increases at all, or if the final sample does not exactly match the start value you recorded in step 0, **ABORT**.

### [ ] 1.2. Writers Fenced
Fencing writers prevents new records or concurrent updates.
```bash
./utils/gh250/fence-writers.sh fence
./utils/gh250/fence-writers.sh verify
```
*Verify the output of the `verify` command confirms writers are fenced. Paste the verification output into your operational log.*

### [ ] 1.3. Backup Taken and Restore Rehearsed
Take a snapshot backup and perform a mock restore to confirm it works.
**Take backup:**
```bash
sqlite3 "$DB_PATH" ".backup '${DB_PATH}.backup'"
```
**Rehearse restore to a dummy location:**
```bash
sqlite3 "${DB_PATH}.restore_test" ".restore '${DB_PATH}.backup'"
sqlite3 "${DB_PATH}.restore_test" "PRAGMA integrity_check;"
```
*(Expect output: `ok`. If it says anything else, **ABORT**).*
Delete the test db afterward:
```bash
rm "${DB_PATH}.restore_test"
```

### [ ] 1.4. Free Space Go/No-Go
Verify there is enough free space on the volume.
**Formula:** `Current DB size + Backup + VACUUM rebuild copy + Margin`.
For example, using the reference ~13.43 GB: `13.43 GB (db) + 13.43 GB (backup) + 1.2 GB (compacted rebuild copy) + 11.94 GB (margin) = ~40 GB required`.

Run this command to check free space on the volume:
```bash
df -k $(dirname "$DB_PATH") | awk 'NR==2 {print $4}'
```
*(This prints the available space in 1K-blocks).*
Ensure the available space is greater than your calculated required threshold. If it does not, **ABORT**.

## 2. Execution

### 2.1. Confirm Journal Mode
We assume WAL mode for these operations. Confirm the database is in WAL mode:
```bash
sqlite3 "$DB_PATH" "PRAGMA journal_mode;"
```
*(Expect output: `wal`. If it is not, the checkpoint commands below will fail).*

### 2.2. Batched Delete
A single monolithic delete transaction will hold the writer lock for too long and inflate the WAL unboundedly. We perform deletes in batches of 50,000 using `NOT EXISTS`.

Run this self-contained copy-pasteable script block in your shell:
```bash
export DB_PATH="/Users/noelsaw/Documents/rebalance-OS/rebalance.db"
export BATCH_SIZE=50000

while true; do
  REMAINING=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);")
  if [ "$REMAINING" -eq 0 ]; then
    echo "Deletion complete. 0 orphans remain."
    break
  fi
  echo "Orphans remaining: $REMAINING. Deleting next batch of $BATCH_SIZE..."
  
  sqlite3 "$DB_PATH" <<EOF
BEGIN IMMEDIATE;
DELETE FROM vec0 WHERE rowid IN (
    SELECT rowid FROM vec0
    WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id)
    LIMIT $BATCH_SIZE
);
COMMIT;
EOF
  if [ $? -ne 0 ]; then
    echo "ERROR: SQL delete failed. Aborting."
    exit 1
  fi

  sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint(TRUNCATE);"
  if [ $? -ne 0 ]; then
    echo "ERROR: WAL checkpoint failed. Aborting."
    exit 1
  fi
  
  sleep 1
done
```

### 2.3. VACUUM INTO
The database needs to be compacted to reclaim the disk space. We use `VACUUM INTO` followed by a two-step atomic cutover sequence. This is safer than a direct `VACUUM` because it rebuilds the database into a new file without modifying the original in-place.

First, verify that no readers or writers remain and that the current DB is healthy:
```bash
./utils/gh250/fence-writers.sh verify
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
```

Run the `VACUUM INTO` command (this will take time):
```bash
sqlite3 "$DB_PATH" "VACUUM INTO '${DB_PATH}.compact';"
```

Before swapping, validate the compacted file:
```bash
sqlite3 "${DB_PATH}.compact" "PRAGMA integrity_check;"
sqlite3 "${DB_PATH}.compact" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
sqlite3 "${DB_PATH}.compact" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
ls -lh "${DB_PATH}.compact"
```
*(Expect `integrity_check` to be `ok`, orphan count to be `0`, live count to match the baseline exactly, and size to be around `1.2 GB`)*. If any of these fail, **ABORT** and discard the compact file.

Perform the cutover sequence. These two `mv` operations constitute an atomic cutover (the original is moved out of the way, and the compact file takes its place). Use uniquely named retained originals:
```bash
TIMESTAMP=$(date +%s)
mv "$DB_PATH" "${DB_PATH}.retained_${TIMESTAMP}"
mv "${DB_PATH}.compact" "$DB_PATH"
```

## 3. Abort and Resume

### Abort Conditions
- **Unexpected orphan count at start**: The orphan count does not match the baseline or has changed unexpectedly.
- **`integrity_check` not `ok`**: The database fails its integrity check at any point.
- **Disk headroom below threshold**: Disk space falls below the calculated safety margin.
- **Any writer still live**: The fence script fails or a writer process is detected.
- **Batch error**: Any batch delete command returns an error or a checkpoint error occurs.

### Resume vs. Restore
- **Resumable (Batched Deletes)**: If the batched deletion loop is interrupted or aborted cleanly, it is safe to just re-run it. Each committed batch is durable, and the query naturally picks up where it left off. Run the pre-delete integrity check and writer fence verify before resuming.
- **Not Resumable (VACUUM)**: If `VACUUM INTO` is interrupted, the output file (`${DB_PATH}.compact`) is corrupt and unusable. It is safe to discard a partial `VACUUM INTO` output and retry. Simply run `rm "${DB_PATH}.compact"` and restart the `VACUUM INTO` step.
- **Restore Required**: If live vectors are inadvertently deleted or a catastrophic corruption occurs during the swap, you must execute a full restore.

### Executing a Restore
If a restore is forced, stop all processes and run:

Verify writers are fenced:
```bash
./utils/gh250/fence-writers.sh verify
```

Move the damaged DB out of the way using a unique name:
```bash
TIMESTAMP=$(date +%s)
mv "$DB_PATH" "${DB_PATH}.bad_${TIMESTAMP}"
```

Restore from the pre-flight backup:
```bash
sqlite3 "$DB_PATH" ".restore '${DB_PATH}.backup'"
```

Verify the restore (integrity + original live/orphan counts):
```bash
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```
*(Expect `integrity_check` to be `ok`, and the live/orphan counts to match your original pre-flight measurements).*

Only unfence once restored and verified:
```bash
./utils/gh250/fence-writers.sh unfence
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
rebalance doctor
```

### [ ] 4.6. Unfence Writers and Verify Sync
Once all checks above have passed:
1. Restore the launchd schedules (unfence):
```bash
./utils/gh250/fence-writers.sh unfence
```
2. Wait for or trigger the next `github_sync`.
3. Confirm the sync completes normally.

## 5. Rollback

If something has gone critically wrong under time pressure and you need to abort the maintenance window quickly:

**1. Halt Execution:**
Press `Ctrl+C` in the terminal to stop any running scripts or `VACUUM`.

**2. Ensure writers are still fenced:**
```bash
./utils/gh250/fence-writers.sh verify
```

**3. Move the bad database files completely out of the way (never overwrite an existing recovery file):**
```bash
TIMESTAMP=$(date +%s)
mv "$DB_PATH" "${DB_PATH}.failed_${TIMESTAMP}"
rm -f "${DB_PATH}-wal" "${DB_PATH}-shm"
```

**4. Execute Restore from the pre-flight backup:**
```bash
sqlite3 "$DB_PATH" ".restore '${DB_PATH}.backup'"
```

**5. Verify the restored DB:**
```bash
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
sqlite3 "$DB_PATH" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```
*(Verify integrity is `ok`, and counts match the pre-flight original).*

**6. Unfence Writers:**
```bash
./utils/gh250/fence-writers.sh unfence
```

*(Do not casually delete the original or failed database; retain them for debugging unless disk space is completely exhausted).*
