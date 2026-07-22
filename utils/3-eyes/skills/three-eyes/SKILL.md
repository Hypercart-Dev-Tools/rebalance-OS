---
name: three-eyes
description: Talk to your 3-Eyes local job supervisor (GH-195) — list/inspect/pause/resume/dry-run scheduled sentinel jobs, check which are loaded, and regenerate the dashboard. Trigger on "3-eyes", "3 eyes", "my sentinel jobs", "what jobs are scheduled", "pause the collector job", "why did <job> fire", "sync the 3-eyes dashboard".
---

# 3-Eyes — talk to your jobs

3-Eyes is the unified, optional, inert-by-default local job supervisor in
`rebalance-OS/utils/3-eyes/` (GH-195). Use this skill to answer "what is my
machine scheduled to do, is it running, and why" and to pause/resume jobs — all
without editing plists by hand.

## First: locate the package and check activation

```bash
cd "$(git rev-parse --show-toplevel)/utils/3-eyes" 2>/dev/null || cd ~/Documents/rebalance-OS/utils/3-eyes
export PYTHONPATH="$PWD"
python3 -m three_eyes status        # ACTIVE vs INERT, live launchctl state, breaker state
```

If it prints **INERT**, that is expected on a fresh clone: 3-Eyes does nothing
until the operator opts in (`cp config/runtime.env.example config/runtime.env` and
set `THREE_EYES_ENABLE=1`). Report that rather than "trying to turn it on" — do not
create `runtime.env` yourself; activation is the operator's call.

## Commands

| Ask | Command |
|-----|---------|
| What jobs exist? | `python3 -m three_eyes list` |
| Full status (active, live, breakers) | `python3 -m three_eyes status` |
| Is the registry valid? | `python3 -m three_eyes validate` |
| What would `<job>` do? (no egress) | `python3 -m three_eyes dry-run <job>` |
| Why does `<job>` fire? | `python3 -m three_eyes why <job>` |
| Pause / resume `<job>` | `python3 -m three_eyes pause <job>` · `resume <job>` |
| Trigger `<job>` now (still gated) | `python3 -m three_eyes run <job>` |
| Regenerate the dashboard | `python3 -m three_eyes sync-dashboard` |

## Rules of engagement

- **Never edit `DASHBOARD.md` by hand** — it is generated from the TOML registry.
  To change what it shows, edit `registry/jobs.d/*.toml` then run `sync-dashboard`.
- **Adding a command to `registry/commands.allow` or activating a `gh-issue`
  route are operator acts** — surface the change, don't make it unprompted.
- `run`/`install` stay gated: on an inert clone they no-op by design. If the
  operator wants a job actually scheduled, point them at `install <job>` after
  they've activated 3-Eyes.
- To triage the raw launchd layer (all agents, not just 3-Eyes), use the
  companion `launchd-triage` skill.
