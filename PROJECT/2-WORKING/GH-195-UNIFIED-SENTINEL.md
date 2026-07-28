---
gh_issue: 195
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/195
title: "3-Eyes — unified, optional, always-safe local job supervisor (XYZ / PDDA / Rebalance collectors)"
slug: three-eyes
codename: 3-Eyes
status: >
  Active — REVISED 2026-07-28 after an audit against the running system. P0/P1/P3/P5 stand.
  P4 is DOWNGRADED: two of its claimed deliverables (adversarial red-team, morning report) do not
  exist in the tree. P2 is REWRITTEN: Cactus-Needle was deleted on 2026-07-27 so "adopt the three
  sentinels" is unachievable as worded; the new target is the full 21-job fleet. Three new phases
  (P6 breaker semantics, P7 Gemma wiring, P8 fleet adoption) carry the remaining work.
created: 2026-07-22
updated: 2026-07-28
owner: Noel (operator) · Codex (implementation) · Claude Code (review/tuning)
doc_type: project
goal: >
  Unify the three sentinels we run today (XYZ GH-281 debug flywheel, Cactus Needle PDDA sentinel,
  Rebalance collector-health sentinel) into one optional, local-first, Python-first job supervisor
  living in rebalance-OS/utils/3-eyes/. Inert by default (no host repo needs it), always-on if the
  operator opts in, with a registry of safe commands/rules/routes, launchd/cron scheduling, circuit
  breakers + pressure-relief valves, an MCP + Claude skill to talk to jobs, and a DASHBOARD.md that
  100% mirrors live job state.
