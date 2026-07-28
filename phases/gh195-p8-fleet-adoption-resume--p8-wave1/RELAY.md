# Marathon Phase p8-wave1
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-P8-WAVE1-TURN-4 builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

# P2 — Wave 1: adopt the five collectors that actually break

## What "adopt" means in this phase

Write a `registry/jobs.d/<id>.toml` and a `commands.allow` entry for each agent, so
3-Eyes *knows about* the job and could render its plist. **You are not installing
anything.** No `three_eyes install`, no `launchctl`, no writes to
`~/Library/LaunchAgents`. The live cutover is a separate, operator-gated step (p5).

Read first: `utils/3-eyes/registry/jobs.d/selfcheck.toml` and `collector-health.toml`
for the schema, `commands.allow` for the allowlist format, and `registry.py` for what is
actually validated.

## The five agents, with their REAL current definitions

Taken from the live plists — use these exactly; do not infer them.

| id | current argv | schedule |
|---|---|---|
| `daily-sync` | `scripts/daily_sync.sh` | daily 06:30 |
| `github-sync` | `scripts/github_sync.sh` | hourly :45, 06:45–23:45 (18×) |
| `vault-sync` | `scripts/vault_sync.sh` | hourly :15, 06:15–23:15 (18×) |
| `health-check` | `.venv/bin/python scripts/health_issue_reporter.py --close` | hourly :10 |
| `health-check-triage` | `.venv/bin/python scripts/health_issue_reporter.py --warn --close --llm-triage --llm-…` | 08:25, 14:25, 20:25 |

All five run from the rebalance-OS repo root, so their `exec`/`args` are **repo-relative**
and belong in the committed `commands.allow` (not the machine-local overlay). Read the
full `health-check-triage` argv off the plist yourself — it is truncated above.

## The hard constraint — read this twice

`health-check` and `health-check-triage` **both run `scripts/health_issue_reporter.py`,
which files GitHub issues.** The existing `collector-health` job already declares
`supersedes = ["com.rebalance-os.health-check", "com.rebalance-os.health-check-triage"]`,
and `launchd.install()` refuses while either is loaded.

That guard exists because **#139 was closed by deleting a duplicate-issue emitter.**
Standing up a second one recreates the exact defect this project is meant to prevent.

So: these three (`collector-health`, `health-check`, `health-check-triage`) are ONE
adoption unit. Your registry entries must make that relationship explicit and
machine-checkable, not just described in prose. Decide and justify:

- Does `health-check` / `health-check-triage` become its own registry job at all, or is
  its behaviour already covered by `collector-health` + the P7b/P7c pipeline that now
  parses telemetry and routes findings?
- If they do become jobs, what stops all three emitting issues concurrently after
  cutover?

There is a real argument that adopting the two `health_issue_reporter.py` agents as
*separate scheduled jobs* is wrong, and that the honest move is to record them as
superseded-by-`collector-health`. If you conclude that, say so and implement that
instead — a smaller correct registry beats a complete wrong one. Whatever you choose,
the reasoning goes in your turn block.

## Also worth knowing

