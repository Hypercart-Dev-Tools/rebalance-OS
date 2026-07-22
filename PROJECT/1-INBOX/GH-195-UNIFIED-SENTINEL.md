---
gh_issue: 195
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/195
title: "3-Eyes — unified, optional, always-safe local job supervisor (XYZ / PDDA / Rebalance collectors)"
slug: three-eyes
codename: 3-Eyes
status: "SKETCH — 4 gating questions locked 2026-07-22; ready to author P0 (2 non-gating questions open)"
created: 2026-07-22
updated: 2026-07-22
owner: Noel (operator) · Claude (architect)
doc_type: project
goal: >
  Unify the three sentinels we run today (XYZ GH-281 debug flywheel, Cactus Needle PDDA sentinel,
  Rebalance collector-health sentinel) into one optional, local-first, Python-first job supervisor
  living in rebalance-OS/utils/3-eyes/. Inert by default (no host repo needs it), always-on if the
  operator opts in, with a registry of safe commands/rules/routes, launchd/cron scheduling, circuit
  breakers + pressure-relief valves, an MCP + Claude skill to talk to jobs, and a DASHBOARD.md that
  100% mirrors live job state.
effort: 4
complexity: 4
risk: 3
phases: 5
ratings_provisional: true
non_goals:
  - Not making any of the three host repos depend on the sentinel — each still works standalone
  - Not rewriting cactus/sleuth/collector-health sentinels in one shot (wrap first, migrate later)
  - Not auto-merging fixes or auto-running unknown commands — the two irreversible edges stay human
  - Not spinning off to its own repo yet — it lives in rebalance-OS/utils/ until a spin-off trigger fires
related:
  - PROJECT/1-INBOX/GH-144-SENTINEL-PROMPT.md            # one-shot rebalance collector sentinel (Agy)
  - PROJECT/2-WORKING/AGY-SENTINEL.md                    # general collector sentinel (referenced by GH-144)
  - utils/job_guard.py                                   # GH-172 circuit breakers to wrap
  - scripts/health_issue_reporter.py                     # LLM budget-cap pressure-relief pattern to reuse
  - "xyz-3-agents-swarm: PROJECT/2-WORKING/GH-281-SENTINEL-TIER2-OVERLAY.md"  # inert-by-default gate pattern
---

# GH-195 · Unified Sentinel (optional, Python-first local job supervisor)

## Status

| What was just completed | What's next |
|---|---|
| Landscape scoped; three sentinels + reusable rebalance primitives identified; Python-first sketch + phasing drafted; issue #195 filed; **codename 3-Eyes** + 4 gating decisions locked. | Author P0: TOML registry schema + `config.py` inert gate + `dashboard.py` generator (TOML→DASHBOARD on every change) + `launchd-triage` skill. |

## Decisions locked (2026-07-22)

1. **Codename: 3-Eyes** — nod to XYZ; the three "eyes" are XYZ-debug · Cactus-Needle-PDDA ·
   Rebalance-collectors. Full naming rationale backfilled later. Directory `utils/3-eyes/`, Python
   package `three_eyes` (valid identifier), CLI `python -m three_eyes` (console alias `3eyes`).
2. **Observe-first.** P0/P1 read the existing 14 `com.rebalance-os.*` / `com.neochro.*` launchd agents
   read-only; 3-Eyes *editing/owning* plists is an available option at P2, not P0.
3. **Dedicated dashboard** at `utils/3-eyes/DASHBOARD.md` — does NOT touch the existing top-level
   `DASHBOARD.md` (code-quality matrix).
4. **Registry = TOML** (stdlib `tomllib`, 3.11+ — stays on the stdlib launchd run-path). The registry is
   authored in TOML; **`DASHBOARD.md` is auto-regenerated from the TOML on every change** (write hook +
   pre-commit + CI `--check`), so the human-readable dashboard can never lag the source of truth.

**Still open (non-gating, can decide during P2/P3):** (5) does "talk to jobs" mutate (pause/resume/
trigger) or stay read-only Q&A; (6) the spin-off-to-own-repo trigger.

## Why this exists