effort: 5
complexity: 4
risk: 3
phases: 8
ratings_provisional: false
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
| **Audit against the running system (2026-07-28).** Compared every phase claim to the live machine. Result: the safety spine works, the *value* path was never connected. Findings recorded in [Audit 2026-07-28](#audit-2026-07-28--doc-vs-running-system). Doc revised: P4 downgraded, P2 rewritten, P6/P7/P8 added. | **P6 first** — it is small and it unblocks a job that is dead right now. Then P7 (wire Gemma to something), then P8 (fleet adoption). |

## Audit 2026-07-28 — doc vs. running system

The doc said P0–P5 were essentially done. The machine says otherwise. Six findings, in the order
they matter.

**A1 — The classifier has never run. Not once.**
`ollama ps` is empty; the 10 GB `gemma4:12b-mlx` is on disk and has never been resident.
`classify.classify()` is reachable from exactly one place — `run.py:_process_emit`, which fires
only when a job drops a finding file at its emit path. `collector-health` has run every 30 minutes
for days, exited `0` every time, and dropped **zero** finding files. So the classifier has no
input path at all. The operator installed a 12B model specifically to have "a smarter model keeping
an eye on things," and nothing was ever wired to ask it a question. **This is the central failure of
the project so far** — the safety machinery was built to a high standard around an empty centre.

**A2 — P4's two headline deliverables do not exist.**
P4 is recorded as "completed — PDDA/GH routing, adversarial red-team (Gemma), morning report."
`grep -ri 'morning|red.team|adversarial' utils/3-eyes/` returns **zero matches**. Routing exists;
the red-team and the morning report were never written. This also settles a recurring operator
question: **there is no feedback/improvement loop in 3-Eyes, and never was.**

**A3 — A tripped breaker is permanent, and loud.**
`run.py:140` computes `ok = code == 0`, so `job_guard`'s *preflight refusal* (exit 4, "refusing to
start: only 0.3 GB available, floor is 7.7 GB") is counted as a job failure. Three of those in a row
latched `skill-sync`'s breaker. Quarantine then skips the *run* but does not unload the *plist* —
launchd keeps firing every 120 s, and each wake appends a finding. **72 of the 73 records in
`findings.jsonl` are the single line `"skill-sync quarantined"`.** Invariant 6 promises exponential
backoff; the quarantined path has none. The findings log — the system's only evidence channel — is
99% noise about its own dead job.

**A4 — The three refusals that latched it were an unrelated regression.**
They came from the GH-219 Lane 4 window in which `available_memory_bytes()` briefly measured *free*
memory only and reported ~1.5 GB against a 7.7 GB floor. That guard bug is fixed. The breaker it
tripped is still latched, because nothing resets it. A transient condition in a *different* project
killed a 3-Eyes job permanently and silently — exactly the class of thing 3-Eyes exists to catch.

**A5 — P2 is unachievable as worded, and the fleet is barely covered.**
P2 says "adopt the three sentinels — XYZ / Cactus-Needle / collector-health." Cactus-Needle was
disabled and deleted on 2026-07-27 (four `com.neochro.*` agents parked in
`~/Library/LaunchAgents/.disabled-cactus-sentinel-2026-07-27/`), so one third of P2 can never be
done. Meanwhile `CATALOG.md` reports **3 managed · 21 to-adopt** — and the to-adopt list contains
every job that actually breaks: `vault-sync` (currently `FAIL(exit 1)`), `github-sync`, `daily-sync`,
`health-check`, `health-check-triage`.

**A6 — Not a defect: the two-registry split.**
`skill-sync` is *not* unregistered, contrary to an earlier report in this repo. It lives in
`registry/jobs.local.d/`, the gitignored overlay for jobs whose commands point at absolute
machine-specific paths. `DASHBOARD.md` deliberately renders only the committed `jobs.d/` set, so a
local job is invisible there but visible to `status` / `health` / `CATALOG.md`. Working as designed;
the surprise is a documentation problem, not a drift problem.

## Decisions locked (2026-07-28)

Taken by the operator after the audit above.

7. **Gemma gets three jobs, not one.** All three surfaces in [P7](#p7--wire-gemma-to-something-new):
   a **daily digest** across the whole fleet, **findings triage** as originally designed, and a
   **failure explainer** that runs on a job's non-zero exit. The digest is sequenced first because
   it is the only one that does not depend on a collector emitting findings.
8. **Guard refusals are not failures, and breakers recover.** Both fixes in
   [P6](#p6--breaker-semantics-new): stop counting `job_guard` exits 3/4 toward the failure
   counter, *and* add a half-open retry after a cooldown.
9. **Adopt the whole fleet.** [P8](#p8--fleet-adoption-rewritten-p2) targets all 21 `to-adopt`
   agents, in waves — not a permanent observe-only posture, and not a partial adoption.
10. **Two delivery channels: `notify` and `gh-issue`.** macOS banner for immediacy, GitHub issue for
    durability. `pdda-inbox` stays available but is not a default route. **`gh-issue` stays gated
    behind duplicate suppression** — #139 was closed by *deleting* a duplicate-issue emitter, and
    P8 must not stand up a second one.

## Table of contents

- [Audit 2026-07-28 — doc vs. running system](#audit-2026-07-28--doc-vs-running-system)
- [Decisions locked 2026-07-22](#decisions-locked-2026-07-22) · [2026-07-28](#decisions-locked-2026-07-28)
- [Why this exists](#why-this-exists)
- [Operator requirements](#operator-requirements-verbatim-intent)
- [Language posture](#language-posture--python-first)
- [Reuse, don't reinvent](#reuse-dont-reinvent-already-in-rebalance-os)
- [Proposed shape](#proposed-shape-utils3-eyes)
- [Load-bearing invariants](#load-bearing-invariants-the-safety-spine)
- [Phasing](#phasing)
- [Acceptance](#acceptance-p0-slice-to-firm-up-after-open-questions)
- [Collector-health domain knowledge](#collector-health-domain-knowledge-from-the-prior-agygemini-sentinel-handoff)
- [Open questions](#open-questions)

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

> **Historical note (2026-07-28).** The "three sentinels" framing above is the 2026-07-22 design
> record and is kept for provenance, but **eye #2 no longer exists**: the Cactus Needle sentinel was
> disabled and deleted on 2026-07-27 (its four `com.neochro.*` agents are parked in
> `~/Library/LaunchAgents/.disabled-cactus-sentinel-2026-07-27/`). It had kept running for weeks
> *because* P2's "adopt Cactus-Needle" step was never completed — 3-Eyes shipped alongside it rather
> than replacing it, and no one noticed a 12B model was being woken to supervise a 28M one. The name
> "3-Eyes" is now historical rather than literal. The scope that replaces it is
> [P8](#p8--fleet-adoption-rewritten-p2): one supervisor for the whole 21-agent fleet.

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
2. **DASHBOARD ≡ registry (100% mirror of the source of truth).** `DASHBOARD.md` is a **deterministic
   generated projection of the TOML registry** — same registry in, byte-identical markdown out —
   regenerated on every registry change (write hook + pre-commit + CI). `dashboard.py --check` fails CI
   if the committed file drifts, so it can never become a hand-edited lie. It mirrors the **registry**
   (what jobs exist and how they are configured), which is the single source of truth; the volatile
   launchctl run-state overlay ("loaded right now?") is a separate `python -m three_eyes status` / MCP
   query and is deliberately NOT baked into the committed file (it must be reproducible in CI, where no
   launchd agents exist). The design record's earlier "registry ⋈ launchctl" phrasing is superseded by
   this static-registry-mirror contract (GH-195 review S9).
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

- **P0 — observe-only skeleton — completed.** Registry schema + `config.py` inert gate + read-only
  `dashboard.py` generator + `launchd-triage` skill. Loads nothing, writes no plists, files nothing.
- **P1 — safety + scheduling — completed.** `breakers.py` (wrap `job_guard`) + `relief.py` +
  `launchd.py`/`cron.py` adapters that render schedules from the registry.
- **P2 — adopt the three sentinels — SUPERSEDED (2026-07-28).** Unachievable as worded: Cactus-Needle
  was deleted on 2026-07-27, so one of its three named targets no longer exists. What it did deliver
  stands — `collector-health` and `selfcheck` are registered and managed, and `skill-sync` was adopted
  into the `jobs.local.d/` overlay. The remaining ambition (own the machine's scheduled work) is
  restated at fleet scale in **[P8](#p8--fleet-adoption-rewritten-p2)**. Do not work P2; work P8.
- **P3 — conversational layer — completed.** `mcp/server.py` + `/three-eyes` skill: list, status,
  pause/resume, why-fired, dry-run.
- **P4 — routes + review — PARTIALLY COMPLETE (corrected 2026-07-28).** PDDA/GH **routing shipped**
  and works (`registry/routes.toml` declares `log-only`, `notify`, `pdda-inbox`, `gh-issue`; `routes.py`
  dispatches with dead-lettering on partial failure). The **adversarial red-team (Gemma)** and the
  **morning report** were never written — zero matches in the tree (audit A2). Both are re-scoped into
  **[P7](#p7--wire-gemma-to-something-new)**. This entry previously read "completed"; that was wrong.
- **P5 — editable Gemma instructions — completed on this branch.** The local model's safety and
  classification instructions now live in `utils/3-eyes/three_eyes/gemma_system_instructions.md`,
  separate from the per-finding prompt. `classify.py` reads the file at inference time, sends it as
  Ollama's `system` message, and fails closed if it is unavailable. The focused integration test proves
  the model payload carries the file contents and the configured model name. **QA gate:**
  `pytest utils/3-eyes/tests` → 94 passed. *Caveat (audit A1): this surface has never been exercised
  in production, because nothing has ever called `classify()`. P7 is what makes P5 real.*

### P6 — breaker semantics (new)

**Why now:** a job is dead on the machine as you read this, and the system that was supposed to
notice is the system that killed it (audit A3/A4). Smallest phase here, highest immediate payoff.

- [ ] **Guard refusals are not failures.** `run.py:140` currently does `ok = code == 0`, folding
      `job_guard`'s exit 3 (instance conflict) and exit 4 (memory preflight refusal) into the failure
      counter. Both mean *deferred*, not *broken*. Classify them as a third outcome — `deferred` — that
      leaves the counter untouched. A busy machine must never be able to quarantine a healthy job.
- [ ] **Half-open recovery.** Add a cooldown: a quarantined job becomes eligible for exactly one probe
      run after N minutes (proposed default 60). Success closes the breaker; failure re-opens it and
      doubles the cooldown. This is invariant 6's promised backoff, which the quarantine path never had.
- [ ] **Quarantine must be quiet.** Today each of the 720 daily wakes of a quarantined 120 s job appends
      a `log-only` finding. Either unload the plist on quarantine (preferred — a quarantined job should
      stop *being scheduled*, as `breakers.py:10` already claims it does) or collapse repeats into a
      single record with a count. Both, ideally.
- [ ] **Purge the noise and un-latch `skill-sync`.** 72 of 73 records in `findings.jsonl` are the same
      line. Archive the file, then `three_eyes resume skill-sync`.
- [ ] Investigate the one-off `3-eyes: no Python with tomllib (>=3.11) found on this host` in
      `skill-sync.err.log`. `.venv/bin/python` is 3.13 and has `tomllib`, so the shim's first candidate
      should always hit — this fired anyway (suspect: reboot, before the volume was ready). Decide
      whether the shim should retry rather than exit 3.

**QA gate — P6**
- [ ] A test drives three consecutive exit-4 guard refusals and asserts the breaker stays **closed**
      (mutation-check it: make refusals count again, and the test must fail).
- [ ] A test drives `trip_after_failures` real failures, advances the clock past the cooldown, and
      asserts exactly one probe run is permitted.
- [ ] `findings.jsonl` gains at most one record per quarantine episode, not one per wake.

### P7 — wire Gemma to something (new)

**Why now:** the whole reason a 12B model is on this machine. Three surfaces (decision 7), sequenced
cheapest-first. Each is independently useful — do not gate the digest on the observer.

- [ ] **P7a — daily digest.** A new registry job runs once each morning, gathers the previous day's
      launchd exit codes and log tails across the whole catalogue, and has Gemma write one ranked
      "what broke, what matters, what to ignore" report. **Depends on nothing** — it reads state that
      already exists, so it does not wait on the collector-health observer. This is the deliverable
      that most directly matches the operator's original intent.
- [ ] **P7b — failure explainer.** On any job's non-zero exit, hand Gemma that job's log tail and ask:
      known-benign, or new? Feeds the known-issues suppression list rather than a route. Cheap, and it
      is the prerequisite that makes `gh-issue` safe to enable in P8.
- [ ] **P7c — findings triage (the original design).** Build the real `collector-health` observer so it
      emits finding files: tail `temp/logs/daily_sync_*.log`, parse the trailing JSON
      (`sync_outcome: degraded|complete`), wait for the terminal marker, and apply the known-issues
      suppression list. See [Collector-health domain knowledge](#collector-health-domain-knowledge-from-the-prior-agygemini-sentinel-handoff)
      and GH-146 — **exit codes lie here**, a naive exit-status observer is wrong. Only once this emits
      does the existing `classify()` → `routes.route()` path have any input.
- [ ] Enforce the existing `[relief]` budgets (`llm_daily_max = 8`, `llm_per_run_max = 5`) across all
      three surfaces — a digest plus a burst of failure explanations must not blow the daily cap.
- [ ] Decide Gemma's residency posture: `ollama` currently holds nothing, and loading 10 GB on demand
      costs latency while keeping it resident costs 10 GB against the GH-219 memory contract. Measure
      before choosing.

**QA gate — P7**
- [ ] The digest runs end-to-end against a seeded day of logs and produces a non-empty ranked report.
- [ ] With 3-Eyes inert, all three surfaces make **zero** `ollama` calls (invariant 1 still holds).
- [ ] A budget-exhaustion test proves the `(classify skipped: LLM budget exhausted)` path, not a crash.
- [ ] The observer is tested against a real degraded `daily_sync` log that **exits 0** — it must report
      degraded, not healthy.

### P8 — fleet adoption (rewritten P2)

**Target (decision 9): all 21 `to-adopt` agents in `CATALOG.md`.** Wrap-then-migrate still applies —
no big-bang rewrite — but the endpoint is now the whole fleet, not three sentinels.

- [ ] **Wave 1 — the collectors that actually break.** `vault-sync`, `github-sync`, `daily-sync`,
      `health-check`, `health-check-triage`. `vault-sync` is `FAIL(exit 1)` today; see
      [#222](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/222). Note the existing
      `supersedes` guard on `collector-health.toml`: `install` refuses while `health-check` and
      `health-check-triage` are loaded, because both run `health_issue_reporter.py` and adopting
      without retiring them would stand up a second issue emitter (#139). Adopt these three **as one**.
- [ ] **Wave 2 — pulse.** `pulse-sync`, `pulse-web-sync`, `pulse-warning-watch`, `obsidian-daily-sync`,
      `obsidian-rollover`.
- [ ] **Wave 3 — the rest.** `com.neochro.*` (GA4 pulls, `hq-rollup`, `servers-monitor`),
      `com.user.*` (`git-pulse`, `stickies2obsidian`), `com.claude.prompt-log-to-md`,
      `com.xyz-3-agents-swarm.hq-marathon-scan`. Several point at absolute paths outside this repo and
      therefore belong in `jobs.local.d/`, not the committed registry — see its README.
- [ ] Classify `com.neochro.sys-mem-attribute` in `catalog-notes.toml` (currently the one unclassified
      agent, so `health` reports it as a gap).
- [ ] Remove the deleted Cactus agents from the catalogue rather than leaving them as `not-loaded`
      to-adopt entries: `cactus-serve`, `needle-router`, `sentinel-daemon`,
      `sentinel-daemon.sleuth-app`.
- [ ] **Routes (decision 10):** wire `notify` broadly; keep `gh-issue` gated until P7b's suppression
      list is proven. A duplicate-issue flood is the specific historical failure (#139) this must not
      repeat.

**QA gate — P8**
- [ ] Every adopted job's plist is rendered from its registry entry — no hand-authored plist survives
      for an adopted job (invariant 3).
- [ ] `three_eyes health` reports zero `unclassified` and zero stale `not-loaded` to-adopt entries.
- [ ] `dashboard.py --check` is green after each wave.
- [ ] A wave-1 dry run files **no** GitHub issue while `health-check-triage` is still loaded.

## Acceptance (P0 slice, to firm up after open questions)

1. No `runtime.env` → `tests/test_inert_by_default.py` green: every entrypoint no-ops, zero egress.
2. `dashboard.py --check` green on a seeded registry; drift a job and it fails (mirror invariant proven).
3. `commands.allow` enforced: a job referencing an unlisted command refuses (unit test).
4. `launchd-triage` skill reads `~/Library/LaunchAgents` + `launchctl print` and explains each agent.
5. Registered in the repo's test runner (pytest); Python-first (only `shims/run-job.sh` is Bash).

## Collector-health domain knowledge (from the prior Agy/Gemini sentinel handoff)

Source: historical operator-local collector-sentinel handoff (2026-07-22). The
`collector-health` job (one of the three "eyes") must absorb these before it is wired to fire for real —
a naive "run command → check exit code" observer is **wrong** here:

- **Exit codes lie (GH-146).** `daily_sync.sh` gracefully degrades and exits `0` even when collectors
  fail. The observer must NOT trust exit status — it must tail `temp/logs/daily_sync_*.log` and parse
  the trailing JSON (`sync_outcome: "degraded"` vs `"complete"`), and wait for a terminal marker
  (`=== rebalance daily sync complete ===`) before evaluating (a log ending at `Fetching …` is
  still-running/lock-blocked, not crashed).
- **Known non-actionable issues → suppress, don't file dupes.** Sleuth staleness (#152, upstream
  publisher, human-only fix), Python bootstrap `Errno 4` (#186, self-recovering), and SQLite
  `database is locked` aborts (expected when `daily_sync`/`github_sync` overlap). The collector-health
  job needs a **known-issues suppression list** so its `gh-issue`/`pdda-inbox` routes don't spam.
- **403 burst collisions (GH-144).** `github_sync` (hourly) and `daily_sync` (06:30 PT) overlapping
  exhausts GitHub rate limits — a scheduling/quiet-hours concern for whichever jobs 3-Eyes ends up
  owning.
- **Unsandboxed DB access.** `rebalance doctor` needs the prod DB outside the workspace sandbox; its
  allowlisted command must run unsandboxed.

This is a **follow-on slice** (a real log-parsing observer + known-issue suppression), not part of the
initial build — captured here so it informs `registry/jobs.d/collector-health.toml` when activated.
Playbook of record: `PROJECT/2-WORKING/AGY-SENTINEL.md`.

## Open questions

**Resolved 2026-07-22 (see Decisions locked):**
1. ~~Own the plists or observe first?~~ → **Observe-first** (P0/P1); editing is a P2 option.
2. ~~DASHBOARD collision?~~ → **Dedicated** `utils/3-eyes/DASHBOARD.md`.
3. ~~Name?~~ → **3-Eyes**.
4. ~~Registry format?~~ → **TOML** (stdlib `tomllib`), with auto-regenerated `DASHBOARD.md` on every change.

**Resolved 2026-07-28 (see [Decisions locked 2026-07-28](#decisions-locked-2026-07-28)):**
7. ~~What should Gemma actually do, given it has never been invoked?~~ → **All three surfaces** (P7).
8. ~~Should a `job_guard` refusal trip a breaker?~~ → **No**, and breakers get half-open recovery (P6).
9. ~~Observe-only, partial adoption, or full?~~ → **Adopt the whole 21-agent fleet**, in waves (P8).
10. ~~Which routes are the defaults?~~ → **`notify` + `gh-issue`**; `gh-issue` gated on suppression.

**Still open (non-gating, decide during P7/P8):**
5. **"Talk to jobs" scope.** Read-only Q&A only, or also mutate (pause/resume/trigger) via MCP?
6. **Spin-off trigger.** What event graduates this from `rebalance-OS/utils/` to its own repo?
11. **Gemma residency.** Keep 10 GB resident for low-latency classification, or load on demand and
    eat the cold-start? Interacts directly with the GH-219 ≤8 GB per-process memory contract — measure
    during P7 rather than deciding now.
