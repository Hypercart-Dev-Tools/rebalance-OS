# rebalance.db vector-bloat reclaim runbook (GH-250 R2)

Reclaims ~10.2 GB from `rebalance.db` by deleting orphaned `github_embeddings` vectors and rebuilding
the file. One operator, one maintenance window, start to finish.

> ## Status — EXECUTED 2026-08-14. Reclaim complete; read the lessons before reusing this.
>
> **Result:** 2,678,350 orphaned vectors deleted, database 14.62 GB → 3.81 GB (~10.8 GB reclaimed),
> `integrity_check=ok`, live vectors **32,908 before and after** — the assertion that proves only
> garbage was deleted. `doctor` now reports OK on both orphan invariants (github and semantic).
> Record: `temp/logs/gh250-reclaim-20260815T050240Z.log`.
>
> **R1 was WAIVED by the operator**, not passed: one post-sync sample rather than three, for wall
> clock. The supporting evidence was that the orphan count read 2,678,350 on four measurements
> spanning 1h40m and two completed syncs, sat at +36 over 9 days against a pre-fix rate of
> ~15,500/sync, and no orphan existed in the top ~145,000 document ids where a live fresh-id leak
> would necessarily deposit them. The waiver is recorded in the run log, not silent.
>
> **Four safety mechanisms in this procedure were found broken when it was finally run for real.**
> Each passed every prior review and rehearsal, because rehearsals exercised the happy path against
> fixtures rather than the live fleet:
>
> 1. **§1.5's fence checked the wrong file.** `fence-writers.sh` defaults `REBALANCE_DB` to the repo
>    root and this runbook never exported it; a stale 491 KB `rebalance.db` from June sat there, so
>    `verify` locked *that* and reported the store fenced while the real one had live writers.
>    Fixed: §0 now exports `REBALANCE_DB` and `PYTHON_CMD`.
> 2. **The fence roster covered 5 of 11 loaded jobs.** It fails closed, so this did not leak writers
>    through — it made the fence unsatisfiable. Fixed in `fence-writers.sh`.
> 3. **`verify`'s pause assertion is wrong.** It requires `three_eyes why` to print
>    "OPEN/quarantined"; a paused job prints "breaker: closed" plus "reason: paused via CLI", so
>    every correctly-paused job reads as NOT paused.
> 4. **`three_eyes pause` does not stop launchd firing the job.** This is the one that cost a run:
>    ten jobs were paused at 21:08, and `pulse-web-sync` fired anyway at ~21:45 and attached to the
>    database, failing the post-batch checkpoint at batch 94 of 268 (`(1, 10086, 10086)`). **Only
>    `launchctl bootout` genuinely quiesces a job.** Do not trust pause for a destructive window.
>
> **Resuming is not the same run.** The abort left ~940k vectors already deleted, whose pages sit in
> the freelist and are also released by `VACUUM`. §1.4's formula counts only *remaining* orphans, so
> on a resume it understates the reclaim and puts the true final size BELOW `EXPECT_MIN` — §4 then
> fails a perfectly good rebuild and sends the operator to roll it back. A resume must add
> `freelist_count * page_size` to `EXPECT_RECLAIM`.
>
> Retained artifacts: `rebalance.db.pre-reclaim-20260815T050240Z` and the verified
> `rebalance.db.backup-20260815T050240Z`. Remove them deliberately, by name, once a full sync has
> completed cleanly and `doctor` still reports 0 orphans.

**This runbook does not implement the reclaim.** Two tested scripts do:

| Script | Tests | Role |
|---|---|---|
| `utils/gh250/fence-writers.sh` | `tests/test_gh250_fencing.py` (9) | stop / verify / restore every db writer |
| `utils/gh250/reclaim.py` | `tests/test_gh250_reclaim.py` (13) | measure, batch-delete, checkpoint, `VACUUM INTO`, integrity-check |

Earlier drafts reimplemented the delete loop and the vacuum in inline shell. That version was
untested, and its queries named `vec0` / `items` — sqlite-vec's *documentation example* tables — so
its very first command failed with `no such table: vec0`. Everything operational below now goes
through the scripts. Where raw SQL appears it is a **read-only** check.

## Conventions used throughout

- Every gate is a real shell conditional that **exits non-zero**. There are no "run this and look at
  it" steps.
- Every gate's output is appended to `$RECORD` via `tee`. If a step's evidence is not in the record,
  the step did not happen.
