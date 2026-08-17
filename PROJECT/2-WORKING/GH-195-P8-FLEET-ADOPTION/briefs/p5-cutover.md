# P5 — the cutover runbook and its dry-run tool (authors only; performs nothing)

Waves 1–3 taught 3-Eyes about 19 agents. None of them is actually managed yet: the live
launchd agents still run exactly as before, and every registry entry declares
`supersedes` for a label that is still loaded.

Cutover is the step that swaps them. It is **destructive, outward-facing, and lands on
the machine this person works on** — `launchd.install()` writes a plist and then runs
`launchctl bootout` + `bootstrap`, replacing running automations that publish, sync, and
pull real data. Get it wrong at 3am and the operator finds out when a day's ingest is
missing.

So this phase does not perform a cutover. It builds the thing that makes a human
cutover safe, and it stops there.

## Deliverable 1 — `utils/3-eyes/three_eyes/cutover.py`

A **planner**, not an executor. It must be incapable of mutating launchd: no
`launchctl`, no `install`, no `uninstall` call anywhere in the module. The egress static
guard (`test_egress_static_guard.py`) already forbids most of this outside the two
boundary modules — make sure your module passes it.

Given a wave, it produces an ordered plan:

1. **Preflight, per job** — the registry entry validates; its command resolves in the
   allowlist; the label it supersedes is currently loaded (if it is already gone,
   something is wrong); the rendered plist parses; the schedule in the registry matches
   the schedule of the live plist it replaces.
2. **The exact commands a human would run**, printed and never executed — the
   `launchctl bootout` for the incumbent, the `three_eyes install` for the replacement.
3. **A rollback line for every step.** Every incumbent plist must be backed up before it
   is retired, and the plan must state the command that puts it back. A cutover with no
   stated path back is not a plan.
4. **A verification step** — what `three_eyes health` should report afterwards, and what
   it would look like if the swap half-succeeded.

Refuse to plan a wave where any preflight fails, and say which job failed and why.
Exit non-zero so a human running it in a terminal notices.

## Deliverable 2 — `PROJECT/2-WORKING/GH-195-P8-FLEET-ADOPTION/CUTOVER.md`

The operator-facing runbook. Written for someone doing this at their desk, awake:

- **Order.** Which wave first and why. Wave 1 contains the health-reporter trio and the
  #139 duplicate-issue constraint (see `p2-wave1.md`) — it is the one that needs care,
  and there is a real argument for doing a low-stakes wave first to prove the mechanism.
  Make a recommendation and defend it.
- **A go/no-go gate per wave**, in terms the operator can check in one command.
- **Rollback**, spelled out, per wave. Not "restore the backup" — the literal commands.
- **What to watch afterwards**, and for how long. `pulse-web-sync` fires 36×/day so a
  break shows within the hour; `obsidian-rollover` fires once at 00:40 and a break is
  invisible until tomorrow. Say which jobs prove themselves fast and which do not.
- **The known-broken one.** `vault-sync` currently fails with `database is locked`
  (#222/#171). Adoption does not fix it. State plainly that it is expected to keep
  failing after cutover, so a red job post-cutover is not mistaken for cutover damage.

## Deliverable 3 — `utils/3-eyes/tests/test_cutover_plan.py`

- The planner **never** shells out to `launchctl` and never calls `install`/`uninstall`
  (assert by inspecting the module source, the way the egress guard does — a mocked call
  proves nothing about a module that could still reach the real one).
- A wave whose preflight fails produces a refusal and a non-zero exit, not a partial plan.
- Every step in a generated plan has a corresponding rollback line.
- A schedule mismatch between registry and live plist is caught by preflight.

## Definition of done

- All three deliverables exist; `pytest utils/3-eyes/tests -q` is green.
- `python -m three_eyes.cutover --wave 1` (or your chosen CLI) prints a plan and changes
  nothing. Prove it: run it, then show `launchctl list | grep rebalance` is unchanged.
- `CUTOVER.md` is complete enough that a competent operator who has not read this
  marathon could execute it.

## Constraints

- **This phase performs no cutover.** No `launchctl`, no `install`, no `uninstall`, no
  writes to `~/Library/LaunchAgents`.
- If you conclude the cutover cannot be made safe for some job, say so in the runbook and
  exclude it with reasons. An honest "do not adopt this one yet" is a better deliverable
  than a plan that pretends a risk away.

## Containment: your filenames are FIXED

The relay containment guard matches allowlisted paths by **exact string**, not by
directory prefix. Any file you create outside the exact list below is treated as an
off-lane edit: your entire turn is discarded and fails with exit 6, however good the
work is. This already happened three times on this phase — the work was correct each
time and thrown away each time.

Create/modify **only** these paths:

- `PROJECT/2-WORKING/GH-195-P8-FLEET-ADOPTION/CUTOVER.md`
- `utils/3-eyes/three_eyes/cutover.py`
- `utils/3-eyes/tests/test_cutover_plan.py`

If the work genuinely requires a file that is not on that list, **do not create it**.
Say so in your turn block and hand back — a turn that reports a blocked requirement is
useful; a turn that gets discarded is not.

Also: `.pytest_cache/` and `.coverage` are now gitignored, so running the test suite is
safe. Do not create scratch files, notes, or scripts anywhere in the tree.
