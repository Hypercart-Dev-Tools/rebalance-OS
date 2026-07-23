---
name: launchd-triage
description: Triage what's scheduled on this Mac — inventory every user LaunchAgent in ~/Library/LaunchAgents, explain what each one runs and when, and flag anything stale, broken, or duplicated. Read-only. Trigger on "what's in launchd", "what's scheduled on my mac", "triage launchd", "what launch agents do I have", "why does <label> keep running", "launchctl list".
---

# launchd triage (read-only)

Answer "what is scheduled to run on this machine, and is any of it wrong?" without
changing anything. This is the observe-first layer 3-Eyes is built on (GH-195):
look at the raw launchd surface, including agents 3-Eyes does not manage.

## Inventory (structured, via 3-Eyes)

```bash
cd ~/Documents/rebalance-OS/utils/3-eyes && export PYTHONPATH="$PWD"
python3 -m three_eyes observe        # every user LaunchAgent, [3eyes]-tagged if managed
```

## Raw launchd, direct

```bash
ls -1 ~/Library/LaunchAgents/*.plist                       # what's installed
launchctl list | grep -iE 'rebalance|neochro|3eyes'        # what's loaded (PID / last exit)
launchctl print gui/$(id -u)/<label>                       # deep state for one label
plutil -p ~/Library/LaunchAgents/<label>.plist             # readable plist dump
```

## Triage checklist

For each agent, report:

1. **What it runs** — `ProgramArguments[0]` + args; does the target file still exist?
2. **When** — `StartInterval` (seconds) or `StartCalendarInterval`; `RunAtLoad`?
3. **Loaded?** — is it in `launchctl list`? Last exit code non-zero = failing.
4. **Logs** — `StandardOutPath` / `StandardErrorPath`; tail them for recent errors.
5. **Smells** — a missing target binary, a plist present but not loaded (or vice
   versa), two agents doing the same job, an interval far too tight, an
   `sk-ant-…` placeholder left in an `EnvironmentVariables` block.

## Boundaries

- **Read-only.** Never `bootout`/`bootstrap`/`unload`/`load` or edit a plist as
  part of triage. Propose changes; let the operator run them.
- The `com.rebalance-os.*` and `com.neochro.*` agents predate 3-Eyes and are NOT
  3-Eyes-managed (no `com.rebalance-os.3eyes.` prefix). Migrating them into the
  3-Eyes registry is a deliberate, later step — flag candidates, don't move them.
