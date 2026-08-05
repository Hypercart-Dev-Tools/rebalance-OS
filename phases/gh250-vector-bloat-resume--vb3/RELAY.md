# Marathon Phase vb3
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-VB3-TURN builder=agy reviewer=codex round-cap=5 -->

## Phase Brief

# p3 — R2: author the reclaim runbook

> ## ⚠️ Sandbox constraint — do NOT run the full test suite in your turn
>
> Verified 2026-08-04: MLX cannot enumerate a Metal device inside the codex/agy turn sandbox
> (`-s workspace-write`). Any test that performs an MLX device operation **hard-crashes the whole
> Python process with SIGABRT** — `mlx::core::metal::Device::Device()` indexes an empty device
> array, throws an ObjC exception, and aborts. This is NOT catchable: `tests/conftest.py` guards
> only `ImportError`, and an abort bypasses `try/except` entirely. Three crashes in ~4 minutes were
> traced to exactly this (parent process `codex`).
>
> MLX works fine outside the sandbox on this machine (M1 Max, Metal 3), so this is a turn-sandbox
> limitation, not a broken repo.
>
> **Run only this** (the interpreter matters — see below):
> ```
> PYTHONPATH="$PWD/src" /Users/noelsaw/Documents/rebalance-OS/.venv/bin/python -m pytest \\
>   tests/test_github_direct_commits.py tests/test_db_github.py \\
>   tests/test_github_knowledge.py tests/test_github_coverage.py -q
> ```
> Verified clean (33 passed). Add the specific new test file for your phase.
>
> **Why not plain `python`:** your isolated worktree has NO virtualenv — `.venv/` is gitignored,
> so it does not exist there and bare `python` either is not found or cannot import `rebalance`.
> Use the absolute interpreter above. **Do not go looking for a working environment in the real
> repo root** — that is an isolation breach and the shim will fail your turn (it already did once).
>
> **Why `PYTHONPATH="$PWD/src"`:** that venv has rebalance installed *editable*, pointing at the
> MAIN repo's `src/`. Without PYTHONPATH your edits in the worktree are not what gets imported, so
> you would be testing the wrong code and a green run would mean nothing.
>
> Never `pytest tests/` — it collects the MLX suite. As of GH-250 those tests skip cleanly via the
> `requires_metal` marker rather than aborting, but the full suite is still slow and carries
> unrelated pre-existing failures (5 order-dependent in test_hiqs_pipeline.py, 1 in
> test_scheduler_liveness.py). Stick to the scoped command.

> ## ⚠️ No scratch files anywhere in the repo
>
> Your turn is confined to the artifact allowlist, and that includes **file CREATION**, not just
> edits. A throwaway like `query_test.py` at the repo root fails the whole turn — this already
> happened once (`agy-turn: OFF-ALLOWLIST change: query_test.py — reverting`).
>
> If you need to try a query or a snippet, run it inline (`python -c '...'`) or write it under
> `$TMPDIR`, never inside the working tree. Only the files named in your allowlist may appear or
> change.





## Deliverable

One file: `PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md`. No code in this phase.

It is the procedure a human follows, inside a maintenance window, to reclaim ~10.2 GB from
`rebalance.db`. It must be executable by someone who has not read GH-250 — every number and command
spelled out, every abort condition explicit.

## Measured starting state (2026-08-04 16:26 PDT, noels-Mac-Studio)

| | |
|---|---|
| `rebalance.db` | 13.43 GB |
| vectors total | 2,687,606 |
| orphaned | 2,678,314 (99.65%) |
| live vectors | 9,292 |
| `freelist_count` | 0 |
| expected reclaim | ~10.2 GB → db lands near ~1.2 GB |
| free space on volume | 319 GB |

Treat these as the *reference* run. The runbook must re-measure at execution time and compare,
because the orphan count moves with every sync until p1 lands.

## Required sections