- No unguarded `rm` or `mv`. Every destructive move checks its source *and* its destination first,
  and accounts for the `-wal` / `-shm` sidecars.
- Run everything from one shell so the exported vars and `$RECORD` persist.

---

## 0. Session setup

```bash
set -uo pipefail          # NOT -e: the gates below handle their own failures explicitly

export REPO="$HOME/Documents/rebalance-OS"
export PY="$REPO/.venv/bin/python"
export DB="$HOME/Library/Application Support/rebalance-os/rebalance.db"
export FENCE="$REPO/utils/gh250/fence-writers.sh"
export RECLAIM="$REPO/utils/gh250/reclaim.py"
export STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
export RECORD="$REPO/temp/logs/gh250-reclaim-$STAMP.log"
export VACUUM_TARGET="${DB%.db}.vacuum.db"        # what reclaim.py writes
export BACKUP="$DB.backup-$STAMP"                 # unique per run; never reused
export PRE="$DB.pre-reclaim-$STAMP"               # retained original after cutover

# fence-writers.sh defaults REBALANCE_DB to "$REPO_ROOT/rebalance.db" and PYTHON_CMD to bare
# `python`. Both defaults are wrong here and the first one is DANGEROUS: a stale 491 KB
# rebalance.db from 2026-06-26 is sitting at the repo root, so an un-exported `verify` would run
# its lsof and BEGIN EXCLUSIVE gates against THAT file and pass while the real 15.7 GiB database
# still had live writers. Export both, and treat these as part of the fence contract.
export REBALANCE_DB="$DB"
export PYTHON_CMD="$PY"

mkdir -p "$(dirname "$RECORD")"
{ echo "=== GH-250 reclaim $STAMP ==="; echo "db=$DB"; } | tee -a "$RECORD"

for f in "$PY" "$FENCE" "$RECLAIM" "$DB"; do
  if [ ! -e "$f" ]; then echo "ABORT: missing $f" | tee -a "$RECORD"; exit 1; fi
done
echo "setup OK" | tee -a "$RECORD"
```

Reusable read-only probes. **These are split on purpose:** on this database `count(*)` is ~0.9s and
the orphan predicate ~1.6s, but `PRAGMA integrity_check` is **~34s** because it scans the whole
13.5 GB file. Keeping integrity out of the cheap probe is what makes the R1 sampling loop and the
post-checks practical — an earlier draft folded them together and a four-call verification pass took
over two minutes.

```bash
db_counts() {   # prints  total|orphans|live      (~2.5s)
  "$PY" - <<'PYEOF'
import os, sqlite3, sqlite_vec
db = os.environ["DB"]
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
c.enable_load_extension(True); sqlite_vec.load(c); c.enable_load_extension(False)
tot = c.execute("SELECT count(*) FROM github_embeddings").fetchone()[0]
orp = c.execute("""SELECT count(*) FROM github_embeddings WHERE NOT EXISTS
    (SELECT 1 FROM github_documents d WHERE d.id = github_embeddings.doc_id)""").fetchone()[0]
print(f"{tot}|{orp}|{tot-orp}")
PYEOF
}

integrity() {   # prints  ok  (or the first error)   (~34s — call deliberately, not in a loop)
  "$PY" - <<'PYEOF'
import os, sqlite3
db = os.environ["DB"]
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=300)
print(c.execute("PRAGMA integrity_check").fetchone()[0])
PYEOF
}

orphan_count() { db_counts | cut -d'|' -f2; }
```

`integrity()` is called exactly three times in this runbook: once on the restored backup (§1.6), once
after the reclaim (§4), and once after a rollback (§5). Nowhere else.

---

## 1. Preconditions

### 1.1 R1 — orphan growth must be flat

