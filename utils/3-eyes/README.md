# 3-Eyes — one optional, always-safe local job supervisor

GH-195. One system unifying the three sentinels we run today — the XYZ debug
flywheel, the Cactus Needle PDDA sentinel, and the Rebalance collector-health
sentinel — under **one TOML registry, one set of circuit breakers + relief valves,
one generated dashboard, and one way to talk to your jobs.**

The name is a nod to XYZ: the three "eyes" are XYZ-debug, Cactus-Needle-PDDA, and
Rebalance-collectors. It lives in `rebalance-OS/utils/3-eyes/` until it needs to
spin off.

## Inert by default (the load-bearing promise)

**With no `config/runtime.env` (or `THREE_EYES_ENABLE != 1`), 3-Eyes is a clean
no-op.** Zero network, zero `ollama`, zero `gh`, zero launchd/cron mutation, zero
marathon fire. None of the three host repos needs it to work. Activation is a
local, gitignored opt-in — nothing here ships enabled, and there is a `test/`
proof (`test_inert_by_default.py`) that stubs `ollama`/`gh`/`curl` to fail loudly
and asserts nothing calls them.

Two hard kill-switches force it off regardless: `THREE_EYES_ENABLE=0` in the
environment, or a `PANIC` file in the state dir.

## Activate it (opt in, locally)

```bash
cp config/runtime.env.example config/runtime.env
$EDITOR config/runtime.env          # set THREE_EYES_ENABLE=1, model, gh repo
python -m three_eyes validate       # registry integrity
python -m three_eyes status         # active/inert + live launchctl + breakers
python -m three_eyes install selfcheck   # write+load the job's launchd agent (gated)
```

## The registry is the source of truth

Jobs are declared in TOML under `registry/`; **launchd/cron entries are rendered
from the registry, never hand-authored**, and `DASHBOARD.md` is a generated
projection of it. "The dashboard mirrors the jobs" and "the jobs mirror the
registry" are the same statement.

- `registry/jobs.d/*.toml` — one job each (command, schedule, rules, breakers, routes, relief)
- `registry/commands.allow` — the ONLY commands a job may execute (no free-form exec, ever)
- `registry/routes.toml`    — the finding sinks (`log-only`, `notify`, `pdda-inbox`, `gh-issue`)

`DASHBOARD.md` regenerates on every registry change via three redundant triggers:
`python -m three_eyes sync-dashboard`, the `hooks/regen-dashboard` pre-commit hook,
and `python -m three_eyes.dashboard --check` in CI (fails on drift).

## Safety

- **Circuit breakers** wrap the existing `utils/job_guard.py` (GH-172): every job
  runs its command tree under a single-instance flock + an RSS/available-memory
  watchdog. On top of that, a per-job **failure breaker** quarantines a job after
  N consecutive failures, and a **global kill-switch** halts everything at once.
- **Relief valves** — daily + per-run LLM/API budgets, quiet hours, exponential
  backoff. A healthy system can't stampede the machine or an API.
- **Two irreversible edges stay human** — adding a command to `commands.allow`
  (what to run) and any `gh`/`git push` route (what to ship) are operator acts.

## Talk to your jobs

`python -m three_eyes <cmd>`: `list`, `status`, `validate`, `dry-run <job>`,
`why <job>`, `pause <job>`, `resume <job>`, `run <job>`, `observe`,
`sync-dashboard`, `install/uninstall <job>`. There's also a Claude skill
(`skills/three-eyes/`) and an MCP server (`mcp/server.py`) exposing the same
read/pause/resume/dry-run surface, plus a `launchd-triage` skill that inventories
everything in `~/Library/LaunchAgents` read-only.

## Layout

```
three_eyes/     config gate · registry · breakers · relief · launchd · cron · classify · routes · dashboard · run · CLI
registry/       jobs.d/*.toml · commands.allow · routes.toml
shims/          run-job.sh   (the only Bash: one-line launchd/cron → python -m three_eyes.run)
hooks/          regen-dashboard   (pre-commit: TOML → DASHBOARD.md)
skills/         launchd-triage/ · three-eyes/
mcp/            server.py
config/         runtime.env.example (+ gitignored runtime.env)
tests/          inert-by-default · dashboard-mirror · breaker trips · allowlist · egress static-guard
DASHBOARD.md    GENERATED mirror of the registry — do not hand-edit
```

Design of record: `PROJECT/1-INBOX/GH-195-UNIFIED-SENTINEL.md`.
