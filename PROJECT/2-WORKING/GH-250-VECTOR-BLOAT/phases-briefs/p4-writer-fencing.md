# p4 — R3: writer-fencing script with guaranteed restore

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
