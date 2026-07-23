---
name: 3-eyes
description: Overall health + master catalog of every scheduled automation on this Mac (managed by 3-Eyes or not). Reports fleet health (which launchd jobs are OK / FAILING / not-loaded), refreshes the machine-specific CATALOG.md if stale, and lists all device jobs whether or not 3-Eyes manages them yet. Also the control surface for managed jobs (pause/resume/dry-run). Trigger on "/3-eyes", "3 eyes", "job health", "are my automations ok", "what's scheduled on this machine", "refresh the catalog", "pause/resume <job>", "which sentinel jobs are failing".
---

# /3-eyes — health + catalog of every scheduled automation

3-Eyes (GH-195, `rebalance-OS/utils/3-eyes/`) is the unified, optional, inert-by-default local job
supervisor. This skill is the **operator dashboard**: one command answers "are my automations healthy,
is the catalog current, and what's running on this box?"

## 0. Locate the package (run first)

```bash
cd "$(git -C ~/Documents/rebalance-OS rev-parse --show-toplevel 2>/dev/null)/utils/3-eyes" 2>/dev/null \
  || cd ~/Documents/rebalance-OS/utils/3-eyes
export PYTHONPATH="$PWD"
python3 -m three_eyes status | head -1     # ACTIVE vs INERT
```

INERT is expected until the operator opts in (`config/runtime.env` + `THREE_EYES_ENABLE=1`). Health,
catalog, and observe all work read-only even when inert — do NOT create `runtime.env` yourself.

## 1. Fleet health (the headline)

```bash
python3 -m three_eyes health
```

Prints `N ok · M FAILING · K not-loaded` and a per-job line (✅ / ❌ / ◦), with the failure-breaker
state for 3-Eyes-managed jobs. **Lead your report with the FAILING jobs** — that's the signal. A
non-zero `last exit` on a launchd agent means its most recent run failed (e.g. `com.local.skill-sync`
exit 78 = the Claude Skills sync is broken).

## 2. Catalog freshness — check, refresh if stale

```bash
python3 -m three_eyes catalog --check || python3 -m three_eyes catalog --write
```

`catalog --check` exits non-zero when `CATALOG.md` is stale — an agent was added (**unclassified** — not
yet in `registry/catalog-notes.toml`) or removed, or the render drifted. On stale, `--write`
regenerates it. `CATALOG.md` is **machine-specific and gitignored** (Time Machine backs it up); the
committed source of truth is `registry/catalog-notes.toml`. If `--check` reports an **unclassified**
agent, tell the operator its label and offer to add an `[agent."<label>"]` block to `catalog-notes.toml`.

## 3. Full device inventory (managed or not)

```bash
python3 -m three_eyes observe     # every LaunchAgent, [3eyes]=managed
python3 -m three_eyes list        # just the jobs 3-Eyes MANAGES (the registry)
```

`CATALOG.md` (from step 2) is the annotated, grouped-by-system version of this — prefer showing it.

## 4. Control managed jobs

```bash
python3 -m three_eyes why <job>      # when/why a managed job fires + breaker state
python3 -m three_eyes dry-run <job>  # what it would do + route previews (no egress)
python3 -m three_eyes pause <job>    # quarantine · resume <job> to clear
python3 -m three_eyes run <job>      # trigger now (still gated: inert clones no-op)
```

## What to report back

A tight summary, in this order:
1. **Health verdict** — "N ok, M failing" + name each FAILING job and its exit code.
2. **Catalog** — current, or refreshed (say what changed / what's unclassified).
3. **Adoption nudge** — the top `🎯 to-adopt` candidate from CATALOG.md's "Suggested next adoptions".

## Rules of engagement

- **Never hand-edit `CATALOG.md`** (generated) or `DASHBOARD.md` (generated from the registry). To
  change the catalog's annotations, edit `registry/catalog-notes.toml` then `catalog --write`.
- **Adopting an observed job into the registry retires its old plist** — never leave both scheduling the
  same work (the `health-check-triage` ⚠️ in the catalog). That's an operator-confirmed migration.
- Raw launchd triage (all agents, plist internals) → the companion `launchd-triage` skill.