`vault-sync` is the job that has been failing (`database is locked`, see #222 and its
sibling #171). Adoption does not fix that and must not pretend to. Do not add a
suppression rule for it — `known_issues.toml` deliberately does not suppress
`database is locked`, and there is a test asserting so.

## Definition of done

- A `jobs.d/*.toml` for each agent you concluded should be a job, each with a
  `supersedes` entry naming the launchd label it replaces.
- Matching `commands.allow` entries; `python -m three_eyes validate` passes.
- `python -m three_eyes sync-dashboard` regenerated and committed (CI checks it).
- `utils/3-eyes/tests/test_adoption_wave1.py` asserting at minimum:
  - every new job's `command` resolves in `commands.allow`;
  - every new job declares `supersedes` for the label it replaces, so the install guard
    can fire;
  - **no two enabled jobs can run `health_issue_reporter.py` concurrently** — encode the
    #139 constraint as a test, not a comment;
  - the schedules you wrote match the live plists (a wrong schedule silently changes when
    the operator's work happens).
- `.venv/bin/python -m pytest utils/3-eyes/tests -q` green.

## Constraints

- **No `launchctl`. No `three_eyes install`. No writes to `~/Library/LaunchAgents`.**
- Do not change any existing job's behaviour; this phase only adds registry knowledge.
- Schedules must reproduce the live plists exactly. If a plist has 18 calendar entries,
  the TOML has 18 — do not "simplify" it to a StartInterval.
- If something in the schema cannot express a live plist faithfully, STOP and say so in
  your turn rather than approximating. An adoption that silently changes a schedule is
  worse than no adoption.

## Containment: your filenames are FIXED

The relay containment guard matches allowlisted paths by **exact string**, not by
directory prefix. Any file you create outside the exact list below is treated as an
off-lane edit: your entire turn is discarded and fails with exit 6, however good the
work is. This already happened three times on this phase — the work was correct each
time and thrown away each time.

Create/modify **only** these paths:

- `utils/3-eyes/registry/jobs.d/daily-sync.toml`
- `utils/3-eyes/registry/jobs.d/github-sync.toml`
- `utils/3-eyes/registry/jobs.d/vault-sync.toml`
- `utils/3-eyes/registry/jobs.d/health-check.toml`
- `utils/3-eyes/registry/jobs.d/health-check-triage.toml`
- `utils/3-eyes/registry/jobs.d/collector-health.toml`
- `utils/3-eyes/registry/commands.allow`
- `utils/3-eyes/tests/test_adoption_wave1.py`
- `utils/3-eyes/DASHBOARD.md`

If the work genuinely requires a file that is not on that list, **do not create it**.
Say so in your turn block and hand back — a turn that reports a blocked requirement is
useful; a turn that gets discarded is not.

Also: `.pytest_cache/` and `.coverage` are now gitignored, so running the test suite is
safe. Do not create scratch files, notes, or scripts anywhere in the tree.


## Debug mantra (auto-triggered — 2 prior attempt(s) on this phase did not reach Approved)

Before trying again, read /Users/noelsaw/Documents/rebalance-OS/.xyz/relay-automation/DEBUG-MANTRA.md and follow its four-step discipline: reproduce reliably, know the fail path, question the hypothesis, treat this round as a breadcrumb for the next one.
Last recorded reason (/Users/noelsaw/Documents/rebalance-OS/phases/gh195-p8-fleet-adoption-resume--p8-wave1/ESCALATION.md): `containment-violation (off-lane edit reverted by a turn-taker)`. Read it before re-guessing.

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): utils/3-eyes/registry/jobs.d/daily-sync.toml,utils/3-eyes/registry/jobs.d/github-sync.toml,utils/3-eyes/registry/jobs.d/vault-sync.toml,utils/3-eyes/registry/jobs.d/health-check.toml,utils/3-eyes/registry/jobs.d/health-check-triage.toml,utils/3-eyes/registry/jobs.d/collector-health.toml,utils/3-eyes/registry/commands.allow,utils/3-eyes/tests/test_adoption_wave1.py,utils/3-eyes/DASHBOARD.md
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-P8-WAVE1-TURN-4 --agent codex --paths "phases/gh195-p8-fleet-adoption-resume--p8-wave1/RELAY.md,utils/3-eyes/registry/jobs.d/daily-sync.toml,utils/3-eyes/registry/jobs.d/github-sync.toml,utils/3-eyes/registry/jobs.d/vault-sync.toml,utils/3-eyes/registry/jobs.d/health-check.toml,utils/3-eyes/registry/jobs.d/health-check-triage.toml,utils/3-eyes/registry/jobs.d/collector-health.toml,utils/3-eyes/registry/commands.allow,utils/3-eyes/tests/test_adoption_wave1.py,utils/3-eyes/DASHBOARD.md"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-P8-WAVE1-TURN-4 --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-P8-WAVE1-TURN-4 --agent codex --to agy
4. Edit ONLY these paths: phases/gh195-p8-fleet-adoption-resume--p8-wave1/RELAY.md and utils/3-eyes/registry/jobs.d/daily-sync.toml,utils/3-eyes/registry/jobs.d/github-sync.toml,utils/3-eyes/registry/jobs.d/vault-sync.toml,utils/3-eyes/registry/jobs.d/health-check.toml,utils/3-eyes/registry/jobs.d/health-check-triage.toml,utils/3-eyes/registry/jobs.d/collector-health.toml,utils/3-eyes/registry/commands.allow,utils/3-eyes/tests/test_adoption_wave1.py,utils/3-eyes/DASHBOARD.md. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: utils/3-eyes/registry/jobs.d/daily-sync.toml,utils/3-eyes/registry/jobs.d/github-sync.toml,utils/3-eyes/registry/jobs.d/vault-sync.toml,utils/3-eyes/registry/jobs.d/health-check.toml,utils/3-eyes/registry/jobs.d/health-check-triage.toml,utils/3-eyes/registry/jobs.d/collector-health.toml,utils/3-eyes/registry/commands.allow,utils/3-eyes/tests/test_adoption_wave1.py,utils/3-eyes/DASHBOARD.md.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-P8-WAVE1-TURN-4 --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-P8-WAVE1-TURN-4 --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh195-p8-fleet-adoption-resume--p8-wave1/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 1 · Builder · codex

- Added declared-but-inert adoptions for `daily-sync`, `github-sync`, and `vault-sync`; their commands are committed, repo-relative allowlist entries, every replacement names its incumbent label, and the 18-entry GitHub/vault schedules reproduce the live plists exactly. Vault's `database is locked` failure is neither suppressed nor reclassified.
- Did **not** create `health-check` or `health-check-triage` registry jobs. Both are legacy `health_issue_reporter.py` emitters; `collector-health` already supersedes both labels and the P7b/P7c path is the sole managed health-finding path. The updated comment and adoption test make that #139 exclusion machine-checkable: no enabled 3-Eyes job resolves to the reporter, while `collector-health` retains both supersedence labels.
- Regenerated `utils/3-eyes/DASHBOARD.md`. Reproduced the initial missing-test failure (`test_adoption_wave1.py` did not exist; this worktree also has no local `.venv`), then used the pinned repository environment with the worktree package path. `python -m three_eyes validate` reports `registry OK`; targeted `test_adoption_wave1.py` passes (3 tests).