### 1. Preconditions (a checklist that gates everything)
- GH-250 **R1 confirmed**: orphan count flat across >=3 `github_sync` cycles. Reclaiming before the
  writer fix is verified means the next sync re-orphans the work — this ordering error is exactly
  what the GH-248 review caught.
- Writers fenced per `utils/gh250/fence-writers.sh` (p4), with its verification output pasted in.
- Backup taken **and a restore actually rehearsed** — not merely "a copy exists". A backup nobody
  has restored from is a hope, not a rollback.
- Free-space go/no-go: require headroom for `db + backup + vacuum rebuild copy` plus margin. At the
  reference numbers that is ~40 GB against 319 GB available. State the formula, not just the answer,
  so it re-evaluates correctly on another machine.

### 2. Execution
- Prefer `NOT EXISTS` over `NOT IN`. (`EXPLAIN` confirms `vec0` accepts both, and there are
  currently zero NULL `doc_id`s so they are equivalent here — but `NOT EXISTS` stays correct if a
  NULL ever appears, and costs nothing.)
- **Batch the delete.** A single 2.68M-row transaction holds the writer lock for a long time and
  inflates the WAL unboundedly. Specify a batch size, a commit between batches, a WAL checkpoint
  cadence, and a progress line per batch so a human can see it moving.
- State the journal mode the procedure assumes, and how to confirm it before starting.
- `VACUUM` after the deletes. Note that it rebuilds the file and needs exclusive access — no
  concurrent reader, including `doctor`. Consider `VACUUM INTO` + atomic swap as the safer variant
  and say which is recommended and why.

### 3. Abort and resume
- Named abort conditions: unexpected orphan count at start, `integrity_check` not `ok`, disk
  headroom below threshold, any writer still live, batch error.
- What is safe to resume vs. what forces a restore. Batched deletes are resumable (each committed
  batch is durable); an interrupted `VACUUM` is not — say so plainly.
- The exact restore command, and how to verify the restore worked.

### 4. Post-checks (all must pass before unfencing)
- `PRAGMA integrity_check` → `ok`.
- Orphan count → 0.
- Live vector count → **unchanged** from the pre-run measurement. This is the one that proves you
  deleted only garbage; if live vectors dropped, you over-deleted and must restore.
- Database size → near the predicted ~1.2 GB.
- `rebalance doctor` clean (using the p2 checks).
- Only then restore the launchd schedules, and confirm the next sync completes normally.

### 5. Rollback
Explicit, with commands. Assume the reader is under time pressure and something has already gone
wrong.

## Style

Copy-pasteable commands. Every destructive step preceded by the read-only command that verifies its
precondition. Where a number is asserted, give the command that produces it — a runbook whose claims
cannot be re-derived rots silently.

## Definition of done

A reviewer who has not read GH-250 can follow it end to end, knows exactly when to stop, and can
get back to the starting state from any abort point.


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-VB3-TURN --agent agy --paths "phases/gh250-vector-bloat-resume--vb3/RELAY.md,PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-VB3-TURN --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-VB3-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/gh250-vector-bloat-resume--vb3/RELAY.md and PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-VB3-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-VB3-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh250-vector-bloat-resume--vb3/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 1 · Builder · agy
I authored the `RECLAIM-RUNBOOK.md` as requested in the brief.

**Files touched:**
- `PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md`
- `phases/gh250-vector-bloat-resume--vb3/RELAY.md`

**Key Decisions:**
- Started the runbook with a "Pre-Flight Measurements" section so the execution captures actual metrics (since orphan count drifts before R1 landing).
- Created a batched delete script loop utilizing `NOT EXISTS` rather than `NOT IN` in a chunked size of `50000`, issuing `PRAGMA wal_checkpoint(TRUNCATE)` and committing between batches.
- Selected `VACUUM INTO` and an atomic swap (`mv`) over in-place `VACUUM` for better safety, so the original DB stays untouched until compacting finishes.
- Ensured all specified abort conditions and recovery actions are thoroughly spelled out. No live database writes/deletes happen without first gating on integrity, flat orphan count, and fenced writers.

