# 3-Eyes Debug Context (Rebalance OS)

**Type:** Durable working spec / context memory — not a one-time handoff. Any human or agent should be
able to use it to diagnose either Rebalance collectors or the 3-Eyes system.
**Repo this describes:** Rebalance-OS system
**Audience:** Any human, Codex, or Claude Code session picking up collector, sentinel, or
launchd-supervisor debugging work on any device where this runs.
**Where this lives:** `utils/3-eyes/skills/3-eyes/CONTEXT.md` — committed, so it travels with a clone and
is visible to every device. Loaded on demand by the `/3-eyes` skill (see `SKILL.md` §0).

## 0. Three layers under "3-Eyes" — read this first

"3-Eyes" names **three distinct but related things**. State which layer you're working on before you
start — they have different code, different gate states, and different failure modes.

| Layer | What it is | Where it lives | Primary tool | Current state |
|---|---|---|---|---|
| **1. Collectors** | The actual data collectors: `daily_sync`, `github_sync`, calendar sync, sleuth/reminders sync | `scripts/daily_sync.sh`, `temp/logs/*.log`, `rebalance.db` | `rebalance doctor`, log tailing | Live, running on schedule (multi-device) |
| **2. Collector Sentinel** | The **local Ollama Gemma 4 12B** monitor: detect → classify/triage → propose repair → reviewed PR for Layer 1 | `PROJECT/2-WORKING/AGY-SENTINEL.md` | Ollama Gemma 4 12B; Codex or Claude Code tunes and reviews it | Design of record, **not yet scheduled** — the playbook's own Phase 0 gate is still open (see §6) |
| **3. Launchd Job Supervisor (GH-195)** | A separate, general-purpose supervisor for *every* scheduled launchd job on this Mac — not specific to collectors. Its name is a nod to the **three sentinels it was built to eventually watch**: XYZ-debug, Cactus-Needle-PDDA, and the Rebalance collector-health sentinel (Layer 2 above) | `utils/3-eyes/`, `PROJECT/2-WORKING/GH-195-UNIFIED-SENTINEL.md`, the `/3-eyes` skill | `python3 -m three_eyes health` / `catalog` / `observe` / `list` | **ACTIVE on this device** (`THREE_EYES_ENABLE=1`); inert by default elsewhere. 3 jobs in the runtime registry — verify per device, see §4 |

**Model and ownership contract.** Antigravity is no longer the collector sentinel. Layer 2's
always-on monitoring role belongs to the local Ollama **Gemma 4 12B** model. Codex or Claude Code sits
above that local monitor: it tunes prompts, rules, thresholds, and response quality; validates its
findings against logs and issue history; and handles work that needs deeper judgment. Gemma observes,
classifies, and proposes; Codex/Claude Code refines and reviews; a human remains responsible for
irreversible actions such as merging or shipping a change.

> ⚠️ **Known doc drift (2026-07-24):** `PROJECT/2-WORKING/AGY-SENTINEL.md` has **not** been updated to
> match this contract. Its title still reads *"…detect → triage → repair → PR loop **(Antigravity)**"*
> and its front-matter is unchanged since 2026-07-18. If you follow that pointer you will land on the
> retired ownership model. Trust this section, not that title, until that file is revised.

