# Changelog

> **Maintainers — there is no `[Unreleased]` section in this project.** Every fix
> or feature takes a version bump at commit/merge time (semver: MAJOR = breaking ·
> MINOR = feature · PATCH = fix) under a `## [x.y.z] - YYYY-MM-DD` heading. Do
> **not** reintroduce an `[Unreleased]` block — add to (or roll work into) the
> current dated version instead. See AGENTS.md → "Versioning & Changelog".

## [0.67.0] - 2026-07-22

### Fixed
- **3-Eyes fleet health called a running server "failing" (GH-195, GH-146 bug class).**
  `health.py` read only the *status* column of `launchctl list` and ignored the *PID*
  column, so `com.rebalance-os.pulse-server` — alive on PID 35845 — reported
  `FAIL(exit -15)` because a *previous* instance had been SIGTERMed by a restart. Since
  restarting the pulse-server is a routine operation, the fleet showed a permanent
  phantom failure. Liveness now comes from the PID column: a job with a live PID is
  `ok`, and the prior exit code is still surfaced (`running; prior exit -15`) rather
  than hidden. This is the same misread `doctor._check_launchd` was fixed for in
  GH-146, reproduced in 3-Eyes' own health module.
- **A health probe that could not run reported a confident answer.** Inside a sandboxed
  shell `launchctl list` exits 1 with no output; `_launchctl_list()` never checked
  `returncode`, so it returned `{}` and every catalogued job fell through to
  `not-loaded` — "0 ok · 0 FAILING · 29 not-loaded", indistinguishable from a real
  dormant fleet. It now raises `LaunchctlUnavailable`, and `scan()` reports a distinct
  `unknown` state with the reason attached.
- **The Focus 5 Float tile rendered an unreadable fleet as green.** Because the tile
  keyed on `failing == 0`, an unavailable probe produced the card *"3-Eyes — all jobs
  OK"* on the operator's primary panel while nothing at all was known. It now renders
  *"3-Eyes — job health UNKNOWN"* with `is_dirty` set, so an unreadable fleet looks
  like it needs attention instead of a clean bill of health.

### Added
- **Adoption guard: `supersedes` (GH-195).** A registry job may now declare the legacy
  launchd labels it replaces, and `install` refuses while any of them is still loaded.
  `collector-health` declares `com.rebalance-os.health-check` and
  `health-check-triage`; both run `scripts/health_issue_reporter.py`, so installing it
  against the live incumbents would have stood up a *second* GitHub-issue emitter and
  reproduced the duplicate-issue defect that #139 was closed by deleting. The check is
  **fail-closed** — only a positive `not-loaded` clears the gate, so an unreadable
  probe blocks the install rather than waving it through.

### Tests
- +10 cases (93 total): PID-beats-prior-SIGTERM liveness, `unknown`-not-healthy on an
  unreachable probe, non-zero-exit raises rather than returning empty, PID/status
  column parsing, `supersedes` parsing/defaults, the shipped `collector-health`
  declaration, and four install-guard cases including the fail-closed `unknown` path
  and a no-probe-when-empty assertion.

