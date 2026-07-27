# Marathon Phase p1
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-GH219-LANE0 builder=agy reviewer=codex round-cap=5 -->

## Phase Brief

# Lane 0 (GH-219 marathon) — #218: doctor reads an empty `launchctl list` as "no jobs loaded"

## Context

`rebalance doctor` reports **14 `com.rebalance-os.*` scheduler jobs as "not loaded on this device"**
on a machine where all 14 are, in fact, loaded and firing. This is a false negative in the health
instrument, and it already cost a live investigation a false lead: it was reported as evidence that
the scheduler fleet was broken, when the real cause was that `launchctl` returns nothing inside a
restricted/sandboxed shell.

This lane runs **first** in the GH-219 memory marathon specifically because the marathon uses
`doctor` as an acceptance gate. Fix the instrument before using it to certify the work.

## The defect

`src/rebalance/doctor.py:502-510`:

```python
def _launchctl_list() -> str | None:
    """Return the live launchd listing, or ``None`` when unavailable."""
    try:
        out = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return out.stdout
```

Two bugs, both in the same three lines:

1. **`returncode` is never inspected.** A non-zero exit is treated as success.
2. **Empty stdout is returned as `""`, not `None`.** The caller (`doctor.py:603-606`) guards with
   `if launchctl_output is None: return []` — and `"" is not None`, so an empty listing flows on
   and is interpreted as "launchd is up, and zero jobs are loaded."

The result is 14 per-job WARN findings (`doctor.py:627-628`) advising a reinstall that is not
needed and would be actively harmful to run.

## Required behaviour

- A **non-zero `returncode`** means the listing is unavailable → `None`.
- **Empty or whitespace-only stdout** means the listing is unavailable → `None`. A genuinely
  running launchd with zero jobs is not a state this tool needs to distinguish; conflating
  "couldn't ask" with "asked, got nothing" is what caused the bug.
- On unavailable, emit **exactly one** finding — "scheduler state undetermined" — and **zero**
  per-job warnings. Do not advise reinstalling anything.
- On available, behaviour is unchanged: jobs genuinely missing still warn per-job.

The distinction to preserve throughout: **"undetermined" is not "broken."** The current code
collapses those two into the loudest possible wrong answer.

## Write-set (do not edit anything else)

- `src/rebalance/doctor.py`
- `tests/test_doctor_launchd.py`

## Tests — required, and required to land with the fix

`tests/test_doctor_launchd.py` already exists with 6 tests; extend it. Cover all three states
explicitly:

1. **available + loaded** → no `scheduler:*` warnings
2. **available + genuinely missing** → per-job warnings still fire (guard against over-correcting
   into silence)
3. **unavailable** — assert this for *each* of: non-zero returncode, empty stdout,
   whitespace-only stdout, `FileNotFoundError` → exactly one "undetermined" finding, zero per-job
   warnings

State 2 is the one most likely to be skipped and is the one that matters most: a fix that makes
doctor silent about real breakage is worse than the bug being fixed.

## Acceptance

- `.venv/bin/python3 -m pytest tests/test_doctor_launchd.py tests/test_doctor.py -q` passes
  (32 tests pass on the pre-fix baseline — no regressions permitted)
- On this healthy device, `rebalance doctor` emits **zero** `scheduler:*` warnings
- In a restricted shell, it emits one honest "undetermined" line and no reinstall advice

## Out of scope

- Rewriting the scheduler policy table or `SCHEDULER.md`
- Any change to which jobs are in the policy list
- The unrelated pre-existing `figma:`, `deep work`, and `commit coverage` warnings
- Anything touching the memory/embedding path — that is Lane 1 and later


## Debug mantra (auto-triggered — 2 prior attempt(s) on this phase did not reach Approved)

Before trying again, read /Users/noelsaw/Documents/rebalance-OS/.xyz/relay-automation/DEBUG-MANTRA.md and follow its four-step discipline: reproduce reliably, know the fail path, question the hypothesis, treat this round as a breadcrumb for the next one.
Last recorded reason (/Users/noelsaw/Documents/rebalance-OS/phases/p1/ESCALATION.md): `no-progress`. Read it before re-guessing.

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/doctor.py,tests/test_doctor_launchd.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-GH219-LANE0 --agent agy --paths "phases/p1/RELAY.md,src/rebalance/doctor.py,tests/test_doctor_launchd.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-GH219-LANE0 --agent agy
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH219-LANE0 --agent agy --to codex
4. Edit ONLY these paths: phases/p1/RELAY.md and src/rebalance/doctor.py,tests/test_doctor_launchd.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/doctor.py,tests/test_doctor_launchd.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH219-LANE0 --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-GH219-LANE0 --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/p1/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
