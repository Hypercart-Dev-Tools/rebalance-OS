# GH-218 — doctor reads an empty `launchctl list` as "no jobs loaded"

> Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/218
> Status: **proposed** — found 2026-07-27 during the #215 memory investigation.

**Component**: `src/rebalance/doctor.py`

## Why

`doctor` cannot tell "`launchctl list` reported no jobs" from "`launchctl list` could not report".
When the command runs but yields nothing usable, doctor concludes every scheduled job is missing
and emits **14 confident WARNs** instructing the operator to reinstall jobs that are loaded and
running.

Same bug class as [#146](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/146), where
months of "collectors are unstable" turned out to be the health signal rather than the collectors.

## How it was found (worth recording)

During the 07-27 memory investigation, a `doctor` run in a restricted shell reported all schedulers
unloaded. Taken at face value, that produced a **false lead** — "no scheduler is loaded, yet
something is firing embedding passes every 40-70 minutes" — a contradiction that existed only
because the instrument was wrong. Re-running unsandboxed showed zero scheduler warnings, and
`launchctl list | grep -c rebalance` returned **14**.

The apparent mystery dissolved entirely: `vault-sync` runs hourly at :15 (06:00-23:00) and
`daily-sync` at 06:30 for ~49 minutes. Nothing was unexplained. A wrong instrument invented a
puzzle and cost real investigation time — which is the strongest argument for fixing it before it
is leaned on as a marathon gate.

## Key concepts

**The intent is already correct in the code; the check is too narrow to deliver it.**
`_launchctl_list()` (`doctor.py:502-510`) returns `None` **only** on `FileNotFoundError` /
`SubprocessError`; `returncode` is never inspected, so a command that runs but produces nothing
returns `""`. The caller's guard (`doctor.py:603-606`) reads

```python
if launchctl_output is None:
    return []  # not macOS / launchctl unavailable — silently skip
```

and `"" is not None`, so it proceeds, `_loaded_rebalance_labels("")` yields an empty set, and every
policy job is reported missing (`doctor.py:627-628`).

**An empty listing is evidence of failure, not of an empty fleet.** A working `launchctl list` on
macOS always returns at least system labels. Zero lines therefore means the call failed.

**Both current outcomes hide the truth** — one by omission (silent `[]`), one by invention (14
fabricated findings). Neither says "I could not determine this."

## Triage

| Axis | Rating | Note |
|---|---|---|
| Severity | Medium-High | Inverts a health signal; remediation is not a no-op |
| Confidence | **PROVEN** | Reproduced both ways live; mechanism read from source |
| Cost | Low | Return-code + empty-output check, plus one honest status line |
| Blast radius | Low | Single function pair, well-covered by a 3-state test |

## Phases

### Phase 1 — distinguish unavailable from empty
- [ ] Treat non-zero `returncode` as unavailable
- [ ] Treat empty/whitespace-only stdout as unavailable, not as "zero jobs loaded"

### Phase 2 — report the blindness honestly
- [ ] Emit exactly one "scheduler state undetermined" finding when unavailable
- [ ] Emit **zero** per-job "not loaded" warnings in that state

### Phase 3 — lock it down
- [ ] Regression test across all three states: available+loaded, available+genuinely missing,
      unavailable
- [ ] Confirm no `scheduler:*` warnings on a healthy device

## Anti-goals

- Not a rework of the scheduler policy table or `SCHEDULER.md`.
- Not a change to which jobs are installed.
- Not a general audit of every doctor check — just this false-negative path.

## Related

- #146 — same bug class.
- #215 / #216 / #217 — the memory investigation this was found during.
