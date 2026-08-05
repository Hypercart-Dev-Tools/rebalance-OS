# Reclaim Runbook for GH-250 Vector Bloat

This runbook outlines the exact procedure for a human to reclaim space from `rebalance.db` by deleting orphaned vectors accumulated from GH-250 vector bloat. This procedure must be executed inside a maintenance window.

## 0. Pre-Flight Measurements

Before beginning the operation, measure the current database state. The orphan count will have drifted from the reference run (~13.43 GB, 2.67M orphans, 9.2k live vectors) due to syncs happening before the R1 fix landed.

Measure the database size (in bytes/GB):
```bash
ls -lh rebalance.db
```

Measure the current orphan count:
```bash
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```

Measure the live vector count:
```bash
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```

Record these numbers. The live vector count **must** match exactly in the post-checks to prove no valid data was destroyed.

## 1. Preconditions

All of the following conditions act as gates. Do not proceed if any step fails.

### [ ] 1.1. Confirm R1 Fix (Orphan Count Flat)
Ensure the orphan count has remained flat across at least 3 `github_sync` cycles to verify the writer fix.
Run the orphan measurement command above and wait across sync cycles. If the count increases, **ABORT**.

### [ ] 1.2. Writers Fenced
Fencing writers prevents new records or concurrent updates during this operation. Run the fence script:
```bash
./utils/gh250/fence-writers.sh
```
*Verify the output confirms writers are fenced. Paste the verification output into your operational log.*

### [ ] 1.3. Backup Taken and Restore Rehearsed
Take a snapshot backup and perform a mock restore to confirm it works. A backup you cannot restore is not a valid rollback.
**Take backup:**
```bash
sqlite3 rebalance.db ".backup 'rebalance.db.backup'"
```
**Rehearse restore to a dummy location:**
```bash
sqlite3 rebalance_restore_test.db ".restore 'rebalance.db.backup'"
sqlite3 rebalance_restore_test.db "PRAGMA integrity_check;"
```
*(Expect output: `ok`. If it says anything else, **ABORT**). Delete the test db afterward: `rm rebalance_restore_test.db`*

### [ ] 1.4. Free Space Go/No-Go
Verify there is enough free space on the volume.
**Formula:** `Current DB size + Backup + VACUUM rebuild copy (~1.2 GB) + Margin (~10 GB)`.
For example, if the DB is currently 14 GB: `14 (db) + 14 (backup) + 1.2 (vacuum) + 10 (margin) = 39.2 GB required`.

Run this command to check free space on the volume:
```bash
df -h .
```
Ensure the "Avail" column shows greater than the required threshold. If it does not, **ABORT**.

## 2. Execution

### 2.1. Confirm Journal Mode
We assume WAL mode for these operations. Confirm the database is in WAL mode:
```bash
sqlite3 rebalance.db "PRAGMA journal_mode;"
```
*(Expect output: `wal`. If it is not, the checkpoint commands below will fail).*

### 2.2. Batched Delete
A single monolithic delete transaction will hold the writer lock for too long and inflate the WAL unboundedly. We perform deletes in batches of 50,000 using `NOT EXISTS` (which correctly handles missing or NULL `doc_id`s compared to `NOT IN`).

Create a file `reclaim_batch.sh` with the following contents:

```bash
#!/bin/bash
BATCH_SIZE=50000
TOTAL_ORPHANS=$(sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);")
echo "Starting to delete $TOTAL_ORPHANS orphaned vectors in batches of $BATCH_SIZE..."

DELETED=0
while [ $DELETED -lt $TOTAL_ORPHANS ]; do
  sqlite3 rebalance.db <<EOF
BEGIN IMMEDIATE;
DELETE FROM vec0 WHERE rowid IN (
    SELECT rowid FROM vec0
    WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id)
    LIMIT $BATCH_SIZE
);
COMMIT;
PRAGMA wal_checkpoint(TRUNCATE);
EOF
  
  if [ $? -ne 0 ]; then
    echo "ERROR: Batch failed at $DELETED. Aborting."
    exit 1
  fi

  DELETED=$((DELETED + BATCH_SIZE))
  echo "Deleted $DELETED / $TOTAL_ORPHANS"
  sleep 1
done
echo "Batched deletion complete."
```