**Gemma instructions (runtime source).** The editable, authoritative system instructions live beside
the runtime package in
[`utils/3-eyes/three_eyes/gemma_system_instructions.md`](../../three_eyes/gemma_system_instructions.md).
The classifier loads that file as Ollama's `system` message and **fails closed** — it refuses to
classify rather than calling the model uninstructed — if the file is missing or empty. It is the single
edit point for Gemma's safety boundaries, severity definitions, evidence rules, escalation behavior, and
JSON response contract. The selected local model is configured separately in
[`utils/3-eyes/config/runtime.env.example`](../../config/runtime.env.example#L14-L15) and honored at
runtime via `THREE_EYES_MODEL`. After changing the instructions, run
`pytest utils/3-eyes/tests/test_routes_classify.py` (or the full suite, `pytest utils/3-eyes/tests`,
94 tests as of 2026-07-24) so the model's runtime wiring and required JSON response contract remain intact.

Important nuance: Layer 3 is not unrelated to Layer 2 — it's *named after* Layer 2 (among others) as one of
the three sentinels it intends to eventually supervise. Layer 3 now has **a first, shallow window into
Layer 1**: its `collector-health` job watches ingest freshness across the collectors (see §4). That is
freshness-level visibility only — it does not yet parse collector logs or suppress known issues (next
scope, GH-146). So the old caution still half-applies: "3-Eyes says the collector job is fine" (launchd
exit code) and "the collectors are producing fresh data" (`sync_outcome` + row freshness) are still
different claims, and neither is yet "the collector's log is clean."

## 1. Purpose — three standing goals

This file (and the log it points to) exists so any future session can pick up any of these without
re-discovering context from scratch:

1. **Debug the Rebalance Collectors across 3 devices (Layer 1).** Collectors run independently on
   multiple Macs, each with its own local clone, local `rebalance.db`, and local `temp/logs/`. A failure
   on one device does not imply the same failure on another — always confirm which device you're
   diagnosing (see §5, log format).
2. **Debug and tune the collector sentinel (Layer 2).** The local Gemma 4 12B monitor's detect →
   classify/triage → repair proposal → PR loop — including its activation, false positives, prompt/rule
   tuning, and whether a proposed repair is safe. Codex or Claude Code owns that higher-level review.
   See §6 for the current gate status.
3. **Debug the `/3-eyes` launchd job supervisor itself (Layer 3, GH-195).** Whether its `health`/`catalog`
   output is accurate, whether `CATALOG.md` has drifted from live `launchctl` state, whether its
   inert-by-default guarantees actually hold, and whether jobs it claims to manage vs. observe are
   correctly classified. See §4.

## 2. Operational constraints & quirks (Layers 1 & 2)

> Unverified as of the 2026-07-24 5th-pass review — these claims came from the original handoff and were
> **not** re-checked against `scripts/daily_sync.sh`. Confirm before relying on them.

- **Sandboxing**: `rebalance doctor` needs the production DB outside the workspace sandbox
  (`~/Library/Application Support/rebalance-os/rebalance.db`). Run `rebalance doctor` and `gh` commands
  unsandboxed (`BypassSandbox: true`).
- **Exit codes are informative, but not complete.** `scripts/daily_sync.sh` exits `0` for **both**
  `"complete"` and `"degraded"` outcomes, and `1` only for `"fatal"` (a migrations-scope error, or every
  stage failing). A clean exit code does **not** mean nothing went wrong — always grep the log's trailing
  JSON for `"sync_outcome"`.
- **Three terminal markers, not one.** A sync log ends with exactly one of:
  - `=== rebalance daily sync complete ===` (clean)
  - `=== rebalance daily sync degraded; partial errors recorded (see JSON above) ===` (partial failure,
    exit 0)
  - `=== rebalance daily sync failed fatally (see JSON above) ===` (exit 1)

  If you only wait for `complete`, a degraded run will look like a hang forever. Wait for **any** of the
  three.
- **Hanging vs. running**: if a log stops mid-line (e.g. `Fetching 10 files...`) with none of the three
  markers above yet, the job is either still running or blocked on a SQLite lock — not necessarily dead.

## 3. Known defects — collectors and their monitor — verify current state before acting on any of these

These were true as of the dates given. Sync jobs and issue states change; **re-check `gh issue view` and
the actual logs before repeating any claim below to a human** — don't propagate stale status.

### Recent GitHub issue context (last seven days; states re-verified 2026-07-24)

Use these as investigation starting points, not as substitutes for current device evidence. The
always-on Gemma monitor should surface and classify the symptoms; Codex or Claude Code should use the
issue history to tune that classification and verify any proposed repair.

| Issue | Why it matters to 3-Eyes / collectors | State when reviewed |
|---|---|---|
| [#206 — pulse-web-sync health](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/206) | Current launchd health signal for the pulse web-sync job. | Open |
| [#205 — health-check-triage scheduler](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/205) and [#204 — health-check scheduler](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/204) | Current scheduler-health failures; validate whether a monitor can see and explain them. Both agents are `not-loaded` on this device as of 07-24. | Open |
| [#199 — launchd authentication health](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/199) | A current control-plane health failure, distinct from collector data freshness. | Open |
| [#195 — 3-Eyes supervisor](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/195) | Design record for the optional, local-first supervisor and its observe-first safety model. Working doc: `PROJECT/2-WORKING/GH-195-UNIFIED-SENTINEL.md`. | Open |
| [#186 — github-sync Python bootstrap crash](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/186) | A real collector-job failure that needs recurrence evidence rather than an automatic repair claim. | Open |
| [#175 — launchd resource and single-instance audit](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/175) | Explains the fleet-wide lack of guards and why the local LLM runtime must be treated as a resource-bearing process. | Closed |
| [#152 — stale git-pulse export clone](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/152) | Separates a stale local mirror from an actual collector or Sleuth outage. | Open |
| [#144 — GitHub request fan-out](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/144) | Documents the request-volume problem, quota evidence, and the need to read `sync_outcome`, not only launchd exit codes. | Open |
| [#141 — email collector silent data loss](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/141) | Confirms that row count alone is not collector health; monitor freshness and quality. | Open |
| [#139 — health issue deduplication](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/139) and [#138 — monitoring installed on zero devices](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/138) | Prevent duplicate/orphaned alerts and never infer fleet coverage from a repo-level policy. | Open |
| [#131 — daily/hourly database-lock collision](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/131) | Historical fix context for the shared SQLite write-lock failure; re-check logs because the symptom has recurred. | Closed |

### GH-144 — github-sync request fan-out
Actual issue title: *"Reduce github-sync request fan-out: ~2,292 requests/run, 63% from a 6x per-PR fetch
(#140 follow-up)"* — it's about request volume, not directly "403s." 403s are a plausible downstream
symptom of that volume, but file/comment against #144 using its real scope, not a renamed one.

### `daily_sync` / `github_sync` overlap + 403s
On 2026-07-22 through 07-24, the 06:45 PT `github_sync` run consistently died early on a `database is
locked` error (from `daily_sync` holding the write lock), and on those same days `daily_sync` itself
reported `"sync_outcome": "complete"`. This *looks* like a burst-collision theory (crashed `github_sync`
never sends its request burst → `daily_sync` sees no 403s), but three days running the same pattern is a
confound, not a proof — the counterfactual (both jobs running cleanly at the same time) hasn't been
observed recently. Also, 403s recorded elsewhere in the same day's `github_sync` log (e.g. 49 occurrences
on 07-22) show the rate-limit pressure didn't go away — only that specific window was clean. Treat this
as an open hypothesis, not settled. *(Log-derived; not re-verified in the 5th-pass review.)*

### Issue #152 — git-pulse-sync / sleuth freshness
Actual issue title: *"git-pulse-sync export clone stopped pulling from origin on 2026-07-10... dashboard
reports live collectors as stale."* This is about the **local clone**, not confirmed to be purely an
upstream publisher problem — don't tell a human to ignore this without checking `git -C ~/git-pulse-sync
status -sb` and the last commit date first. **Re-verified 2026-07-24:** the clone is healthy —
`main...origin/main` with no divergence, last commit same-day (`acc882f8`, 08:00 PT). So the warning, if
it recurs, needs fresh diagnosis, not a standing "ignore it" rule. There is no
`sleuth-reminders-export.timer` anywhere in this repo — if that's the claimed upstream cause, find where
it actually lives before repeating the claim.

### Issue #186 — github-sync Python bootstrap crash
`Fatal Python error: error evaluating path (InterruptedError: [Errno 4])` — believed transient/self-healing
on the next hourly run. Still open; track recurrence rate before calling it fully benign.

### SQLite lock contention
`daily_sync` (daily) and `github_sync` (hourly) share one `rebalance.db` write lock. When they overlap,
`github_sync` aborts with `database is locked`. Reported recurring on 07-22, 07-23, and 07-24. This is
an architectural bottleneck, not a one-off bug — a real fix means serializing the two jobs or moving to
WAL-mode-safe access, not just noting it.

## 4. Layer 3 — launchd job supervisor (GH-195) current state

**Working doc:** [`PROJECT/2-WORKING/GH-195-UNIFIED-SENTINEL.md`](../../../../PROJECT/2-WORKING/GH-195-UNIFIED-SENTINEL.md)
— status *"Active — P0–P4 shipped; Gemma system-instructions surface built"*. Read it before changing
Layer 3 behavior; it holds the phasing, the load-bearing safety invariants, and the collector-health
domain knowledge. Next functional scope: the real collector-health observer — log parsing and
known-issue suppression (GH-146).

- **Check activation per device — never assume.** Inert-by-default is the *repo* guarantee, not a
  statement about the box you're on:
  ```bash
  cd ~/Documents/rebalance-OS/utils/3-eyes && PYTHONPATH="$PWD" python3 -m three_eyes status | head -1
  ```
  **On this device (noels-Mac-Studio, 2026-07-24) it reports `3-Eyes: ACTIVE`** —
  `config/runtime.env` exists with `THREE_EYES_ENABLE=1` and `THREE_EYES_MODEL=gemma4:12b-mlx`
  (created 2026-07-22, gitignored). Do not describe this device as inert.
- **Inert by default is still the load-bearing promise for every other clone.** With no
  `config/runtime.env` (or `THREE_EYES_ENABLE != 1`), it's a clean no-op — zero network, zero `ollama`,
  zero `gh`, zero launchd/cron mutation. Two hard kill-switches force it off regardless:
  `THREE_EYES_ENABLE=0` in the environment, or a `PANIC` file in its state dir. If you're debugging
  *whether it's safe*, start by confirming these guarantees still hold
  (`utils/3-eyes/tests/test_inert_by_default.py` is the existing proof).
- **"How many jobs are managed?" has three different right answers.** Don't quote one as the whole truth:
  | View | Count | Why it differs |
  |---|---|---|
  | `DASHBOARD.md` / `registry/jobs.d/` | 2 | Committed registry only — deliberately fleet-portable |
  | `python -m three_eyes list` | 3 | Adds the gitignored machine-local overlay `registry/jobs.local.d/` |
  | `CATALOG.md` | 3 🟢 | Generated from live `observe` ⋈ `catalog-notes.toml`; can lag until re-rendered |

  The three runtime jobs on this device:
  - **`collector-health`** — launchd every 1800s, routes `pdda-inbox` + `notify`, breakers
    single-instance/≤8GB/trip@3, LLM relief 5-per-run and 8-per-day. *"Watch ingest freshness across
    GitHub / Slack-Sleuth / Gmail / Google Calendar / Zapier collectors."* This is the Layer 3 → Layer 1
    bridge referenced in §0.
  - **`selfcheck`** — launchd every 3600s, log-only. The no-op that proves the guarded-run → breaker →
    route loop works.
  - **`skill-sync`** *(machine-local overlay, gitignored)* — launchd every 120s. **The first real
    adoption**: the ad-hoc `com.local.skill-sync` LaunchAgent was stuck at launchd exit 78 (`EX_CONFIG`,
    a stale job config — the script itself was healthy); 3-Eyes renders a fresh
    `com.rebalance-os.3eyes.skill-sync` plist and the old plist was retired. It syncs shared `SKILL.md`
    files between `giant-brains-claude-skills` and `xyz-3-agents-swarm` — it does **not** sync this
    repo's own skills (see §5's note on the detached `~/.claude/skills/3-eyes/` copy).
- **`CATALOG.md` is generated and machine-specific** (gitignored, Time Machine covers it) — never
  hand-edit it. Source of truth for annotations is `registry/catalog-notes.toml`; regenerate with
  `python -m three_eyes catalog --write`. **Re-rendered 2026-07-24:** 39 launchd agents ·
  3 🟢 managed · 21 🎯 to-adopt · 9 vendor/OS ignored. Adopting a job without adding an
  `[agent."<label>"]` block leaves it **unclassified** and the catalog stale — that was the state of
  `com.rebalance-os.3eyes.collector-health` until it was classified in this pass.
- **Adoption retires the old plist.** If a job gets adopted into the registry, its original LaunchAgent
  plist must be retired — never leave both scheduling the same work. `skill-sync` above is the worked
  example; `health-check-triage` is still flagged as a ⚠️ risk pattern in the catalog.
- **Live fleet health, 2026-07-24 (after re-render):** `25 ok · 0 FAILING · 5 not-loaded`. The
  not-loaded five include `com.rebalance-os.health-check` and `com.rebalance-os.health-check-triage`
  (cf. issues #204 / #205).
- Raw launchd internals (all agents, plist contents) → the companion `launchd-triage` skill, not `/3-eyes`.

## 5. Interaction log — `temp/3-eyes.log`

Every Claude Code session in `rebalance-OS` appends a summary of its request + outcome to
**`temp/3-eyes.log`** (repo root — note this is a *file*, not the `temp/3-eyes/` *directory*) via a `Stop`
hook (`utils/3-eyes-session-log.py`, committed in `1b7cd96`, wired in `.claude/settings.json` as an async
hook with a 15s timeout). The log is gitignored (`/temp` is not tracked) — it's local to each device's
clone, which is exactly what you want for goal #1 above: don't expect to see another device's entries in
your local log; each device keeps its own.

The hook writes a dedupe marker to `temp/.3-eyes-log.state` (the last logged assistant-message UUID) so
that `Stop` firings from `/clear`, resume, and compact don't duplicate the previous entry. It is
contractually silent: **every** failure path exits 0 without writing, so an empty or absent log is not
proof the hook is wired correctly — smoke-test it by piping a real payload with a valid
`transcript_path` into the script.

> ⚠️ **Path trap.** An empty `temp/3-eyes/3-eyes.log` may exist inside the `temp/3-eyes/` directory.
> **Nothing writes to it.** If you tail that file you will see silence and wrongly conclude no sessions
> were logged. The live log is `temp/3-eyes.log` at the repo root.

### Log entry format

```
=== 2026-07-24T14:32:10-07:00 | device noels-Mac-Studio.local | session 823bc4b3 | cwd /Users/noelsaw/Documents/rebalance-OS ===
REQUEST:
<the user's actual prompt for that turn, clipped to ~2000 chars>

OUTCOME:
<the assistant's final message for that turn — findings, what changed, what's next — clipped to ~8000 chars>
```

Fields:
- **timestamp** — ISO 8601, local timezone offset included.
- **device** — the machine's hostname (`socket.gethostname()`), so a cross-device debugging session can
  tell at a glance which box produced which entries if logs are ever merged or compared side by side.
- **session** — first 8 chars of the Claude Code session UUID (enough to cross-reference a transcript,
  not a full ID dump).
- **cwd** — working directory at time of the turn.

### Skill install note

`~/.claude/skills/3-eyes` is a **symlink** to this directory
(`~/Documents/rebalance-OS/utils/3-eyes/skills/3-eyes`), so edits to `SKILL.md` or `CONTEXT.md` go live
immediately — no copy step, no installer, and the `skill-sync` job is unrelated (it covers two *other*
repos). Verify with `readlink ~/.claude/skills/3-eyes`.

Two consequences worth knowing:
- **A plain `ls -la` through a compacting wrapper can hide the symlink arrow** and make this look like a
  detached copy. Use `readlink` before concluding the live skill is stale.
- **The symlink only exists on a device where someone created it.** On another Mac, `/3-eyes` will not
  resolve until the link is made:
  ```bash
  ln -s ~/Documents/rebalance-OS/utils/3-eyes/skills/3-eyes ~/.claude/skills/3-eyes
  ```

## 6. Sentinel scheduling and tuning (Layer 2) — check before assuming this device is live

`PROJECT/2-WORKING/AGY-SENTINEL.md` is the detect → triage → repair → PR playbook for the local Ollama
Gemma 4 12B monitor. Its always-on role is the design of record; whether that monitor is actually enabled
and scheduled is device-specific. As of its last recorded update (2026-07-18), its own front-matter states:
*status: Proposed — Phase 0 (emitter overlap) is blocking and unresolved... nothing is scheduled yet. Do not
stand this up before Phase 0 closes.* That gate was still open at the 2026-07-24 review. If you're picking
up sentinel work, **re-read that file's current front-matter and the device's scheduler state first** — do
not turn a design role into a false claim that the monitor is live.

Do not confuse this with Layer 3's `collector-health` job (§4), which **is** enabled and scheduled on this
device. That job is 3-Eyes' own freshness watcher, not the AGY-SENTINEL repair loop.

Note also that this file's title and front-matter still name Antigravity as the owner — see the drift
warning in §0. When the monitor is enabled, use the division of responsibility in §0: Gemma performs
continuous local observation and first-pass triage; Codex or Claude Code tunes its behavior and
independently verifies important findings before repair or PR work proceeds.

## 7. General advice

Gemma's sentinel job (Layer 2) is to close the loop from *a collector broke* to *a reviewed repair or PR
proposal*. Codex or Claude Code then tunes and reviews that work; a human decides whether a PR lands.
Before filing a new issue for a failure, check whether it matches one of §3's known patterns and whether
that issue is already open — but don't use §3 as a reason to suppress a *new* symptom that only
superficially resembles an old one. For Layer 3 work, prefer the `/3-eyes` skill's own reporting order
(failing jobs first, then catalog freshness, then adoption nudges) over ad hoc `launchctl` spelunking —
that's what `launchd-triage` is for.

---

## Changelog

- **2026-07-24 (5th pass)** — Accuracy review against live repo state. Moved this file out of gitignored
  `temp/` into `utils/3-eyes/skills/3-eyes/CONTEXT.md` so it is committed, travels with a clone, and is
  loadable by the `/3-eyes` skill. Corrections: the §0/§4 managed-job count contradiction (1 vs 2) is
  resolved into the three-views table — the runtime registry has **3** jobs including the machine-local
  `skill-sync`; recorded `skill-sync` as the first completed adoption (retiring `com.local.skill-sync`,
  exit 78); replaced "Layer 3 has no deep visibility into Layer 1" with the accurate nuance now that
  `collector-health` is enabled at 1800s; flagged that this device is **ACTIVE**, not inert, and gave the
  per-device check command; noted `CATALOG.md` is stale (`collector-health` unclassified); fixed the
  `test/` → `tests/` path; added the §5 path trap for the empty `temp/3-eyes/3-eyes.log` and the hook's
  silent-failure contract; added the detached `~/.claude/skills` copy note; added the
  GH-195-UNIFIED-SENTINEL.md pointer and next scope (GH-146); flagged the AGY-SENTINEL "(Antigravity)"
  title drift in §0 and §6; marked §2 and parts of §3 as not re-verified. Verified accurate and left
  unchanged: all 13 issue states/titles in §3, the #152 clone health, `gemma4:12b-mlx` in `ollama list`,
  the classifier's system-instruction wiring, and the log entry format.
  **Repo fixes made in the same pass:** classified `com.rebalance-os.3eyes.collector-health` in
  `registry/catalog-notes.toml` and re-rendered `CATALOG.md` — it had been adopted without a catalog
  entry, leaving the catalog stale and `health` reporting 1 unclassified agent (now
  39 agents · 3 🟢 · 21 🎯 · 9 vendor, `25 ok · 0 FAILING · 5 not-loaded`).
  **Two self-corrections during the pass, recorded so they are not re-derived:** (1) an early read
  concluded `~/.claude/skills/3-eyes` was a detached manual copy needing a `cp` install step — it is a
  **symlink** to this directory; a compacting `ls -la` wrapper had hidden the arrow, and identical
  mtime/`diff` output was consistent with either. (2) The first count of managed jobs (2) came from
  `DASHBOARD.md` alone and missed the machine-local overlay; `three_eyes list` shows 3.
- **2026-07-24 (4th pass)** — Added the editable Gemma runtime instructions at
  `utils/3-eyes/three_eyes/gemma_system_instructions.md`. The classifier now loads that file as its
  Ollama `system` message; this spec and the 3-Eyes README link to it as the one prompt-tuning surface.
- **2026-07-24 (3rd pass)** — Corrected the Layer 2 sentinel ownership: Antigravity is retired from this
  role; the local Ollama Gemma 4 12B model is the always-on monitor of record. Added the operating
  contract that Codex or Claude Code tunes and reviews Gemma's work, while a human retains authority for
  irreversible actions. Added a linked seven-day GitHub issue index and preserved the distinction between
  that design role and device-specific proof that the monitor has actually been scheduled.
- **2026-07-24 (2nd pass)** — Added Layer 3 (the `/3-eyes` launchd job supervisor, GH-195) as an explicit
  third standing goal per operator correction. Restructured §0 into a three-layer table covering scope,
  location, tooling, and current state for each; clarified that Layer 3 is *named after* Layer 2 (among
  two other sentinels) but currently has shallow visibility into it. Added §4 (Layer 3 current state:
  inert-by-default guarantees, catalog generation rules, adoption/retirement rule, current fleet counts).
  Renumbered all subsequent sections.
- **2026-07-24 (1st pass)** — Rewritten from a one-time handoff into a durable project-spec doc. Corrected
  several stale/inaccurate claims found during review: exit-code
  semantics, the three terminal markers, GH-144's actual scope, the burst-collision theory's confound,
  issue #152's direction and the non-existent `sleuth-reminders-export.timer`, and the AGY-SENTINEL
  Phase-0 gate contradiction. Added the two-goal purpose statement and the log entry format (now
  including per-session device name). Renamed from `3-eyes.txt` to `3-eyes.md`.
- **2026-07-22** — Original pre-Gemma handoff drafted, covering initial collector quirks and defects
  #144, #152, #186, and the DB lock pattern.