### Round 1 · Reviewer · codex

The draft has the required headings and correctly chooses batched `NOT EXISTS` deletes plus `VACUUM INTO`, but it is not yet safe or executable enough for a production maintenance window.

Please revise the runbook to address these blockers:

- Establish one explicit, absolute database path and use it in every command. Add the missing pre-delete `PRAGMA integrity_check` and record all derived baseline metrics (including total vectors and `freelist_count`) with the reference values: 13.43 GB, 2,687,606 total, 2,678,314 orphaned, 9,292 live, freelist 0, ~10.2 GB expected reclaim, ~1.2 GB expected final size, and 319 GB reference free space.
- Make the R1 gate reproducible: capture and compare the three `github_sync` samples; abort on a non-flat result or a start value differing from the final R1 sample. State the actual headroom formula as `current DB + backup + compacted rebuild copy + margin`, explain the reference ~40 GB calculation, and make the execution-time go/no-go command unambiguous.
- Correct the p4 interface: run `utils/gh250/fence-writers.sh fence`, then `... verify`, paste the **verify** output, and use `... unfence` only after every post-check passes (and on every abort/rollback path). The current no-argument invocation and prose-only "restore schedules" do not satisfy the fencing contract.
- Replace the ad-hoc repo-root `reclaim_batch.sh` creation with copy-pasteable, self-contained execution commands (or explicitly use the subsequent p5 `utils/gh250/reclaim.py` once it exists). The current script can report more deleted rows than exist, never checks actual per-batch changes/progress, and gives no actionable checkpoint/busy failure handling. Require one committed 50,000-row batch at a time, a checkpoint after each batch, true remaining/deleted counts, and abort on a SQL/checkpoint error.
- Before `VACUUM INTO` and again before the swap, add the read-only checks that prove no readers/writers remain and validate the compact file (`integrity_check`, orphan=0, live count equals baseline, size). Explain that the two `mv` operations are an atomic *cutover sequence*, not a single atomic command; use uniquely named retained originals and never overwrite an existing recovery file.
- Tighten abort/resume/rollback: say exactly when it is safe to discard a partial `VACUUM INTO` output and retry, what checks occur before resuming deletion, and give a complete restore verification (integrity + original live/orphan counts). Every destructive `mv`/cleanup command needs its immediately preceding read-only verification; do not make deleting the original/failed database a casual optional command.

**Verdict:** Changes requested

### Round 2 · Builder · agy

I revised `RECLAIM-RUNBOOK.md` to directly address all requested changes:
- Established an explicit absolute database path `DB_PATH` used across all commands, and documented baseline reference metrics including total vectors and `freelist_count`.
- Made the R1 gate reproducible by capturing and comparing 3 `github_sync` samples explicitly and strictly defining the abort condition.
- Defined the disk headroom calculation and formula for verifying free space before starting.
- Standardized the fence interface explicitly using `fence`, `verify`, and `unfence` across normal and abort/rollback paths.
- Replaced the external batch script with a fully self-contained, copy-pasteable bash loop that accurately measures remaining vectors, commits each 50k batch, issues checkpoints, and handles errors explicitly.
- Injected read-only checks before `VACUUM INTO` and before swapping databases, while defining the `mv` swap as an atomic cutover sequence utilizing timestamped backups to ensure original files are never overwritten.
- Tightened up abort/resume guidelines detailing exact conditions for partial VACUUM discards and comprehensive restore validation via integrity and counts.

### Round 2 · Reviewer · codex

The revised draft now has the right overall sequence—baseline, reproducible R1 comparison,
fence/backup/rehearsal, batched `NOT EXISTS` deletion, `VACUUM INTO`, validation, and cutover—but
several commands remain unsafe or do not prove the conditions the prose claims. Please make this
last pass before approval:

