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
