# Marathon Phase vb5
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-VB5-TURN builder=agy reviewer=codex round-cap=9 -->

## Phase Brief

# p5 — Rehearse the reclaim against a throwaway COPY

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





## The one rule

**This phase must never write to the live database.** Every operation runs against a copy. The
reclaim script must *refuse* to run against the production path unless an explicit override flag is
passed — and that flag is for the human executing R4 later, never for this phase, never for a test.

Build the safety in as a guard, not as a convention. A comment saying "don't point this at prod" is
not a guard.

## Deliverables

### `utils/gh250/reclaim.py`
The real reclaim, written once, used by both the rehearsal and (later, by a human) the production
run. It implements what `RECLAIM-RUNBOOK.md` (p3) specifies:

- `--database PATH` required; refuses the production path unless `--i-know-this-is-production`.
- `--dry-run` default. Actually deleting requires an explicit `--execute`.
- Batched deletes with `NOT EXISTS`, commit + WAL checkpoint per batch, progress per batch.
- `PRAGMA integrity_check` after.
- Prints a before/after table: db size, total vectors, orphans, **live vectors**, `freelist_count`.
- Non-zero exit on any post-check failure.
- Resumable: re-running after an interrupt must pick up correctly (committed batches are durable).

### `utils/gh250/rehearse.sh`
1. Copy the live db to a scratch location (use the repo's scratch/temp convention; never `/tmp`
   directly if the repo has its own).
2. Record the copy's starting metrics.
3. Run `reclaim.py --execute` against the copy.
4. Assert every post-check from the runbook.
5. Print a rehearsal report: bytes reclaimed, live vectors before/after, `integrity_check` result,
   wall-clock elapsed, peak WAL size observed.
6. Delete the copy (and clean up on failure too — trap it).

The db is ~13.4 GB, so the copy needs ~13.4 GB free and the run will not be instant. Check headroom
before copying and fail fast with a clear message if it is short.

## The assertion that matters most

**Live vector count must be identical before and after.** Bytes reclaimed proves the delete did
something; unchanged live vectors proves it deleted *only* garbage. At the reference numbers:

| | before | after |
|---|---|---|
| total vectors | 2,687,606 | 9,292 |
| orphaned | 2,678,314 | **0** |
| **live vectors** | 9,292 | **9,292 — unchanged** |
| db size | 13.43 GB | ~1.2 GB |

If live vectors drop by even one, the predicate is wrong. Fail loudly.

## Tests — `tests/test_gh250_reclaim.py`

Use small synthetic databases, not the production copy — these must run in CI in seconds.

1. Build a fixture db with N live + M orphaned vectors; run the reclaim; assert exactly M deleted, N
   survive, orphans → 0.
2. `--dry-run` (the default) changes nothing.
3. Production-path guard: pointing at the real db path without the override **refuses**, exits
   non-zero, and writes nothing. Assert this by mtime or hash, not just exit code.
4. Batching correctness: with a batch size smaller than the orphan count, the result is identical to
   a single batch.
5. Resume: interrupt after the first batch, re-run, end state is still correct.
6. Zero-orphan input is a clean no-op that still passes post-checks.
7. `integrity_check` failure surfaces as a non-zero exit.

## Reporting

Write the rehearsal report to `PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/REHEARSAL-REPORT.md` and
reference it from the runbook, so the human doing R4 knows the exact timing and reclaim to expect —
and can tell immediately if the production run is diverging from the rehearsal.

## Definition of done

- The rehearsal completed against a copy, with a report showing ~10.2 GB reclaimed, orphans 0, live
  vectors unchanged, `integrity_check` ok.
- The production-path guard is proven by a test, not asserted by a comment.
- `RECLAIM-RUNBOOK.md` now points at a *rehearsed* script rather than describing SQL in prose.
- **R4 remains un-run.** This phase ends with production untouched — that is success, not an
  incomplete phase.


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): utils/gh250/reclaim.py,utils/gh250/rehearse.sh,tests/test_gh250_reclaim.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-VB5-TURN --agent agy --paths "phases/gh250-vb-reordered--vb5/RELAY.md,utils/gh250/reclaim.py,utils/gh250/rehearse.sh,tests/test_gh250_reclaim.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-VB5-TURN --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-VB5-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/gh250-vb-reordered--vb5/RELAY.md and utils/gh250/reclaim.py,utils/gh250/rehearse.sh,tests/test_gh250_reclaim.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: utils/gh250/reclaim.py,utils/gh250/rehearse.sh,tests/test_gh250_reclaim.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-VB5-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-VB5-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh250-vb-reordered--vb5/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 1 · Builder · agy

Implemented the requested deliverables:
1. `utils/gh250/reclaim.py`: Python script with `--execute` requirement, dry-run by default, refusal to run on `rebalance.db` without `--i-know-this-is-production`, batching with transaction checkpointing, and `PRAGMA integrity_check` verification.
2. `utils/gh250/rehearse.sh`: Bash script that checks disk headroom, copies `rebalance.db` into `scratch/`, runs the reclaim script in the background while monitoring WAL size, asserts on final conditions, and prints the rehearse report to `scratch/rehearsal-report.txt`.
3. `tests/test_gh250_reclaim.py`: A pytest suite validating `dry-run`, production path guard, batching logic, resume capabilities (via a testing environment variable), and integrity failures.

Note: I could not execute `rehearse.sh` against the actual repository's `rebalance.db` because it lacks the `vec0` table (likely a sandbox stub DB), but the tests in `test_gh250_reclaim.py` passed successfully.

Ready for review!

### Round 1 · Reviewer · codex

**Assessment:** Changes requested.

1. `reclaim.py` only deletes rows. It never rebuilds/vacuums the copy, so its database size is effectively unchanged and `rehearse.sh` will report zero bytes reclaimed rather than the expected physical reclaim. Put the compact/rebuild operation in the single reclaim code path and include its result in the post-check metrics.
2. Successful completion does not assert `after_metrics["orphans"] == 0`; `--batch-size 0` (or a negative value) exits successfully with all orphans remaining. Reject non-positive batch sizes and make remaining orphans a failing post-check.
3. The production guard is CWD-relative (`Path("rebalance.db")`). It misses the actual production file when the command is invoked from another directory with an absolute database path. Resolve a canonical production path (while retaining an operator-friendly default) and test that exact protected target. The current test neither snapshots mtime/hash nor proves that the database is untouched, contrary to the brief.
4. The rehearsal copy must be a transactionally consistent SQLite backup. `cp` of the main DB plus sidecars can capture an inconsistent live state. Use SQLite's backup facility to create the copy, without writing the source DB.
5. Use the repository temp/scratch convention with a unique per-run directory, clean its DB artifacts on every exit, and write the durable report to the required GH-250 report path (the current `scratch/rehearsal-report.txt` is neither the required report location nor durable documentation). The script should also use the repository virtualenv/interpreter rather than an unqualified `python`.

`PYTHONPATH="$PWD/src" /Users/noelsaw/Documents/rebalance-OS/.venv/bin/python -m pytest tests/test_gh250_reclaim.py -q` passed (7 passed), but that coverage does not exercise the failures above.

**Verdict:** Changes requested
