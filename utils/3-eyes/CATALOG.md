# 3-Eyes — Master Automation Catalog

> **The human master list of every scheduled automation on this machine**, across all systems,
> until each is formally adopted into the 3-Eyes TOML registry. This is a **manually curated**
> companion to the auto-generated [`DASHBOARD.md`](DASHBOARD.md):
>
> - **`DASHBOARD.md`** = deterministic mirror of what 3-Eyes **manages** (the TOML registry). CI-checked.
> - **`CATALOG.md`** (this file) = the full inventory of what **exists**, managed or not, with an
>   adoption plan. Refresh the observed rows from `python -m three_eyes observe`.
>
> Companion registry for **ports & long-running servers** (Dify, MySQL, Cactus, tunnels, GCP): see
> [`~/bin/servers.md`](file:///Users/noelsaw/bin/servers.md). This catalog is the **scheduled-job** view;
> servers.md is the **listening-service** view. Together they are the "one roof."

**Last inventoried:** 2026-07-22 (from `three_eyes observe` — 38 launchd agents + 1 crontab).

## Status legend

| | Meaning |
|---|---|
| 🟢 **managed** | A 3-Eyes registry job (`registry/jobs.d/*.toml`) — scheduled + guarded + on the dashboard. |
| 👁 **observe-only** | 3-Eyes sees it (read-only) but does not own it. The current state of almost everything. |
| 🎯 **to-adopt** | A candidate to migrate into the registry (retire its hand-rolled plist → registry job). |
| ⚙️ **system** | Vendor/OS agent (Google, Setapp, Homebrew). Not ours — ignore. |

---

## 1. 3-Eyes (managed)

| Automation | Does what | Schedule | Entrypoint | Status |
|---|---|---|---|---|
| `com.rebalance-os.3eyes.selfcheck` | No-op that proves the guarded run→breaker→route loop | every 3600s | `shims/run-job.sh selfcheck` | 🟢 managed |
| `collector-health` *(declared, not installed)* | Rebalance collector freshness (see §4) | every 1800s | registry job | 🎯 to-adopt (needs the GH-146 log-parsing observer first) |

## 2. Claude · Skills & Prompt Logs

| Automation | Does what | Schedule | Entrypoint | Status |
|---|---|---|---|---|
| `com.local.skill-sync` | **Claude Skills sync** — syncs the giant-brains skills library | every 120s | `giant-brains-claude-skills/utils/skill-sync/skill-sync.sh` | 👁 → 🎯 **top adopt candidate** |
| `com.claude.prompt-log-to-md` | CLIO: render Claude prompt logs → markdown | every 300s | CLIO `prompt-log-to-md.sh` | 👁 to-adopt |

## 3. XYZ swarm

| Automation | Does what | Schedule | Entrypoint | Status |
|---|---|---|---|---|
| `com.xyz-3-agents-swarm.hq-marathon-scan` | HQ marathon-readiness scan | every 3600s | xyz-3-agents-swarm HQ | 👁 to-adopt |
| *(crontab)* git-bundle-snapshot | GH-233 daily backup bundle of xyz-3-agents-swarm | daily 09:00 | `xyz-3-agents-swarm/utils/git-bundle-snapshot.sh` | 👁 to-adopt |

## 4. Rebalance-OS · collectors & sync

| Automation | Does what | Schedule | Status |
|---|---|---|---|
| `com.rebalance-os.daily-sync` | Full daily collector sync (**GH-146: exits 0 even when degraded — parse `sync_outcome`**) | daily 06:30 | 👁 to-adopt |
| `com.rebalance-os.github-sync` | Hourly GitHub collector | hourly :45 | 👁 to-adopt |
| `com.rebalance-os.health-check` | Collector health probe | hourly :10 | 👁 to-adopt |
| `com.rebalance-os.health-check-triage` | LLM-triage + issue-file health failures | 3×/day :25 | 👁 to-adopt (⚠️ **would double-schedule the registry `collector-health` job — adopt as ONE**) |
| `com.rebalance-os.vault-sync` | Obsidian vault → collector | hourly :15 | 👁 to-adopt |
| `com.rebalance-os.pulse-sync` | HiQS pulse regenerate | hourly :00 | 👁 to-adopt |
| `com.rebalance-os.pulse-web-sync` | Pulse static web regenerate | 2×/hr | 👁 to-adopt |
| `com.rebalance-os.pulse-warning-watch` | Pulse warning watcher | 4×/hr | 👁 to-adopt |
| `com.rebalance-os.pulse-server` | FastAPI pulse web server (:8767) | on-demand (server) | ⚙️ server → servers.md |
| `com.rebalance-os.obsidian-daily-sync` | Obsidian daily sync | daily 18:20 | 👁 to-adopt |
| `com.rebalance-os.obsidian-rollover` | Obsidian daily-note rollover | daily 00:40 | 👁 to-adopt |

## 5. Cactus Needle & Sleuth sentinels (the other two "eyes")

| Automation | Does what | Schedule | Status |
|---|---|---|---|
| `com.neochro.sentinel-daemon` | **Cactus Needle PDDA sentinel** — watches cactus `PROJECT/**` docs | on-demand (poll 3s) | 👁 to-adopt (a 3-Eyes "eye") |
| `com.neochro.sentinel-daemon.sleuth-app` | **Sleuth** variant of the Needle sentinel | on-demand | 👁 to-adopt (a 3-Eyes "eye") |
| `com.neochro.needle-router` | Cactus Sentinel routing shim (:8082) | on-demand (server) | ⚙️ server → servers.md (⚠️ launcher path missing, see servers.md) |
| `com.neochro.cactus-serve` | Cactus Needle SLM OpenAI server (:8081) | on-demand (server) | ⚙️ server → servers.md |

## 6. GA4 → BigQuery daily pulls

| Automation | Does what | Schedule | Status |
|---|---|---|---|
| `com.neochro.ga-pull-binoid` | GA4→BQ pull, Binoid | daily 10:00 PT | 👁 to-adopt |
| `com.neochro.ga-pull-bounce` | GA4→BQ pull, Bounce | daily 10:05 PT | 👁 to-adopt |
| `com.neochro.ga-pull-bloomz` | GA4→BQ pull, Bloomz | daily 10:10 PT | 👁 to-adopt |

## 7. HQ · vault · misc automations

| Automation | Does what | Schedule | Status |
|---|---|---|---|
| `com.neochro.hq-rollup` | HQ ROADMAP rollup → Obsidian (via agy) | daily 17:50 | 👁 to-adopt |
| `com.neochro.servers-monitor` | Port/service conflict monitor (→ Resend email) | every 1800s | 👁 to-adopt |
| `com.user.git-pulse` | **Git Pulse Sync** — hourly git activity sync | every 3600s | 👁 to-adopt |
| `com.user.stickies2obsidian` | macOS Stickies → Obsidian | every 300s | 👁 to-adopt |
| `com.neochro.linkding-web` / `-tasks` / `-tunnel` | linkding server + huey worker + CF tunnel (:8090) | on-demand (servers) | ⚙️ servers → servers.md |

## 8. System / vendor (ignore — not ours)

`com.google.GoogleUpdater.wake`, `com.google.keystone.*`, `com.setapp.DesktopClient.*`,
`homebrew.mxcl.mysql`, `homebrew.mxcl.postgresql@17`.

---

## Adoption plan (how "observe-only" becomes "managed")

The north star: every 👁 row becomes a 🟢 registry job, one careful migration at a time. Per adoption:

1. Add a `registry/jobs.d/<name>.toml` — an allowlisted health/observe command + schedule + rules + routes.
2. `python -m three_eyes install <name>` (renders + loads the launchd/cron entry from the registry).
3. **Retire the old hand-rolled plist** so nothing is double-scheduled (the key risk — see the
   `health-check-triage` ⚠️ above).
4. It now appears in the CI-checked `DASHBOARD.md` automatically.

**Suggested first adoptions (low risk, high signal):**
- 🎯 `skill-sync` (Claude Skills) — self-contained, frequent, easy to health-check.
- 🎯 `git-pulse` (Git Pulse Sync) — self-contained, hourly.
- 🎯 the two **Needle/Sleuth sentinels** — they *are* two of the three eyes; unifying them is the point.

**Not yet:** `collector-health` needs its real log-parsing observer first (GH-146: exit codes lie).