### Operational
- The three `com.neochro.ga-pull-*` agents (binoid/bloomz/bounce) were **booted out and
  disabled** on the Mac Studio. They had failed on all 85 runs since 2026-04-24 with
  `ModuleNotFoundError: No module named 'wpdbtk'` — a `sys.path` problem, not a missing
  package (the script is invoked by absolute path, so the repo-root package is
  invisible; `WorkingDirectory` does not put CWD on `sys.path`). Tracked in
  [BinoidCBD/LTVera-Pandas#70](https://github.com/BinoidCBD/LTVera-Pandas/issues/70);
  plists and logs were left in place, and `launchctl enable` reverses it.
- Fleet health after both fixes: **25 ok · 0 FAILING · 4 not-loaded** (was reported as
  24 ok · 4 FAILING · 1 not-loaded, of which 1 was a phantom).

## [0.66.0] - 2026-07-22

### Added
- **3-Eyes — first real adoption + machine-local registry overlay (GH-195).**
  - **Machine-local overlay** — gitignored `registry/jobs.local.d/*.toml` and
    `registry/commands.local.allow` let an adopted automation whose command is an
    *absolute, machine-specific path* (outside rebalance-OS) enter 3-Eyes without
    leaking that path into the committed registry. Runtime (`run`/`status`/`list`/
    `health`/`catalog`) reads the overlay (`include_local=True`); the committed,
    fleet-portable `DASHBOARD.md` renders committed-only (`include_local=False`) so
    a downstream clone never inherits another machine's jobs. `.example` + a
    `jobs.local.d/README.md` document the mechanism.
  - **Adopted `skill-sync`** (the Claude Skills `SKILL.md` LWW sync) as the first
    managed job. Its ad-hoc `com.local.skill-sync` LaunchAgent had been failing at
    the launchd layer (`exit 78 EX_CONFIG`, no run since 2026-07-08) though the
    script itself was healthy; 3-Eyes renders a fresh `com.rebalance-os.3eyes.skill-sync`
    plist and the stale plist is retired so nothing double-schedules — one move
    fixes the failure and completes the adoption.

- **Focus 5 Float — 3-Eyes job-health tile (GH-195).** `GET /focus-5.json`
  (`src/rebalance/web.py`) now appends ONE synthetic roster card summarizing 3-Eyes
  fleet job health — a red status dot + `"3-Eyes — N jobs FAILING"` when any
  catalogued job is failing, healthy otherwise — so the failure signal rides on the
  panel the operator already watches. It renders through the app's existing dynamic
  roster (no native-app change; documented in `Focus5Float/CONTRACT.md`). Additive +
  defensive (never breaks the endpoint), gated on 3-Eyes being active (a downstream/
  inert clone never shows it), and short-TTL cached so the polled route never spawns
  `launchctl list` per request. `summary.roster_size` stays repo-only.

### Changed
- **3-Eyes notify throttle** — a job that is *already* quarantined now re-routes only
  to `log-only` on each skipped run instead of re-firing a `notify` banner every
  scheduling tick (a 120s job would otherwise banner every 2 minutes). The operator
  is still banner-alerted once, at the moment the breaker opens.

### Tests
- +8 cases (83 total): machine-local overlay load/exclude/validate/dashboard-isolation
  and the quarantine re-notify throttle.

### Operational status
- **3-Eyes is now ACTIVE on Noel's Mac Studio** — this is a device-local activation, not
  a repo default: it rides the gitignored `config/runtime.env`, so every other clone stays
  inert. It manages `com.rebalance-os.3eyes.skill-sync` (plus the `selfcheck` demo job),
  the stale ad-hoc `com.local.skill-sync` LaunchAgent is retired, and the Focus 5 Float
  fleet-health tile is live. The committed `collector-health` job is registered but not
  yet installed; everything else in the catalog is observed, not managed.
- **Continuity check:** `cd utils/3-eyes && PYTHONPATH=$PWD python3 -m three_eyes status`.
  **Deactivate on a device:** remove/edit `config/runtime.env` (or `THREE_EYES_ENABLE=0`);
  **retire a managed plist:** `python -m three_eyes uninstall <job>`.
- **Known quirk:** `three_eyes health` shells out to `launchctl list`, which a sandboxed
  shell blocks — it then reports *every* job `not-loaded`. Re-run it unsandboxed before
  concluding anything about fleet health.

## [0.65.0] - 2026-07-22

### Added
- **3-Eyes — unified local job supervisor (GH-195)** in `utils/3-eyes/`. One
  optional, Python-first system that unifies the three sentinels we run today (XYZ
  debug flywheel, Cactus Needle PDDA sentinel, Rebalance collector-health) under a
  single TOML registry, one set of circuit breakers + pressure-relief valves, one
  generated dashboard, and one way to talk to jobs (CLI + MCP + Claude skills).
  - **Inert by default** — with no gitignored `config/runtime.env` (or
    `THREE_EYES_ENABLE!=1`) it is a clean no-op: zero network / ollama / gh /
    launchd / cron. Proven by `tests/test_inert_by_default.py` (egress primitives
    stubbed to fail loudly). Two hard kill-switches: `THREE_EYES_ENABLE=0`, PANIC file.
  - **Registry is the source of truth** — launchd/cron entries render from the TOML;
    `DASHBOARD.md` is a deterministic generated projection kept honest by
    `python -m three_eyes.dashboard --check` in CI + a `regen-dashboard` pre-commit hook.
  - **Safety** — circuit breakers wrap the existing `utils/job_guard.py` (GH-172
    single-instance flock + memory ceiling) and add a per-job failure breaker;
    relief valves add daily/per-run LLM budgets, quiet-hours, and backoff. A
    `commands.allow` allowlist means no free-form command execution.
  - Egress confined to two boundary modules (`classify.py` ollama, `routes.py` gh),
    enforced by a static-guard test. 51 pytest cases, wired into CI.

## [0.64.2] - 2026-07-21

### Fixed
- The floating macOS app icon now uses the platform-sized transparent margin, so its visual footprint matches neighboring Dock and app-switcher icons instead of appearing oversized.

## [0.64.1] - 2026-07-21

### Fixed
- The floating macOS panel now reopens after being hidden, resizes vertically without inheriting a maximum from the wrong display, and draws its visible shell to the menu-bar boundary instead of retaining a hidden-titlebar safe-area gap. Real panel-chrome regression coverage protects both the unbounded-height contract and the zero top inset.

## [0.64.0] - 2026-07-19

### Added
- **GH-164 Cognee integration plan + technical spike artifacts.** Added a new active PDDA plan doc for Cognee integration (`PROJECT/2-WORKING/GH-164-COGNEE-INTEGRATION-PLAN.md`) with phased QA gates and recorded Phase 0 findings. The spike validated local Cognee runtime in an isolated venv (`cognee==1.4.0`), completed a session-memory `remember`→`recall` roundtrip, and projected recall output into a probe SQLite table (`temp/spikes/gh-164-cognee/spike_results.sqlite`) to prove ingest-shape viability before implementation.

### Fixed
- **Focus5Float's Prompt Log viewer no longer loads an unbounded CLIO file into memory.** The
  `PromptLogReader.load` path read the entire `.md` into RAM, split every line, and parsed every
  entry with no cap — then re-did it on the 90s poll timer. A CLIO log accumulates forever and
  never rotates, so at tens of MB this would hitch the panel and balloon its footprint each poll.
  `load` is now bounded: a **1 MB byte ceiling** on the read and a **10k-entry row cap**, both
  keeping the *newest* prompts (CLIO writes newest-first at the top of the file). Added 3 tests
  (row cap, byte-ceiling truncation, missing-file).

### Changed
- **DRY: extracted the shared bounded-file read into `FileLoad`.** The telemetry `.md` viewer
  already had a 1 MB ceiling + 10k row cap (GH-121); the prompt-log viewer had neither. Rather
  than duplicate the guard, both viewers now call `FileLoad.boundedText(_:byteCeiling:)`, and
  `Focus5Model.telemetryMarkdownByteCeiling` / `telemetryRowCap` alias `FileLoad.markdownByteCeiling`
  / `feedRowCap` (single source of truth). The two parsers stay separate — only the read mechanism
  is shared. 51 swift tests pass (+3).

## [0.63.0] - 2026-07-19

### Added
- **CLIO exporter is now idempotent by content and self-healing across devices.** Implemented
  Phases 1–2 of the durability plan (via marathon; builder codex, reviewer agy) in the
  `prompt-log-to-md.sh` exporter in `utils/CLIO/INSTALL.md`:
  - Every rendered entry carries an invisible `<!-- clio:id:session_id:timestamp -->` marker,
    emitted inline by the existing `jq` pass. The exporter skips any entry whose ID is already
    in the note, so re-runs and a deleted/corrupt cursor state no longer duplicate; the cursor
    is demoted to a scan optimization. A verify-after-write step withholds the cursor advance
    until the emitted IDs are confirmed present.
  - Conflict-copy reconciliation: before exporting, it recovers full entry blocks stranded in
    sync conflict siblings (`*.sync-conflict-*.md`, `* (conflicted copy*).md`, iCloud numeric
    dupes), deduped by ID, and **quarantines** each processed copy under `.clio-reconciled/`
    instead of deleting it. Honors `CLIO_RECONCILE_DRY_RUN=1`.
  - `Focus5Float`'s `PromptLogReader` now drops `<!--` lines before positional parsing, so the
    Prompt Log tab tolerates the new ID comments (48 swift tests pass, +7).

### Fixed
- **CLIO exporter no longer aborts on macOS's bash 3.2.** The new reconciliation loop expanded
  an empty `conflict_siblings` array under `set -u`, which raises "unbound variable" on bash
  < 4.4 (macOS `/bin/bash` is 3.2) — the common zero-siblings case, so every normal run failed
  and produced no output. Caught in post-marathon verification (the `swift build` gate could not
  exercise the shell path) and fixed with the portable `${arr[@]+…}` guard. Re-verified on
  `/bin/bash` 3.2: idempotency, state-delete safety, full-block reconciliation, and dry-run.

## [0.62.0] - 2026-07-19

### Changed
- **CLIO Markdown exporter auto-sync default is now every 1 minute (was 5).** Updated the
  launchd `StartInterval` in `utils/CLIO/INSTALL.md` (300 → 60) and the live
  `com.claude.prompt-log-to-md` job on this machine (reloaded; prior plist backed up to
  `*.plist.bak-300s`). Faster surfacing of new prompts into the shared Obsidian note, at the
  cost of higher concurrent-write odds — which motivates the durability plan below.

### Added
- **Plan: durable, idempotent CLIO writes to the shared Obsidian note.** Root-caused CLIO's
  best-effort merge gap (the per-device line-count cursor is load-bearing for correctness and
  advances whether or not a write survives sync; no content-level idempotency; no conflict-copy
  reconciliation) and drafted a 4-phase fix: content-addressed entry IDs, conflict-copy
  reconciliation, verify-after-write, and a coupled `PromptLogReader` change to skip HTML-comment
  lines. → `PROJECT/1-INBOX/CLIO-DURABLE-IDEMPOTENT-WRITES.md`

## [0.61.0] - 2026-07-18

### Added
- Direct branch pushes in watched repositories now retain a durable event
  receipt, per-commit identity, and exact changed-file records. The bounded
  enrichment path surfaces non-PR commits in activity, HiQS evidence, and the
  dashboard while preventing duplicate signals when a matching PR is present.

## [0.60.0] - 2026-07-18

### Fixed
- **Collector health signal no longer reports a working system as broken.** Months of "the
  collectors are unstable" traced to the health checks, not the collectors — 6 of 6 findings
  investigated on 2026-07-18 were misreads, and **zero** were real collector defects. (GH-146)
  - `scripts/daily_sync.sh` no longer exits 1 when any single sub-source errors. A transient
    GitHub rate limit was failing an otherwise-successful ~49-minute refresh, which launchd
    recorded as status 1 and `doctor` then reported hourly — 7 of the last 10 runs ended
    `finished with errors` this way. A new `classify_sync_outcome()` splits fatal (migrations
    failure, or every stage failed/skipped) from degraded (exit 0), and the JSON gains
    `sync_outcome` alongside existing keys.
  - `doctor`'s launchd check reads the run's structured result instead of asserting a stale
    `launchctl` exit status as current health; an unknown state now reports as stale rather than
    as a current failure.
  - Device-bound checks (`pulse collector:*`, `scheduler:*`) no longer warn on machines they do
    not describe. Laptops that are legitimately asleep stopped raising alerts on the Mac Studio.
  - The `deep work` stall check pins "today" to the operator's local day via `tz_utils.local_tz()`
    instead of UTC. After 17:00 PDT it had been reporting **every** tracked project quiet on a UTC
    day that was two hours old — same bug class as GH-129's day-boundary tz pin, fixed there and
    missed here.

### Known gaps (GH-146)
- `launchd:pulse-server — exited with status -15` still warns. `-15` is SIGTERM from a deliberate
  restart; the phase brief named this target but no test covered it and it was not fixed.
- `launchd:daily-sync` now reports honestly ("stale/unknown") but still surfaces as a WARN; whether
  an unknown state should warn at all is unresolved.
- Device ownership is hardcoded by device id in `_DEVICE_SCOPE_REGISTRY`; it will drift as machines
  are added or renamed.

Net effect measured on the same host, same config, same moment: **6 warns → 5**, against a target
of 0. `daily_sync.sh`'s effect is not observable until the next 06:30 scheduled run.

## [0.59.1] - 2026-07-16

### Fixed
- `daily-sync` no longer fails with `"database is locked"` when it collides with
  the hourly `github-sync` job. The github-scope refresh now retries (linear
  backoff, bounded, never silently swallowed) instead of failing the whole run
  and cascading into a skipped dashboard note. (GH-131)
- Focus5Float's telemetry-tab `.md` viewer no longer reads an unbounded file
  synchronously on the main thread. The read is now capped at 1MB with a
  byte-safe truncation (never mid-codepoint) and a visible truncation note;
  files under the cap are unaffected. (GH-121)

## [0.59.0] - 2026-07-16

### Added
- Shared UTC→local display formatters (`format_local()`, `format_relative()`)
  in `tz_utils.py`, which already owned local-timezone *resolution* but had no
  shared *display*-formatting layer. Five independent ad-hoc implementations
  across `pulse.py`, `next_actions.py`, `daily_report.py`, `note_builder.py`,
  and `web.py` now share one tested core (behavior-preserving — each keeps its
  own format string and fallback text).

### Fixed
- `rebalance semantic-query` printed a bare, unconverted, unlabeled UTC
  timestamp (`updated: 2026-07-16 15:27:...`). Now shows the converted local
  time with an explicit label (`Local Time: 2026-07-16 08:27 PDT`).

## [0.58.1] - 2026-07-14

### Fixed
- Git Pulse daily summary no longer falsely reports "no git activity" on active
  days. The day-boundary was derived from the ambient timezone, so a scheduled
  run under UTC (or after local-evening, once UTC has rolled to the next day)
  filtered out the whole day's commits. The day boundary is now pinned to the
  machine's real local timezone (or an explicit override) regardless of the
  runtime environment.

## [0.58.0] - 2026-07-14

### Added
- Claude Code Cloud web sessions as a work signal: read the day's cloud coding
  jobs and their status (finished / running / failed), enriched with each head
  branch's pull-request merge state (merged / open / none). Wired into the
  ranked next-action pipeline through the collector candidate seam, shipping
  dormant behind an opt-in flag so the signal is watched via a daily-note data-
  quality grade before it is allowed to influence the ranked verdict.
- A daily Obsidian note block grading that signal's data quality — attribution
  (repo+branch resolved), attestation (per-job summary), outcome coverage, and
  pull-request linkage — as the observation surface before promotion.

## [0.57.0] - 2026-07-14

### Added
- **HiQS — all six signals unified into one ranked pipeline** ([GH-125](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/125), supersedes the remaining scope of #101/#115/#116/#119) — GitHub, the vault, Google Calendar, Slack reminders, email, and design comments now feed a single bundle that produces a single ranked verdict, read by every synthesis surface. Previously two surfaces disagreed — the broad-synthesis path saw no Slack reminders, email, or design comments; the ranked what's-next engine saw no email or design comments — and email and design comments reached no synthesis at all. Each candidate is now Attested: it carries its source, its evidence, and why it was ranked. The design-comment arm ships dormant-and-correct, staying empty until an explicit file-key allow-list turns the opt-in collector on. This is wiring, not new machinery.

### Changed
- **One ranked verdict, structurally drift-proof** ([GH-125](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/125)) — the broad-synthesis result now carries the ranked "what to do next" verdict as a first-class field, read from the persisted cache. It never recomputes the ranking, so the default path costs no extra model call. The precise invariant: **no surface computes its own ranking** — there is exactly one ranking in the system, written by the refresh paths and read by everyone — so two surfaces can never show *different* rankings, rather than merely agreeing today. (On a never-ranked database the broad-synthesis surface reports an empty ranking while the dashboard bootstraps the cache: an absence, not a disagreement. It stays that way by design — that surface must never trigger a network synthesis.) The ranked verdict is now **always** returned to agent callers under a top-level key, replacing the previous opt-in side-channel; the synthesis prompt gains a labelled section carrying each action's receipts rather than bare titles.
- **A source reaches the ranking by registering a collector, not by editing a dispatch chain** ([GH-125](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/125)) — the hand-written per-source candidate dispatch in the ranker is replaced by a walk over the collector registry, reusing the same registration seam the semantic-document providers already use. Each source now owns its candidate shape at registration time, so adding a seventh work signal touches neither the ranker nor the query layer — pinned by a test that registers a fake source and asserts its rows reach the ranked output with no edit to either. This is the headline of the change and the guiding principle it discharges. The cross-day velocity signal is explicitly **not** folded in: it is a multi-day derived scan, and the provider contract is single-day, so it stays observe-only rather than being bent to fit. The speculative second ingest path for email and calendar is killed as planned, but its handler stubs are **kept** — they are the live dispatch targets of a shipped, tested webhook receiver, which the plan had overlooked.

### Fixed
- **A contentless email can no longer outrank real work** ([GH-125](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/125)) — email ranks above open GitHub items, so a message row carrying neither a sender nor a subject would have surfaced at the top of the list as "(no subject) from unknown sender". Such a row has nothing to attest with and is now dropped before ranking. Found by running the new pipeline against real data, which revealed the reason it had not already been hit: **the email collector is landing badly broken rows** — of 124 stored messages, 119 have no sender, no subject, and no timestamp, and are invisible today only because the missing timestamp excludes them from every window. They would all have surfaced the moment that was fixed. The guard is here so this cannot become a signal-quality regression later; the ingest defect that produced the rows is fixed separately, below.
- **Email push-ingest no longer accepts contentless rows — the root cause of the broken table** — the agent-facing push path (the supported way to keep mail fresh when an agent holds the mail connector) took caller-supplied records and defaulted every missing field to an empty string. A caller whose payload used *different key names* therefore had every unmatched field silently coerced to empty, and the rows were stored anyway: they looked ingested, and were unusable. That is what happened on this device — a single push landed 119 rows, 96% of the whole table, carrying an id, a snippet and labels but no sender, no subject and no timestamp. Nothing reported a problem; the rows sat there for three weeks and were only discovered when the new ranked pipeline went looking for email and found nothing rankable. Such a record is now **rejected at the write boundary** (a message with no sender *and* no subject *and* no timestamp is not a message), the count comes back to the caller as a first-class field, and — because the caller is an agent, not a human reading logs — the tool response also carries an explicit warning naming the expected key names. One real field is enough to be stored; the guard rejects only total emptiness. **Silent coercion at a write boundary is how a source starves without ever reporting unhealthy: freshness only checks whether rows exist, not whether they mean anything.** The already-corrupted rows were purged from the operator's local store as part of the fix — the dead records and their embeddings (which had also been polluting semantic search) are gone, the five real messages are intact, and the store passes an integrity check. Teaching source health to assert row *quality* and not merely row *count* — the reason this hid for three weeks, and a gap that applies to every source, not just email — is tracked separately.

### Notes
- The consolidation bet recorded in 0.56.1 rested on "124 real email rows feeding nothing". Verification against real data shows only **5** of those rows carry content, the newest received seven weeks earlier. The email arm is therefore correctly wired but **starved**: its payoff is gated on fixing ingest, not on this change. The correction is recorded rather than the original claim quietly restated. The stated net-lines-of-code-at-or-below-zero acceptance criterion was **missed** (+519 net): two planned deletions proved unsafe on inspection, and six sources genuinely needed wiring. Recorded as a failed criterion.

## [0.56.1] - 2026-07-14

### Changed
- **Four overlapping signal efforts consolidated into one plan: HiQS** ([GH-125](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/125)) — a review of how the six ingested sources reach a user found the product's core claim was only about two-thirds true. There is no unified pipeline: two independent synthesis surfaces exist and they disagree. The broad-synthesis path sees no Slack reminders, no email, and no design comments; the ranked "what to do next" engine that powers the dashboard sees no email and no design comments. Email and design comments are collected, stored, and embedded — and then reach no synthesis at all, only raw search. On the primary device that is 124 real email rows feeding nothing. The two surfaces share no code, so nothing prevents them from drifting further apart. HiQS ("High Quality Signals") is now the named plan to make all six sources feed one bundle that produces one ranked verdict every surface reads. Four issues were retired into it — the observe-first source-health contract, the alternative-ingest webhook work, the cross-day velocity signal, and the HiQS branding pass — each of which had independently started describing a piece of "the work signal." **All code already shipped under them is kept; only their unfinished scope was absorbed.** The plan's own third phase carries a net-lines-of-code-at-or-below-zero acceptance criterion, so the consolidation has to pay for its own wiring.

  **The bet.** Retiring four active issues into one is reversible (reopen the issues, move the docs back) but not free: it concentrates four independently-gated efforts behind a single plan, so if that plan stalls, four things stall. The call is that the *reason* they were all gated is the same missing piece — nothing combined the signals, so no single one of them could prove its own value in isolation. Expected signal by the close of the plan's first two phases: the ranked list visibly contains email-sourced items, and the two synthesis surfaces return the identical ranking. Revisit trigger: if unifying the bundle does not measurably improve the ranked output, the consolidation was organizational rather than substantive, and the absorbed efforts should be re-split rather than left dormant behind one doc.

  Naming collision resolved along the way: the source-health contract carried `codename: HiQS` in its frontmatter while the branding issue claimed HiQS as a marketing label for the ranked signal. Both are retired; the new plan is the single owner of the name. Docs moved to the superseded bucket; roadmap ledger gained a `Superseded` section so retired work stays visible instead of vanishing.

  **Three design decisions locked against the guiding principles**, whose appendix fixes the priority order as *local-first > signal quality > architectural cleanliness > implementation speed*. That order overruled the smaller diff twice. (1) The broad-synthesis surface will expose the ranking as a real, discoverable field rather than a hidden side-channel attribute — the side channel was the smaller change but fails the "structured" pillar and is a band-aid that the very next phase would tear out. Its pinned return-shape test will be updated to assert the new contract, not preserved to hide the change. (2) Rankings must arrive *attested* — every action carries its source, evidence, and reasoning through to both the synthesis prompt and the UI; a rank with no basis is not a high-quality signal, and this is now an executable test rather than a promise. (3) The per-source dispatch chain in the ranking engine is a standing violation of "extend by addition, not by editing a dispatch chain" — the plan knowingly grows it by two arms in its first phase to prove the signal is real, then collapses all eight into a collector-registered provider that mirrors the semantic-document provider seam already in the orchestrator. Reuse of an existing seam, not a new abstraction; it is also where the net-lines-at-or-below-zero target gets paid for.

### Fixed
- **PDDA compliance restored on the project-health-axes doc** — it was missing a roadmap ledger pointer (failing `roadmap-coverage`) and its status table used a non-contract header (`Most recently completed phase` instead of the exact `What was just completed`), failing `status-table`. Both pre-dated this iteration and were failing silently because the suite had not been run in blocking mode. Full-mode PDDA now passes clean across the repo.

## [0.56.0] - 2026-07-11

### Added
- **Commit-threshold auto-promotion of watched repos** ([GH-124](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/124)) — a watched-but-unconfirmed repo now auto-promotes into `project_registry` once the operator (or a known cloud-agent bot acting on their behalf) has authored `auto_promote_commit_threshold` commits to it (default 3, config `auto_promote_enabled`/`auto_promote_commit_threshold`). Reuses the existing `machine_owned` write contract from activity/calendar inference (never overwrites a curated row), reuses `pulse.py`'s existing author-identity filter against `github_commits` rather than inventing a second one, and wires into `_refresh_github()` immediately after the watchlist coverage guard — no new scheduling surface. Forks/starred repos with zero operator commits never promote; the commit-count gate is the fork filter, no separate detection needed. Every promotion surfaces non-silently: a `project_auto_promoted` badge on `/auth-log` and a "New repo added" banner on the pulse dashboard's repo-activity chart. Plan Codex-reviewed to approval via `relay-xyz` (3 rounds) before build. 20 new tests across detection, surfacing, and orchestrator wiring; full suite verified zero-regression against a pre-change baseline; `rebalance doctor` clean.

## [0.55.0] - 2026-07-06

### Added
- **Cross-day deep-work signal (observe-only)** ([GH-116](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/116)) — a new `rebalance doctor` check flags a project that went quiet after recent activity while it still has open GitHub work, computed by diffing the existing daily pulse snapshot across day boundaries (no re-summarization of the vault's Gemini prose, no new table). Read-only for now — does not change the "what to do next" ranking; folding it in is a gated follow-up. 63 new/updated tests green.
- **Zapier webhook receiver (Phase 1)** ([GH-115](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/115)) — a new authenticated endpoint accepts Zapier-triggered events (HTTP Basic Auth primary, query-param fallback, dry-run support, in-memory rate limiting, a health-check route), routing by source to placeholder handlers. The real email/calendar ingest logic behind those handlers lands in a follow-up phase. 8 new tests green.
- **Focus 5 off-roster reason — desktop parity** ([GH-104](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/104)) — the macOS Focus5Float app's off-roster strip now shows the same specific reason (uncommitted, unpushed, etc.) per repo that the web view already showed, reusing the existing server-computed reason string rather than re-deriving the logic client-side. Web slice shipped 2026-07-03; this closes the desktop half.

## [0.54.0] - 2026-07-05

### Added
- **Signal-quality contract Phase 2 — derived status/reason + doctor warning** ([GH-101](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/101)) — `get_index_status()` now derives a `status` (`ok`/`warn`/`degraded`) + `reason` per source from staleness and collapsed 7-day volume, merged into the existing `payload["freshness"]` dict alongside the pre-existing semantic-drift keys (never clobbering them). One new `rebalance doctor` warning line prints degraded sources with their reason — read-side only, no ingest gate, no new table. Live-verified: `doctor` correctly flagged `email` (fresh, 0 rows/7d) and `figma` (stale 25d) same day. 33 new/updated tests green.
- **Capabilities manifest (Phase 2, scope-pinned)** ([GH-106](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/106)) — a static `capabilities/manifest.yaml` + generated read-only `capabilities/INDEX.md` documenting 3 high-risk skill bundles (`relay-xyz`, `xyz`, `consult`) by reference — no dynamic loader/trust engine. Scoped to this repo only; the full cross-repo (Rebalance + XYZ) manifest remains open. 3 tests green; regeneration confirmed idempotent.
- **Zapier ingest — module split forced for swarm eligibility** ([GH-115](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/115)) — a `swarm-preflight` pass found the original single-module design (Phase 2 email + Phase 3 calendar both writing one `zapier_ingest.py`, both wiring into `web.py`) wasn't path-disjoint. Split into `zapier_email.py`/`zapier_calendar.py`, with Phase 1 owning `web.py`'s dispatch exclusively via stub handlers, so Phase 2 and Phase 3 can run as a real concurrent lane. Phase 0 spike also shipped: Gmail/GCal trigger field mapping documented, auth decision landed (HTTP Basic Auth primary, query-param fallback; HMAC deferred pending Zapier Premium header support).

## [0.53.0] - 2026-07-05

### Added
- **Zapier ingest project created** ([GH-115](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/115)) — 5-phase project plan for Zapier webhook ingestion as an alternative to direct Gmail/GCal OAuth. HMAC-authenticated endpoint in `web.py` routes to normalizers in `zapier_ingest.py`; Zapier email reuses the existing `ingest_email_messages()` single-writer path; Zapier calendar gets a new push function in `calendar.py`. Operator config flags (`email_source`, `calendar_source`) keep OAuth the default. Phase 0 spike is next. → `PROJECT/2-WORKING/GH-115-ZAPIER-INGEST.md`

## [0.52.2] - 2026-07-05

### Added
- **Multi-device Git Pulse daily synthesis to Obsidian vault** ([GH-114](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/114)) — created `utils/git_pulse_daily_synthesis.py` and Claude Code skill `git-pulse-daily-synthesis` to project multi-device git commit logs (via `view.sh --today`) into an idempotent block at the bottom of the Obsidian vault's "0. Today's Notes.md". The synthesis uses Gemini (no Qwen fallback) and includes a late-run guard to prevent colliding with the 00:00 rollover.

## [0.52.1] - 2026-07-04

### Fixed
- **focus5 Mac app: refresh no longer strands worktrees removed from disk** ([GH-109](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/109), [PR #111](https://github.com/Hypercart-Dev-Tools/rebalance-OS/pull/111)) — `summarize_focus5` (`src/rebalance/ingest/focus5_scan.py`) gained a `_repo_path_live()` existence check (mirrors `iter_git_repos`'s `.git` predicate), applied on the read path via a `drop_missing_paths=True` default, so a repo whose folder or `.git` no longer exists drops from the roster/off-roster on the next read-only `GET /focus-5.json` fetch — no full ~30s device rescan required. 2 new regression tests in `tests/test_focus5_scan.py` (153 passed pre-merge, 105 in the focus5 file post-merge on `development`); the synthetic-path ranking unit tests opt out via `drop_missing_paths=False`. Visually verified end-to-end in the native Focus5Float app (not just the Python suite): a throwaway git worktree was synced into the live roster, deleted from disk, and confirmed to drop from the running app's panel via its own read-only refresh path.
- **focus5 repo-name font shrunk ~20%** ([GH-110](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/110), [PR #111](https://github.com/Hypercart-Dev-Tools/rebalance-OS/pull/111)) — the Mac app's `Theme.display` (`macOS/Apps/Focus5Float/Sources/Focus5Float/Theme.swift`) went 17pt → 14pt, and the HTML `/focus-5` page's `.f5-name` (`src/rebalance/web.py`) went 15px → 12px. Verified visually in a `swift build`/`swift run` of the native app — repo names render clearly legible at the smaller size with no clipping. `/Applications/Focus 5 Float.app` rebuilt and reinstalled via `make-app.sh` so the installed copy carries both fixes.

## [0.52.0] - 2026-07-03

### Added
- **6 low-risk GSD Core pattern-review adoptions landed** ([GH-106](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/106), follow-on to the closed review [GH-103](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/103)) — all scored low-medium risk / trivial-to-easy reversibility, batched into one pass rather than an XYZ marathon (marathon is serial anyway, and two of the six share `PROJECT/PDDA.md` as a target, which marathon's phase isolation can't safely coordinate): (1) a `Verification summary` phase-close convention plus (4) a named `Discuss` pre-planning step, both in `PROJECT/PDDA.md` → "Named phase-loop steps"; (2) a corrected read-before-edit hook port — gsd-core's own `gsd-read-guard.js` explicitly self-disables on Claude Code ("Claude Code natively enforces read-before-edit"), so the actual gap was a leaf-ingest bypass nudge instead: `utils/pdda/pdda-leaf-ingest-guard.py`, an advisory (never-blocking) `PreToolUse` hook wired in `.claude/settings.json`, firing only on inline-Python `rebalance.ingest` calls that bypass `register_collector`/`refresh_index`; (3) a subagent/`consult` hand-back contract (`PROJECT/PDDA.md` → "Subagent & consult hand-back contract"); (5)+(6) a new `SKILLS-INVENTORY.md` — a hand-maintained (not dynamically generated, per a real YAGNI objection raised during cross-model review) skill/command/hook ownership map + discoverability index. `doctor` clean, `pytest tests/` 1264 passed / 10 skipped, `pdda.sh run` clean. The 7th, higher-effort adoption (a narrow `capabilities/`-style manifest) stays queued as GH-106 Phase 2.

## [0.51.4] - 2026-07-02

### Added
- **XYZ ⇄ Rebalance integration project captured** (`PROJECT/1-INBOX/GH-102-XYZ-REBALANCE-INTEGRATION.md`, GH-[#102](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/102)) — formalized the outcome of a "dueling Claudes" brainstorm (`relay-system/2026-07-02/xyz-rebalance-integration.md`, `claude-xyz` ⇄ `claude-reb`, 4 rounds, closed) into PDDA intake: a Top-3 integration-seams contract (build order #2→#1→#3) between the XYZ agent-swarm harness and Rebalance — (#1) an `xyz` collector feeding marathon/session `XYZ.json` into the signal plane via `register_collector` (`index_ops.py:95`) + GH-101 health fields, (#2) a pinned harness release channel (`xyz-sync check` over `registry.tsv` `source_commit`/`tick_version`), (#3) the return path seeding cross-repo tick lanes via `roadmap_signals` (Phase-2, gated behind #1). Parked in `ROADMAP.md`; depends on GH-101. Planning/intake only — no product code.

### Fixed
- **Relay pointer format deadlocked the duel poll parser** (`relay-system/2026-07-02/xyz-rebalance-integration.md`) — the scaffolded thread wrote `**NEXT: claude-reb**` (bold wrapping the whole line), but `.xyz/relay-automation/poll.sh`'s `relay_next_agent` (`poll.sh:156`) only tolerates bold on the key (`**NEXT:** value`), so it parsed `claude-reb**`, misclassified the seat as a non-Claude agent, and returned `nudge-cross-model` — stalling turn 1. Normalized both `STATUS:`/`NEXT:` lines to `**KEY:** value`. (Upstream hardening — make `poll.sh` strip trailing markdown — captured as XYZ-maintainer feedback, not fixed here.)

## [0.51.3] - 2026-07-01

### Fixed
- **Client gap-fill prompt silently dropped the calendar signal when a GitHub signal was also present** (`src/rebalance/ingest/project_inference.py`) — `_project_activity_snippets()` capped its return to `snippets[:2]`, but a project with both repo activity (2 lines: `Repos:` + GitHub activity) and calendar activity (1 line) produces 3 candidate lines, so the calendar line was truncated away before ever reaching the Gemini gap-fill prompt. Found reviewing the PR #100 merge (`test_client_gapfill.py::test_gapfill_prompt_includes_recent_signals` was failing on `development`, uncaught because it wasn't in that PR's test plan). Removed the cap — all built snippets (max 3) now reach the prompt. `pytest tests/` 1258/1258 green.
- **Unified refresh QA-R remediation** (`scripts/pulse_server.py`, `scripts/pulse_web.py`, `scripts/apple_reminders_helper_app.swift`, [PR #100](https://github.com/Hypercart-Dev-Tools/rebalance-OS/pull/100)) — closed all 7 findings from the v1 QA review: a failed EventKit helper call now returns `ok: false` and the dashboard shows a "⚠ Reminders stale" badge instead of silently serving stale data (last-good `active.json` preserved); DB-less rendering on cold start is now an explicit documented design choice instead of an unstated regression; the `active.json` path is a single shared `ACTIVE_JSON_PATH` constant instead of two hardcoded literals; the on-disk contract is a versioned envelope (`{"schema_version": 1, "items": [...]}`) with a backward-compat reader for the old bare-list shape; the Swift helper's `semaphore.wait()` is now bounded to 4.5s with a typed timeout instead of hanging indefinitely. 8 new tests in `tests/test_unified_refresh_remediation.py`. agy-reviewed, Approved. → `PROJECT/2-WORKING/UNIFIED-REFRESH-RESTART.md`
- **Focus5Probe no longer aborts when launched without usable stdio** (`macOS/Apps/Focus5Native/Sources/Focus5Probe/main.swift`) — the sandbox harness's `line(_:)` helper used Foundation's `print`, which routes through `NSConcreteFileHandle` and can raise an Objective-C exception if the probe is launched from an app/sandbox context with closed or invalid stdout/stderr. Replaced that path with direct `Darwin.write` calls plus `SIGPIPE` ignore/fallback-to-stderr behavior, so detached launches now exit cleanly instead of crashing before the git probes run. Validated with a detached subprocess launch (`stdout=DEVNULL`, `stderr=DEVNULL`) and a normal foreground run; both exit `0`.

### Changed
- **Client auto-discovery Phase 2 closed at v1 by kill-check** (`src/rebalance/ingest/project_inference.py`, [PR #100](https://github.com/Hypercart-Dev-Tools/rebalance-OS/pull/100)) — the Gemini gap-fill for `None`-client projects (batched call, fail-soft) shipped code-complete, but measuring owner-as-client coverage against the live repo-local registry found 15/15 active projects (100%) already labeled, so the ≥90% kill switch fired: Gemini gap-fill ships dormant with no live rows to exercise it, activating automatically only if a calendar-only or personal-account project appears. No interface changes to `registry.py`/`next_actions.py`. → `PROJECT/2-WORKING/CLIENT-AUTO-DISCOVERY.md`

## [0.51.2] - 2026-06-30

### Fixed
- **git-pulse collector now stages the PDDA registry projection** (`experimental/git-pulse/collect.sh`, GH-[#96](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/96)) — the collector staged `pulse-<device>.md` and `devices/<device>.yaml` but not the `pdda/registry-<device>.tsv` projection that PDDA's `install.sh` writes into the sync repo, so on PDDA-installed devices it sat as untracked dirt and never committed/pushed. Added a guarded `append_stage_path "pdda/registry-$device_id.tsv"` before `git add` (scoped to the single per-device file; the `[ -f ]` guard keeps it a no-op on devices without PDDA). This is the sync-side half of the multi-device PDDA rollup; the write-side path-autodetection fix was `Hypercart-Dev-Tools/pdda#7`. Verified by a new `tests/test_git_pulse_collect_cli.py` case (projection is staged when present) → 5/5 in that file; `bash -n` clean; `rebalance doctor` clean; `pdda.sh run` clean. -> `PROJECT/3-COMPLETED/GH-96-GITPULSE-STAGE-PDDA-PROJECTION.md`

## [0.51.1] - 2026-06-30

### Changed
- **Apple Reminders dashboard complete is now truly optimistic** (`scripts/pulse_web.py`) — the row checks + collapses immediately on click and the write runs in the background, instead of freezing the row until the server responds. The server-side write can wait on the `rebalance.db` write lock during a concurrent sync (`busy_timeout=30s`); only a real failure now rolls the row back. The EventKit op itself is ~1s; the lag was the audit-row `INSERT` contending with syncs, not the reminder write.

## [0.51.0] - 2026-06-30

Made the pulse "Today" dashboard Apple Reminders column actionable (Apple Reminders Unified Plan, Phase 6 dashboard write-back v1).

### Added
- **Dashboard "complete" for Apple Reminders** — a per-reminder check in the pulse "Today" column now completes the reminder via `POST /api/apple-reminders/complete` (`scripts/pulse_server.py`). The write routes through the existing Phase 5.1 orchestrator (`apply_reminder_writes` → signed helper), so the single-writer + audit-table discipline is preserved and the web layer holds no EventKit/SQLite write of its own. `create`/`delete` stay CLI-only.
- **Regression tests** — `tests/test_pulse_server_apple_reminders.py` (5 tests): the endpoint builds exactly one `complete` op in `apply` mode, missing id → 400, helper/auth failure → 502, per-op error → 502 (the row never falsely shows "done"), and a static guard that the web layer contains no direct EventKit/SQLite write.

### Changed
- **Apple Reminders column UX** (`scripts/pulse_web.py`) — rows now render a clickable complete check carrying `data-reminder-id`; on success the row greys out optimistically (the local table reconciles on the next scoped sync, since the loopback server has no Full Disk Access). The "read-only" empty-state copy was dropped. A row without a `reminder_id` degrades to read-only.

## [0.50.1] - 2026-06-30

Fixed the Focus 5 macOS app assuming `rebalance serve` on port 8787 was the only valid local backend.

### Fixed
- **Dual-port local fallback** — when `FOCUS5_BASE_URL` is unset, the Focus 5 macOS client now probes `http://localhost:8787` first and then the mirrored pulse server on `http://127.0.0.1:8767` for the Focus 5 JSON/note/goals routes, instead of failing outright on the first dead port.
- **Misleading offline copy** — the app's offline message and README now describe both supported local server paths so an always-on pulse-server setup does not look broken when `rebalance serve` is down.

## [0.50.0] - 2026-06-30

Added Obsidian-backed reminders to the Focus 5 macOS app and made their failure states diagnosable instead of collapsing into a generic load error.

### Added
- **Obsidian Reminders block in Focus 5 Float** — the macOS app now shows a second reminders section under Apple Reminders, sourced from the first 8 open checkbox items in the vault-root `0. Goals.md`, with checkbox-complete write-back that flips only the exact matched markdown line.
- **Shared goals-file runtime** — `0. Goals.md` parsing and checkbox mutation now live in one shared helper used by both the pulse flow and Focus 5, including line-index-aware completion fallback and atomic tmp-file replace.
- **Local Focus 5 goals routes** — `GET /focus-5/goals` and `POST /api/focus5/goals/complete` expose the Obsidian reminders read + partial-write path to the native app through the same localhost contract pattern already used by the Focus 5 note drawer.

### Changed
- **Apple reminders labeling and cap** — the native app now labels the EventKit block explicitly as Apple Reminders and caps both Apple and Obsidian reminder lists at 8 rows for a consistent drawer height.

### Fixed
- **Opaque Obsidian-reminders errors** — the native client now distinguishes transport, HTTP, and decode failures for `/focus-5/goals`, so server-down, route-missing, and malformed-response failures surface different messages instead of the generic "Couldn't load Obsidian reminders."
- **Missing-vault/file observability** — the server goals payload now carries explicit `reason` / `message` metadata for `vault_not_configured`, `file_missing`, and `read_failed`, letting the app explain exactly why `0. Goals.md` is unavailable.

## [0.49.1] - 2026-06-30

Fixed the "what to do next" list collapsing to ~2 items right after 0.49.0 shipped.

### Fixed
- **Reasoning-model truncation** — `gemini-2.5-flash` is a thinking model; on the ranking prompt it spent ~1962 of its 2048-token budget on hidden reasoning and hit `finishReason=MAX_TOKENS` after emitting only ~2 list items (24 candidates went in). `_synthesize_gemini` / `_synthesize_with_fallback` now accept a `thinking_budget`, and the next-actions ranking call passes `thinking_budget=0` to disable reasoning so the whole budget goes to the answer (the full ~15-item list). `ask()` is unchanged (default `None`). Covered by `tests/test_querier_gemini_parse.py::TestThinkingBudget` + `tests/test_next_actions.py`.
- **Self-reference feedback loop** — the generated `Dashboards/What To Do Next.md` was itself picked up as a "recent vault edit" and ranked in its own list every refresh. `_operator_candidates` now skips rebalance's own generated next-actions file (`_is_generated_next_actions_file`).

## [0.49.0] - 2026-06-29

Made the daily "what to do next" genuinely Gemini-synthesized (paid key file) and published it to a fixed Obsidian vault file. Root cause of the prior placeholder titles: the default Gemini model had been retired, silently forcing every synthesis onto the local Qwen fallback.

### Added
- **Paid-key file resolver** in `get_gemini_api_key()` (`src/rebalance/ingest/config.py`): a new resolution step reads the key from a file — path from `GEMINI_API_KEY_FILE` env → `gemini_key_file` config → default `~/secrets/gemini-paid-key.txt` — after env vars and before the gcloud fallback. `_pick_api_key` extracts the `AIza…` key from a multi-line file (e.g. a project-id line + key line). The file lives outside the repo by design; the key is read in-memory and never logged. Covered by `tests/test_gemini_key_resolution.py`.
- **Vault render sink** in `src/rebalance/ingest/next_actions.py`: `render_next_actions_markdown()` + `write_next_actions_to_vault()` write the SAME ranked output to the fixed file `Dashboards/What To Do Next.md` (single-writer generated banner), wired into the `refresh_index` precompute hook (gated on `update_dashboard_note` + a resolved vault, reusing the resolved path). Covered by `tests/test_next_actions.py::TestVaultRender` and `tests/test_next_actions_precompute.py`.

### Fixed
- **Retired Gemini model** — `DEFAULT_GEMINI_MODEL` was `gemini-2.0-flash`, which Google now 404s as "no longer available", silently forcing every synthesis onto the local Qwen-0.6B fallback (the source of the `<rank>. <title>` placeholder titles). Standardized on `gemini-2.5-flash` (already used by `note_builder.py`/`cli/dashboard.py`); the ranking synthesis call gets 2048-token headroom so a reasoning model isn't truncated to a no-text response.
- **Placeholder-echo hardening** — `_parse_ranked_synthesis` now drops a line whose title is an unfilled `<rank>`/`<title>` template token and ignores `<…>` field values, so a weak fallback model can never surface the format spec as a real action (the deterministic ranking survives instead).
- Made `tests/test_repair_fsm.py` hermetic — its `_make_fsm` helper no longer resolves an ambient machine key, so the "no API key" path is tested deterministically regardless of local key files.

## [0.48.0] - 2026-06-26

Added a bottom note to the Focus 5 Float macOS card: it reads a hand-written `focus5.md` from the operator's Obsidian vault and renders it under the roster, with a hint when no note exists.

### Added
- New read-only route `GET /focus-5/note` in `src/rebalance/web.py` (`focus5_note()`) — projects `focus5.md` at the configured vault root as `{exists, content, path}`, capped at 64 KiB, always HTTP 200. Strictly read-only (never creates/writes the file). Covered by `tests/test_web_focus5.py::Focus5NoteRouteTests`.
- Focus 5 Float now fetches the note on every refresh/poll and renders it pinned at the bottom of the Focus 5 / Dirty Five card (`Focus5NoteView` in `ContentView.swift`), with light markdown (headings, bullets, inline emphasis/links). When the vault has no `focus5.md`, it shows: *"To show a text file here, add a doc called focus5.md into your Obsidian vault."*
- Wire contract documented in `macOS/Apps/Focus5Float/CONTRACT.md` (new "Bottom note" section) with the Swift `Focus5Note` codec.

### Changed
- Focus 5 Float layout polish: the note now renders as a content-hugging card at the end of the roster scroll (was a greedy fixed-height footer that reserved ~280px even for a short note). Default panel size 360×640 → 380×560 with a 360-wide minimum so the 3-tab header + status light stop clipping; frame autosave bumped to `.v2` so a stale oversized saved frame resets once.

## [0.47.2] - 2026-06-25

Registered a new Apple Reminders project and consolidated prior reference docs into one execution-ready working plan.

### Added
- New active project plan at `PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md` with frontmatter, near-top status table, TOC, phased execution checklists, and QA gates per phase.

### Changed
- Added roadmap ledger registration for the Apple Reminders unified integration plan under in-progress work.

## [0.47.1] - 2026-06-25

Focus 5 Float Telemetry tab is hardened against large files: the loader is bounded and the row list keys are made collision-proof.

### Fixed
- Telemetry `ForEach` now keys on the enumeration offset instead of `health_title`, eliminating SwiftUI duplicate-ID glitches (dropped rows, broken scroll) when two rows share the same health + title — likely once a file holds thousands of entries.
- Telemetry loader caps retained/rendered rows at the newest 10k (`Focus5Model.telemetryRowCap`) via `prefix` after the newest-first sort, so decode and render stay bounded even if the source file grows unbounded.

## [0.47.0] - 2026-06-25

Focus 5 Float Telemetry tab gains explicit file selection from the F5 menu bar and surfaces decode errors in the UI.

### Added
- "Select Telemetry File…" (⌘T) menu item in the F5 right-click menu; opens `NSOpenPanel` for `.json` files, saves the selection to `UserDefaults`, and switches the panel to the Telemetry tab automatically.
- Menu item label updates dynamically to "Telemetry: \<filename\>" after a file is selected; reverts to "Select Telemetry File…" when cleared.
- Visible decode error state in the Telemetry tab: if the selected file exists but has invalid structure, the tab shows an actionable error message instead of a blank screen.
- "No file selected" empty state in the Telemetry tab (default before any file is chosen); replaces the Phase 1 auto-folder scan as the primary entry point.
- Cold-start restore: previously-selected telemetry file reloads automatically on relaunch (path persisted in `UserDefaults`).

### Changed
- Telemetry tab header info row now shows the selected filename + entry count instead of a generic "N signals" label.

## [0.46.0] - 2026-06-25

Focus 5 Float gains a third Telemetry tab: reads health-annotated JSON rows from `~/Documents/telemetry/` and renders them with green/orange/red dots, title, description, and relative timestamp — all via existing design tokens and components.

### Added
- Focus 5 Float Telemetry tab: a third panel option (`📊 Telemetry`) in the header segmented control that reads `*.json` files from `~/Documents/telemetry/`, decodes them as flat arrays of `{ health, title, description, updatedAt }` rows, and renders them newest-first with `HealthDot` (green/orange/red), title, description, and a relative timestamp.
- `TelemetryModels.swift`: `HealthStatus` enum and `TelemetryEntry: Codable, Identifiable` wire model.
- `TelemetryReader.swift`: pure file-reader that merges all `*.json` files in the telemetry folder, skips malformed files with a logged warning, and sorts by `updatedAt` descending.
- `HealthDot` component in `Components.swift`: orange-capable status dot for telemetry rows (parallel to `StatusDot`, which remains unchanged for repo cards).
- `ViewMode` enum (`Focus5Model.swift`): decouples panel selection (`focus5` / `dirtyFive` / `telemetry`) from server-side `rankingMode` so switching to Telemetry and back preserves the last ranking.
- Telemetry header health rollup: the existing `RosterHealth.tint` logic now drives a "Status: N" dot over non-green telemetry signals when the Telemetry tab is active.
- Demo seed at `~/Documents/telemetry/focus5float-demo.json` with three sample rows (green/orange/red).

### Changed
- Focus 5 Float header Picker binding migrated from `isDirtyView: Bool` to `ViewMode`; `isDirtyView` is retained as a computed shim so all existing server-fetch and caching paths are unchanged.
- Refresh button (`↻`) now re-reads telemetry files when the Telemetry tab is active; Start Server button is hidden in Telemetry mode (irrelevant).

## [0.45.0] - 2026-06-25

Focus 5 Float reaches a real installable app: it now ships to `/Applications`, can launch at login, and surfaces overall roster health at a glance.

### Added
- Focus 5 Float roster-health traffic light in the panel header (top-right, so it never reads as a close button): green = all roster repos clean, orange = some dirty, red = all dirty, labeled "Status: N" where N is the dirty count. Backed by a pure `RosterHealth.tint` rollup with a `FOCUS5_HEALTHTEST` headless self-check.
- Focus 5 Float launch-at-login: a "Launch at Login" toggle in the F5 menu-bar menu (via `SMAppService.mainApp`) with a live checkmark and graceful failure logging.
- Focus 5 Float docs: an app `README.md` (build/run, `rebalance serve` prerequisite, launch-at-login, icon, self-checks, contract) and a pointer to it from `macOS/README.md`.

### Changed
- Focus 5 Float Phase 5 (packaging) completed and the project doc marked `status: complete`; the settings-window and per-setting controls were deliberately descoped (YAGNI for a single-operator menu-bar tool — `FOCUS5_BASE_URL` covers server config). Icon wiring is in place (`make-app.sh` auto-picks `Resources/AppIcon.icns`); artwork is pending.

## [0.44.0] - 2026-06-24

The headline activity board now ranks on whether *your local checkout* committed recently — read from the HEAD reflog — instead of matching a single configured author email. Working under more than one identity (CLI vs web-merge noreply) no longer silently drops recent local work off the board.

### Added
- Local-commit recency vector: a reflog operation classifier (accept a commit / amend / cherry-pick / revert / rebase / real merge; reject a fast-forward pull, fetch, checkout, clone, reset; an unrecognized op is rejected and logged) feeding a recorded fallback ladder — local reflog → author email → any commit (only when the reflog is genuinely unavailable) → none.
- A recorded ranking basis on every repo signal plus a minimal explain payload (per-repo basis and the board's #5 cutoff) so it is always visible *why* a repo ranks, with no silent bias.
- Operator-facing explain UX on the activity board: each off-roster repo now shows, inline, why it isn't in the top 5 (its last local commit vs the #5 cutoff), and any repo ranked by a fallback basis (e.g. a clone whose reflog is disabled) carries a visible badge — answering "why is repo X here / not here?" without `git log` forensics.

### Changed
- The default headline ranking now uses the identity-agnostic local-commit recency; the author-email signal is retained as a displayed diagnostic and a fallback input. Other ranking modes are unchanged.
- A migration-test fixture now builds its prior-version database by applying the real intermediate migrations rather than stamping them, so additive column migrations that touch earlier tables are exercised faithfully.

### Fixed
- Repos whose recent local commits were authored under a non-matching email (forks, web-merge noreply, multi-identity work) no longer silently disappear from the board. On a real 88-repo device, 24 such repos became eligible again.
- Hiding a repo right after the upgrade can no longer blank the board: a backfill step populates the new recency columns for pre-existing rows, so a re-rank before the first fresh scan reproduces the prior roster instead of dropping everything as ineligible.
- The "below the #5 cutoff" explanation is shown only on the headline board; the at-risk (Dirty Five) view no longer labels its own cutoff with headline-board wording.

## [0.43.0] - 2026-06-23

Focus 5 Float reaches feature-complete (Phases 1–4) and passes an automated Codex QA pass — the macOS menu-bar app now renders the real, live Focus 5 roster as a floating, collapsible card stack over the same `summarize_focus5()` the web `/focus-5` uses.

### Added
- macOS `Focus 5 Float` is now a runnable menu-bar app: a non-activating, always-on-top floating `NSPanel` (F5 status-item toggle, right-click menu, Esc-to-hide, first-mouse interaction, frame autosave, hidden window chrome) hosting a SwiftUI card stack.
- Live data: a read-only `Focus5Client` pulls `GET /focus-5.json` (90s poll, manual Refresh, ranking-mode re-fetch, offline handling, tap-a-card-to-open-in-VS-Code) — no ranking/git/DB logic in Swift; the server stays the source of truth.
- Collapsible repo cards mirroring the web card: tap to expand into Tree health / Newest PR / Recent activity, plus an in-panel Focus 5 ⇄ Dirty Five toggle, a ⚠ stale badge, and a collapsible off-roster footer.
- `Focus5Float` SwiftPM package harvesting the TextReplacementStudio design system (`Theme`, `KeyCap`/`GroupTag`/`StatusDot`), `Codable` wire models, a bundled fixture, and headless `FOCUS5_SELFTEST` / `FOCUS5_LIVETEST` decode smoke tests.
- `make-app.sh` packaging for Focus 5 Float: release build → ad-hoc-signed `.app` bundle (menu-bar agent via `LSUIElement`) installed to `/Applications` (Phase 5 install path).

### Changed
- Focus 5 Float repo cards are now zebra-striped — alternate rows use an `elevatedAlt` fill (the elevated color darkened ~12%) for easier row scanning.

### Fixed
- Focus 5 Float mode/refresh race: concurrent poll, manual refresh, and ranking-mode switches could apply out of order; a generation guard now lets only the latest fetch apply, and an optimistic mode flip reverts on a real fetch failure. (Codex QA)
- Focus 5 Float empty-state copy no longer implies that in-app Refresh rebuilds the roster — it correctly directs the operator to build the roster server-side, then re-pull. (Codex QA)
- Focus 5 Float now keeps its local-only data posture: a non-loopback `FOCUS5_BASE_URL` is honored only under an explicit debug opt-in, otherwise it falls back to localhost (the payload carries `local_path` / `vscode_url` / `author_email`). (Codex QA)
- Focus 5 Float menu-bar checkmarks no longer drift from the active ranking mode: the context menu recomputes its checkmarks from the model on open, so the in-panel toggle and the menu stay in sync. (Codex QA)

## [0.42.0] - 2026-06-23

Focus 5 Float Phase 0 spike and PDDA doc compliance corrections — shipping the local FastAPI JSON endpoint and macOS floating panel spike, alongside repo-wide doc hygiene and test collection fixes.

### Added
- FastAPI `GET /focus-5.json` read-only local endpoint (macOS Focus 5 Float Phase 0) serving the Focus 5 card stack roster and off-roster warnings.
- macOS `Focus 5 Float` SwiftUI application target scaffolding and the interactive, non-activating always-on-top spike (`FloatPanelSpike.swift`).

### Changed
- Consolidated the `utilities/` folder into `utils/` at the repository root to simplify project directories.

### Fixed
- A bug in `pdda-check-changelog.sh` regex parser that missed SemVer formatted headings and falsely reported the changelog as stale.
- Cleaned up absolute hardcoded paths in project documents to comply with the portable, machine-neutral contract.
- Added required frontmatter (`title` and `goal`) and `## Status` headers to active plans to satisfy the PDDA active-doc contract.
- Linked active plans (`FOCUS-5-RANKING-BUG-AND-REMEDIATION.md` and `P2-TEAM-CALENDAR-SIGNAL.md`) in `ROADMAP.md` to satisfy roadmap coverage checks.
- Renamed the onboarding manual test script to `smoke_onboarding.py` to prevent it from breaking standard pytest collection.

## [0.41.1] - 2026-06-21

Front-door, portability, and auth-hardening cleanup — closing the remaining
runtime-contract, test-coverage, and documentation gaps so a newcomer's
clone-to-working path and the credential model are accurate and enforced.

### Fixed
- Semantic-maintenance commands no longer silently accept calendar/reminder
  sources they cannot actually index. The accepted source set is now derived
  from the live indexing stage, so the maintenance CLI and the runtime can no
  longer drift apart, and an unsupported source is rejected with a clear error
  instead of doing nothing.
- Restored the test suite: a broken module import had been interrupting
  collection and leaving continuous integration red, so the contract tests
  were not actually running on every change.
- The Gmail re-auth hint no longer tells operators to run a redundant migration
  step that the setup flow already performs in one pass.

### Added
- The health check now reports posture for the Figma integration and
  distinguishes "optional and not configured" (a clean skip) from "configured
  but broken" — for example, files selected to sync with no token — so a
  silently failing integration becomes visible. This immediately surfaced a
  real, previously-silent misconfiguration.
- CI-enforced contract tests for the credential model: secrets can no longer
  leak back into repo-local config; migration refuses to remove a secret from
  the legacy location until the new store has provably retained it, so an
  unattended job can never be locked out; and auth-activity plus token-lifetime
  metadata survive migration and token refresh (fingerprint-only, with the
  original authorization date preserved). The dashboard re-ingest path and the
  opt-in Figma path gained real (non-mocked) coverage.

### Changed
- Operator and newcomer documentation now matches the shipped credential model
  everywhere: the OS keyring is primary, with a permission-locked data-only
  fallback stored outside the repository. Retired token-format and redundant
  migration wording were removed; the one legacy migration step that still does
  real work is kept and scoped to that purpose.
- The front door now states the supported platform, the cross-platform subset
  that runs without the on-device embedding stack, and the one-time first-run
  network access (the model download and the GitHub/Google APIs) before the
  first install command — correcting the prior overstated platform requirement.
- The Gmail local-account versus host-connector ingest choice now states the
  privacy trade-off (whether data stays on the machine or routes through the
  host cloud) and the connector precondition inline. Calendar host-connector
  ingestion is clearly marked as planned, not shipped.

## [0.41.0] - 2026-06-18

P2 **Phase 2 — v0.5 "What should we work on next"** (product milestone *v0.5*; the
semver continues forward from 0.40.x). A ranked, person-attributed next-action view
blended from the operator's signals + teammate calendars, synthesized by Gemini, on
its own dashboard page. Built Ultra-Code; one 30-agent adversarial review applied.

### Added
- **Shared ranking core `next_actions.rank_next_actions`** ([next_actions.py](src/rebalance/ingest/next_actions.py)) —
  the single ranked-output service both the dashboard route and `ask()` call (the DRY
  parity gate). Productizes the Phase-0 A/B harness blend + content de-dup; reads
  teammate rows via the new person-scoped `calendar.get_team_upcoming_by_person`;
  applies the `SignalWeights` levers + a per-person additivity gate (Matt-first; sparse
  teammates earn in by logging density); synthesizes through the existing Gemini→Qwen
  `_synthesize_with_fallback` adapter with a deterministic ranked fallback so it never
  returns blank. **Migration 0006** adds the local-only `ranked_next_actions` precompute
  cache (never exported).
- **`/whats-next` dashboard page** ([web.py](src/rebalance/web.py)) — its OWN page, live on
  `rebalance serve` and the always-running `pulse_server`; reads the precompute and
  recomputes live (+persists) on `?refresh`.
- **`ask(team=True)` MCP parity** — returns the same ranked output via a sidecar attribute,
  leaving the pinned `QueryResult` contract byte-identical for `team=False`.
- **Precompute hook in `refresh_index`** — the network-allowed sync computes + persists the
  ranked list (gated, fail-safe) so the offline launchd dashboard can read it.
- **`automation` tag** — each ranked action is inferred as a candidate for a GitHub-issue →
  coding-agent (Codex / Claude Code) hook (a code/repo task vs a meeting/email/vague hold),
  via an `automation=` field in the synthesis grammar + a deterministic `_infer_automation`
  heuristic. Surfaced as an "⚙ automation" tag in the UI. (No issue is created and no agent
  is triggered yet — tag only.)

### Changed
- **Static pulse "what's next" is now a slim teaser**, not a full embedded panel — it shows
  the top item, a ranked/automation-ready count, and a link to the dedicated `/whats-next`
  page, so it no longer crowds the main dashboard.
- Calendar reader defaults (`get_upcoming_events`/`get_recent_events`/`get_daily_totals`)
  now bind `OPERATOR_CALENDAR_ID` instead of the literal `"primary"` (DRY).

### Fixed (30-agent adversarial review, 14 verified findings)
- **Synthesis fallback integrity (HIGH):** a degenerate Gemini/Qwen parse (any numbered prose
  line) could overwrite the *good* deterministic candidate ordering with metadata-stripped
  prose. The output now uses a uniform pipe `key=value` grammar with a robust parser and an
  **acceptance gate** — the deterministic fallback survives unless ≥½ parsed items carry a
  structured field. Validated live (Qwen prose rejected, candidates kept).
- Multi-day teammate dedup, accurate `blended` badge, route persists every live compute
  (no recompute-per-load), `ask(team=True)` prefers the cache (no second LLM call), additivity
  over a trailing-30d window, and the dropped-ball class is now named/targeted in the prompt.

### Privacy
- Teammate `person` labels stay local-display-only; export paths (`sync_snapshot`,
  `export_calendar_snapshot`, pushed pulse) untouched; the precompute cache is local-only.
  `test_next_actions_privacy.py` regression-locks the invariant. (992 tests.)

## [0.40.2] - 2026-06-17

P2 Phase 1 — privacy-seam test hardening (follows 0.40.1 F1). A re-run of the
two-model consult hand-off re-confirmed the seam at HEAD and asked for explicit
export-path coverage of the `person`-label omission; added below.

### Added
- **Regression tests locking the `person`-label export omission.** Both off-machine
  export paths now assert that an adversarial `primary` row *carrying* a person label
  (plus a teammate row) never leaks the label or the teammate row:
  `test_sync_snapshot.test_person_label_never_exported` (JSON snapshot) and
  `test_pulse_calendar_scope.test_person_label_never_in_upcoming` (pushed pulse render).
  The `person` omission was previously enforced only structurally (`_CALENDAR_COLUMNS`
  and the narrow pulse `SELECT`); a future edit re-adding `person` to either path now
  fails loudly. (918 tests.)

## [0.40.1] - 2026-06-17

P2 Phase 1 — privacy-seam QA follow-up. A scoped local review plus a two-model
`/consult` (Codex + Gemini) of `export_calendar_snapshot` + migration `0005`
found no leak path and no data-loss scenario; the only finding was a
single-source-of-truth nit (F1), fixed here.

### Changed
- **Calendar-scope filters unified to `OPERATOR_CALENDAR_ID`** (F1). The operator-only
  calendar scope was hardcoded as the literal `'primary'` at six sites; all now use the
  `OPERATOR_CALENDAR_ID` constant (`calendar_config.py`) for a single source of truth:
  `sync_snapshot.export_calendar_snapshot` (the off-machine export seam),
  `pulse._query_calendar_upcoming` (the pushed render), `querier` (vacation check),
  `index_ops._refresh_calendar` (operator write/canonical store + dry-run + result), and the
  `scripts/dashboard.py` / `scripts/spike_morning_brief.py` readers. Behaviour is unchanged
  (`OPERATOR_CALENDAR_ID == "primary"`); the bound value stays fixed (never caller-supplied)
  and `'primary'` remains reserved at config load, so the no-widening privacy guarantee is
  preserved. The pulse site's prior "keep this a constant literal" guard is intentionally
  overridden — each site carries an inline `REVERT PATH` note to inline the literal again if
  defense-in-depth is ever preferred over DRY.

### Fixed
- **Stale scheduler-policy test token.** `test_scheduler_policy.py` still required the pulse-sync
  wrapper to contain `publish_pulse(..., push=True)`, but `72ebd7e` (PULSE_PUSH opt-out) changed the
  wrapper to `push=push`; the test token is now aligned. Test-only; no runtime behaviour change.

## [0.40.0] - 2026-06-12

P2 Phase 1 — team-calendar signal — plus a max-effort code-review hardening pass
(findings A–G) and a follow-up external review.

### Added
- **Team-calendar signal (P2 Phase 1).** `calendar_config.json` gains a `team_calendars` list (`{person, calendar_id}`); `refresh_index` syncs each teammate calendar alongside the operator's own and attributes rows via a new `person` column on `calendar_events`.
- **`calendar_events` composite primary key** (migration `0005`): row identity is now `(id, calendar_id)` so the same Google event id can coexist on the operator's and a teammate's calendar; adds the `person` column and a `(calendar_id, start_time)` index.
- **Gemini cloud synthesis** for `ask()` (preferred over local Qwen), with the API key resolved from Google Secret Manager.

### Fixed
- **`calendar-sync` crashed on pre-0005 databases** — `sync_calendar` (the only writer of `calendar_events`) now runs migrations at the write chokepoint, so callers that skip `refresh_index` (notably the `calendar-sync` CLI) no longer hit `OperationalError: no such column: person`.
- **One inaccessible teammate calendar aborted the whole calendar refresh** — the `team_calendars` loop now isolates per-calendar failures (mirroring the GitHub loop), so a revoked/404 teammate calendar no longer discards the operator's own sync result or suppresses the dashboard note.
- **Operator reports/timesheet/inference came up empty under a non-'primary' config** — `get_day_data`, `note_builder`, and `project_inference` now read the operator's canonical `'primary'` rows (new `OPERATOR_CALENDAR_ID` constant) instead of `config.calendar_id`.
- **Teammate-data export leak via misconfig** — a `team_calendars` entry whose `calendar_id` is the reserved `'primary'` is now rejected at config load (it would otherwise be exported off-machine to the pulse repo).
- **Gemini synthesis crashed on MAX_TOKENS/SAFETY responses** — `_synthesize_gemini` parses defensively, raising a clear error (with finishReason/blockReason) and returning partial text instead of a raw `KeyError`/`IndexError`.
- **Collectors ran against a half-migrated schema** — `refresh_index` now skips collectors (recording each scope as skipped) when `run_migrations` fails, instead of emitting confusing secondary errors.
- **`calendar-sync --calendar-id` was silently ignored** — an explicit calendar id is now synced verbatim; only the operator's own default calendar is canonicalised to `'primary'`. `CalendarSyncResult` reports the calendar actually synced.
- **Gemini key resolution** — `get_gemini_api_key` adds a `gcloud secrets versions access` fallback (the documented P2 pattern) so the key resolves even without the optional GCP Python package; env vars still short-circuit first.

### Changed
- **Migration runner owns each migration's transaction.** Migration files must no longer carry their own `BEGIN`/`COMMIT`; the runner wraps each one so a bare multi-statement migration that fails mid-script rolls back atomically (previously only self-wrapped migrations were safe). `0005` and the migrations README updated.
- **Version metadata reconciled.** `pyproject.toml` (`0.35.0`) and `rebalance.__version__` (`0.39.2`) were stale relative to the changelog and are now aligned to `0.40.0`.

## [0.39.3] - 2026-06-12

### Changed
- **Sidebar reminders now match the "show reminders" Slack command** — same sections (Due Today → Due after today → Due within last 7 days → Due older than 7 days), same chronological sort, same global A/B/C labels, and resolved assignee display names. The sidebar reads `display.*` fields from the published git-pulse file (which Sleuth's v1.4.184+ export already pre-renders) instead of extracting raw `reminder_message_text` from SQLite. Falls back to the previous flat SQLite list when the published file is unavailable. Addresses the follow-up noted in sleuth-app CHANGELOG v1.4.184.
- `fetch_sleuth_display_sections()` added to [scripts/dashboard.py](scripts/dashboard.py): reads the local published JSON, recomputes `ageDays` from `createdOn`, returns `(sections, total)` bucketed in `sectionOrder` sequence.
- `build_nav_data` in [scripts/pulse_web.py](scripts/pulse_web.py) gains a `sleuth_sections` parameter; when present, renders section sub-headers and canonical reminder lines (`{label}.) {summary} ({N}d old) · {assigneeName}` with Slack permalink). Flat `sleuth_rows` fallback path unchanged.
- Stream badge count reflects the full published total when sections are available (previously capped at 6).

### Fixed

- **PAT guidance named a nonexistent scope (`repo:read`) — user-reported.**
  GitHub classic tokens have no read-only repo scope, so users hunting for
  "repo:read" landed on `public_repo` or the fine-grained "Public
  repositories" default — making their private work silently invisible to
  discovery and github-scan. All six doc sites (README, ARCHITECTURE,
  PROJECT ×3, /welcome skill + demo transcript) now give correct guidance:
  classic `repo` scope, or fine-grained with All-repos read-only
  Contents/Metadata. PROJECT.md's threat-model line restated honestly
  (classic `repo` is read/write — treat as sensitive). `setup_github_token`
  now returns a `visibility_warning` when a valid token likely can't see
  private repos (classic without `repo`; fine-grained default-trap
  advisory), and the welcome agent surfaces it verbatim at setup time.

## [0.39.1] - 2026-06-11

### Fixed

- **Phase 6 adversarial-review fixes (Gemini).** Status precedence is now
  `done` > `blocked` > `skipped` — a skip marker never masks unmet
  prerequisites (the review's "hard to reverse later" call, fixed before any
  client depends on it). Ctrl+C during a CLI optional-stage offer no longer
  persists a skip. Executor dispatch survives non-checkout installs (absolute
  venv python, `sys.executable` fallback, remediation listing when no repo
  root). OAuth status checks now probe the token FILE the collectors actually
  read, not just the keyring (hermetic mode skips the machine-global path).
  Detached HEADs are no longer flagged as unpushed work. `rebalance reset`
  sweeps the canonical DB path in half-reset states, enumerates
  `sleuth_web_api`, and removes OAuth token files (verified live: 2 files +
  5 secrets found that 0.39.0 missed). Declined with rationale: `com.user.*`
  agents stay outside reset's footprint; launchctl/mtime graduation checks
  stay in the doctor (the contract remains filesystem-pure).

## [0.39.0] - 2026-06-11

### Added

- **Phase 6 complete — the welcome agent ships end to end.**
  - *Graduation stages:* `schedulers_installed` and `first_pulse` join the
    lifecycle contract (optional, after `db_synced`) with patchable seams for
    hermetic sandboxes; clients picked them up with zero edits.
  - *CLI parity finished:* interactive `rebalance onboard` now offers each
    incomplete optional stage (Calendar/Gmail OAuth, scheduler fleet, first
    pulse) by dispatching the contract's executor hints; declining persists
    the skip. `--yes` never launches OAuth or installs jobs silently.
  - *Local discovery (6.1):* `ingest/local_repos.py` promotes the git-pulse
    scanner — scan `local_repo_roots` for checkouts, parse GitHub identity,
    measure unpushed commits; discovery surfaces uncovered on-disk repos as
    `provenance=local-scan` candidates ("found on disk — promote?"). New
    doctor check `local repos` WARNs on unpushed work as an ongoing signal.
  - *Reset path:* `rebalance reset` — dry-run by default, `--force` executes;
    unloads/removes the launchd fleet, deletes config + knowledge base,
    enumerates keyring secrets (deleted only with `--include-keyring`), vault
    never touched.
  - *Hermetic walkthrough:* `tests/test_welcome_walkthrough.py` drives clone →
    first pulse with real config writes in 0.06s. It caught a second
    machine-global escape: the gh-CLI token fallback leaked the operator's
    real login into "fresh" sandboxes — new `REBALANCE_HERMETIC=1` disables
    keyring *and* gh-CLI fallbacks.
  - *Docs:* README Getting Started leads with `/welcome` (manual steps kept
    as reference); PROJECT.md v1.1 note updated — a future desktop UI is now
    just another client of the same state machine; demo transcript committed
    as the skill's UX baseline.

## [0.38.0] - 2026-06-11

### Added

- **Phase 6 (slices 1–3) — lifecycle contract v2 + the welcome agent's front
  ends.** `CONTRACT_VERSION` 2 in `ingest/lifecycle.py`:
  - `REBALANCE_NO_KEYRING=1` makes every keyring helper a no-op — the
    injection seam that lets hermetic walkthroughs run on an operator machine
    without seeing real secrets (Phase 5 spike finding #1).
  - `skipped` status: optional stages can be deliberately skipped (persisted
    via `set_onboarding_stage_skipped` in rbos.config; new
    `skip_onboarding_stage` MCP tool, optional-only) instead of being offered
    as `next` forever; completing a stage always wins over a stale skip
    marker (spike finding #2).
  - Machine-executable `executor` hints per stage (`mcp:` / `cli:` /
    `script:` vocabulary) alongside human remediation prose (spike finding #3).
- **`/welcome` skill** (`.claude/skills/welcome/SKILL.md`): conversational
  onboarding agent — renders where-am-I from one `onboarding_status` call per
  turn, dispatches stages via executor hints, verifies each stage flips to
  done, offers-then-skips optional auth, runs the provenance-grouped promote
  review, graduates into the Phase 4 scheduler installers + first pulse.
  Secrets never enter the transcript; resume works from the contract.
- **`rebalance onboard --status`**: the no-LLM parity client — renders the
  same lifecycle stage map (glyphs for done/now/next/blocked/skipped, fix
  hints for now/blocked) from one `evaluate_setup` call.

## [0.37.0] - 2026-06-11

### Added

- **Phase 5 lifecycle contract — `src/rebalance/ingest/lifecycle.py`.** Two
  machine-readable maps the Phase 6 welcome agent will render: the project
  lifecycle ownership table (discovery → review → confirmation → persistence →
  inference → prioritization, each with one owner and a write-semantics
  vocabulary) and the setup stage machine (config, vault, GitHub PAT, optional
  Calendar/Gmail auth, registry, projections) with `done`/`now`/`next`/`blocked`
  statuses and per-stage remediation hints. `onboarding_status` is now a thin
  view over it (legacy `steps` list preserved).
- **Discovery provenance end to end.** `Project.provenance` field
  (`remote-activity` | `vault-note` | `inferred`; `local-scan` reserved for the
  Phase 6 git-pulse promotion); candidates stamped at discovery, persisted via
  `custom_fields_json` (same pattern as `external`), lifted back to top level by
  `get_projects`.
- **Onboarding E2E tests** (`tests/test_onboarding_e2e.py`): discover →
  confirm → list promote path, provenance round-trip, read-only discovery,
  setup status flipping to done. **Lifecycle contract tests**
  (`tests/test_lifecycle_contract.py`, 13 tests): blocked propagation,
  exactly-one-now, optional-stays-offered, re-poll stability.
- **Thin Phase 6 spike** (`scripts/spike_welcome_status.py`): disposable driver
  that walks the status contract on a sandbox fresh machine (all assertions
  pass) and renders "where am I" for the real machine via `--real`.

### Fixed

- **Discovery no longer creates the registry file.** `discover_candidates`
  called `load_registry`, which writes the default registry when missing — so
  merely running discovery flipped `registry_exists` to done before any
  confirmation. New `read_registry` (pure read) used on the discovery path.
- **Inference can no longer clobber curated registry rows.**
  `sync_inferred_project_registry` skips any name owned by a non-inference row
  (the upsert is name-keyed and would have overwritten curated
  summary/priority/custom_fields wholesale); skips are reported in
  `InferenceSummary.skipped_curated_*` and echoed by the CLI.

### Changed

- **One text normalizer.** `normalize_match_text` in `project_classifier` is
  the canonical implementation; `project_inference` and `project_priority`
  delegate (was three identical copies).
- **ARCHITECTURE.md** documents the registry write discipline and the
  lifecycle module.

## [0.36.0] - 2026-06-11

### Added

- **Phase 4 scheduler consolidation — SCHEDULER.md policy table.** Single source
  of truth for the 10-job launchd fleet (labels, cadences, scopes, prerequisites,
  outputs), the intentional freshness model (vault-sync embeds semantically every
  hour; github-sync defers semantic backfill to daily-sync), and the operator
  runbook. Enforced hermetically by `tests/test_scheduler_policy.py` (17 tests:
  plistlib template rendering, cadence/label/RunAtLoad conformance, wrapper policy
  lines, installer flow, doc coverage — no `launchctl` anywhere).
- **Shared launchd runtime** `scripts/lib/scheduler_common.sh`: env bootstrap,
  per-day logs, job-lifecycle events, retention trimming — sourced by
  `daily_sync.sh`, `vault_sync.sh`, `github_sync.sh`, `pulse_sync.sh`,
  `pulse_web_sync.sh`, `pulse_server.sh` (each shrank to its policy payload).
- **Shared installer flow** `scripts/lib/install_common.sh`: always-unload,
  template render (`{{REBALANCE_DIR}}`/`{{PYTHON}}`/`{{HOME}}`), `plutil -lint`,
  load, poll-verified registration. All `install_*.sh` are now thin wrappers; new
  installers added for the jobs that had none: `install_health_check_scheduler.sh`,
  `install_health_check_triage_scheduler.sh`, `install_obsidian_rollover_scheduler.sh`
  (plus a tracked `com.rebalance-os.obsidian-rollover.plist.template` for the
  previously hand-created plist).
- **`scripts/_bootstrap.py`** — the single remaining `sys.path` shim for
  directly-run scripts (was 7 inserts across 5 scripts: `pulse_web.py`,
  `pulse_server.py`, `dashboard.py`, `chat_eval.py`, `health_issue_reporter.py`).

### Fixed

- **Invalid XML in two plist templates.** `pulse-warning-watch` and
  `health-check-triage` templates carried `--` inside XML comments — rejected by
  expat (plutil tolerates it). Caught by the new conformance tests.
- **Stale `IGNORED_FILES` entries** in `scripts/audit_modules.py` (`db.py`,
  `ask-self-ingest-throttled.py`) unblocked the module audit.

### Changed

- **config.py imports `find_project_root` at module level** — the circular-import
  risk that justified the Phase-1 lazy import no longer exists (`paths.py` imports
  nothing from the package). Closes both Phase-1 deferred items.
- **ARCHITECTURE.md / README.md** point at SCHEDULER.md as the scheduler
  authority; file map documents `scripts/lib/` and `_bootstrap.py`.

## [0.35.0] - 2026-06-10

### Added

- **Phase 5 collector test coverage.** `tests/test_phase5_collector_smoke.py` (13 tests):
  - Smoke tests (dry-run) for all 5 raw sources: vault, calendar, sleuth, email (oauth
    and MCP-skip modes), plus github (already covered in `test_index_ops.py`).
  - Auth/config failure tests for all 5 sources via the `refresh_index` error envelope:
    vault missing path, github missing token, calendar/sleuth API exceptions, email
    `GmailAuthError` returned inline rather than raised.
  - Idempotency tests: vault second-run reports 0 new/updated files (real SQLite);
    calendar result shape is stable across identical calls; github dry-run planning
    is deterministic.

### Changed

- **ARCHITECTURE.md updated for Phase 4/5 contracts.** Calendar credential row now
  references `resolve_oauth_token_path("calendar")`; `paths.py` entry documents
  `resolve_project_root` and `resolve_oauth_token_path` as the stable path resolvers.

## [0.34.0] - 2026-06-10

### Changed

- **Portability contract cleanup (Phase 4).** All `parents[N]` path hacks replaced
  by `resolve_project_root(Path(__file__))` (walk-up resolver in `paths.py`) across
  `cli/_core.py`, `ingest/token_meta.py`, `ingest/auth_log.py`,
  `ingest/semantic_index.py`, and `chat.py`.
- **Auth token paths centralized.** `resolve_oauth_token_path(service)` added to
  `paths.py`; `calendar.py` and `gmail.py` now call it instead of hardcoding
  `Path.home() / ".config" / "rebalance-os" / ...`.
- **Sleuth client-mapping is config-first.** `sleuth_grouping._find_client_mapping_path()`
  checks `rbos.config["sleuth_client_mapping_path"]` (via new
  `config.get_sleuth_client_mapping_path()`) before falling back to the heuristic
  sibling-checkout path.
- **`update_dashboard_note` documented as optional output.** `refresh_index` docstring
  clarifies that the Obsidian write-back is a documented side-output, not a required
  control-plane dependency; callers without a vault set `update_dashboard_note=False`.
- **Operator config contract recorded.** `temp/rbos.config` (gitignored) is the
  repo-local operator store; `~/.config/rebalance-os/config.json` (`USER_CONFIG_DIR`)
  holds cross-repo/user defaults.

## [0.33.0] - 2026-06-10

### Changed

- **Semantic projection is now stage-owned (single writer).** The `semantic`
  collector is the sole writer of `semantic_documents` and `semantic_embeddings`.
  Per-source `_refresh_*` functions no longer call `backfill_semantic_documents`
  or `embed_pending` inline — sources write their raw tables only; the `semantic`
  stage handles all projection and embedding as a follow-on step. This fixes the
  email-never-embedded gap and makes semantic freshness predictable: documents
  become searchable on the next `semantic` run (included in every default recipe).
- **`semantic` stage now covers all five sources.** `_ALL_SEMANTIC_SOURCES =
  ["vault","github","email","code","figma"]` — the semantic stage projects the
  full set, including `code` (previously only run when the code collector ran) and
  `figma` (via the registry-driven provider path).
- **`include_semantic` parameter removed from `refresh_index` and `_refresh_github`.**
  Semantic work is no longer an opt-out flag on individual source refreshes; it
  runs as its own stage. Passing `include_semantic` was previously the only way to
  skip it — use `scope=["github"]` (without `"semantic"`) for source-only refreshes.

## [0.32.0] - 2026-06-10

### Changed

- **Code & docs search now uses Gemini embeddings.** The code-intelligence
  search index was rebuilt on a higher-quality Gemini embedding model instead of
  the local model, improving retrieval relevance. Trade-off: querying it now
  requires the API key and the index is built per environment rather than shipped
  prebuilt. The separate activity/data search index stays fully local by design.
- **A full "all" refresh now means all raw incoming sources.** Refreshing "all"
  covers the raw sources (calendar, GitHub, vault notes, Slack reminders, email);
  the derived search-projection and export steps run as named follow-on stages of
  the default full refresh. A no-argument refresh still does everything, so
  scheduled and daily syncs are unchanged. Also fixed a latent bug where an
  unscoped refresh could skip vault notes.
- **Every data source is now explicitly classified.** Raw sources, local scans,
  the search-projection stage, and the export stage are modeled distinctly instead
  of being treated as interchangeable peers — clearer refresh behavior and a guard
  against future drift.
- **Unified the data write paths.** All command-line and assistant-facing
  data-write operations now flow through a single owned path per source instead of
  calling low-level ingest functions directly, so behavior stays consistent across
  the CLI, the assistant tools, and scheduled syncs. Behavior is preserved and is
  protected by an automated check that fails the build if a new bypass is added.

### Added

- **Sleuth reminder graph page (`/sleuth-graph`).** Cytoscape.js force-directed
  graph (CDN, `cose` layout) visualizing active reminders as compound nodes
  clustered inside their group (client / GitHub / channel / other). Cross-group
  GitHub URL connections render as dashed blue edges. Hover any reminder node
  for a tooltip with full task text, channel, and state; click to highlight its
  neighborhood. Color-coded legend by group kind. Linked from the sidebar nav
  as "Reminder Graph". No bundling — single CDN `<script>` tag.

- **Sleuth reminder grouping + home page search.** Active Sleuth reminders are
  now clustered by inferred relationship and surfaced directly on the web app
  home page (`/`). Grouping mirrors the Sleuth `show-me` rules (ported from
  `reminder-clustering.js`): shared GitHub URL (transitive union-find) →
  same client (channel/repo-pattern from `client-channel-mapping.json`) →
  same channel (2+ members) → Other. A live search input filters task text
  across all groups client-side. Connection surfacing (`find_connections`) is
  also available for building the suggestion system. Logic lives in
  `src/rebalance/ingest/sleuth_grouping.py` (47 tests).

- **CI check status on Open PRs panel.** `check_status` (already collected
  per-PR via the GitHub check-runs API) is now surfaced in the dashboard.
  Each PR row shows an inline badge (`✗ CI` / `~ CI` / `⟳ CI`) for
  failing, mixed, and pending states. A red **"N failing CI"** filter button
  appears alongside the existing stale toggle — both are independent and
  composable (clicking one doesn't clear the other). Failing/mixed PRs are
  sorted to the top of the fetch so they always appear within the limit
  regardless of age. No new API calls, no schema changes, no backfill.
  Header label updated "N newest" → "N open" to reflect the new sort order.

- **Auth-log page search filter.** The `/auth-log` page now has a live filter
  input. Typing a substring (e.g. `github`, a device name, a detail value)
  narrows the table client-side; typing an issue keyword (`error`/`errors`/
  `fail`/`failure`/`failed`/`warning`/`warnings`/`issue`/`issues`) switches to a
  severity filter that shows only error (`danger`) and warning (`warn`) rows. A
  live `N / M shown` counter accompanies the box. Pure client-side JS over the
  already-rendered rows (each tagged with `data-severity`); no backend change.

- **Obsidian daily-notes rollover utility.** A nightly launchd job
  (`utils/obsidian_daily_rollover.py` + the `utils/obsidian_rollover.sh`
  wrapper) that, at midnight, prepends `0. Today's Notes.md` to the top of
  `0. Yesterday.md` under a dated header (a rolling, newest-first log) and blanks
  Today's Notes so each morning starts clean. Auto-creates Today's Notes if it
  goes missing, guarded against churn by a **vault sentinel** (won't write unless
  the real vault is mounted — checks `0. Now.md`) and a **circuit breaker** (trips
  after 3 auto-creates in 24h to stop a sync-loop spewing conflict copies; reset
  with `--setup`). The job runs through a `/bin/bash` wrapper rather than execing
  python directly so it inherits the existing Full Disk Access grant and needs no
  new TCC entry to reach the `~/Documents` vault; launchd stdout/stderr are kept
  outside `~/Documents` (in `~/Library/Logs`). Surfaces in `rebalance doctor` as
  `launchd:obsidian-rollover`.

- **Monitor external GitHub repos in the unified pipeline.** You can now watch
  third-party repos for *everyone's* activity (commits/PRs), not just your own.
  Declare them in the project registry with a project flagged `external: true`
  and list the repos under `repos` (see `rebalance.ingest.registry.get_external_repos`).
  No second pipeline: external repos enter the canonical watched set
  (`get_watched_repos` gains an `external_repos` source) and are artifact-synced by
  the existing `sync_github_repo`, so they immediately appear in the repo-scoped
  feeds, open-PRs panel, semantic search, and readiness tools. The one added step
  (`rebalance.ingest.github_watch`) derives a whole-repo `github_activity` rollup
  under a sentinel login so external repos also surface in the org-activity
  dashboards/reports (`note_builder` org view, `dashboard.fetch_org_activity`) and
  in a new "Watched repos (external activity)" section of the hourly pulse.
  - **De-dupe / pause across the clone lifecycle.** A watched repo can become
    active work — cloned and worked locally, or driven through a cloud agent — and
    later go quiet again, possibly oscillating (Claude Code cloud → local → Codex
    cloud → local). `reconcile_watched_repo` is recomputed every refresh and is
    idempotent + bidirectional: when the repo is active work (signals:
    `focus5_repo_signals` local clone with a recent commit, `github_pushed_repos`
    push/collab access, real per-login activity, or cloud-agent authored commits)
    it **suppresses and purges** the sentinel rollup so it never double-counts
    against your own per-login rows; when the work goes quiet it **resumes**.
    Artifact tables dedupe by sha/number, so the rollup is the only layer that
    needs reconciling, and it's kept mutually exclusive with the owned rows.

- **Figma comments land as the first plugin `SourceModule`.** Onboards Figma
  through the registry-driven plugin contract (`PROJECT/2-WORKING/PLUGINS.md`),
  reusing the prior figma-collector client **without** the hardcoded `if "figma"`
  branches it had scattered through the core. The frozen `Collector` descriptor
  (`index_ops.py`) gains optional `semantic_docs` (a `conn -> Iterable[SemanticDoc]`
  provider) + `secrets`, a `SourceModule = Collector` alias, and
  `_semantic_source_names()`. `semantic_index.backfill_semantic_documents` gains a
  flag-gated `use_registry_providers` iteration path that runs **alongside** the
  existing vault/github/email/code if-ladder — a strangler, so existing-source
  vectorization is provably unchanged (the if-ladder removal is a later
  parity-gated PR). A module *yields* `SemanticDoc`s; the index owns
  hash/upsert/embed.
  - `figma.py` (client, `X-Figma-Token` header) + a `figma_semantic_docs()`
    provider (skips empty/reaction-only comments); `0004_add_figma_comments.sql`
    **renumbered from the prior `0002`** — a duplicate `0002` would be silently
    skipped on an already-stamped DB and the table never created (the
    no-silent-happy-errors trap). Keyring-backed `get/set/clear_figma_token`
    (mirrors `github_token`, not cleartext) + `get/set_figma_file_keys`; registered
    `included_in_all=False` (PAT-gated, opt-in via `scope=["figma"]`).
  - Verified live against a real Figma file: **686 comments** ingested →
    `figma_comments` → `semantic_documents` → embedded → semantic query returns the
    relevant comments. Tests inject a fake client + `embed_texts` (no
    PAT/network/mlx, per the embedder's Apple-Silicon lock).

- **Sleuth production now reads a published file — SSH tunnel removed.** Replaced
  the SSH-tunnel pull of the firewalled prod Sleuth API with a read of a file the
  Sleuth box **pushes** to the private `rebalance-git-pulse` repo
  (`sync/sleuth/reminders-<ws>.json`; the publisher lives in the `sleuth-app`
  repo). `sync_sleuth_reminders` now treats a `file://`/local-path `base_url` as a
  local-file source (`_local_source_path` / `_read_payload_from_file`) and reads
  the locally-synced clone directly — **no inbound access, no SSH key, no open
  port, no tunnel**. An `http(s)://` `base_url` still uses the live API, so **dev
  is unchanged** (the dev box is reachable directly). Configure with
  `rebalance config set-sleuth --base-url "~/git-pulse-sync/sync/sleuth/reminders-neochrome.json" --token file-source --workspace neochrome`.
  - **Removed** the now-obsolete tunnel apparatus:
    `scripts/com.rebalance-os.sleuth-tunnel.plist.template` and
    `scripts/install_sleuth_tunnel_scheduler.sh` (deleted; the local LaunchAgent is
    unloaded). Rewrote `SLEUTH_SYNC.md` for the file model and updated the
    `ARCHITECTURE.md` / `UPGRADE.md` pointers.
  - **Review hardening (blocking + should-fix from external review):**
    - **Contract validation before any DB write** — a wrong-workspace file, a
      truncated/partial export, or publisher drift no longer silently retires live
      reminders. `_validate_payload_contract` rejects (raises `SleuthApiError`,
      aborting before the transaction) on `workspaceName` mismatch, a file source
      missing `filters.activeOnly=true` / wrong `source.type`, or any `reminders[]`
      entry that isn't a dict with a non-empty `reminderId` (previously silently
      dropped — which reads as a retirement). Relative `file://` paths are rejected.
    - **Publisher heartbeat → real staleness detection.** The publisher now stamps
      an hourly-rounded `exportGeneratedAt`; the consumer persists it in a new
      `sleuth_sync_meta` table and `rebalance doctor` compares **that source
      timestamp** (not the local `last_synced_at`, which re-reads keep bumping) to
      now — warning past ~3h. A dead publisher is now visible instead of looking
      fresh forever.
    - **Freshness is shared + non-destructive.** Moved the pre-read clone refresh
      out of `_refresh_sleuth` into `sync_sleuth_reminders` (so CLI, MCP, and daily
      refresh all get fresh data, not just the launchd path), and replaced
      `git pull --rebase --autostash` with `git fetch` + a scoped checkout of only
      the export file — it can't race/conflict with other jobs writing the same
      clone. Status surfaces as `source_refresh`; opt out with `refresh_source=False`.
  - **Tests:** `tests/test_sleuth_reminders.py` grew to 25 cases — source detection,
    relative-path rejection, file ingest (HTTP asserted unused), the five contract
    violations (each asserted to leave the table untouched), heartbeat persistence,
    and missing-file / invalid-JSON. Full suite green (507 passed).
  - **One-command device onboarding** — `scripts/setup_sleuth_file_source.sh` clones
    the private export repo (or reuses/pulls it), points rebalance at the local
    export file (`config set-sleuth` → file source), and verifies with
    `sleuth-sync` + `doctor`. Idempotent; `--workspace` / `--clone-dir` / `--repo-url`
    flags. Documented as the primary path in `SLEUTH_SYNC.md`.

- **GitHub deauth resilience — gh-CLI token fallback (options A + D).** When the
  stored GitHub PAT is rejected with **401** (revoked / expired / lost a scope)
  during a refresh, the collector now falls back to the `gh` CLI's token if the
  host is authorized for it (A), then **persists** that token to keyring +
  `rbos.config` so the launchd background jobs recover too (D). Wired into
  `refresh_index` (covers `rebalance refresh`, the `refresh_index` MCP tool, and
  launchd) at token-resolution time, so `sync_pushed_repos`, `scan_github`, and
  per-repo sync all use the working token. Only triggers on 401 (rate-limit
  403/429 is left alone) and only resolves interactively (launchd's stripped
  environment cannot run `gh` — it relies on the persisted heal). New helpers:
  `config.get_github_token_via_gh()` and `github_scan.resolve_working_token()`.
  A `gh_fallback` event is written to the unified auth log (a *recovery*, not a
  failure — so `rebalance doctor` shows the integration as healed once it fires).
  The explicit `rebalance github-scan --token` command is unchanged (it respects
  the token you pass and never auto-persists gh's token).
- `validate_github_token()` now returns the HTTP `status` alongside `valid`, so
  callers can distinguish a 401 deauth from a 403 rate-limit.

### Fixed

- **Semantic embedding was silently inert on this Mac — the `embeddings` extra was
  never installed.** `refresh_index(...)`'s embed step failed with `No module named
  'mlx_embeddings'` (surfaced as a per-scope error envelope, not a crash), so
  `semantic_documents` rows stayed **un-embedded** and `semantic_query` / `ask()`
  degraded to FTS/lexical hits only (no vector-kNN ranking). Root cause:
  `ingest/embedder.py` is correct — it loads via **`mlx-embeddings`**
  (`load`/`generate` → `output.text_embeds`; model `Qwen/Qwen3-Embedding-0.6B`,
  1024-dim, unit-norm) — but `mlx-embeddings` is the optional `embeddings` extra in
  `pyproject.toml` and had simply never been installed into the venv.
  - **Fix (environment, not code):** `.venv/bin/python -m pip install -e ".[embeddings]"`
    (Apple-Silicon only; first model load downloads ~1.2 GB from HuggingFace).
    Confirmed: 686 Figma comments embedded in ~15s and real vector+FTS queries
    return relevant results. There is **no code change** — wherever semantic
    embedding runs (interactive shell + the launchd refresh hosts) must have the
    extra installed; CI installs base deps only by design.
  - **Why the library matters (cross-repo provenance, for future retrieval):** an
    embedding checkpoint must load via `mlx-embeddings` (native pooled,
    L2-normalized embeddings), **not** `mlx-lm` — `mlx-lm` is a causal-LM loader
    that rejects an embedding checkpoint's flat weights ("Received N parameters not
    in model") and produces a fast, valid-but-**empty** index. rebalance-OS was
    already on the right library; the sibling `ask-self` repo hit and fixed the
    `mlx-lm` mistake first — see its `CHANGELOG.md` **0.6.0** ("qwen-mlx … now load
    via `mlx-embeddings`") and **0.7.4** (L2-normalize vectors at every `vec0`
    boundary; `vec0` ranks by L2 distance, so unit-norm vectors give
    cosine-equivalent ranking — `mlx-embeddings` returns unit-norm `text_embeds`).
  - **Footprint caveat:** `mlx-embeddings 0.1.0` pulls a heavy transitive stack
    (`mlx`, `mlx-lm`, `mlx-audio`, `mlx-vlm`, `transformers` 5, `numpy` 2, `pandas`
    3, `opencv`) and upgraded `starlette` 1.0.0 → 1.2.1 — verified FastAPI-compatible
    (`pip check` clean, 621 tests pass).

- Corrected the stale claim that `set_github_token()` "removes any legacy
  plaintext copy from `rbos.config`" (see 0.31.6 below). It deliberately writes
  **both** keyring and `rbos.config` — the config copy is the launchd safety net
  (launchd's stripped environment may not reach the keychain), which
  `doctor._check_token` relies on. Updated the stale unit test to match.

## [0.31.10] - 2026-06-08

### Added

- **Sleuth sync success events now appear in the unified auth log.** Successful reminder syncs emit a dedicated Sleuth success event with the source mode and sync counts, so the system log can distinguish "source saved" from "source verified by a real sync."

### Changed

- **The auth-log UI now shows a green success badge for Sleuth file-source syncs.** When a published-file Sleuth sync completes, the System Log renders a clear `file source synced` success label instead of only leaving the earlier blue `token (re)set` marker.

## [0.31.9] - 2026-06-08

### Added

- **Pulse homepage Figma module.** The home page now shows a `Recent Figma comments` card with the newest stored comments, tracked project IDs, and last-sync context so Figma activity is visible alongside GitHub, email, and calendar signals.
- **One-step Figma project add flow on the homepage.** A new `Add Figma project ID` form accepts either a raw Figma file key or a full Figma URL, appends the normalized key to local config, triggers a Figma sync, and regenerates the page so newly-added files appear without a manual config edit.

### Changed

- **Streams list now reflects the available connectors programmatically.** The sidebar stream list is derived from the registered source set instead of a hard-coded subset, so optional connectors such as Email and Figma always appear even before they are heavily populated.

## [0.31.8] - 2026-06-04

### Fixed

- **Stickies-to-Obsidian launchd install now carries the real vault target.**
  The standalone installer now renders `STICKIES_DIR`, `OBSIDIAN_FILE`, and
  `STATE_FILE` into the launchd plist so background syncs target the intended
  vault note instead of always falling back to the demo default path.

## [0.31.7] - 2026-06-04

### Added

- **Stickies-to-Obsidian standalone utility.** Added a lightweight macOS
  utility that incrementally imports Apple Stickies note content into an
  Obsidian markdown file with SHA-256 deduplication, dry-run previews, atomic
  prepend writes, and a launchd template plus installer for background sync.

## [0.31.6] - 2026-06-01

### Added

- **`keyring` integration (Issue #39 Phase 0)** — secrets now stored in the OS keyring
  (macOS Keychain, Windows Credential Locker) via the `keyring` library.
  Resolution order: keyring → `rbos.config` (legacy, auto-migrated on first read) → `gh-cli`.
  `set_github_token()` writes to keyring and removes any legacy plaintext copy from
  `rbos.config`. `clear_github_token()` clears both. Keyring unavailable (headless CI,
  no backend) silently falls back to `rbos.config` — no behaviour change on those hosts.
- **Calendar OAuth keyring support** — `get/set/clear_calendar_oauth_token_json()` in
  `config.py` for storing serialized Google OAuth2 token in keyring; existing pickle
  fallback preserved until migration is complete.
- **`sync_subdir` config key** — `get_sync_subdir()` / `set_sync_subdir()` in `config.py`
  (default `"sync"`). Foundation for Issue #39 device snapshot sharing within the existing
  pulse repo: `{pulse_target_path}/sync/calendar/<device_id>.json`, etc.
- **`rebalance config doctor` keyring section** — shows OS keyring backend, GitHub token
  source (`keyring` / `config` / `gh-cli`), and Calendar OAuth keyring status.

### Changed

- `keyring>=25.0.0` added to core dependencies in `pyproject.toml`.

## [0.31.5] - 2026-06-01

### Added

- **`src/rebalance/repair.py` — `RepairFSM`** — lightweight finite-state-machine
  for deterministic repair with bounded Haiku escalation. States: `PENDING →
  REPAIRED | ESCALATED → REPAIRED | DEAD`. Circuit breakers: unrecoverable error
  class exits immediately; `max_deterministic_attempts` (default 2) and
  `max_haiku_attempts` (default 1) cap retries; Haiku picks from a bounded action
  menu by name — no free-form execution. 17 unit tests in `tests/test_repair_fsm.py`.
- **Pulse self-repair loop** (first FSM consumer) — `publish_pulse` now runs the
  FSM on non-fast-forward push rejections. Autonomous action menu: `pull_rebase`
  (preferred), `abort_rebase`, `notify_only`. `reset_hard` excluded from autonomous
  menu — it discards the local commit containing the new content and reports a false
  success. Post-repair content verification confirms the remote HEAD matches the
  rendered output before returning `pushed=True`. Result dict carries `repaired`,
  `repair_log`, `repair_status`, and `repair_error` fields. 6 hermetic tests in
  `tests/test_pulse_self_repair.py` including content-preservation and menu-boundary
  assertions.

### Refactored

- **MCP server decomposed** — the 857-line `create_server()` god-function split into
  `src/rebalance/mcp/` package: `server.py` (thin orchestrator) + `tools/` with 7
  modules by domain (`projects`, `onboarding`, `retrieval`, `calendar`, `index`,
  `hygiene`, `sleuth`). `mcp_server.py` kept as a 5-line backward-compatibility shim.
- **Org activity chart** — replaced broken list view (repo names wrapping
  character-by-character in a 56px grid column) with a Chart.js doughnut where each
  org is one slice sized by combined commit+PR+issue count.

## [0.31.4] - 2026-05-28

### Changed

- The Pulse health banner copy action now uses a dependency-free inline SVG clipboard icon instead of visible button text or an icon-font dependency. The button keeps the existing clipboard behavior, exposes accessible labels for screen readers, and stays self-contained within the static page.

## [0.31.3] - 2026-05-28

### Changed

- Background collector wrappers and MCP launch configs now force the repo checkout's `src/` tree onto `PYTHONPATH`, so launchd jobs and local MCP clients execute the live code in this repo instead of a stale wheel copy in `.venv/site-packages`.

### Fixed

- Rebalance config discovery now resolves `temp/rbos.config` from the active checkout or an explicit `REBALANCE_CONFIG` override, even when Python imported `rebalance` from `site-packages`. This restores vault path, GitHub token, and pulse config visibility for background jobs that previously looked under `.venv/lib/.../temp/rbos.config`.
- The Pulse web app top bar no longer treats GitHub watched-repo freshness as the entire collector status. It now computes collector-wide activity from all sources, renders a prominent one-row warning/error banner at the top of the page using `rebalance doctor`, and marks the collector pill degraded when background checks are failing.

## [0.31.2] - 2026-05-28

### Changed

- The committed portable ask-self index was refreshed in fully portable local-Qwen mode. A fresh clone still queries immediately from the tracked SQLite baseline, while maintainers rebuild it with the same on-device embedding setup instead of a hosted embedding dependency.

### Fixed

- Portable ask-self harnesses now point committed indexes through the dedicated committed-index path setting instead of the temp-index filename setting. This keeps the portable query and refresh path aligned with the current integration contract and avoids silently routing a committed index through the wrong lookup path.
- The portable ask-self ingest wrapper no longer crashes under macOS Bash when `set -u` is enabled and an explicit ingest mode is passed. It now builds the final argv incrementally instead of expanding an empty optional array directly into `exec`.
- The Mac portable ask-self maintainer path no longer depends on operator memory for the fragile `qwen-local` settings. The ingest wrapper now auto-applies the stable macOS defaults for this repo's local-Qwen harness: `TOKENIZERS_PARALLELISM=false`, `ASK_SELF_QWEN_BATCH_SIZE=8`, `ASK_SELF_QWEN_MAX_TOKENS=2048`, and `--concurrency 1` unless the operator overrides them.

## [0.31.1] - 2026-05-25

### Fixed

- `rebalance github-sync-artifacts --repo owner/name` can now proceed without a PAT when you explicitly target a public repo. The shared GitHub client omits the `Authorization` header when no token is present, and the CLI keeps the token requirement for implicit/project-derived repo sets where a PAT is still the expected path.
- The ask-self portable ingest wrapper now defaults to `--mode all` when no explicit mode is passed, so repo-local refreshes and future slash-command integrations rebuild the full code+docs index instead of silently falling back to ask-self's upstream docs-only default.
- The ask-self portable ingest wrapper now fails fast when PR ingestion is enabled but no valid local GitHub auth source is available. It promotes `SLEUTH_RAG_GITHUB_PAT` into `GITHUB_TOKEN`, otherwise falls back to a healthy `gh` login, and tells the operator to re-auth or pass `--no-prs` instead of quietly omitting the remote PR slice.

## [0.31.0] - 2026-05-19

### Added

- `Collector` dataclass and `COLLECTORS` source registry in `src/rebalance/ingest/index_ops.py`. `refresh_index` now routes `scope=[...]` through the registry instead of a hard-coded dispatch chain. External integrators can call `register_collector()` to add new data sources without editing the dispatcher. `included_in_all=False` marks opt-in collectors that are skipped by `scope=["all"]`.
- Shared GitHub HTTP client (`src/rebalance/ingest/_http.py`) extracted from the duplicated `urlopen` + retry + pagination logic in `github_scan.py` and `github_knowledge.py`. Single entry point with 30 s timeout, exponential backoff on 429/5xx, and `per_page=100` automatic pagination.
- `[project.optional-dependencies] server` group in `pyproject.toml` — `pip install -e '.[server]'` installs `fastapi>=0.110.0` and `uvicorn[standard]>=0.29.0` so the pulse-server venv is reproducible from a fresh clone without manual installs.

### Changed

- Logging bootstrap consolidated: `ingest/` modules now use `logging.getLogger(__name__)` via a shared setup path; the 24 duplicate `Path("rebalance.db"), envvar="REBALANCE_DB"` option declarations across the CLI were deduplicated through the shared `DBOption`.

### Fixed

- `scripts/dashboard.py` data-fetch functions (`fetch_recent_github`, `fetch_repo_activity_counts`, `fetch_vault_recent`, `fetch_recent_emails`, `fetch_watched_summary`) now return empty lists instead of raising when the DB is absent or has no tables yet. Prevents `pulse_web.py` and the terminal dashboard from crashing on a fresh checkout before the first sync.

## [0.30.0] - 2026-05-14

### Added

- The goals panel now shows a second column with the next six uppermost open todos from the same goals source, while keeping the primary three goals on the left.

## [0.29.2] - 2026-05-14

### Fixed

- Calendar viewer upcoming-event lists now compare event starts by absolute time instead of raw ISO text, so offset-stamped morning events no longer disappear while they are still upcoming.

## [0.29.1] - 2026-05-14

### Fixed

- The pulse-server launchd job is now template-managed like the other five jobs. Previously `com.rebalance-os.pulse-server.plist` lived only in `~/Library/LaunchAgents/` with four hardcoded `/Users/<name>/...` paths and no checked-in template or installer — the one launchd job PR #18 didn't reach. Added [scripts/com.rebalance-os.pulse-server.plist.template](scripts/com.rebalance-os.pulse-server.plist.template) with `{{REBALANCE_DIR}}` placeholders and [scripts/install_pulse_server_scheduler.sh](scripts/install_pulse_server_scheduler.sh) to render + load it. `pulse_server.sh` itself already derived `REBALANCE_DIR` from script location (0.29.0).
- `install_pulse_server_scheduler.sh` always attempts an `launchctl unload` before `load`, rather than gating the unload behind a `launchctl list | grep` check. The grep check can miss a job that is loaded but momentarily absent from `launchctl list`, in which case `launchctl load` fails with an opaque `Input/output error` (observed reinstalling pulse-sync and github-sync). The other five installers still use the older gated pattern — a uniform fix across all six is a follow-up.

## [0.29.0] - 2026-05-13

### Changed

- **Operator-breaking**: the ask-self wrappers ([scripts/ask-self-ingest.sh](scripts/ask-self-ingest.sh), [scripts/ask-self-query.sh](scripts/ask-self-query.sh)) now require `ASK_SELF_PATH` to be set in the environment and fail with an actionable error message when it isn't. Previously they fell back to a hardcoded `/Users/noelsaw/...` path that didn't exist on any other operator's machine — a missing env var manifested as a confusing "ask-self repo not found at <someone-else's-path>". Add `export ASK_SELF_PATH="$HOME/Documents/GitHub/ask-self"` (adjust to your checkout) to your shell rc to keep using these wrappers.

### Fixed

- The launchd installers no longer ship with one developer's home directory baked in. All five sync shell scripts (`daily_sync.sh`, `vault_sync.sh`, `pulse_sync.sh`, `pulse_web_sync.sh`, `github_sync.sh`) now derive `REBALANCE_DIR` from their own location, and their five plists became `.plist.template` files with a `{{REBALANCE_DIR}}` placeholder that each `install_*_scheduler.sh` substitutes with the local checkout path before writing into `~/Library/LaunchAgents/`. The rendered plists are gitignored, so a fresh clone on any machine installs cleanly with no per-user editing.
- The author-fallback in `PROJECT/cleanup.sh` no longer hardcodes a single operator's username — it falls back to `os.environ.get('USER', 'unknown')` when neither the existing frontmatter nor git provides an author.
- The `Degraded Mac` test fixture in [tests/test_git_pulse_health_check.py](tests/test_git_pulse_health_check.py) no longer embeds a real operator path in its `scan_failure_examples` example; it uses a generic `/Users/operator/...` placeholder instead.
- The project's `.claude/settings.json` permission allowlist had a few stale `Bash(...)` entries pointing at paths from another machine (`/Users/noelsaw/Documents/GitHub-Repos/...` and `/Users/noelsaw/Documents/rebalance-OS/...`) along with a corresponding `additionalDirectories` entry — all removed since they were dead-ends on this checkout.

### Action required on existing machines

If you already had launchd jobs or ask-self wrappers set up against the previous code, the changes above don't take effect until you do the following on each affected machine:

1. **Re-install the launchd jobs** so the rendered plists in `~/Library/LaunchAgents/` are regenerated from the new templates with your local checkout path. The install scripts unload any existing job before re-rendering, so this is safe to re-run:

   ```bash
   bash scripts/install_scheduler.sh             # daily sync (06:30)
   bash scripts/install_vault_scheduler.sh       # hourly vault refresh
   bash scripts/install_pulse_scheduler.sh       # hourly pulse publish
   bash scripts/install_pulse_web_scheduler.sh   # 30-min pulse-web refresh
   bash scripts/install_github_scheduler.sh      # hourly github-only sync
   ```

   Skip any installer for a job you don't currently have loaded (`launchctl list | grep rebalance-os` shows what's running).

2. **Set `ASK_SELF_PATH` in your shell** if you use the ask-self wrappers — there is no longer a built-in default. Add to `~/.zshrc` / `~/.bashrc`:

   ```bash
   export ASK_SELF_PATH="$HOME/Documents/GitHub/ask-self"   # adjust to your checkout
   ```

No DB or vault migration is required — only the install paths above change behavior.

## [0.28.3] - 2026-05-13

### Added

- Single-command triage wrapper [experimental/triage/run_triage.py](experimental/triage/run_triage.py). Wraps the multi-step triage flow (github-sync, sleuth-sync, `spike.py`) into one invocation with flags for `--sync`, `--publish`, and `--dry-run`. Existing direct `spike.py` workflows are unchanged.
- Two new triage buckets in [experimental/triage/spike.py](experimental/triage/spike.py): **close candidates** (scores open issues against merged PRs to surface issues likely already fixed) and **stale issues** (uses last-comment dates instead of `updated_at`, since the latter is bumped by edits/labels/assignee changes that don't indicate progress). A notes-section counter also surfaces orphaned remote branches whose `head_sha` matches a merged PR.

### Changed

- `load_project_matchers(db, config=None, *, priority_rules=None)` and `_build_matchers_from_priority_rules(rules=None)` now accept an explicit `priority_rules` override. `None` (default) preserves production behavior — read operator-local `project_priority_rules` from `temp/rbos.config`. `[]` skips operator rules entirely; a list of rule dicts injects test fixtures. Previously, any test exercising the classifier (directly or via `generate_daily_report` / `generate_weekly_report`) inherited whatever brand rules happened to be on the host machine, making test outcomes depend on the operator's local config. `tests/test_calendar_reports.py` drops its `setUpModule`/`tearDownModule` pair as a result; `tests/test_calendar_aggregator.py` shrinks similarly.

### Fixed

- The triage spike's **PRs unblocked** bucket now filters out merged PRs, requires CI-green status, excludes drafts, and adds a staleness warning when activity stalls. Previously merged PRs could appear because the filter relied on `state` alone.
- The triage spike's **release blockers** bucket now joins `github_milestones` to surface due dates and flags overdue items. Previously the rendered table had no time signal.
- The triage spike's **perf concrete** bucket now reads `labels_json` and warns on close-intent labels (`wontfix`, `duplicate`, etc.), reducing false-positive recommendations.
- `bucket_client_visible` in [experimental/triage/spike.py](experimental/triage/spike.py) now handles a missing `sleuth_reminders` table gracefully — catches `sqlite3.OperationalError` and returns an empty bucket instead of crashing the whole triage run when Sleuth hasn't been synced on this checkout.
- Eight test-suite failures carried over from pre-0.28 main are now resolved, restoring a fully green `pytest tests/` from a fresh clone.
- Real client/org names were scrubbed from 15 test fixture files (`Binoid` → `AcmeCorp`, `Bloomz` → `Mainline`, `CreditRegistry` → `AcmeReg`, etc., with longest-match-first to preserve substring relationships). Test fixtures no longer advertise real client relationships, and the suite is portable to anyone running it without the operator's `temp/rbos.config` priority rules.

## [0.28.2] - 2026-05-13

### Changed

- Timezone handling centralized into `src/rebalance/tz_utils.py` (single source of truth). `local_tz()` resolves device timezone via `REBALANCE_TZ` env var → `/etc/localtime` symlink → UTC fallback. Stored timestamps remain UTC ISO 8601; conversion happens only at display.
- **Behavior change:** operator-facing timestamps in the terminal dashboard, pulse, and calendar reports now default to the **OS-detected local timezone** instead of hardcoded fallbacks (`America/Los_Angeles` for `scripts/dashboard.py`, `America/New_York` for `CalendarConfig`). Set `REBALANCE_TZ` or pin a `timezone` value in `temp/calendar_config.json` to keep a specific zone regardless of host.
- `src/rebalance/ingest/calendar_config.py` default `timezone` value changed from `"America/New_York"` to `""` — empty resolves to the device-local zone at load time via `local_tz().key`.
- `src/rebalance/ingest/pulse.py` and `scripts/dashboard.py` drop their inline `_parse_iso()` / `ZoneInfo("America/Los_Angeles")` duplicates and route through `tz_utils`.
- `src/rebalance/ingest/dashboard.py::_format_generated_at()` now renders in local zone with `%Z` suffix instead of forced UTC.

## [0.28.1] - 2026-05-13

### Fixed

- Pulse web now labels the main feed as `Recent GitHub activity` and shows one additional GitHub history row in that card.
- The pulse web/dashboard data layer now treats missing optional SQLite tables such as `calendar_events` and `sleuth_reminders` as empty-state sources instead of aborting the whole page render.

## [0.28.0] - 2026-05-12

### Changed

- Canonical `rebalance.db` location moved from the project tree (`~/Documents/rebalance-OS/rebalance.db`) to `~/Library/Application Support/rebalance-os/rebalance.db` on macOS (or `$XDG_DATA_HOME/rebalance-os/` / `~/.local/share/rebalance-os/` on Linux). The new path is not TCC-protected, so the SwiftUI dashboard (and any other GUI consumer) can read it without an Allow-prompt dance on first launch.
- `src/rebalance/paths.py::resolve_database_path()` gained a third resolution layer for the canonical path, inserted between the `REBALANCE_DB` env var and the user-config `database_path` field. Existing env-var and explicit-path overrides continue to win; stale paths simply fall through to the canonical location.
- `scripts/dashboard.py` now resolves the DB via `rebalance.paths.resolve_database_path()` instead of reading `REBALANCE_DB` directly with a `"rebalance.db"` relative fallback. Survives running outside the project tree.
- `.vscode/mcp.json` updated to point `REBALANCE_DB` at the canonical app-data location.

### Added

- `src/rebalance/paths.py::migrate_database_to_canonical()` — idempotent migration that moves `rebalance.db` plus its `-wal` and `-shm` sidecars to the canonical location, and clears the user-config `database_path` field when it was pointing at the just-migrated source. Run via `python -m rebalance.paths --migrate` (add `--dry-run` to preview).
- Phase 0 of the Mac SwiftUI Dashboard port landed under `experimental/mac-dashboard/` — Xcode app project (xcodegen-generated) consuming `HypercartMacOSDashboard` and GRDB. Renders 23 GitHub-balance rows from the live SQLite in ~69 ms on the canonical path. See [PROJECT/2-WORKING/MAC-DASHBOARD-PORT.md](PROJECT/2-WORKING/MAC-DASHBOARD-PORT.md) for findings.

## [0.27.1] - 2026-05-12

### Fixed

- Gmail 403 handling is now conservative: only true insufficient-scope responses are rewritten into the `gcloud auth application-default login` remediation message. Other 403s, such as a disabled Gmail API, surface their original upstream error instead of being mislabeled as a scope problem.

## [0.27.0] - 2026-05-12

### Added

- Gmail inbox ingest via `refresh_index(scope=["email"])`. Phase 1 syncs the newest 100 inbox messages, stores message metadata plus Gmail-provided snippets in SQLite, and backfills them into the unified semantic index so email participates in default `semantic_query()` results.
- New `gmail_query_filter` config key in `temp/rbos.config` to narrow the Gmail fetch scope without code changes. Defaults to `in:inbox`.
- `index_status()` now reports an `email` source block with message count, last sync time, and newest received timestamp.

### Fixed

- Gmail auth failures caused by missing `gmail.readonly` scope now return an explicit remediation message with the exact `gcloud auth application-default login` command to rerun.

## [0.26.0] - 2026-05-12

### Added

- Pulse FastAPI server autostart at login. New LaunchAgent `com.rebalance-os.pulse-server` (managed at `~/Library/LaunchAgents/com.rebalance-os.pulse-server.plist`) runs `scripts/pulse_server.sh` with `RunAtLoad=true` + `KeepAlive=true` + `ThrottleInterval=30s`. Previously the server was on-demand only — the 30-minute `pulse-web-sync` job kept the static `web/pulse.html` fresh but the interactive Refresh/filter layer at `http://127.0.0.1:8767` only ran when a terminal was open. Logs to `temp/logs/pulse_server_stdout.log` and `pulse_server_stderr.log`.
- Per-repo activity doughnut on the pulse page. New `fetch_repo_activity_counts(days=7, limit=12)` in `scripts/dashboard.py` returns a UNION-of-three-tables count (items + commits + comments) grouped by `repo_full_name` for the last N days, honoring the existing `github_ignored_repos` blocklist. `scripts/pulse_web.py` renders this as a Chart.js 4.4 doughnut (loaded from `cdn.jsdelivr.net` with `defer`) with per-slice colors from a 12-entry palette, an embedded JSON payload (`<script type="application/json" id="repo-pie-data">`) that the existing `PULSE_JS` IIFE reads on `load`, and tooltips showing count + percentage. The chart sits in the right column of the body grid (where Index Health used to live); Watched repos now stacks above it. Falls back to a friendly empty-state when no activity exists in the window.
- Pulse page layout restructured to put Index Health on a full-width row beneath the two-column grid. The grid is now Recent Activity (left col, 2fr) / Watched + Repo Activity doughnut (right col, 1fr), with `<div class="full-row">` holding Index Health below. New CSS: `.full-row { margin-top: 16px }`, `.repo-pie .card-head { display: flex; justify-content: space-between }`, `.repo-pie-wrap { padding: 8px 14px 16px }`.
- Slack deep links on Sleuth reminder rows in the pulse sidebar. New `build_slack_url(reminder)` helper in `scripts/pulse_web.py` constructs `https://<workspace>.slack.com/archives/<channel_id>/p<ts-no-dot>` from the reminder's own `workspace_name` + `original_channel_id` (falling back to `target_channel_id`) + `original_message_id` (falling back to `original_thread_ts`). macOS Slack registers `slack.com` as a Universal Link and opens these URLs directly in the desktop app when installed. Each sleuth row that resolves a URL now renders as `<li class="side-row has-link"><a class="side-row-link" target="_blank" rel="noopener noreferrer">…</a></li>`; rows without a usable channel degrade gracefully to the plain non-link form. New CSS rules: `.side-row.has-link { padding: 0 }`, `.side-row-link { display: block; padding: 7px 8px; color: inherit; text-decoration: none }`, `.side-row-link:hover { background: rgba(124,196,255,.10) }`, `.side-row-link:hover .side-row-title { color: var(--info) }`. `fetch_sleuth_due` in `scripts/dashboard.py` now selects `workspace_name`, `original_channel_id`, `target_channel_id`, `original_message_id`, `original_thread_ts` so the renderer has everything it needs.
- Sleuth workspace blocklist. New `sleuth_ignored_workspaces` array key in `temp/rbos.config` (the same gitignored config file that holds `github_ignored_repos` and `calendar_ignored_summaries`) suppresses reminders from listed Slack workspaces. `get_pulse_config()` in `src/rebalance/ingest/config.py` now whitelists this key — previously the explicit-keys return dict silently dropped any unknown config keys, which caused the first iteration of the filter to no-op. `fetch_sleuth_due` reads the list and appends `AND LOWER(workspace_name) NOT IN (?, ?, …)` to both SQL branches (the `slack_user_id` one and the unauthenticated one). Edits take effect on the next render or refresh — no restart needed. Example:

    ```json
    {
      "sleuth_ignored_workspaces": ["neochrome-dev"]
    }
    ```

- Production Sleuth Web API support. `_load_sleuth_env(which="production")` in `src/rebalance/cli.py` now looks up `~/secrets/sleuth-web-api-{which}.env` first (default: production), falling back to the legacy `sleuth-web-api-development.env` if the requested file doesn't exist. Existing dev-only setups continue working without modification. Operator-side setup is unchanged: create the new env file (mode 600) with `SLEUTH_WEB_API_BASE_URL` / `SLEUTH_WEB_API_TOKEN` / `SLEUTH_WORKSPACE_NAME`. Because the prod Sleuth Web API typically only listens on the host's loopback (port 2020 firewalled from the public internet), `SLEUTH_WEB_API_BASE_URL` is usually a local port-forward target (e.g. `http://127.0.0.1:12020` with a separate SSH tunnel managed by a `com.rebalance-os.sleuth-tunnel` LaunchAgent).

### Changed

- `get_pulse_config()` whitelist now exposes `sleuth_ignored_workspaces` (defaults to `[]`). All other keys are unchanged. The new key documentation in the docstring explicitly mentions the `["neochrome-dev"]` blocklist pattern as the canonical example.

## [0.25.0] - 2026-05-07

### Added

- Centralized path resolution via new module `src/rebalance/paths.py`. Single source of truth for "where is the database?" and "where are the secrets?". Layered resolver chain: (1) explicit `--database` flag, (2) `REBALANCE_DB` env var, (3) walk up from cwd for a project marker (`.git` / `pyproject.toml`) and look for `rebalance.db` next to it, (4) `database_path` field in `~/.config/rebalance-os/config.json`. When no layer resolves, raises `DatabaseNotFoundError` whose message names every candidate it tried and the four routes to fix it. Same chain for secrets: `REBALANCE_SECRETS_DIR` env var → `secrets_dir` user-config field → `~/secrets/` legacy default. Migrates the previously-hardcoded operator paths (`/Users/noelsaw/secrets/google-calendar.env`, `/Users/noelsaw/secrets/sleuth-web-api-development.env`) onto the resolver, closing the AGENTS.md portability TODO. All 24 `Path("rebalance.db"), envvar="REBALANCE_DB"` defaults across the CLI plus the MCP server's `main()` now route through the resolver. New CLI subcommands `rebalance config set-default-database <path>`, `rebalance config set-secrets-dir <path>`, and `rebalance config show-defaults` (debug helper that prints what every layer of the resolver currently sees).
- 30-minute web pulse refresh. New launchd job `com.rebalance-os.pulse-web-sync` runs `scripts/pulse_web_sync.sh` every 30 minutes from 06:00 to 23:30, regenerating `web/pulse.html` from the same SQLite the TUI reads. The page itself uses `<meta refresh content="30">` so any browser tab pointed at `file://` reloads on a cadence; pair the two and the local mirror stays within ~30 min of the SQLite truth. Atomic via tmp+replace (a crashed run leaves the previous HTML intact). No network, no git push — separate from the hourly markdown→private-repo pulse-sync job. Install with `bash scripts/install_pulse_web_scheduler.sh`.
- Repository hygiene audit (`scripts/audit_modules.py`). Verifies that ingest collectors and render modules are documented in ARCHITECTURE.md + CHANGELOG.md, and that recent commits' file changes appear in the latest CHANGELOG version section. Three checks: ARCHITECTURE.md mention, CHANGELOG.md historical mention, and recent-commit coverage (last N commits since the live version's date, default 20). A baseline lockfile (`scripts/audit_modules.lock`) silences pre-existing gaps so the audit fails only on NEW drift; `--init` re-snapshots the baseline after a deliberate doc backfill. `--include-uncommitted` adds a pre-commit preview that flags working-tree changes (modified/untracked audit-worthy `.py`/`.sh`/`.plist` files) not yet in the latest CHANGELOG section. `--json` emits a stable schema (`audit_version: 1`) with `passed`, `summary`, structured `checks`, and an actionable `next_steps` array suitable for orchestrating agents.
- `audit_modules` MCP tool (registered in `src/rebalance/mcp_server.py`). Wraps `scripts/audit_modules.py --json` for host agents (Claude Code / Claude Desktop). Parameters mirror the CLI: `init`, `commits_window`, `include_uncommitted`. Returns the same stable JSON schema as the CLI, with subprocess-launch errors surfaced as `passed: False, exit_code: 2` and diagnostic fields rather than raised exceptions.
- Audit script scope expansion. `scripts/audit_modules.py` now also scans top-level `src/rebalance/*.py` files (cli.py, mcp_server.py, paths.py) — previously the discovery was limited to `src/rebalance/ingest/*.py` + `scripts/*.py`, which silently let new top-level modules slip past. `__main__.py` was added to IGNORED_FILES alongside the existing `__init__.py` since both are package shims. The substring mention check is now case-insensitive so docs can talk about a module using capitalized prose ("the CLI", "the MCP server") and still satisfy the audit; trades a small false-positive risk (English word matching a stem) for catching the previously-silent false-negative class.
- `rebalance raw` calibration command. Shows GitHub events from the last N minutes (default 30) and classifies each against local pipeline state: ✓ captured (`last_active_at >= event_time` for that repo), ⏳ pending (repo watched but pipeline hasn't caught up yet), ✗ unwatched (repo not in `github_repo_meta` — silently missing from the pipeline). The output now includes a second **team activity** table that fetches per-repo events for the top N most-active watched repos (default 10, tunable with `--top`) and filters out the current user's own actions — surfaces teammate activity that `/users/{login}/events` alone cannot see (the same gap that motivated the "use PAT + per-repo branch queries" calibration practice). A third **unwatched repos with recent pushes** section uses `/user/repos?sort=pushed` to compare your accessible repos against `github_repo_meta` independent of the events feed — surfaces freshly-created or low-event repos (default 7-day push threshold) that the time-bounded event sections can't see, so a new repo you push to once and forget no longer slips past calibration. Honors the configured ignored-repos list and skips archived/disabled repos. Total cost: 1 + N + 1 GH API requests per invocation. `--watch N` re-runs every N seconds (recommended floor 30s due to GH events API ~30s eventual consistency); `--json` emits a structured snapshot for orchestration with `events` (your activity), `team_activity.events`, and `unwatched_active_repos.repos` arrays. Used to verify that recent commits/PRs/issues — yours and your team's — are making it into rebalanceOS, and that no accessible repo is silently missing from the watch list.
- Project plan doc [PROJECT/2-WORKING/P1-MODULE-REGISTRY.md](PROJECT/2-WORKING/P1-MODULE-REGISTRY.md) (created as `1-INBOX/P3-MODULE-REGISTRY.md`; promoted P3→P1 and moved to `2-WORKING` on 2026-05-31) covering three approaches to drift control (post-hoc audit / proactive registry / SOP-only), with empirical findings from the Approach A prototype and an explicit recommendation to revisit a declarative registry only if drift recurs after this round.
- Static web mirror of the terminal pulse dashboard. `scripts/pulse_web.py` renders a self-contained `web/pulse.html` from the same SQLite knowledge base the TUI reads, with an "Open in Obsidian" link in the hero, a left sidebar that surfaces the next 6 calendar events and 6 Sleuth reminders, and meta-refresh-driven auto-reload. Run one-shot via `./.venv/bin/python scripts/pulse_web.py`, or in `--watch` mode for continuous regeneration. Goals are pulled from `{vault_path}/0. Goals.md` by default; override with `--goals` or `PULSE_GOALS`.
- Calendar ignore list. Add a `calendar_ignored_summaries` array to `temp/rbos.config` (the same gitignored config file that holds `github_ignored_repos`) to suppress recurring events from both the web mirror and the terminal dashboard. Patterns are matched case-insensitively as substrings against `calendar_events.summary` — no glob or regex syntax. Example:

    ```json
    {
      "calendar_ignored_summaries": ["Daily Standup", "Lunch Break"]
    }
    ```

  Edits take effect on the next render or refresh — no restart needed.

### Fixed

- Background HTTP calls to the GitHub API now have a 30-second timeout (`urlopen(req, timeout=30)`) in `github_scan.py`, `github_knowledge.py`, and `diagnose.py`. Without this, a stalled HTTPS connection (commonly after macOS sleep/wake) could leave a long-running terminal dashboard blocked inside `urlopen` indefinitely, holding a SQLite writer connection across the hang.
- SQLite connections now set `PRAGMA busy_timeout=30000`, so brief writer contention waits up to 30 seconds for a slot instead of erroring instantly. Together with the HTTP timeouts, this prevents the cascade where one stalled request silently broke the daily sync, every hourly vault sync, and the TUI auto-refresh with "database is locked" until the holder process was manually killed.

## [0.23.9] - 2026-05-05

### Added

- Local project/client priority rules can now assign dashboard priority tiers, value scores, client labels, value levels, and risk levels without committing private account metadata.
- The dashboard now ranks projects by local priority score before activity, shows the priority metadata in each project block, and can surface configured priority projects even before they exist in the active registry.
- Calendar/project classification now uses the same local priority aliases, so important client or project nicknames route to the right dashboard row.
- The config CLI can set, list, and remove local project priority rules stored in the ignored operator config.

## [0.23.8] - 2026-05-05

### Changed

- Full index refreshes now update the Obsidian dashboard note after successful ingest and immediately re-ingest/embed that note so the local SQLite index sees the refreshed operating dashboard.
- The generated dashboard note now shows a visible "Last generated" timestamp directly under the title, making freshness/staleness obvious without inspecting frontmatter.

## [0.23.7] - 2026-05-05

### Changed

- Pulse Sleuth reminder sections now include tasks assigned by the operator to other people, not only tasks assigned to the operator, so delegated follow-ups remain visible in the daily operating view.

## [0.23.6] - 2026-05-05

### Added

- GitHub triage reports can now include configured related/affiliate project repos, showing open external issues and PRs alongside whether each one is already linked from a central tracker issue.
- Local config now supports per-tracker related GitHub repo lists so implementation repos can stay separate while project tracking remains centralized.

## [0.23.5] - 2026-05-05

### Fixed

- The terminal pulse dashboard now skips GitHub semantic embedding during its background refresh, preventing the terminal process from loading the local embedding model and consuming excessive memory. Daily sync and explicit refresh calls still run semantic work by default.

## [0.23.4] - 2026-05-04

### Added

- Dashboard-triggered GitHub refreshes now append profile records to local logs, and `rebalance profile-sync` can read those logs to show the slowest repos from the latest live refresh instead of only the daily sync job.

## [0.23.3] - 2026-05-04

### Fixed

- Starred or watched GitHub repos no longer become automatically monitored. Auto-discovered watched repos now require at least one real work signal such as a push, commit, issue, PR, comment, or review.

## [0.23.2] - 2026-05-04

### Fixed

- The terminal pulse dashboard now filters its recent GitHub feed through the configured GitHub ignore list, so ignored repos stay hidden even when older rows are still present in the local database.

## [0.23.1] - 2026-05-04

### Fixed

- The terminal pulse dashboard now uses explicit dark and light palettes instead of ANSI reverse-video styling, preventing low-contrast text on light terminal backgrounds while preserving the inverse visual mode.
- Rich is now declared as a runtime dependency so the terminal dashboard and profiling tables are available after a normal package install.

## [0.23.0] - 2026-05-03

### Added

- A new `rebalance pulse` terminal dashboard (`scripts/dashboard.py`) — a Rich Live four-pane monitor of watched repos, recent GitHub activity, vault/calendar/sleuth signals, and index health. Polls the local SQLite every 2 seconds and runs `refresh_index(scope=["github"])` in a background thread every 10 minutes so the underlying data actually changes. Themed with the "Refined Dark" palette (single amber accent, low-contrast borders) and toggleable to inverse-video via `PULSE_INVERSE=1` for a brain-hack visual modality.
- A new `diagnose_repo` MCP tool that walks the watched-repos and sync funnel for a single repo and explains why it is or isn't being monitored. Supports per-commit and per-PR diagnoses (`sha=`, `pr=`) and an opt-in `live=True` that probes GitHub directly so callers can distinguish "we never synced" from "PAT can't see it."
- A new hourly vault refresh job (`scripts/com.rebalance-os.vault-sync.plist` + `vault_sync.sh` + `install_vault_scheduler.sh`) that calls `refresh_index(scope=["vault"])` at HH:15 from 06:15 to 23:15, so notes edited mid-day surface within the hour instead of waiting for the daily 06:30 sync.
- A new `rebalance profile-sync` subcommand that parses the most recent `daily_sync_*.log`, extracts per-repo GitHub timings, and prints a sorted Rich table with semantic colour bands for outliers and a `--top N` flag. The log parser walks the file with `JSONDecoder.raw_decode` for the last valid object, so it survives shell-prefixed lines, `tqdm` progress bars on the JSON line, and even multi-run logs.
- A new Slack user lookup (`src/rebalance/ingest/slack_users.py` + user-editable, gitignored `temp/slack_users.json`) that rewrites `<@U…>` mentions to friendly names across the dashboard sleuth panel and the published pulse markdown. Cached against the file's mtime so edits land on the next read without a restart.

### Changed

- The `rebalance` CLI now launches the live dashboard when invoked with no arguments. All existing subcommands continue to work and `rebalance --help` lists the full surface; `rebalance dashboard` is exposed explicitly so the launcher is discoverable. The CLI defaults `REBALANCE_DB` to the repo's `rebalance.db` so the dashboard works from any cwd.
- The vault note ingester now refreshes `vault_files.last_modified` when the on-disk mtime moves but content bytes don't, so a no-op save in Obsidian still registers as a "touch" in the dashboard. A new `touched_files` counter is reported alongside `new_files` / `updated_files` in the `refresh_index` JSON.
- The pulse markdown publisher now runs reminder messages through the same Slack mention rewrite, so reminders rendered into the daily pulse use friendly names instead of raw user IDs.

## [0.22.0] - 2026-04-28

### Added

- A new dashboard rendering command that synthesizes one Obsidian-ready operating note from recent local project, calendar, and GitHub signals.
- Structured dashboard output that pulls recent release highlights and current weekly goals into the same generated note so the operating surface stays anchored in recent shipped work and current intent.
- Focused tests covering dashboard note write-back plus the optional Gemini summary path.

### Changed

- Dashboard generation now supports an optional Gemini narrative layer for the operator summary while keeping project verdicts and evidence deterministic from local data.
- The dashboard flow now supports an optional cleanup mode that tightens the Gemini-written summary without changing the underlying structured evidence.

## [0.21.0] - 2026-04-28

### Added

- A new inferred project-registry pipeline that builds `project_registry` rows from existing GitHub and Calendar activity already stored in local SQLite, instead of requiring a hand-written registry to exist first.
- A `rebalance ingest infer-project-registry` command with a dry-run mode so inferred project rows can be previewed before they are written into the canonical SQLite registry.
- Focused tests covering repo-plus-calendar project merging, calendar-only project inference, ignored-repo exclusion, and stale inferred-row cleanup on resync.

### Changed

- Organization-style owners such as `NeochromeTeam` and `BinoidCBD` now collapse into cleaner umbrella project names when their repos are inferred from GitHub activity.
- Project inference now ignores repos with zero activity in the latest GitHub scan and filters out several recurring non-project calendar labels, producing a more usable first-pass registry.

## [0.20.0] - 2026-04-28

### Added

- A first-class local GitHub ingest ignore list stored in gitignored operator config, with CLI commands to add, remove, and list exact skipped repos.
- A destructive-but-audited GitHub repo purge path that can preview row counts with `--dry-run`, requires `--confirm` for execution, and records purge activity in the local audit log.
- Targeted tests covering ignored-repo config normalization, CLI management flows, GitHub scan filtering, artifact-sync rejection, purge cleanup, and semantic backfill exclusion.

### Changed

- GitHub activity scans now filter ignored repos before persistence and report how many repos were skipped.
- GitHub artifact sync and unified GitHub semantic backfill now enforce the same ignored-repo contract so skipped repos cannot be reintroduced through later ingest runs.

## [0.19.0] - 2026-04-24

### Added

- A new unified semantic index layer with `semantic_documents`, `semantic_embeddings`, and `semantic_embedding_meta` so vault chunks and GitHub artifact documents can be embedded and queried through one shared contract instead of separate per-source vector tables.
- New `rebalance semantic-backfill`, `rebalance semantic-embed`, and `rebalance semantic-query` CLI commands for populating, embedding, and querying the unified semantic layer directly from the existing local SQLite database.
- Focused semantic-index tests covering cross-source backfill, shared embedding/query behavior, and incremental re-embed behavior when only one source row changes.

### Changed

- Vault ingest now dual-writes into the unified semantic document layer after chunk updates, keeping the derived semantic index aligned with the canonical `chunks` table.
- GitHub artifact sync now dual-writes into the unified semantic document layer after rebuilding `github_documents`, so the new cross-source semantic index stays current without a separate post-sync job.
- GitHub artifact sync tests now assert that semantic write-through is happening, not just the legacy `github_documents` population.

## [0.18.4] - 2026-04-23

### Fixed

- `collect.sh` now treats watched-repo access failures as degraded scans instead of silently collapsing them into "no commits yet." When a repo scan fails, the collector still syncs metadata and any successfully scanned repos, but it records `repo_scan_failures`, `scan_status`, and `scan_failure_examples` in `devices/<device_id>.yaml` so the failure is visible.
- The collector no longer advances `~/.config/git-pulse/last-run` after a partial scan. That preserves the broken window for later re-collection once repo access is restored instead of making those commits invisible.
- `git-pulse-health` now reports recent-but-partial scans as `DEGRADED` rather than `ALIVE`, so the new heartbeat does not mask blocked watched repos.
- `install.sh` and `config.example.sh` now default repo discovery to non-protected roots (`~/code`, `~/src`, `~/Projects`) instead of `~/Documents`, aligning the installer with the launchd/TCC recovery guidance.

## [0.18.3] - 2026-04-23

### Fixed

- `git-pulse-health` no longer treats a quiet but healthy machine as stale just because its `pulse-<device_id>.md` file has not changed recently. The collector now publishes a sync-visible heartbeat in each device metadata record, and health checks prefer that heartbeat before falling back to pulse-file git history on older installs.
- Health output now reports the last scan timestamp instead of only the last pulse-file commit timestamp, and adds notes that surface the age of the last pulse update and last local commit when that context is available.

## [0.18.2] - 2026-04-22

### Fixed

- Hourly launchd-triggered git-pulse runs were silently failing on every machine because the sync repo and the watched repos lived under `~/Documents`, a macOS TCC-protected location. Launchd-spawned shells inherit no Full Disk Access, so `git` exited with `fatal: Unable to read current working directory: Operation not permitted` on every fire (`launchctl list` showed exit 128). The Phase 0 SQLite spike documented this risk only for the future SQLite layer; it should have been flagged for the existing collector too.
- Discovered as a follow-on issue: `~/.config/git-pulse/last-run` gets bumped to the scan-start epoch even when the watched-repo reflog walk fails inside the loop, so commits authored during the broken window become invisible to subsequent runs unless the operator rolls `last-run` back manually. Worth a future hardening pass on `collect.sh` so `last-run` only advances after a scan that actually iterated the watched repos successfully.

### Per-machine recovery instructions

The same recovery applies to every machine where launchd-triggered git-pulse hasn't been pushing on its expected hourly cadence (check with `git-pulse-health` — STALE for hours = likely affected).

```bash
# 1. Stop the launchd agent so we can reconfigure cleanly
launchctl unload ~/Library/LaunchAgents/com.user.git-pulse.plist

# 2. Move the sync repo out of ~/Documents (TCC-protected)
#    Adjust the source path to match this machine's current sync_repo_dir.
mv "$HOME/Documents/GH Repos/rebalance-git-pulse" "$HOME/git-pulse-sync"

# 3. Update sync_repo_dir in the config to the new location
sed -i '' "s|/Users/$USER/Documents/GH Repos/rebalance-git-pulse|/Users/$USER/git-pulse-sync|" \
  ~/.config/git-pulse/config.sh

# 4. Reload the launchd agent
launchctl load ~/Library/LaunchAgents/com.user.git-pulse.plist
```

If your watched repos in `~/.config/git-pulse/config.sh` (`repos=(...)`) still live under `~/Documents`, you also need **one** of the following so launchd-spawned `bash` can reach them:

- **Recommended for personal Macs:** add `/bin/bash` to System Settings → Privacy & Security → Full Disk Access. Open the pane with `open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"`, click `+`, press `⌘⇧G`, paste `/bin/bash`, Add, and ensure the toggle is on. macOS TCC tracks the responsible parent process; granting FDA on `git` alone does not propagate when invoked from a non-FDA shell.
- **Alternative:** move each watched repo out of `~/Documents` (mirrors the sync-repo fix). More disruptive — re-points editor workspaces and IDE bookmarks.

Then optionally roll back `last-run` so commits authored during the broken window get re-collected on the next fire:

```bash
# Use this machine's pulse file. Replace <device-id> with the slug from `git-pulse-health`.
tail -1 ~/git-pulse-sync/pulse-<device-id>.md | cut -f1 > ~/.config/git-pulse/last-run
```

Verify:

```bash
launchctl kickstart -k gui/$(id -u)/com.user.git-pulse
sleep 5
launchctl list | grep git-pulse        # exit code should be 0, not 128
git-pulse-health                       # this machine should flip to ALIVE
```

### Known quirk surfaced during recovery

`collect.sh` filters reflog entries down to `commit:` / `commit (initial):` / `commit (amend):` prefixes. Commits produced by `git rebase` are recorded in the reflog with different prefixes (`rebase:` family) and are therefore not captured into pulse files. The reachable orphan commits from before a rebase still get captured; the rebased target commits do not. Worth tracking; not blocking for this release.

## [0.18.1] - 2026-04-22

### Fixed

- Git pulse copied Python launchers now install their shared support files beside `~/bin/git-pulse-recap` and `~/bin/git-pulse-health`, including `pulse_common.py` and the recap summary rulebooks, so the new commands work on machines using copy mode from protected folders like `~/Documents`.
- The Python git-pulse entrypoints now resolve imports from their real script directory, which keeps shared-helper imports working in both copied and symlinked launcher modes.

## [0.18.0] - 2026-04-22

### Added

- New `git-pulse-health` command that reads the sync repo's git log for each `pulse-<device_id>.md` file and reports time-since-last-push per machine. Flags devices as ALIVE / STALE / ALERT / NO PUSHES with configurable thresholds (`--warn-hours`, `--alert-hours`). Exit codes: 0 all alive, 1 at least one stale, 2 any alert or missing pushes — suitable for shell chaining.
- Recap Daily Activity tables (both personal `recap.py` and team `team-recap.py`) now surface quiet days explicitly. Consecutive zero-activity days inside the coverage window collapse into a single `_<start> to <end> — no activity (N days)_` row so the reader can see gaps at a glance instead of inferring them from missing rows.

### Changed

- `pulse_common.py` gains `daily_activity_with_gaps(day_rows)` to compute the gap-aware reverse-chronological timeline; both recap scripts and any future SQLite-backed renderers share it.
- `install.sh` now installs a fourth launcher, `~/bin/git-pulse-health`, alongside the collector, view, and recap commands.

### Per-machine re-install instructions

Each machine already running git-pulse needs to pull the updated scripts and refresh its `~/bin/` launchers so launchd picks up the new `collect.sh` (from the earlier `hardware_uuid` work) and gains the new `git-pulse-health` command:

```bash
# On every machine running git-pulse:
cd /path/to/rebalance-OS
git pull
bash experimental/git-pulse/install.sh
```

`install.sh` is idempotent — it re-copies the launcher scripts, rewrites the launchd plist, and reloads the agent. No config changes required. After re-install, verify with:

```bash
git-pulse-health           # prints per-machine health table
git-pulse --dry-run        # quick smoke test of the collector
```

Running the collector once post-install (manually or by waiting for the next hourly launchd fire) will also rewrite that machine's `devices/<id>.yaml` with `schema_version: 2` and its `hardware_uuid`, completing the legacy metadata migration.

## [0.17.1] - 2026-04-22

### Fixed

- Git pulse collector migration now stages both renamed files and removed legacy files so duplicate machine pulse entries are actually deleted from the sync repo on push.
- Collector integration coverage now matches the real `git add -A -- ...` staging path used during legacy device-id cleanup.

## [0.17.0] - 2026-04-21

### Added

- A new `git-pulse-recap` command that merges overlapping saved TSV reports and renders an all-machines Markdown recap with summary metrics, coverage, repo rollups, daily activity, recent activity, and exception flags.
- Integration coverage for the recap flow, including default discovery from `sync_repo_dir/reports` and writing the rendered Markdown to disk.

### Changed

- The git-pulse installer now exposes a third launcher, `~/bin/git-pulse-recap`, alongside the collector and unified view commands.
- The git-pulse README now documents the saved-report recap workflow and the new recap artifact path under the sync repo's `reports/` directory.

## [0.16.3] - 2026-04-20

### Added

- Collector self-healing for old git pulse ids: a normal non-dry-run collection now migrates older UUID-based ids and older apostrophe-split slugs to the current human-friendly slug for that machine.
- Integration coverage for collector-driven device-id migration so the self-heal path is exercised without manual cleanup steps.

## [0.16.2] - 2026-04-20

### Changed

- Git pulse slug generation now drops apostrophes instead of turning them into extra separators, so names like `Noel's` become `noels` rather than `noel-s`.

## [0.16.1] - 2026-04-20

### Changed

- Git pulse device ids now default to human-friendly computer-name slugs instead of generated UUIDs when `device_id` is left blank.
- Git pulse hostname sanitization now trims leading and trailing dashes so device ids and host tags do not pick up quote-induced trailing separators.

## [0.16.0] - 2026-04-20

### Added

- A new `--include-local-unsynced` mode for the git pulse viewer so a saved report can combine synced cross-device pulse files with this Mac's current unsynced local reflog activity.
- Integration coverage for combined git pulse report generation, including writing a reusable TSV report to disk via `--output`.

### Changed

- The git pulse viewer can now generate a real reusable combined range report with `--days N --include-local-unsynced --output ...` instead of requiring ad-hoc terminal merges.

## [0.15.0] - 2026-04-20

### Added

- A new 14-day style window filter for the git pulse viewer so recent activity can be read as a bounded local-time slice instead of only single-day views.
- An integration test that exercises the git pulse viewer with a deterministic clock stub and verifies the flat row output contract.

### Changed

- The git pulse viewer now emits one canonical tab-separated schema with explicit local day and local time columns, replacing the previous comment-heavy preamble format.

## [0.14.0] - 2026-04-20

### Added

- Experimental Phase 0 plan for a deterministic GitHub Action that scans open issues against merged PRs and produces close-candidate recommendations every 2-3 days.
- Experimental standalone Action helper script in `/experimental` that reads open issues and merged PRs directly from the GitHub REST API, scores deterministic issue <-> PR matches, and emits JSON plus Markdown reports.
- Focused tests for the experimental Action helper covering explicit auto-close and strong inferred close recommendations.

### Changed

- Product memory now explicitly captures the intended split between deterministic GitHub hygiene in Actions and weekly higher-context local agent review.

## [0.13.0] - 2026-04-18

### Added

- New GitHub issue <-> PR reconciliation pass that suggests open issues likely fixed by merged PRs, grouped into high-confidence and medium-confidence recommendations with evidence.
- New `github-close-candidates` CLI command for reviewing explicit auto-close candidates and inferred close recommendations from the local GitHub corpus.
- New `github_close_candidates` MCP tool so hosts can ask for likely closeable issues before release or deployment planning.
- Unit tests covering explicit auto-close detection, strong inferred issue/PR matches, and medium-confidence review candidates.

### Changed

- GitHub planning can now distinguish between issues with explicit closing links and issues that only have strong inferred evidence from branch names, cross-mentions, commit messages, and title overlap.

## [0.12.0] - 2026-04-17

### Added

- Weekly report write-back path for the Obsidian vault: `calendar-weekly-report --vault ... --write-week-note` now creates `Weekly Notes/week-of-YYYY-MM-DD.md`.
- Weekly notes now include a deterministic `End of Week Summary` block with week window, total retained hours, working-day count, busiest day, review-needed count, and top project buckets so that next-week retrieval has a compact searchable recap.
- CLI tests covering weekly note write-back, required vault validation, and the automatic re-ingest/re-embed path.
- Weekly notes are now formatted as vault-native review artifacts with frontmatter and a stable `week-of-YYYY-MM-DD.md` naming contract for downstream retrieval.

### Changed

- Weekly report generation now supports turning the report into a vault-native note with frontmatter for downstream ingestion and retrieval.
- Writing a weekly vault note can immediately re-ingest and embed the updated vault so the generated summary becomes part of the local knowledge base without a separate operator step.
- The weekly review flow now closes the loop between calendar reporting and second-brain retrieval instead of leaving weekly output as a disconnected export.

## [0.11.0] - 2026-04-17

### Added

- New explicit GitHub readiness inference over the local corpus, including milestone selection, blockers, evidence, release-branch detection, deployment-issue parsing, and confidence scoring.
- New `github-release-readiness` CLI command for current-state inspection from locally synced GitHub signals.
- New `github_release_readiness` MCP tool so hosts can ask for review, merge, release-candidate, and deploy-ready state without live GitHub scanning.
- Unit tests covering repo metadata and branch sync plus a focused readiness-inference scenario with review blockers and a missing release branch.

### Changed

- GitHub artifact sync now stores repo metadata and branches so readiness inference can reason about default branches, release branches, and promotion paths locally.
- The public tool surface now treats GitHub readiness inference as live functionality instead of planned-only work.

## [0.10.0] - 2026-04-17

### Added

- Local-first GitHub knowledge sync for detailed artifacts: issues, pull requests, labels, milestones, releases, comments, reviews, review comments, commits, and check runs are now stored in SQLite instead of being read live at answer time.
- A new local GitHub document corpus built from issue bodies, PR bodies, comments, reviews, review comments, and commit messages, ready for semantic retrieval with local embeddings.
- New CLI commands for the GitHub corpus workflow: `github-sync-artifacts`, `github-embed`, and `github-query`.
- New `query_github_context` MCP tool for semantic retrieval over the local GitHub corpus.
- Linked-issue extraction from pull request text using closing keywords such as `fixes #123`, so the local store can preserve issue-to-PR relationships for readiness inference.
- Two focused GitHub unit tests covering artifact sync, document creation, embedding, and semantic query against mocked GitHub responses.

### Changed

- The main `ask` flow now includes relevant semantic GitHub artifacts alongside structured GitHub activity when local GitHub context is available.
- Version metadata is now aligned again across the package, manifest, and changelog.

## [0.9.0] - 2026-04-15

### Added

- New `rebalance calendar-snap-edges` CLI command — detects slightly overlapping calendar events and trims Event 1's end to 1 minute before Event 2's start, producing clean adjacent boundaries. Dry-run by default; pass `--apply` to patch Google Calendar.
- Batch mode via `--days` flag (1-7 consecutive days per run) with per-day overlap reporting.
- New `snap_calendar_edges` MCP tool with the same capabilities for agent-driven workflows.
- First `events().patch()` integration — the project can now update existing Google Calendar events (previously only read and create).
- 18 unit tests covering overlap detection (2-event pairs, 3+ cluster skips, contained events, adjacent non-overlaps, UTC Z-suffix), patch call verification, dry-run vs apply behaviour, timezone preservation, and batch validation.

### Changed

- All-day events and clusters of 3+ overlapping events are intentionally skipped — not enough context for automated resolution. Skipped clusters are reported so operators can resolve them manually.

## [0.8.0] - 2026-04-14

### Added

- New `rebalance calendar-create-event` CLI command for creating Google Calendar events from plain terminal sessions without needing the rebalance MCP server to be registered in the calling client.
- Dry-run support for calendar event creation. Operators can preview the normalized payload, including all-day date expansion into timezone-aware midnight boundaries, with no network calls or calendar writes.
- CLI tests covering the dry-run payload shape and the required write-scope guard.
- Duplicate guard for calendar event creation: before writing, the CLI now searches the target calendar for an existing event with the same title and start date.
- Idempotency controls for calendar creation: `--skip-if-exists`, optional `--dedupe-key`, and local structured JSONL logging for created, skipped, and blocked attempts.
- Machine-readable CLI output via `--output json`, including distinct statuses for `created`, `skipped_existing`, `blocked_duplicate`, and `idempotency_hit`.

### Changed

- Google Calendar docs now include a "Creating Events Programmatically" section with write-scope validation, dry-run workflow, and a copy-paste project reminder example.
- MCP docs now recommend the CLI path for non-MCP clients and clarify why the project bypasses raw JSON-RPC for local operator workflows.
- Calendar event docs now call out duplicate-guard blind spots (title edits, overlapping multi-day events), recommend when to use `--dedupe-key`, and document local log rotation expectations.

## [0.7.0] - 2026-04-14

### Added

- Write-capable Google Calendar MCP tool: `create_calendar_event`. Agents can now create events with summary, start/end time, optional description, location, attendees, calendar override, and timezone payload.
- Calendar write-path tests covering OAuth scope enforcement, timezone-aware validation, and event insertion payload generation.

### Changed

- `scripts/setup_calendar_oauth.py` now supports `--write-access` so a device can be reauthorized with Google Calendar write scope instead of the previous read-only scope.
- Version metadata is now aligned across the Python package, manifest, and changelog at `0.7.0`.

## [0.6.2] - 2026-04-07

### Fixed

- Aggregator skip words no longer tokenize `exclude_titles`. Previously, a title like "Post Daily Timesheet" leaked "post", "daily", and "timesheet" into the aggregator, silently suppressing legitimate project keywords. `exclude_titles` and `aggregator_skip_words` now serve separate purposes with no cross-contamination.
- Preflight activity date parsing now uses the canonical `parse_calendar_dt` helper instead of inline Z-replace, preventing a CI grep check failure.
- Added `# raw-ok` annotations to `calendar.py` connection calls that can't use the helper due to circular imports.

### Added

- 16 unit tests for the canonical calendar helpers: datetime parsing (Z-suffix, offset-aware, date-only, invalid), duration calculation (normal, all-day, mixed naive/aware, negative, empty), and connection context manager (open/close lifecycle). 68 tests total.

## [0.6.1] - 2026-04-07

### Changed

- Extracted shared calendar helpers into a single canonical module: datetime parsing (`parse_calendar_dt`), duration calculation (`event_duration_minutes`), and database connection setup (`calendar_connection`). Eliminates duplicated patterns across the daily report, calendar sync, and MCP server modules.
- `calendar-daily-totals` now applies the same `calendar_id`, `exclude_titles`, and `hours_format` filters as the daily and weekly report commands. Previously showed unfiltered counts that didn't match the other reports. Resolves Hypercart-Dev-Tools/rebalance-OS#5.

### Fixed

- All-day events (date-only strings from Google Calendar) no longer crash the daily report duration calculation. They appear in the event list with 0 duration instead. Resolves Hypercart-Dev-Tools/rebalance-OS#4.

### Added

- CI grep checks that fail the build if raw datetime parsing or duration calculation patterns appear outside the canonical helpers without a `# raw-ok` escape hatch.

## [0.6.0] - 2026-04-07

### Added

- **Agent review layer for calendar reports.** Events that pass the exclude filter but don't match any configured project now appear in a "Needs Review" section at the bottom of daily reports. Agents or users can classify these via the new `review_timesheet` and `classify_event` MCP tools.
- Two new MCP tools: `review_timesheet(date)` returns unclassified events for a given date with available project names; `classify_event(summary, decision)` persists a classification ("include", "exclude", or "project:Name") so the same event pattern is handled automatically in future reports.
- Review decisions persist to `temp/review_decisions.json` (gitignored) so they survive across sessions.
- New config field `aggregator_skip_words` — broad terms (e.g. "wrap", "setup", "test") that are skipped during project aggregator grouping but do **not** filter events from the report.

### Changed

- **Breaking (config):** `exclude_keywords` replaced by `exclude_titles` for event filtering. Filtering now uses **exact title matching** (case-insensitive) instead of substring matching. This prevents real work events like "Wrap up Countdown Timer" and "Setup rebalance app" from being silently dropped when "wrap" or "setup" appear in the exclude list. Legacy `exclude_keywords` in existing config files is automatically migrated to `exclude_titles`.

### Fixed

- Resolves Hypercart-Dev-Tools/rebalance-OS#2 — exclude keywords no longer filter out legitimate work events containing common verbs.

## [0.5.8] - 2026-04-07

### Added

- CI test suite for Google Calendar functionality: config loading and validation, duration formatting (decimal and hm), daily reports (filtering, timezone, empty days), weekly reports (summary totals, project aggregator, both formats), calendar-sync config resolution, and calendar_id filtering. 36 tests total.
- GitHub Actions CI workflow running tests on Python 3.12 and 3.13 for every push and pull request to main (10-minute hard timeout).
- Google Calendar API dependencies declared as `[calendar]` optional dependency group in pyproject.toml (`pip install -e ".[calendar]"`).

### Fixed

- Report output now uses correct grammar: "1 event" instead of "1 events" in daily totals and project aggregator lines.

## [0.5.7] - 2026-04-07

### Added

- Configurable hours format for calendar reports: set `"hours_format": "decimal"` (default, e.g. `4.50h`) or `"hm"` (e.g. `4h 30m`) in the calendar config. Applies to daily reports, weekly summaries, and project aggregator tables.

## [0.5.6] - 2026-04-07

### Fixed

- `rebalance calendar-sync` now reads `calendar_id` from the calendar config instead of defaulting to `"primary"`. Previously, syncing always pulled from the user's personal calendar unless `--calendar-id` was passed explicitly, even when the config pointed to a shared team calendar. The `--calendar-id` CLI flag still overrides when provided.

### Changed

- Rewrote Google Calendar documentation with Prerequisites, Team Quick Setup, and Claude Code Setup sections for smoother developer onboarding.
- Updated README Step 4 to reflect embedded OAuth credentials — developers no longer need to create a Google Cloud project or download a separate client secret file.

## [0.5.5] - 2026-04-07

### Added

- Calendar report project matching now supports a non-Obsidian fallback: if no synced project registry exists in SQLite, reports load canonical project names and aliases from the calendar config.

### Changed

- Calendar config now supports a `projects` list for lightweight local project definitions when a developer only needs calendar timesheet grouping without the full Obsidian registry workflow.

## [0.5.4] - 2026-04-07

### Changed

- Calendar report project aggregation now treats the synced project registry as the canonical source of truth for project names and aliases, falling back to keyword grouping only for unmatched events.

### Fixed

- Daily and weekly calendar reports now preserve canonical project casing from the registry instead of reformatting matched names through heuristic title-casing.

## [0.5.3] - 2026-04-07

### Fixed

- Weekly and daily project aggregators now skip low-signal verb labels such as "can", "change", and similar filler terms, so grouped work is easier to scan.
- Project aggregation now reuses the same calendar exclude keywords as event filtering, so one keyword source drives report cleanup across the calendar reporting flow.

## [0.5.2] - 2026-04-07

### Added

- Example calendar config template at repo root for new users.
- Calendar config setup guide (4 steps: create temp folder, copy example, edit config, verify).

### Changed

- Replaced inline config template with repo-root example file.
- Clarified README calendar config instructions with code examples.

## [0.5.1] - 2026-04-07

### Added

- Portability audit confirming zero hardcoded user data across calendar setup and configuration.
- Step-by-step new user setup guide for OAuth, config, testing, and scheduling.

### Changed

- OAuth setup script now lists all available calendars with IDs and provides next-step instructions.

## [0.5.0] - 2026-04-07

### Added

- Daily and weekly calendar report CLI commands (`calendar-daily-report`, `calendar-weekly-report`) with event filtering, project aggregator grouping, and time totals.
- Per-device calendar config for calendar selection, exclude keywords, and timezone (gitignored).
- Project aggregator groups similar events by keyword, counts, and sums durations.
- Exclude keywords filter events from reports while keeping them in the database.
- Timezone-aware report times (configurable, defaults to America/Los_Angeles).
- All reports generated in clean markdown format suitable for Obsidian, email, or archival.

### Fixed

- Database layer now gracefully handles systems without sqlite-vec extension support.

## [0.4.2] - 2026-04-07 — Google Calendar multi-calendar + daily totals

- Extended `calendar.py` to support reading from any calendar (not just primary): `sync_calendar(calendar_id=...)` parameter.
- Added `DailyEventTotal` dataclass — aggregates event count and duration by day with helper methods (total_hours, __str__).
- Added `get_daily_totals(database_path, days_back, days_forward)` — calculates combined daily event metrics from calendar_events table.
- Added `rebalance calendar-daily-totals` CLI command — displays daily event summary (count, duration) with aggregate stats (total events, avg events/day, avg hours/day).
- Updated `calendar-sync` command to accept `--calendar-id` parameter (email or group ID).
- Updated PROJECT.md: documented calendar parameter, daily totals command, and updated access setup to use new `setup_calendar_oauth.py` script.
- Added `scripts/setup_calendar_oauth.py` — automated OAuth2 setup script that generates and stores token in `~/.config/gcalcli/oauth`.

## [0.4.1] - 2026-03-30 — Claude Desktop manual config + MCP.md tool surface update

- Added step-by-step Claude Desktop manual setup instructions to MCP.md (config path, absolute paths, troubleshooting table).
- Updated README.md: Claude Desktop section now leads with manual config (recommended) and moves `.mcpb` extension to "coming soon".
- Updated MCP.md tool surface: `ask`, `query_notes`, `search_vault`, and all onboarding tools (`onboarding_status`, `setup_github_token`, `run_preflight`, `confirm_projects`) moved from Planned to Live.
- Reduced Planned tool surface to `todays_agenda`, `morning_brief`, and `query_github_context`.

## [0.4.0] - 2026-03-29 — Google Calendar integration

- Added `calendar.py` — Google Calendar API collector that fetches events and persists to `calendar_events` SQLite table with 1-year retention.
- OAuth2 flow via `google-auth-oauthlib` with token stored at `~/.config/gcalcli/oauth`. Auto-refresh on expiry.
- Added `rebalance calendar-sync` CLI command with configurable `--days-back` (default 30, use 365 for initial backfill) and `--days-forward`.
- Wired calendar context into `ask` tool: upcoming events (next 2 days) + recent events (last 7 days) included in both prompt and raw context.
- Updated PROJECT.md: P2 Google Calendar now marked Active with full access setup docs, vectorization status noted on all signal sources.
- Updated ARCHITECTURE.md: signal sources table now includes Vectorized column, calendar added to storage layer and module map.

## [0.3.0] - 2026-03-29 — `ask` tool + multi-source query engine

- Added `querier.py` — general-purpose natural language query engine that gathers context from all data sources (project registry, GitHub activity, vault embeddings, vault file modification dates) and optionally synthesizes a first-pass answer via local Qwen3-0.6B LLM (mlx-lm).
- Added `ask` MCP tool — host agents call this with any natural language question and get back both a local LLM synthesis and raw structured context for review/refinement.
- Added `rebalance ask` CLI command with `--no-llm` flag for raw context only.
- Two-layer LLM architecture: local Qwen3 does fast on-device synthesis, host agent (Claude, Copilot, etc.) reviews and refines.
- Added `ARCHITECTURE.md` — documents data flow, signal pipeline pattern, two-layer LLM design, and how to add new data sources.

## [0.2.0] - 2026-03-29 — Vault ingestion + embeddings pipeline

- Added `db.py` — shared database layer with sqlite-vec extension loading, WAL mode, and schema creation for all vault/embedding tables.
- Added `md_parser.py` — pure markdown parsing: YAML frontmatter extraction, wikilink/embed detection, #tag extraction, heading-based chunking.
- Added `note_ingester.py` — vault walker with SHA-256 hash-based delta detection, TF-IDF keyword extraction (pure Python, no sklearn), and wikilink/embed tracking.
- Added `embedder.py` — batch embedding via mlx-embeddings (Qwen3-Embedding-0.6B, 1024-dim), sqlite-vec storage, model version tracking for automatic re-embed on model change, ANN similarity search.
- Added CLI commands: `rebalance ingest notes`, `rebalance ingest embed`, `rebalance query`, `rebalance search`.
- Added MCP tools: `query_notes` (semantic search), `search_vault` (keyword search).
- Fixed frontmatter serialization: `date` objects from YAML now serialize to ISO strings via custom JSON encoder.
- Fixed sqlite-vec KNN query: uses `e.k = ?` constraint required by vec0 virtual tables.
- Added `.venv/*` to default ingest exclude patterns to prevent indexing Python package metadata.
- Added `sqlite-vec` to core dependencies, `mlx-embeddings` as optional `[embeddings]` extra in pyproject.toml.

## [0.1.1] - 2026-03-28 — Onboarding MCP tools + schema fixes

- Added 4 onboarding MCP tools: `onboarding_status`, `setup_github_token`, `run_preflight`, `confirm_projects` — enables agent-driven onboarding through any MCP host.
- Refactored `preflight.py`: split monolithic `run_preflight()` into `discover_candidates()` (read-only) + `confirm_and_write()` (write + sync). CLI re-wired to call both.
- Added `validate_github_token()` in `github_scan.py` — validates PAT against GitHub `/user` endpoint and captures OAuth scopes.
- Fixed schema mismatch between MCP server and registry: server now queries `repos_json` column (not `repos`) and decodes as JSON (not YAML).
- Fixed registry `sync_db()` to write JSON (not YAML) into `_json` columns.
- Shipped `.vscode/mcp.json` for automatic MCP server registration on workspace open.
- Added `CLAUDE.md` with agent onboarding instructions so any MCP host can drive first-run setup.
- Updated PROJECT.md and MCP.md: aligned onboarding sequence to MCP-driven flow, standardized segment naming to match code (`*_projects` suffix), fixed `REBALANCE_DB` documentation, added refactor notes.

## 2026-03-28 (onboarding sequence)

- Expanded [PROJECT.md](PROJECT.md) with a reusable `Onboarding User Story Sequence` for first-run VS Code + AI agent setup.
- Defined first-run detection rules for missing/blank config, missing registry, and invalid stored GitHub PAT.
- Documented target onboarding bootstrap flow:
  - review README
  - start MCP server/services
  - detect new user
  - request GitHub PAT
  - validate PAT via live GitHub auth
  - pre-populate registry from GitHub activity into 7-day / 8-14 day / 15-30 day buckets
  - merge with vault-discovered candidates
  - write canonical registry and sync projections
- Added recommended follow-on onboarding steps: vault path confirmation, minimal metadata capture, optional calendar setup, resumable onboarding state, and startup smoke test.

## 2026-03-28 (activity segmentation)

- Implemented activity-based candidate segmentation in preflight generation:
  - Updated `run_preflight()` in `src/rebalance/ingest/preflight.py` to route curated projects into:
    - `most_likely_active_projects` (activity in last 14 days)
    - `semi_active_projects` (activity 15-30 days ago)
    - `dormant_projects` (activity 31+ days ago)
    - `potential_projects` (no activity signal available)
  - GitHub-derived candidates now persist `last_activity_at` from scanner output to support bucketing.
  - Added `_calculate_days_since_activity()` helper for ISO date parsing and resilient fallback behavior.
- Updated default registry section descriptions in `src/rebalance/ingest/registry.py` to document the new segmented buckets.

## 2026-03-29 (continued, part 2)

- **Tested GitHub & vault preflight discovery**:
  - GitHub PAT authentication working with a non-production operator account.
  - GitHub activity scanner runs correctly; no recent activity in last 14 days (most recent events: Aug 2025).
  - Vault title scanner discovered **36 project candidates** spanning active work, templates, scratchpads, and admin notes.
  - Registry file now properly formatted (newlines fixed in `_default_registry_markdown()` and `save_registry()` functions).
  - All 36 candidates stored in `potential_projects` section ready for curation.

## 2026-03-29 (continued)

- Preflight now includes **GitHub activity discovery** as a project intake signal:
  - `discover_repos_from_activity()` scans recent GitHub activity and returns repos sorted by activity score.
  - `rebalance ingest preflight --include-github` surfaces touched repos as potential project candidates (with commit counts and activity scores pre-populated).
  - Discovered via `github_token` parameter (from stored config) — gracefully degrades if GitHub scan fails.
- Config management system (`src/rebalance/ingest/config.py`):
  - Stored in `temp/rbos.config` (plaintext JSON, gitignored) for MVP simplicity.
  - `rebalance config set-github-token <PAT>` — stores PAT in config.
  - `rebalance config get-github-token` — check if token is configured (masked output for security).
  - `rebalance config show-config-path` — show config file location.
  - Future: upgrade to `keyring` library when multi-user or compliance required.
- Updated `rebalance ingest preflight` signature: now accepts `--include-github` and `--github-days` options.

## 2026-03-29

- Ported GitHub activity reader from `gitdaily` (TypeScript → Python):
  - `src/rebalance/ingest/github_scan.py` — PAT auth, events pagination (3-page cap), per-repo aggregation (commits/pushes/PRs/issues/reviews), SQLite persistence in `github_activity` table.
  - `rebalance github-scan` CLI command (accepts `--token`, `--days`, `--database`; `GITHUB_TOKEN` + `REBALANCE_DB` env vars).
  - `github_balance(since_days)` MCP tool in `mcp_server.py` — joins `project_registry.repos` with `github_activity` to surface idle vs active projects.
- Fixed regex bug in `src/rebalance/ingest/registry.py`: `YAML_BLOCK_PATTERN` had `\\s*` (string-escaped) in a raw string; corrected to `\s*`.
- `mcp_server.py`: added `json` import, `repos` column to project query (decoded from JSON string), `_project_repos_map()` helper.

## 2026-03-28

- Updated `PROJECT.md` to make in-vault Markdown registry canonical (`Projects/00-project-registry.md`) with sync modes: `pull`, `push`, `check`.
- Added preflight workflow spec: discover project candidates from vault page titles, curate keep/remove, collect 2-3 sentence summary, and capture quantitative/qualitative custom fields.
- Scaffolded Python package with CLI and ingest modules:
  - `rebalance ingest preflight`
  - `rebalance ingest sync --mode pull|push|check`
- Added registry and projection plumbing:
  - Markdown registry loader/saver
  - `projects.yaml` projection writer
  - SQLite `project_registry` upsert path
- Added initial MCP server scaffold with `list_projects(status="active")` tool.
- Added template file: `templates/project-registry.template.md`.
- Updated `README.md` with initial scaffold status and developer bootstrap commands.
