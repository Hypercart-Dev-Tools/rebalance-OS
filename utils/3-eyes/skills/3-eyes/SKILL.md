---
name: 3-eyes
description: Overall health + master catalog of every scheduled automation on this Mac (managed by 3-Eyes or not), PLUS the debugging scope/context for the three layers named "3-Eyes" (Rebalance collectors, the Gemma collector sentinel, and this launchd supervisor) and the cross-session interaction log. Reports fleet health (which launchd jobs are OK / FAILING / not-loaded), refreshes the machine-specific CATALOG.md if stale, and lists all device jobs whether or not 3-Eyes manages them yet. Also the control surface for managed jobs (pause/resume/dry-run). Trigger on "/3-eyes", "3 eyes", "job health", "are my automations ok", "what's scheduled on this machine", "refresh the catalog", "pause/resume <job>", "which sentinel jobs are failing", "debug the collectors", "what did the last 3-eyes session do".
---

# /3-eyes — health + catalog of every scheduled automation

3-Eyes (GH-195, `rebalance-OS/utils/3-eyes/`) is the unified, optional, inert-by-default local job
supervisor. This skill is the **operator dashboard**: one command answers "are my automations healthy,
is the catalog current, and what's running on this box?"

## 0. Scope check — which of the three layers is this?

"3-Eyes" names **three different things**, with different code, gates, and failure modes:

1. **Collectors** — `daily_sync`, `github_sync`, calendar/sleuth sync. Tool: `rebalance doctor`, logs.
2. **Collector Sentinel** — the local Ollama Gemma 4 12B detect→triage→repair→PR monitor. Design of
   record but **not scheduled** (its Phase 0 gate is open).
3. **Launchd Job Supervisor (GH-195)** — *this skill*: every scheduled launchd job on this Mac.

**This skill's fast path (§1–§4 below) is Layer 3 only.** If the request is about collector debugging,
sentinel tuning, known collector defects, or anything cross-layer, **read the full context spec first**:

```bash
cat ~/Documents/rebalance-OS/utils/3-eyes/skills/3-eyes/CONTEXT.md
```

`CONTEXT.md` carries the layer map, per-device activation rules, the known-defect register with live
GitHub issue states, the "how many jobs are managed" three-views trap, and the interaction-log spec.
Skip it for a plain "are my automations ok" health check — it is not needed for §1–§4.

## 0.5. Locate the package (run first)

```bash
cd "$(git -C ~/Documents/rebalance-OS rev-parse --show-toplevel 2>/dev/null)/utils/3-eyes" 2>/dev/null \
  || cd ~/Documents/rebalance-OS/utils/3-eyes
export PYTHONPATH="$PWD"
python3 -m three_eyes status | head -1     # ACTIVE vs INERT
```

**Check this per device — never assume.** Inert-by-default is the *repo* guarantee, not a claim about
the box you're on; `noels-Mac-Studio` reports **ACTIVE** (`config/runtime.env` + `THREE_EYES_ENABLE=1`).
Health, catalog, and observe all work read-only even when inert — do NOT create `runtime.env` yourself.

## 1. Fleet health (the headline)

```bash
python3 -m three_eyes health
```

Prints `N ok · M FAILING · K not-loaded · U unclassified` and a per-job line (✅ / ❌ / ◦), with the
failure-breaker state for 3-Eyes-managed jobs. **Lead your report with the FAILING jobs** — that's the
signal. A non-zero `last exit` on a launchd agent means its most recent run failed; launchd exit 78
(`EX_CONFIG`) means a stale job config, not necessarily a broken script — that was the `com.local.skill-sync`
diagnosis before 3-Eyes adopted it as the `skill-sync` job and retired the old plist.

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

⚠️ **"How many jobs are managed?" has three right answers** — never quote one as the whole truth:
`DASHBOARD.md` / `registry/jobs.d/` = committed registry only (fleet-portable); `three_eyes list` =
adds the gitignored machine-local overlay `registry/jobs.local.d/`; `CATALOG.md` = generated and may be
stale. Use `list` for "what actually runs here." Details in `CONTEXT.md` §4.

## 4. Control managed jobs

```bash
python3 -m three_eyes why <job>      # when/why a managed job fires + breaker state
python3 -m three_eyes dry-run <job>  # what it would do + route previews (no egress)
python3 -m three_eyes pause <job>    # quarantine · resume <job> to clear
python3 -m three_eyes run <job>      # trigger now (still gated: inert clones no-op)
```

## 5. Session history — what previous sessions did

Every Claude Code turn in `rebalance-OS` appends its request + outcome to a gitignored, **per-device**
log via a `Stop` hook (`utils/3-eyes-session-log.py`). Read it to pick up prior debugging context
instead of re-deriving it:

```bash
grep -c '^=== ' ~/Documents/rebalance-OS/temp/3-eyes.log  # how many turns logged
grep -n '^=== ' ~/Documents/rebalance-OS/temp/3-eyes.log | tail -20   # recent turn headers
tail -c 20000 ~/Documents/rebalance-OS/temp/3-eyes.log   # read the recent entries themselves
```

Entries look like `=== <ISO timestamp> | device <hostname> | session <8-char id> | cwd <path> ===`
followed by `REQUEST:` and `OUTCOME:` blocks. Scan the `=== ` header lines first, then read only the
entries you need — the file grows unbounded.

- **The log is written automatically.** You never append to it by hand; the hook owns it.
- ⚠️ **Path trap:** the live log is `temp/3-eyes.log` (a file at the repo root). An empty
  `temp/3-eyes/3-eyes.log` may exist inside the `temp/3-eyes/` *directory* — nothing writes to it.
- **Per-device.** Another Mac's sessions are not in this file. When reporting cross-device findings,
  quote the `device` field rather than assuming one box's history is the fleet's.
- **Absence is not proof.** The hook exits 0 silently on every failure path, so an empty or missing log
  may mean "not wired" rather than "no sessions." Smoke-test it by piping a payload with a real
  `transcript_path` into the script before concluding anything.

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
- **Keep `CONTEXT.md` honest.** It is the durable scope/context spec for all three layers and is
  committed alongside this file. If you discover a claim in it is stale — a job count, a gate state, an
  issue status, a device's ACTIVE/INERT state — fix it and add a changelog entry rather than working
  around it. This directory is symlinked into `~/.claude/skills/3-eyes`, so edits are live immediately.
- Raw launchd triage (all agents, plist internals) → the companion `launchd-triage` skill.