The writer fix (#249 plus the vb1 idempotence work) must be confirmed live **before** reclaiming.
Reclaiming first lets the next sync re-orphan the work.

Take three samples, each immediately after a **completed** `github_sync`, and require them to be
**identical** — not merely non-increasing.

```bash
# Repeat this once after each of three completed syncs. Confirm completion first:
SYNC_LOG="$REPO/temp/logs/github_sync_$(date +%F).log"
DONE=$(grep -c "sync complete" "$SYNC_LOG" 2>/dev/null || echo 0)
S=$(orphan_count)
echo "orphan sample: $S (completed syncs today: $DONE)" | tee -a "$RECORD"
```

Then gate on the three recorded values:

```bash
# Fill in the three sampled values. Left empty, the gate below ABORTS — it must not be
# possible to pass R1 by forgetting to record the samples.
export S1= S2= S3=

if [ -z "$S1" ] || [ -z "$S2" ] || [ -z "$S3" ]; then
  echo "ABORT R1: S1/S2/S3 are not all set — record three post-sync samples first." | tee -a "$RECORD"
  exit 1
fi
if [ "$S1" != "$S2" ] || [ "$S2" != "$S3" ]; then
  echo "ABORT R1: orphan count not flat ($S1/$S2/$S3) — the writer fix is not holding." | tee -a "$RECORD"
  exit 1
fi
export BASELINE_ORPHANS="$S3"
echo "R1 PASS: orphans flat at $BASELINE_ORPHANS" | tee -a "$RECORD"
```

### 1.2 Baseline — from the tested measurement path

`reclaim.py`'s dry run is the baseline. It uses the same predicate the delete uses, so the numbers
cannot disagree with what §2 will do.

```bash
if ! "$PY" "$RECLAIM" --database "$DB" --i-know-this-is-production 2>&1 | tee -a "$RECORD"; then
  echo "ABORT: baseline dry-run failed" | tee -a "$RECORD"; exit 1
fi

BASE=$(db_counts); echo "baseline counts: $BASE" | tee -a "$RECORD"
IFS='|' read -r BASELINE_TOTAL B_ORP BASELINE_LIVE <<<"$BASE"
export BASELINE_TOTAL BASELINE_LIVE
export BASELINE_BYTES=$(stat -f%z "$DB")
if [ "$B_ORP" != "$BASELINE_ORPHANS" ]; then
  echo "ABORT: orphan count moved between R1 ($BASELINE_ORPHANS) and baseline ($B_ORP)" | tee -a "$RECORD"
  exit 1
fi
echo "baseline: total=$BASELINE_TOTAL live=$BASELINE_LIVE orphans=$BASELINE_ORPHANS bytes=$BASELINE_BYTES" | tee -a "$RECORD"
```

### 1.3 Disk headroom — computed, not eyeballed

Peak concurrent usage is the live db **plus** a full backup **plus** the vacuum rebuild: all three
exist at once before cutover. Require that, plus 20%.

```bash
NEED=$(( BASELINE_BYTES * 3 * 12 / 10 ))
AVAIL=$(( $(df -k "$(dirname "$DB")" | awk 'NR==2{print $4}') * 1024 ))
printf 'headroom: need %s bytes (3x db + 20%%), have %s\n' "$NEED" "$AVAIL" | tee -a "$RECORD"
if [ "$AVAIL" -lt "$NEED" ]; then
  echo "ABORT: insufficient free space" | tee -a "$RECORD"; exit 1
fi
```

### 1.4 Expected end state — recomputable, not "~1.2 GB"

Derive the target range from the measured baseline, so §4's size check is a real assertion rather
than a number someone remembered:

```bash
# 1024-dim float32 = 4096 bytes per vector; reclaimed bytes ~= orphans * 4096.
export EXPECT_RECLAIM=$(( BASELINE_ORPHANS * 4096 ))
export EXPECT_MAX=$(( BASELINE_BYTES - EXPECT_RECLAIM * 90 / 100 ))    # at least 90% recovered
export EXPECT_MIN=$(( (BASELINE_BYTES - EXPECT_RECLAIM) * 70 / 100 ))  # allow extra vacuum gain
printf 'expect final size between %s and %s bytes\n' "$EXPECT_MIN" "$EXPECT_MAX" | tee -a "$RECORD"
```

### 1.4a Journal mode must be WAL

Everything below assumes WAL: the checkpoint gates in §1.6 and inside `reclaim.py` are meaningless in
`delete` or `truncate` mode, and would pass vacuously. Verify, do not assume.

```bash
JM=$("$PY" -c "
import os,sqlite3
db=os.environ['DB']
c=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
print(c.execute('PRAGMA journal_mode').fetchone()[0])")
echo "journal_mode: $JM" | tee -a "$RECORD"
if [ "$JM" != "wal" ]; then
  echo "ABORT: journal_mode is '$JM', not 'wal' — the checkpoint gates below would pass vacuously." | tee -a "$RECORD"
  exit 1
fi
```

Measured on this database 2026-08-05: `wal`.

### 1.5 Fence every writer

```bash
if ! "$FENCE" fence 2>&1 | tee -a "$RECORD"; then
  echo "ABORT: fence failed" | tee -a "$RECORD"; exit 1
fi
if ! "$FENCE" verify 2>&1 | tee -a "$RECORD"; then
  echo "ABORT: fence verify failed — a writer is still live" | tee -a "$RECORD"
  "$FENCE" unfence 2>&1 | tee -a "$RECORD"; exit 1
fi
echo "FENCED" | tee -a "$RECORD"
```

`fence` records pre-fence state and restores exactly that on `unfence`, leaving jobs you had already
paused untouched. **From here until §4.1, every abort path must call `"$FENCE" unfence`.**

### 1.6 Backup, then rehearse the restore

A backup nobody has restored from is a hope, not a rollback.

```bash
if [ -e "$BACKUP" ]; then echo "ABORT: $BACKUP exists" | tee -a "$RECORD"; exit 1; fi

CP=$("$PY" -c "
import os,sqlite3
c=sqlite3.connect(os.environ['DB'],timeout=60)
print('|'.join(str(x) for x in c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()))")
echo "pre-backup checkpoint: $CP" | tee -a "$RECORD"
if [ "$CP" != "0|0|0" ]; then
  echo "ABORT: checkpoint not 0|0|0 — a reader/writer holds the db" | tee -a "$RECORD"
  "$FENCE" unfence | tee -a "$RECORD"; exit 1
fi

if ! "$PY" -c "
import os,sqlite3
s=sqlite3.connect(os.environ['DB']); d=sqlite3.connect(os.environ['BACKUP'])
s.backup(d); d.close(); s.close()" 2>&1 | tee -a "$RECORD"; then
  echo "ABORT: backup failed" | tee -a "$RECORD"; "$FENCE" unfence | tee -a "$RECORD"; exit 1
fi

export REHEARSE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/gh250-restore-XXXXXX")
cp "$BACKUP" "$REHEARSE_DIR/restored.db"
R_OK=$(DB="$REHEARSE_DIR/restored.db" integrity)
RESULT=$(DB="$REHEARSE_DIR/restored.db" db_counts)
echo "restore rehearsal: integrity=$R_OK counts=$RESULT" | tee -a "$RECORD"
if [ "$R_OK" != "ok" ] || [ "$RESULT" != "$BASELINE_TOTAL|$BASELINE_ORPHANS|$BASELINE_LIVE" ]; then
  echo "ABORT: restored backup does not match baseline — the backup is not trustworthy" | tee -a "$RECORD"
  "$FENCE" unfence | tee -a "$RECORD"; exit 1
fi
echo "BACKUP VERIFIED: $BACKUP (rehearsal dir kept at $REHEARSE_DIR)" | tee -a "$RECORD"
```

Remove `$REHEARSE_DIR` yourself after reviewing it. This runbook does not delete it — an automatic
`rm -rf` on a path built from a variable is exactly the step that goes wrong at 2am.

---

## 2. Execution

`reclaim.py --execute` performs the whole mutation: batched deletes, a `wal_checkpoint(TRUNCATE)`
before *and* after every batch (failing unless the busy column is `0`), per-batch progress,
`VACUUM INTO`, `PRAGMA integrity_check`, and a final assertion that the **live** vector count is
unchanged. It exits non-zero on any of those, and it deliberately does **not** move the rebuilt file.

```bash
if [ -e "$VACUUM_TARGET" ]; then
  echo "ABORT: $VACUUM_TARGET already exists — inspect and move it aside" | tee -a "$RECORD"
  "$FENCE" unfence | tee -a "$RECORD"; exit 1
fi
if ! "$FENCE" verify 2>&1 | tee -a "$RECORD"; then
  echo "ABORT: writers came back before execution" | tee -a "$RECORD"
  "$FENCE" unfence | tee -a "$RECORD"; exit 1
fi

"$PY" "$RECLAIM" --database "$DB" --i-know-this-is-production --execute --batch-size 10000 2>&1 | tee -a "$RECORD"
RC=${PIPESTATUS[0]}
echo "reclaim exit: $RC" | tee -a "$RECORD"
if [ "$RC" -ne 0 ]; then
  echo "ABORT: reclaim failed — see §3" | tee -a "$RECORD"
  "$FENCE" unfence | tee -a "$RECORD"; exit 1
fi
```

### 2.1 Cutover — guarded, sidecar-aware

**The first rename is atomic; the two-rename cutover as a whole is not** — there is a window where
the original has been moved aside and the replacement is not yet in place. That is why the original is
*retained*, never deleted here.

```bash
if ! "$FENCE" verify 2>&1 | tee -a "$RECORD"; then
  echo "ABORT: writer live at cutover" | tee -a "$RECORD"; "$FENCE" unfence | tee -a "$RECORD"; exit 1
fi
if [ ! -f "$VACUUM_TARGET" ]; then
  echo "ABORT: no rebuilt file at $VACUUM_TARGET" | tee -a "$RECORD"; exit 1
fi
for s in -wal -shm; do
  if [ -e "$VACUUM_TARGET$s" ]; then
    echo "ABORT: unexpected sidecar $VACUUM_TARGET$s — rebuild not quiesced" | tee -a "$RECORD"; exit 1
  fi
done
if [ -e "$PRE" ]; then echo "ABORT: $PRE exists" | tee -a "$RECORD"; exit 1; fi

# Step 1 — move the original aside (retained).
if ! mv "$DB" "$PRE"; then
  echo "ABORT: could not move original aside" | tee -a "$RECORD"
  "$FENCE" unfence | tee -a "$RECORD"; exit 1
fi
for s in -wal -shm; do [ -f "$DB$s" ] && mv "$DB$s" "$PRE$s"; done

# Step 2 — put the rebuilt file in place. On failure, roll step 1 straight back.
if ! mv "$VACUUM_TARGET" "$DB"; then
  echo "CUTOVER FAILED mid-swap — restoring the original" | tee -a "$RECORD"
  mv "$PRE" "$DB"
  for s in -wal -shm; do [ -f "$PRE$s" ] && mv "$PRE$s" "$DB$s"; done
  "$FENCE" unfence | tee -a "$RECORD"; exit 1
fi
echo "CUTOVER OK — original retained at $PRE" | tee -a "$RECORD"
```

---

## 3. Abort and resume

| Failure | Resumable? | Action |
|---|---|---|
| A batch errored mid-run | **Yes** | Every batch commits durably. Re-run §1.5 fence verify, then re-run §2 — it picks up the remaining orphans. |
| Checkpoint not `0\|0\|0` | Yes | A reader holds the db. Find it via `"$FENCE" verify`, then re-run §2. |
| `VACUUM INTO` failed | **No** | The partial `$VACUUM_TARGET` is not a database. Inspect it, `mv` it to a unique name (never `rm` blind), then re-run §2. |
| Cutover failed mid-swap | Handled inline | §2.1 restores the original automatically. Confirm with §4, then investigate. |
| Post-checks failed | — | §5 rollback. Do not unfence first. |

Never resume without re-running §1.5's fence verify. A resume against a live writer is worse than a
restart.

---

## 4. Post-checks — all must pass before unfencing

```bash
F_OK=$(integrity)
FINAL=$(db_counts); echo "final: integrity=$F_OK counts=$FINAL" | tee -a "$RECORD"
IFS='|' read -r F_TOTAL F_ORPHANS F_LIVE <<<"$FINAL"
F_BYTES=$(stat -f%z "$DB")

FAIL=0
[ "$F_OK" = "ok" ]                 || { echo "FAIL integrity_check=$F_OK" | tee -a "$RECORD"; FAIL=1; }
[ "$F_ORPHANS" -eq 0 ]             || { echo "FAIL orphans=$F_ORPHANS" | tee -a "$RECORD"; FAIL=1; }
[ "$F_LIVE" -eq "$BASELINE_LIVE" ] || { echo "FAIL live changed $BASELINE_LIVE -> $F_LIVE (OVER-DELETION)" | tee -a "$RECORD"; FAIL=1; }
if [ "$F_BYTES" -gt "$EXPECT_MAX" ] || [ "$F_BYTES" -lt "$EXPECT_MIN" ]; then
  echo "FAIL size $F_BYTES outside expected $EXPECT_MIN..$EXPECT_MAX" | tee -a "$RECORD"; FAIL=1
fi
if [ "$FAIL" -ne 0 ]; then
  echo "POST-CHECKS FAILED — do NOT unfence. Go to §5." | tee -a "$RECORD"; exit 1
fi
echo "POST-CHECKS PASS: live=$F_LIVE orphans=0 bytes=$F_BYTES" | tee -a "$RECORD"
```

**Live count unchanged** is the check that proves only garbage was deleted. Bytes reclaimed only
proves the delete did something.

### 4.1 Unfence, then confirm a real sync

```bash
if ! "$FENCE" unfence 2>&1 | tee -a "$RECORD"; then
  echo "WARNING: unfence reported failure — resolve before leaving" | tee -a "$RECORD"; exit 1
fi
"$REPO/.venv/bin/rebalance" doctor 2>&1 | tee -a "$RECORD"
```

`doctor`'s `orphaned vectors:github` check must now read **0**. It failed at 2,678,314 before this
runbook ran; that flip is the outcome.

Then wait for the next scheduled `github_sync` and confirm it completed:

```bash
grep -c "sync complete" "$REPO/temp/logs/github_sync_$(date +%F).log" | tee -a "$RECORD"
```

Once one full sync has completed cleanly and `doctor` still reports 0 orphans, remove `$PRE` and
`$BACKUP` **deliberately, by name, after checking each exists**. Not before.

---

## 5. Rollback

Restores the pre-reclaim database. Preserves every artifact — nothing is deleted.

```bash
"$FENCE" fence 2>&1 | tee -a "$RECORD"
if ! "$FENCE" verify 2>&1 | tee -a "$RECORD"; then
  echo "ABORT ROLLBACK: writers live" | tee -a "$RECORD"; exit 1
fi

# Move the bad current file aside under a unique name — never delete it.
BAD="$DB.failed-$STAMP"
if [ -f "$DB" ] && [ ! -e "$BAD" ]; then
  mv "$DB" "$BAD"
  for s in -wal -shm; do [ -f "$DB$s" ] && mv "$DB$s" "$BAD$s"; done
  echo "moved failed db to $BAD" | tee -a "$RECORD"
fi

# Prefer the retained original; fall back to the verified backup.
if [ -f "$PRE" ]; then
  mv "$PRE" "$DB"
  for s in -wal -shm; do [ -f "$PRE$s" ] && mv "$PRE$s" "$DB$s"; done
  echo "restored from retained original $PRE" | tee -a "$RECORD"
elif [ -f "$BACKUP" ]; then
  cp "$BACKUP" "$DB"
  echo "restored from backup $BACKUP" | tee -a "$RECORD"
else
  echo "FATAL: neither $PRE nor $BACKUP exists — stop and escalate" | tee -a "$RECORD"; exit 1
fi

C_OK=$(integrity); CHECK=$(db_counts)
echo "rollback verify: integrity=$C_OK counts=$CHECK (baseline $BASELINE_TOTAL|$BASELINE_ORPHANS|$BASELINE_LIVE)" | tee -a "$RECORD"
if [ "$C_OK" != "ok" ] || [ "$CHECK" != "$BASELINE_TOTAL|$BASELINE_ORPHANS|$BASELINE_LIVE" ]; then
  echo "FATAL: restored db does not match baseline — do NOT unfence, escalate" | tee -a "$RECORD"; exit 1
fi
"$FENCE" unfence 2>&1 | tee -a "$RECORD"
echo "ROLLBACK COMPLETE — artifacts kept: $BAD, $BACKUP" | tee -a "$RECORD"
```

---

## Appendix — what this reclaims and why

Measured 2026-08-05 on `noels-Mac-Studio`:

| | |
|---|---|
| `rebalance.db` | 13.53 GB |
| `github_embeddings` share | 92.2% (12,742 MB) |
| total vectors | 2,712,534 |
| **orphaned** (no live document) | **2,678,314 (98.7%)** |
| live vectors | 34,220 |
| expected reclaim | **~10.2 GB** = 10,970,374,144 B (2,678,314 x 4096) |
| expected final size | **~3.3 GB** (13.54 − 10.22); §1.4's computed gate range is 2.4–4.4 GB |

All sizes here are **GiB**, matching what `stat` and `df` report. 2,678,314 x 4096 B is
10,970,374,144 B — 10.22 GiB, or 10.97 GB decimal. An earlier revision of this appendix quoted the
decimal figure while every other number was binary; they are the same bytes.

The expected final size is **~3.3 GiB**, not the ~1.2 GB quoted in early GH-250 analysis (which
assumed only ~26k live vectors; the live count is 34,220 and the file has grown) and not the ~2.5 GB
an intermediate revision claimed. §1.4 recomputes the range at run time from the measured baseline,
so the gate never depends on any figure written here staying true.

Root cause was `sync_direct_commit_documents()` deleting `direct_commit` documents and re-inserting
them with fresh autoincrement ids while never pruning their vectors — fixed in #249 and made
idempotent in vb1. `doctor` gained a hard zero-orphan invariant in vb2, so a recurrence is visible in
hours rather than after 10 GB.

The semantic family also carries 302 orphans (`doctor` reports them). That is a separate, much smaller
leak and is **out of scope here** — this runbook touches `github_embeddings` only.
