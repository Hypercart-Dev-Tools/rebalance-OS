# P4 — Wave 3: eight machine-local jobs into the gitignored overlay

Same shape as Waves 1 and 2 (`p2-wave1.md` Constraints apply unchanged). What makes this
wave different is **where the files go**.

## Read this before writing anything

`utils/3-eyes/registry/jobs.local.d/README.md`. The split is load-bearing:

- **`jobs.d/` + `commands.allow`** — committed, fleet-portable. `dashboard.render()` loads
  with `include_local=False`, so these appear in `DASHBOARD.md` on every clone.
- **`jobs.local.d/` + `commands.local.allow`** — gitignored, machine-specific. This is
  where a job goes when its command is an **absolute path outside rebalance-OS**. Putting
  such a path in the committed registry would give every clone a path that does not exist
  on their machine, and would make CI's `dashboard --check` non-deterministic.

Every job in this wave points outside this repo. **All eight belong in
`jobs.local.d/`.** `commands.local.allow` is itself gitignored — commit your additions to
`commands.local.allow.example` instead, so a future machine can reproduce the setup.

## The eight agents, with their REAL current definitions

| id | current argv | schedule |
|---|---|---|
| `prompt-log-to-md` | `~/.claude/hooks/prompt-log-to-md.sh "<abs path>/0. Claude Prompts.md"` | StartInterval=300 |
| `ga-pull-binoid` | `<WP-DB-Toolkit>/.venv/bin/python3 <…>/ga/pull_aggregates.py --…` | daily 10:00 |
| `ga-pull-bounce` | same script, different site args | daily 10:05 |
| `ga-pull-bloomz` | same script, different site args | daily 10:10 |
| `hq-rollup` | `/bin/bash -l -c "<xyz-3-agents-swarm>/utils/hq/rollup.sh"` | daily 17:50 |
| `servers-monitor` | `/bin/bash <AI-DDTK>/tools/servers-monitor.sh` | StartInterval=1800 |
| `git-pulse` | `~/bin/git-pulse` | StartInterval=3600 |
| `hq-marathon-scan` | `/bin/bash <xyz-3-agents-swarm>/utils/hq/hourly-global-scan.sh` | StartInterval=3600 |

Read every full argv off its plist. The three `ga-pull-*` agents share one script and
differ only in arguments — check whether the registry schema lets three jobs share one
`commands.local.allow` entry with per-job args, or whether it needs three entries. Do
what the schema actually supports, and say which in your turn.

## Things that need care

- **`hq-rollup` runs `/bin/bash -l -c "…"`** — a login shell wrapping a quoted command.
  That is a shape the allowlist may not express directly (`_resolve_argv` in
  `breakers.py` resolves an `exec` plus a fixed `args` list; it does not build a shell
  string). If it cannot be represented faithfully, say so rather than rewriting the
  command into something that merely looks equivalent. Dropping `-l` changes the
  environment the script runs in and can break it in ways that only show up days later.
- **Paths containing spaces** — `Documents/GH Repos/…` appears in several. Verify these
  survive `_resolve_argv` without shell interpretation.
- **`hq-rollup` and `hq-marathon-scan` belong to `xyz-3-agents-swarm`**, a different
  repo with its own maintainer. Adopting *scheduling* of another project's automation is
  a real decision, not a formality. Flag it; do not quietly take ownership.
- **`git-pulse`** has a known projection-path gotcha (`PDDA_GITPULSE_DIR`); its
  environment matters. Check the plist's `EnvironmentVariables` and preserve them, or
  state that the schema cannot.

## Definition of done

- Eight `jobs.local.d/*.toml`, each with `supersedes` naming the label it replaces.
- Additions recorded in `commands.local.allow.example` (the real
  `commands.local.allow` is gitignored; you may write it locally, but the committed
  artifact is the example).
- `python -m three_eyes validate` passes **with the overlay loaded**.
- `DASHBOARD.md` must be **unchanged** by this wave — local jobs are deliberately
  invisible to it. If `dashboard --check` reports drift, something went into the wrong
  directory. Assert this in a test.
- `utils/3-eyes/tests/test_adoption_wave3.py` asserting: every wave-3 job is in the
  local overlay and NOT in the committed registry; no absolute machine path appears in
  any committed file; schedules match the live plists.
- `.venv/bin/python -m pytest utils/3-eyes/tests -q` green.

## Constraints

- **No `launchctl`. No `three_eyes install`. No writes to `~/Library/LaunchAgents`.**
- **No absolute machine-specific path may enter a committed file.** This is the one that
  breaks other clones, and a test must enforce it.
- Do not modify Wave 1 or Wave 2 files.

## Containment: your filenames are FIXED

The relay containment guard matches allowlisted paths by **exact string**, not by
directory prefix. Any file you create outside the exact list below is treated as an
off-lane edit: your entire turn is discarded and fails with exit 6, however good the
work is. This already happened three times on this phase — the work was correct each
time and thrown away each time.

Create/modify **only** these paths:

- `utils/3-eyes/registry/jobs.local.d/prompt-log-to-md.toml`
- `utils/3-eyes/registry/jobs.local.d/ga-pull-binoid.toml`
- `utils/3-eyes/registry/jobs.local.d/ga-pull-bloomz.toml`
- `utils/3-eyes/registry/jobs.local.d/ga-pull-bounce.toml`
- `utils/3-eyes/registry/jobs.local.d/hq-rollup.toml`
- `utils/3-eyes/registry/jobs.local.d/servers-monitor.toml`
- `utils/3-eyes/registry/jobs.local.d/git-pulse.toml`
- `utils/3-eyes/registry/jobs.local.d/hq-marathon-scan.toml`
- `utils/3-eyes/registry/commands.local.allow.example`
- `utils/3-eyes/tests/test_adoption_wave3.py`

If the work genuinely requires a file that is not on that list, **do not create it**.
Say so in your turn block and hand back — a turn that reports a blocked requirement is
useful; a turn that gets discarded is not.

Also: `.pytest_cache/` and `.coverage` are now gitignored, so running the test suite is
safe. Do not create scratch files, notes, or scripts anywhere in the tree.
