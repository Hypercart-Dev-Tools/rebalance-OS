# p5 — Rehearse the reclaim against a throwaway COPY

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