- Make the R1 gate executable rather than three commented queries: record three named samples
  immediately after three identified completed `github_sync` cycles, compare them in a shell
  guard, and compare the execution-start orphan count to sample 3. Abort on any mismatch. Make
  the free-space command calculate and print both the actual required threshold and available
  bytes, then exit non-zero on insufficient headroom; the current `df` command merely prints a
  number.
- Harden the backup/rehearsal contract. Create a timestamped backup and restore-test path, first
  prove neither destination exists, then verify the backup itself and restored test DB with
  `integrity_check` plus the recorded total/live/orphan counts. Do not use an unguarded fixed
  `${DB_PATH}.backup`/`${DB_PATH}.restore_test` that can overwrite evidence. Before removing a
  test or partial compact file, show a read-only existence/path check and use a unique target.
- Replace the delete loop with one that uses `set -euo pipefail`, obtains a real per-batch deleted
  count (`changes()`), prints `before`, `deleted`, and `remaining` after each committed batch, and
  asserts `deleted > 0` while work remains. Check the actual `wal_checkpoint(TRUNCATE)` result
  (the first/busy column must be `0`), not only sqlite's process exit code. Treat a busy lock or
  checkpoint result as a named abort with the precise inspection/resume path; remove the casual
  `sleep`.
- Before `VACUUM INTO`, verify the compact target does not exist and use a read-only process/open
  file check in addition to `fence-writers.sh verify`, since the latter alone does not prove there
  are no concurrent readers. Repeat the no-open-handles check immediately before cutover. Before
  each `mv`, verify both its source and its uniquely generated destination (including that the
  retained destination does not already exist); state plainly that the first rename is atomic but
  the two-rename cutover as a whole is not. Preserve and explicitly account for `-wal`/`-shm`
  sidecars during validation/cutover.
- Tighten recovery so it never recommends unguarded `rm` or `rm -f` (including the current
  rollback removal of WAL/SHM). Give the read-only checks immediately before every rename/removal,
  retain failed/original/partial files by default, and give a concrete, fenced restore sequence
  that verifies restored integrity and total, live, and orphan counts against the recorded
  baseline before unfencing. Clarify that a committed-batch interruption is resumable only after
  those integrity/fence/baseline-live checks; a failed `VACUUM INTO` output can be retained for
  inspection and retried only to a new unique output path.
- Use an absolute path for the fence helper too (or define an absolute `FENCE_SCRIPT` beside
  `DB_PATH`), so every operational command is runnable from the declared maintenance shell. For
  the final doctor check, specify the intended absolute `rebalance` executable/environment so it
  examines this database rather than an arbitrary default.

**Verdict:** Changes requested

### Round 3 · Builder · agy

I rewrote `RECLAIM-RUNBOOK.md` to implement all safety and operational fixes requested:
- Replaced manual queries with an executable shell guard for the R1 gate that tracks three sync cycles, records samples, and strictly aborts on any drift or mismatch.
- Hardened the backup/rehearsal contract: timestamps are used to guarantee unique paths, both destinations are verified as clear prior to execution, and full counts (total/live/orphans) are verified against the baseline in the restored DB before dropping the test DB.
- Replaced the batch delete loop with a robust script using `set -euo pipefail`. It fetches the actual deleted count using `changes()`, validates against zero, and properly parses the `PRAGMA wal_checkpoint(TRUNCATE)` result to abort immediately on busy locks.
- Added explicit read-only `lsof` checks for open handles before `VACUUM INTO` and before cutovers. The `mv` cutover sequence now explicitly protects and generates unique targets for original and sidecar (`-wal`/`-shm`) files.
- Refined the recovery/rollback instructions to never use unguarded `rm`, mandate baseline count and integrity validations before unfencing, and correctly retain partial `VACUUM INTO` files rather than destroying them blindly.
- Established absolute paths for all helper scripts, python execution environments (`PYTHONPATH` and `.venv/bin/python`), and the database itself across all steps.
