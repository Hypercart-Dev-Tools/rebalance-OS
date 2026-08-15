---
title: "p4 — R3: writer-fencing script with guaranteed restore"
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

# p4 — R3: writer-fencing script with guaranteed restore

## Status

| What was just completed | What's next |
|---|---|
| Phase complete, merged 2026-08-04 in PR #253 — but the script it produced failed in three ways when first run against the live fleet on 2026-08-14: it locked a stale repo-root database instead of the real one, its roster covered 5 of 11 loaded jobs, and its pause assertion greps for a string a paused job never prints. The first two are fixed; the restore path did work as designed. | The pause assertion cannot be fixed until pause state is readable at all — see [3EYES-PAUSE-DOES-NOT-STOP-LAUNCHD.md](../../../1-INBOX/3EYES-PAUSE-DOES-NOT-STOP-LAUNCHD.md). Until then, treat `launchctl bootout` as the only real fence. |

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





## Why this is a phase and not a runbook paragraph

`VACUUM` needs exclusive access, and this box runs `github_sync` 18x/day, `daily_sync` daily,
`pulse-sync` 18x/day, plus `3eyes.collector-health` every 30 minutes. "Run it when nothing else is
running" is not a procedure on a machine with 25 loaded launchd agents.

The failure mode that matters is not *forgetting to fence* — it is **fencing and then failing to
unfence**. If the operator's collectors stay unloaded after an aborted reclaim, data silently stops
flowing and the next person to notice is whoever reads a stale dashboard days later. The restore
path must be impossible to skip.

## Deliverable

`utils/gh250/fence-writers.sh` with three subcommands:

- `fence` — unload every job that can write `rebalance.db`; record what was actually unloaded to a
  state file.
- `verify` — prove nothing is holding the database: no target job loaded, no live process with the
  db open, and a writer lock can be acquired and released.
- `unfence` — restore exactly what `fence` recorded, then confirm each is loaded again.

## Hard requirements

1. **Restore is trap-guaranteed.** Install a shell `trap` on `EXIT`/`INT`/`TERM` so an interrupted
   `fence` (or an operator Ctrl-C) restores what it already unloaded. Never leave partial fencing.
2. **Record before acting.** Write the pre-fence state to a durable file *before* unloading anything,
   so `unfence` works even from a fresh shell after a crash or reboot. Include a timestamp and the
   resolved job labels.
3. **Idempotent.** `fence` twice must not corrupt the record; `unfence` twice must be harmless.
   `unfence` with no state file must say so clearly and exit non-zero rather than guessing.
4. **Derive the job list, don't hardcode it.** The set of db writers must come from the 3-Eyes
   registry / launchd inventory, not a literal list that silently rots when a job is added. If you
   must enumerate, put the list in one named constant with a comment pointing at the source of
   truth, and make `verify` fail if it finds a loaded writer outside the known set — so the rot is
   detected instead of ignored.
5. **`verify` must be able to fail.** A verifier that always passes is worse than none. It has to
   actually detect a live writer.
6. **No `sudo`.** These are user LaunchAgents (`gui/$(id -u)`).
7. Prefer 3-Eyes' own `pause`/`resume` where a job is 3-Eyes-managed — it records breaker state
   properly. Fall back to `launchctl bootout`/`bootstrap` only for unmanaged jobs, and say which
   path each job took.

## Tests — `tests/test_gh250_fencing.py`

Do not unload the operator's real jobs in a test. Drive the script's logic against a fake:
parameterise the launchctl invocation (env var or injected command) so tests can substitute a stub
that records calls.

1. `fence` records pre-state before issuing any unload.
2. Interrupting mid-fence restores everything already unloaded (simulate a failure on the Nth job
   and assert the first N-1 were restored).
3. `unfence` restores exactly the recorded set — no more, no less.
4. `unfence` with no state file exits non-zero with a clear message.
5. `verify` fails when a stub reports a writer still loaded.
6. `fence` twice does not clobber the original record.

## Definition of done

- Fencing an already-fenced system is safe; unfencing an unfenced one is safe.
- A killed `fence` leaves the system fully restored.
- `verify` demonstrably fails when a writer is live.
- The script is referenced by name from `RECLAIM-RUNBOOK.md` (p3), and its `verify` output is what
  the runbook's precondition checklist asks the operator to paste in.