We run **three** sentinels today, each hand-wired, each with its own scheduling, safety, and reporting:

1. **XYZ GH-281 Sentinel Debug Flywheel** (`xyz-3-agents-swarm`) — `debug.log` → Gemma classify → PDDA
   draft → marathon. Ships inert-by-default (PR #285/#287).
2. **Cactus Needle PDDA sentinel** — `com.neochro.sentinel-daemon` launchd →
   `cactus/tools/sentinel-daemon.sh` (+ a `sleuth-app` variant).
3. **Rebalance collector-health sentinel** — Agy desktop, watches collector activity from GitHub,
   Slack/Sleuth, Gmail, Google Calendar, Zapier, etc. (see [GH-144](GH-144-SENTINEL-PROMPT.md)).

Applying the lens of **XYZ** (swarm/marathon/relay), **PDDA** (lifecycle + selection rule), and the
**Rebalance collectors** (activity ingest), these are the same shape wearing three coats: *a scheduled,
safety-bounded local job that observes a signal, classifies it locally, and routes a finding.* This
sketch unifies them under one system so there is **one** registry, **one** set of circuit breakers,
**one** dashboard, and **one** way to talk to your jobs.

It lives in `rebalance-OS/utils/3-eyes/` for now; it spins off to its own repo only when a spin-off
trigger fires (open question #6).

## Operator requirements (verbatim intent)

- **Optional** — the 3 repos each work standalone without it.
- **Always-on** if the user installs it and wants it that way.
- A **registry** of schedulable *safe commands*, *rules*, and *routes*.
- **Launchd-aware** — a Claude **skill** that triages what's in `~/Library/LaunchAgents` / `launchctl`.
- Uses **launchd or cron** for scheduling.
- **Safety circuit breakers and pressure-relief valves.**
- **MCP + Claude Skill** so the user can *talk with* their sentinel jobs.
- A human-readable **DASHBOARD.md that 100% mirrors** the current jobs in the system.
- **Compatible with our suite & ecosystem** — XYZ, PDDA, `tick`, `relay`, Cactus Needle, Rebalance
  collectors, and the Guiding Principles (local-first, reversibility, verified-success-only).

## Language posture — Python-first

**Implementation is Python**, matching the repo's Python-default posture. **Bash only when absolutely
needed** — the sole unavoidable case is the shim launchd `ProgramArguments` execs, and even that is a
one-line `exec python3 -m three_eyes.run <job>`. All logic (registry, breakers, relief, launchd/cron
rendering, classify, routes, DASHBOARD generation, MCP) is Python, **stdlib-first** like `job_guard.py`
so it runs under system `python3` inside launchd jobs and inside the rebalance venv without an install
step. Third-party deps (e.g. a YAML parser) are additive and confined to the venv path; the launchd
run-path degrades to stdlib.

## Reuse, don't reinvent (already in rebalance-OS)

| Requirement | Existing asset to wrap |
|---|---|
| Circuit breakers | `utils/job_guard.py` (GH-172) — `SingleInstanceLock` + `MemoryCeiling`, kernel-panic-hardened, stdlib-only |
| Pressure-relief valves | `scripts/health_issue_reporter.py` LLM budget caps (`--llm-daily-limit 8`, `--llm-max-per-run 5`) |
| Optional / opt-in gate | GH-281 inert-by-default (`runtime.env` gitignored + `SENTINEL_ENABLE=1`) |
| Classifier | Ollama `gemma4:12b-mlx` (13B, nvfp4, 131k ctx) — needs sandbox-off for `localhost:11434` |
| File-an-issue lifecycle | PDDA selection rule + 1-INBOX→2-WORKING→3-COMPLETED + `pdda.sh` |
| Whose-turn / audit / auto-fix | `tick` events + `relay-xyz` (builders = Codex/agy, Claude orchestrates) |
| De-facto job registry today | the 14 `com.rebalance-os.*` / `com.neochro.*` launchd plists in `~/Library/LaunchAgents` |

## Proposed shape (`utils/3-eyes/`)

```
utils/3-eyes/
  README.md                  # what it is; activation; inert-by-default statement
  three_eyes/                # the Python package (valid identifier for the "3-Eyes" product)
    __main__.py              # `python -m three_eyes` CLI: list|status|pause|resume|dry-run|why|sync-dashboard
    run.py                   # single job entrypoint launchd/cron execs
    config.py                # the single activation gate (three_eyes_active)
    registry.py              # load/validate jobs.d/*.toml + commands.allow + routes.toml (stdlib tomllib)
    breakers.py              # wraps job_guard: single-instance + mem ceiling + failure-count trip + global kill-switch
    relief.py                # budgets (daily/per-run LLM+API caps), backoff, quiet-hours, max-concurrent
    launchd.py               # generate/load/unload plists FROM the registry; read launchctl state
    cron.py                  # crontab alternative to launchd, same registry source
    classify.py              # ONLY ollama caller (gemma4:12b-mlx), stubbable
    routes.py                # ONLY gh/git-push caller, gated
    dashboard.py             # render DASHBOARD.md from registry ⋈ launchctl; --check asserts no drift
  registry/
    jobs.d/*.toml            # one file per job: command (allowlisted) · schedule · rules · routes · breakers
    commands.allow           # the ONLY commands a job may execute
    routes.toml              # where findings go: gh-issue | pdda-inbox | notify | log-only
  shims/run-job.sh           # ONLY bash file: one-line `exec python3 -m three_eyes.run "$@"` for launchd
  hooks/regen-dashboard      # pre-commit hook: on any registry/*.toml change, regenerate + stage DASHBOARD.md
  skills/launchd-triage/     # Claude skill: read ~/Library/LaunchAgents + launchctl print, explain/triage
  skills/three-eyes/         # Claude skill: talk to your jobs (calls the MCP)
  mcp/server.py              # MCP: list_jobs, job_status, pause/resume, why_fired, dry_run, dashboard
  DASHBOARD.md               # GENERATED from the TOML registry ⋈ live launchctl — never hand-edited
  config/runtime.env.example # documents the gitignored activation settings
  config/.gitignore          # ignores runtime.env
  tests/                     # pytest: inert-by-default proof · dashboard-mirror invariant · breaker trips · egress static-guard
```

### A job, conceptually (one `registry/jobs.d/*.toml`)

```toml
id = "rebalance-collector-health"
command = "collector-health-check"          # MUST be a key in commands.allow

[schedule.launchd]
StartInterval = 1800                         # or [schedule.cron] expr = "*/30 * * * *"

[rules]                                       # when to act on the observed signal
fire_when  = "stale_minutes > 90"
quiet_hours = "22:00-07:00 PT"

[breakers]                                    # per-job safety
single_instance   = true
max_rss_gb        = 8
trip_after_failures = 3                       # open the breaker → quarantine + notify

routes = ["pdda-inbox", "notify"]            # where a finding goes (pdda-inbox → PDDA selection rule)

[relief]
llm_daily_max   = 8
llm_per_run_max = 5
```

### TOML → DASHBOARD.md (the human-readable mirror)

The registry is authored in TOML; `DASHBOARD.md` is a **generated projection** of it, refreshed on
**every** registry change via three redundant triggers so it can never drift:

- **On write** — `python -m three_eyes sync-dashboard` regenerates it (any CLI mutation calls this).
- **Pre-commit** — `hooks/regen-dashboard` regenerates + stages `DASHBOARD.md` whenever a
  `registry/*.toml` is staged, so a commit that changes a job can't land a stale dashboard.
- **CI** — `dashboard.py --check` fails if the committed `DASHBOARD.md` differs from a fresh render.

## Load-bearing invariants (the safety spine)

1. **Inert by default (tested, not asserted).** No `runtime.env` (or `THREE_EYES_ENABLE != 1`) ⇒ the
   whole system is a clean no-op: **zero** network / `ollama` / `gh` / launchd-load / cron-write /
   marathon fire. A single `config.three_eyes_active()` gate decides activation; all egress routes
   through `classify.py` / `routes.py`. Proven by `tests/test_inert_by_default.py` with fail-loud stubs.
2. **DASHBOARD ≡ reality.** `DASHBOARD.md` is **generated** by `dashboard.py` from the TOML `registry ⋈
   launchctl` live state, regenerated on every registry change (write hook + pre-commit + CI).
   `dashboard.py --check` fails CI if the committed file drifts — it can never become a hand-edited lie.
   This is the literal "100% mirror" guarantee.
3. **Registry is the single source of truth.** launchd/cron entries are *rendered from* the registry, not
   authored by hand. "The dashboard mirrors the jobs" and "the jobs mirror the registry" become one
   statement.
4. **Safe-command allowlist.** A job may only execute a command declared in `commands.allow`; anything
   else refuses and trips. No free-form command execution, ever.
5. **Circuit breakers (wrap `job_guard.py`).** Single-instance lock + memory ceiling (existing), plus a
   per-job failure-count breaker (open after N consecutive failures → quarantine the job, stop
   re-scheduling, notify) and a **global kill-switch** (`THREE_EYES_ENABLE=0` or a `PANIC` file halts all).
6. **Pressure-relief valves.** Daily + per-run LLM/API budgets (the `health_issue_reporter` pattern),
   exponential backoff on repeated failure, quiet-hours, and a max-concurrent-jobs cap so the box never
   thrashes (the GH-172 kernel-panic lesson, generalized).
7. **Two irreversible edges stay human.** *What to run* (adding a command to the allowlist) and *what to
   ship/push* (any `gh`/`git push` route) require the operator — never auto-decided (CONSTITUTION).
8. **Ecosystem compatibility.** Findings that file issues follow the **PDDA** selection rule
   (`eligible = risk<=2 AND not ratings_provisional`; route-to-human on `risk>=4 OR provisional OR
   foreign repo`) and land as `1-INBOX` captures with a Swarm Preflight Contract; whose-turn/auto-fix
   uses `tick` + `relay-xyz`; auto-fix marathons go through XYZ's `marathon-drive.sh` unchanged.

## Phasing

- **P0 — observe-only skeleton.** Registry schema + `config.py` inert gate + read-only `dashboard.py`
  generator + `launchd-triage` skill. Loads nothing, writes no plists, files nothing. Ships inert.
- **P1 — safety + scheduling.** `breakers.py` (wrap `job_guard`) + `relief.py` + `launchd.py`/`cron.py`
  adapters that *render* schedules from the registry. Still no host-repo behavior change.
- **P2 — adopt the three sentinels.** Register the existing XYZ / Cactus-Needle / collector-health
  sentinels into `registry/jobs.d/` — **wrap first** (observe their current plists), then migrate to
  registry-rendered plists one at a time. No big-bang rewrite.
- **P3 — conversational layer.** `mcp/server.py` + `/three-eyes` skill: list, status, pause/resume,
  why-fired, dry-run.
- **P4 — routes + review.** PDDA/GH routing, adversarial red-team (Gemma), morning report.

## Acceptance (P0 slice, to firm up after open questions)

1. No `runtime.env` → `tests/test_inert_by_default.py` green: every entrypoint no-ops, zero egress.
2. `dashboard.py --check` green on a seeded registry; drift a job and it fails (mirror invariant proven).
3. `commands.allow` enforced: a job referencing an unlisted command refuses (unit test).
4. `launchd-triage` skill reads `~/Library/LaunchAgents` + `launchctl print` and explains each agent.
5. Registered in the repo's test runner (pytest); Python-first (only `shims/run-job.sh` is Bash).

## Open questions

**Resolved 2026-07-22 (see Decisions locked):**
1. ~~Own the plists or observe first?~~ → **Observe-first** (P0/P1); editing is a P2 option.
2. ~~DASHBOARD collision?~~ → **Dedicated** `utils/3-eyes/DASHBOARD.md`.
3. ~~Name?~~ → **3-Eyes**.
4. ~~Registry format?~~ → **TOML** (stdlib `tomllib`), with auto-regenerated `DASHBOARD.md` on every change.

**Still open (non-gating, decide during P2/P3):**
5. **"Talk to jobs" scope.** Read-only Q&A only, or also mutate (pause/resume/trigger) via MCP?
6. **Spin-off trigger.** What event graduates this from `rebalance-OS/utils/` to its own repo?
