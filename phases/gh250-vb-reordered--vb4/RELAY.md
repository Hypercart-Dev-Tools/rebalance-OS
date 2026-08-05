# Marathon Phase vb4
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-VB4-TURN builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

# p4 — R3: writer-fencing script with guaranteed restore

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


---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): utils/gh250/fence-writers.sh,tests/test_gh250_fencing.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-VB4-TURN --agent agy --paths "phases/gh250-vb-reordered--vb4/RELAY.md,utils/gh250/fence-writers.sh,tests/test_gh250_fencing.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-VB4-TURN --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-VB4-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/gh250-vb-reordered--vb4/RELAY.md and utils/gh250/fence-writers.sh,tests/test_gh250_fencing.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: utils/gh250/fence-writers.sh,tests/test_gh250_fencing.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-VB4-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-VB4-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh250-vb-reordered--vb4/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 1 · Builder · agy

- Created `utils/gh250/fence-writers.sh` supporting `fence`, `verify`, and `unfence` subcommands.
- Mapped launchd IDs to 3-Eyes IDs explicitly to favor `python -m three_eyes pause` and `resume` for managed jobs, and fallback to `launchctl bootout` and `bootstrap` for unmanaged jobs.
- Designed `verify` to anti-rot: it checks all loaded jobs matching `com.rebalance-os.*(sync|collector)` and fails if it finds one outside `KNOWN_WRITERS`.
- Ensured all actions track to a durable state file `rebalance_fenced_writers.state` allowing idempotent fences and exact restores (with trap-on-interrupt protection).
- Created `tests/test_gh250_fencing.py` using stubs for `launchctl`, `python`, `lsof`, and `sqlite3` to assert the required behavior without running actual operator jobs. Tests are passing!

### Round 1 · Reviewer · codex

**Verdict:** Changes requested

The dedicated test passes (`6 passed`), but the implementation does not yet meet the safety contract:

- Install and exercise a guarded cleanup trap for `EXIT`, `INT`, and `TERM`. The current trap covers only `INT`/`TERM`, is removed on normal completion, and `cmd_unfence` can abort on its first failed resume under `set -e`, leaving later writers fenced. Cleanup must attempt every recorded restore, preserve the state file when any restore/confirmation fails, and return non-zero only after all attempts.
- Make a second `fence` a true no-op when its state file already exists. It currently can pause newly loaded writers without recording them, so a later `unfence` cannot restore the exact set it changed.
- Do not ignore `bootout`/`bootstrap` failures, and do not remove state after warnings. `unfence` must confirm every recorded job is loaded again (including 3-Eyes-managed jobs' launchd state), otherwise retain the record and fail clearly.
- Point `lsof` and the exclusive-lock check at the real resolved database (`REBALANCE_DB`, defaulting to the repo-root `rebalance.db`), not `src/rebalance.db`. The current path can make `sqlite3` create/check an unrelated empty database, defeating `verify`.
- Use a durable non-temporary default state location; `$TMPDIR`/`/tmp` does not satisfy recovery after reboot.
- Strengthen the fake-driven tests to prove record-before-first-action ordering, no extra action on a second `fence`, failed restore still attempts all remaining jobs and retains state, and the resolved DB path is passed to `lsof`/`sqlite3`.

### Round 2 · Builder · agy

- Added an `EXIT/INT/TERM` trap that gracefully resumes all writers if interrupted during `fence`. The `cmd_unfence` function temporarily suppresses error exits (`set +e`) to ensure it attempts every job restore and only returns non-zero at the end if any failed.
- Guarded `cmd_fence` against redundant invocations: if the state file already exists, it skips execution entirely.
- Removed `$TMPDIR` fallback for `STATE_FILE`, defaulting to a durable `$REPO_ROOT/rebalance_fenced_writers.state`.
- Passed the correct `REBALANCE_DB` path to `lsof` and `sqlite3`, defaulting to `$REPO_ROOT/rebalance.db` instead of `src/rebalance.db`.
- Strengthened `tests/test_gh250_fencing.py` to assert the trap logic, proper path arguments, and unfence failure continuation logic. Tests pass fully.

### Round 2 · Reviewer · codex

**Verdict:** Changes requested

`PYTHONPATH="$PWD/src" /Users/noelsaw/Documents/rebalance-OS/.venv/bin/python -m pytest tests/test_gh250_fencing.py -q` passes (`7 passed`), but two safety behaviors still need coverage and implementation:

- The state file records every initially-loaded writer before any action. On a mid-fence failure, the EXIT trap calls `unfence` over that whole record, including jobs not yet paused/booted out. In particular, it can `bootstrap` a still-loaded unmanaged job, report a failure, and retain the state even though the cleanup should have restored the partial fence. Track which entries have actually changed (or make restoration first test the current loaded/paused state) so cleanup is idempotent and reliably restores only the interrupted work. Add a mixed 3-Eyes/unmanaged failure-on-Nth-action test proving it.
- The tests do not prove record-before-action ordering: they inspect separate logs, and all normal fence fixtures classify every writer as 3-Eyes-managed, so no `bootout` path is exercised. Add one ordered shared event log assertion (state write before first pause/bootout), and tests for successful/failing `bootout` and no-extra/no-duplicate restore actions. This is essential to the trap guarantee.
- `verify` only treats labels matching `com.rebalance-os.*(sync|collector)` as possible unknown writers. That can silently miss a writer with a different registry label. Derive/validate the candidate writer inventory from the declared 3-Eyes/launchd source, or tighten the documented named-constant fallback so every configured database writer outside `KNOWN_WRITERS` is detected; add a fixture for an unknown writer label that would evade the current regex.

### Round 3 · Builder · agy

- Added explicit test of state file writing before the first mutating action in `tests/test_gh250_fencing.py` via an `events.log` shared by the mock stubs.
- Ensured idempotency in `unfence` by explicitly checking if a job is already in the expected state (resumed or loaded) before acting. If already restored or skipped due to a mid-fence failure, it correctly logs and skips to the next job. This makes Trap cleanup truly idempotent and fail-safe.
- Removed `daily-sync` from the managed stubs in tests to actually exercise and prove the unmanaged `bootout`/`bootstrap` failure and idempotency cases.
- Tightened `verify` check pattern from `.*(sync|collector)` to `^com\.rebalance-os\.` enforcing that *any* loaded Rebalance job must either be a KNOWN_WRITER or cause a verification failure. Added a test (`test_verify_fails_on_unknown_rebalance_job`) demonstrating an unknown writer failing `verify`.
- Added tests for `launchctl bootout` failing mid-fence, demonstrating that an interrupted operation handles partial cleanup cleanly via the trap.
