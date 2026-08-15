---
title: "p5 — Rehearse the reclaim against a throwaway COPY"
status: "Phase complete (merged 2026-08-04, PR #253)"
created: 2026-08-04
updated: 2026-08-14
owner: noel
gh_issue: 250
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). The tracked effort is GH-250,
  parked in ROADMAP.md via PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/SCOPE.md.
---

# p5 — Rehearse the reclaim against a throwaway COPY

## Status

| What was just completed | What's next |
|---|---|
| Phase complete, merged 2026-08-04 in PR #253. The rehearsal correctly proved the reclaim math, `integrity_check`, and before/after counts, all of which held exactly on the real run of 2026-08-14. | The gap worth naming: rehearsing against a throwaway copy validated the *mutation* and nothing about the *environment*. Every defect that actually bit — a fence pointed at the wrong file, a roster missing six jobs, a pause that does not pause — was invisible to a copy-based rehearsal by construction. A future rehearsal should exercise the fence against the live fleet, which is read-only and cheap. |

> ## ⚠️ NEVER write the absolute repo path in your transcript
>
> The turn shim scans your transcript for the real repo root and fails the turn as an "isolation
> breach" if it appears (`agy-turn.sh` does a literal `grep -qF "$ROOT"`). This already failed two
> turns. So refer to the interpreter ONLY through the exported variable **`$GH250_PY`** — never
> spell out the path, not in a command, not in prose, not in a quoted log line.
>
> ```
> PYTHONPATH="$PWD/src" "$GH250_PY" -m pytest <your test files> -q
> ```


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
> PYTHONPATH="$PWD/src" "$GH250_PY" -m pytest \\
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





## SCOPE NARROWED — do not rehearse against the real 13 GB database in your turn

Originally this phase asked for a full rehearsal against a copy of the live database. That was a
bad ask for an autonomous turn: it means copying ~13.4 GB and running a VACUUM, which is slow,
needs ~27 GB of headroom, and is exactly the kind of heavyweight operation a contained turn should
not be doing.

**Your deliverable is the CODE, proven on synthetic databases:**
- `utils/gh250/reclaim.py` and `utils/gh250/rehearse.sh` — complete and correct.
- `tests/test_gh250_reclaim.py` — full coverage using pytest `tmp_path` fixtures with SMALL
  synthetic databases (a few live + a few orphaned vectors is enough to prove the predicate,
  batching, resume, and the production-path guard).
- `rehearse.sh` must be *runnable* and correct, but you do NOT execute it against the real
  database. An operator does that later, in the maintenance window, alongside R4.

Everything else in this brief still applies — especially the production-path guard, which must be
proven by a test rather than asserted by a comment, and the live-vector-count-unchanged assertion.

## The one rule

**This phase must never write to the live database.** Every operation runs against a copy. The
reclaim script must *refuse* to run against the production path unless an explicit override flag is
passed — and that flag is for the human executing R4 later, never for this phase, never for a test.

Build the safety in as a guard, not as a convention. A comment saying "don't point this at prod" is
not a guard.

## Where test databases may live — NOT in the working tree

This phase manipulates databases, so it will want scratch ones. A previous turn was failed by
containment for creating `test.db` at the repo root (`agy-turn: OFF-ALLOWLIST change: test.db —
reverting`). Containment reads git porcelain and cannot distinguish your scratch file from an
off-lane escape, so it fails the whole turn.

Rules:
- In tests, use pytest's `tmp_path` / `tmp_path_factory` fixtures. Never a relative `test.db`.
- In `rehearse.sh`, use `mktemp -d` and clean up with a `trap`.
- Never create a database, journal, WAL, or SHM file anywhere inside the repo.

`*.db` / `*.sqlite` and their sidecars are now gitignored as a second line of defence, but do not
rely on that — put them in a temp directory because that is correct, not because the ignore file
will hide the mistake.

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