Run the script:
```bash
chmod +x reclaim_batch.sh
./reclaim_batch.sh
```

### 2.3. VACUUM INTO
The database needs to be compacted to reclaim the disk space. We recommend `VACUUM INTO` followed by an atomic swap. This is safer than a direct `VACUUM` because it rebuilds the database into a new file without modifying the original in-place, offering a much safer abort path. Note: this requires exclusive access; no concurrent reader (including `doctor`) can run during the swap.

Run the VACUUM INTO command (this will take time):
```bash
sqlite3 rebalance.db "VACUUM INTO 'rebalance_compact.db';"
```

Perform the atomic swap:
```bash
mv rebalance.db rebalance_old.db
mv rebalance_compact.db rebalance.db
```

## 3. Abort and Resume

If the procedure encounters issues, follow these rules:

### Abort Conditions
- **Unexpected orphan count at start**: The orphan count does not match the baseline or has changed unexpectedly.
- **`integrity_check` not `ok`**: The database fails its integrity check at any point.
- **Disk headroom below threshold**: Disk space falls below the calculated safety margin.
- **Any writer still live**: The fence script fails or a writer process is detected.
- **Batch error**: Any batch delete command returns an error.

### Resume vs. Restore
- **Resumable (Batched Deletes)**: If the batched deletion script is interrupted, it is safe to just re-run it. Each committed batch is durable, and the query naturally picks up where it left off.
- **Not Resumable (VACUUM)**: If `VACUUM INTO` is interrupted, the output file (`rebalance_compact.db`) is corrupt and unusable. Simply delete the partial `rebalance_compact.db` file and restart the `VACUUM INTO` step.
- **Restore Required**: If live vectors are inadvertently deleted or a catastrophic corruption occurs during the swap, you must execute a full restore.

### Executing a Restore
If a restore is forced, stop all processes and run:
```bash
# Move the damaged DB out of the way
mv rebalance.db rebalance_bad.db
# Restore from the pre-flight backup
sqlite3 rebalance.db ".restore 'rebalance.db.backup'"
# Verify the restore
sqlite3 rebalance.db "PRAGMA integrity_check;"
```

## 4. Post-checks

All post-checks must pass before unfencing writers.

### [ ] 4.1. Integrity Check
```bash
sqlite3 rebalance.db "PRAGMA integrity_check;"
```
*(Expect output: `ok`)*

### [ ] 4.2. Orphan Count is 0
```bash
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```
*(Expect output: `0`)*

### [ ] 4.3. Live Vector Count Unchanged
```bash
sqlite3 rebalance.db "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM knowledge WHERE knowledge.id = vec0.doc_id);"
```
*(Expect output: Exactly the same as the pre-flight measurement)*

### [ ] 4.4. Database Size Reduced
```bash
ls -lh rebalance.db
```
*(Expect output: Size is near the predicted ~1.2 GB)*

### [ ] 4.5. Rebalance Doctor is Clean
Run the doctor with p2 checks:
```bash
rebalance doctor
```
*(Expect output: Clean output, no issues reported)*

### [ ] 4.6. Unfence Writers and Verify Sync
Once all checks pass:
1. Restore the launchd schedules (unfence).
2. Wait for or trigger the next `github_sync`.
3. Confirm the sync completes normally.

## 5. Rollback

If something has gone critically wrong under time pressure and you need to abort the maintenance window quickly:

**1. Halt Execution:**
Press `Ctrl+C` in the terminal to stop any running scripts or `VACUUM`.

**2. Ensure writers are still fenced:**
```bash
./utils/gh250/fence-writers.sh
```

**3. Move the bad database files completely out of the way:**
```bash
mv rebalance.db rebalance_failed.db
rm -f rebalance.db-wal rebalance.db-shm
```

**4. Execute Restore from the pre-flight backup:**
```bash
sqlite3 rebalance.db ".restore 'rebalance.db.backup'"
```

**5. Verify the restored DB:**
```bash
sqlite3 rebalance.db "PRAGMA integrity_check;"
```

**6. Unfence Writers:**
Restore the launchd schedules.

*(Optional)* If space is critical, you may delete the failed database:
```bash
rm rebalance_failed.db
```
