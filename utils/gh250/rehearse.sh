#!/bin/bash
set -euo pipefail

DB_FILE="rebalance.db"
RUN_ID=$(date +%s)_$$
SCRATCH_DIR=$(mktemp -d -t rehearse_$RUN_ID.XXXXXX)
COPY_FILE="$SCRATCH_DIR/rebalance.rehearsal.db"
REPORT_DIR="PROJECT/2-WORKING/GH-250-VECTOR-BLOAT"
REPORT_FILE="$REPORT_DIR/REHEARSAL-REPORT.md"

# Cleanup function
cleanup() {
    echo "Cleaning up rehearsal copy..."
    rm -rf "$SCRATCH_DIR"
}
trap cleanup EXIT

echo "--- Rehearsal Started ---"
if [[ ! -f "$DB_FILE" ]]; then
    echo "ERROR: $DB_FILE not found."
    exit 1
fi

mkdir -p "$REPORT_DIR"

DB_SIZE_BYTES=$(stat -f %z "$DB_FILE")
FREE_SPACE_BYTES=$(df -k . | awk 'NR==2 {print $4 * 1024}')
REQUIRED_SPACE=$(( DB_SIZE_BYTES * 3 + 10*1024*1024*1024 )) # Source + backup + vacuum target + 10GB margin

if (( FREE_SPACE_BYTES < REQUIRED_SPACE )); then
    echo "ERROR: Insufficient disk space. Need $REQUIRED_SPACE bytes, have $FREE_SPACE_BYTES bytes."
    exit 1
fi

echo "Disk space check passed. Required: $REQUIRED_SPACE, Available: $FREE_SPACE_BYTES"

echo "Copying $DB_FILE to $COPY_FILE via SQLite backup..."
sqlite3 "$DB_FILE" ".backup '$COPY_FILE'"

echo "Gathering before metrics..."
BEFORE_SIZE=$(stat -f %z "$COPY_FILE")
BEFORE_TOTAL=$(sqlite3 "$COPY_FILE" "SELECT count(*) FROM vec0;")
BEFORE_ORPHANS=$(sqlite3 "$COPY_FILE" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);")
BEFORE_LIVE=$(sqlite3 "$COPY_FILE" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);")

echo "Running reclaim.py on rehearsal copy..."
START_TIME=$(date +%s)
# Note: we need to run reclaim in a way that we can observe peak WAL size.
# We'll run reclaim in background and monitor WAL size.

PYTHONPATH="$PWD/src" "${GH250_PY:-python3}" utils/gh250/reclaim.py --database "$COPY_FILE" --execute &
RECLAIM_PID=$!

PEAK_WAL=0
while kill -0 $RECLAIM_PID 2>/dev/null; do
    if [[ -f "$COPY_FILE-wal" ]]; then
        WAL_SIZE=$(stat -f %z "$COPY_FILE-wal")
        if (( WAL_SIZE > PEAK_WAL )); then
            PEAK_WAL=$WAL_SIZE
        fi
    fi
    sleep 0.1
done

wait $RECLAIM_PID || { echo "ERROR: reclaim.py failed"; exit 1; }

END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))

echo "Reclaim finished. Gathering after metrics..."

AFTER_SIZE=$(stat -f %z "$COPY_FILE")
AFTER_TOTAL=$(sqlite3 "$COPY_FILE" "SELECT count(*) FROM vec0;")
AFTER_ORPHANS=$(sqlite3 "$COPY_FILE" "SELECT count(*) FROM vec0 WHERE NOT EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);")
AFTER_LIVE=$(sqlite3 "$COPY_FILE" "SELECT count(*) FROM vec0 WHERE EXISTS (SELECT 1 FROM items WHERE items.id = vec0.doc_id);")
INTEGRITY=$(sqlite3 "$COPY_FILE" "PRAGMA integrity_check;")

if [[ "$INTEGRITY" != "ok" ]]; then
    echo "ERROR: Integrity check failed! Result: $INTEGRITY"
    exit 1
fi

if [[ "$AFTER_LIVE" != "$BEFORE_LIVE" ]]; then
    echo "ERROR: Live vectors changed! Before: $BEFORE_LIVE, After: $AFTER_LIVE"
    exit 1
fi

if [[ "$AFTER_ORPHANS" != "0" ]]; then
    echo "ERROR: Orphans not fully deleted! Remaining: $AFTER_ORPHANS"
    exit 1
fi

RECLAIMED_BYTES=$(( BEFORE_SIZE - AFTER_SIZE ))

echo "--- Rehearsal Report ---" | tee "$REPORT_FILE"
echo "Bytes Reclaimed: $RECLAIMED_BYTES" | tee -a "$REPORT_FILE"
echo "Live Vectors Before: $BEFORE_LIVE" | tee -a "$REPORT_FILE"
echo "Live Vectors After: $AFTER_LIVE" | tee -a "$REPORT_FILE"
echo "Orphans Remaining: $AFTER_ORPHANS" | tee -a "$REPORT_FILE"
echo "Integrity Check: $INTEGRITY" | tee -a "$REPORT_FILE"
echo "Wall-clock Elapsed: ${ELAPSED}s" | tee -a "$REPORT_FILE"
echo "Peak WAL Size: $PEAK_WAL bytes" | tee -a "$REPORT_FILE"

echo "Rehearsal successful. See $REPORT_FILE for details."
