# P1 Module Registry

> **Priority:** Promoted P3 → **P1** and moved to `2-WORKING` on 2026-05-31 (was `1-INBOX/P3-MODULE-REGISTRY.md`).
> **Status:** Decision taken 2026-05-31 — adopt **Approach B′ (extend the existing `index_ops` collector registry)**, incrementally, descriptor-first. Supersedes the 2026-05-08 "defer B" recommendation; see [Update 2026-05-31](#update-2026-05-31--the-registry-already-exists-extend-index_ops). Original balanced analysis (Approaches A/B/C) retained below unchanged for provenance.
> **Original status (2026-05-08):** Open proposal — written to be reviewed by another agent.
> **Author note:** the original doc is intentionally balanced. Pros and cons are listed for each approach. The 2026-05-31 update lands the decision the original deferred, on the strength of new evidence.

## TOC

- [Update 2026-05-31 — the registry already exists (extend index_ops)](#update-2026-05-31--the-registry-already-exists-extend-index_ops)
- [Why the 2026-05-08 verdict changed](#why-the-2026-05-08-verdict-changed)
- [Approach B′ — extend the runtime collector registry](#approach-b--extend-the-runtime-collector-registry)
- [Phased plan](#phased-plan)
- [What this explicitly does not do](#what-this-explicitly-does-not-do)
- --- original 2026-05-08 proposal below ---
- Trigger
- Problem statement
- Required fan-out (shared by every approach)
- Approach A — Post-hoc audit script
- Approach B — Proactive registry / scaffolder
- Approach C — Do nothing automated; tighten the SOP only
- Comparison
- Findings from Approach A prototype (2026-05-08)
- Open questions
- Recommended next step

## Update 2026-05-31 — the registry already exists (extend index_ops)

The 2026-05-08 analysis deferred Approach B (proactive registry) as premature: "N=1 drift, ~600–1000 lines of scaffolding, forces a uniform shape on eight heterogeneous collectors." Two things have changed that flip that cost-benefit.

**1. A runtime collector registry already exists — we don't have to build one.** Since the original doc was written, [src/rebalance/ingest/index_ops.py](../../src/rebalance/ingest/index_ops.py) grew a `Collector` registry (`register_collector`, `COLLECTORS`) that already declares every ingest source — `vault`, `github`, `calendar`, `sleuth`, `email`, `semantic` (lines ~1008–1013) — and dispatches `refresh_index` / `index_status` / `scope=["all"]` through it. Crucially it sidesteps Approach B's worst Con: each collector supplies an arbitrary `refresh` callable, so the registry does **not** force a uniform module shape — it accommodates the heterogeneity (different secrets, concurrency, delta strategies) the original doc worried about. The expensive part of B (build a registry from scratch + a scaffolder/codegen) is no longer on the table. What remains is cheap and additive: give the descriptor a few more optional fields.

**2. The drift/implicit-classification cost (original finding #5) has recurred — and now bites agents, not just docs.** Concrete evidence from 2026-05-31:

- The same source set (`vault/github/calendar/sleuth/email/semantic`) is **re-enumerated independently in four places** — `index_ops.COLLECTORS` (registry ✅), [doctor.py](../../src/rebalance/doctor.py) (hardcoded `_check_*` + manual appends ❌), `querier.ask` (`_gather_*_context` ❌), and the new morning-brief collector ([scripts/spike_morning_brief.py](../../scripts/spike_morning_brief.py), its own hardcoded reads ❌). Adding a source means editing four lists that drift.
- An agent setting up Google Calendar had to **grep** the repo for `setup_calendar_oauth.py` because `rebalance doctor` already knew the remediation but is **CLI-only — not exposed as an MCP tool**, and `onboarding_status` doesn't check calendar OAuth. The right knowledge existed in one enumeration (doctor) and was unreachable from the surface the agent is told to use (MCP). That is exactly the "data wanting to be a field / fanout drift" failure, now manifesting as an agent dead-end rather than a stale doc.

This is the "recurred at least once more" trigger the original doc named as the condition for revisiting B.

## Why the 2026-05-08 verdict changed

| Original Con of Approach B | Status as of 2026-05-31 |
|---|---|
| "~600–1000 LOC to build a registry + scaffolder" | **Gone.** The registry exists (`index_ops.COLLECTORS`). No scaffolder/codegen is proposed. Work is additive optional fields + pointing existing consumers at it. |
| "Forces uniform shape on heterogeneous collectors" | **Gone.** Collectors already register an arbitrary `refresh` callable; new fields are optional callables too. No shape is imposed. |
| "Premature at N=1 drift" | **Resolved.** Drift recurred (4-way re-enumeration + the calendar-OAuth agent dead-end). Finding #5 (implicit classification) is now load-bearing, as predicted. |
| "Registry itself can drift; still needs an audit (A)" | **Still true** — and fine. Approach A's [audit_modules](../../scripts/audit_modules.py) becomes the verifier of the registry (Phase 5), which is where the original doc said A naturally lives. |

Net: this is not the original Approach B (new `module_registry.yaml` + `scaffold-module` codegen). It is **B′** — extend the registry that already exists. Smaller, additive, reversible per phase.

## Approach B′ — extend the runtime collector registry

Promote `index_ops.Collector` from a *refresh-only* descriptor into the **one place a source is declared**, by adding optional fields (defaults preserve today's behavior — existing collectors keep working un-touched):

- `health_check: Callable | None` — returns a doctor `Check` (credential present? token valid? table fresh?). When absent, doctor falls back to a generic freshness check derived from `storage_tables`.
- `read_for_brief: Callable | None` — returns the source's morning-brief candidate rows. When absent, the source simply doesn't contribute to the briefing.
- Classification metadata (the data that finding #5 showed "wants to be a field"): `module_class: "source" | "render" | "helper"`, `storage_tables: tuple[str, ...]`, `secrets: tuple[str, ...]`, `scheduler: "own" | "piggyback" | None`, `user_facing: bool`, `strategic_alignment: str | None`.

Then the four consumers stop hardcoding and **iterate the registry**:

- `refresh_index` / `index_status` — already do (no change).
- `doctor` — iterate `COLLECTORS`, call each `health_check`; expose as a new MCP `health_check()` tool so MCP-first agents reach remediation hints (closes the calendar-OAuth gap).
- morning brief — iterate `COLLECTORS`, call each `read_for_brief`; a newly-registered source auto-appears in the briefing.
- `querier.ask` — iterate `COLLECTORS` for `_gather_*_context`.

Registering one `Collector` then wires a source into refresh, status, health, briefing, and read — instead of five separate edits that drift.

## Phased plan

Each phase is independently shippable and reversible (new fields are optional; nothing breaks if a phase stops here).

- [ ] **Phase 1 — Extend the descriptor.** Add the optional fields above to `Collector` in [index_ops.py](../../src/rebalance/ingest/index_ops.py). Backfill `module_class` / `storage_tables` / `secrets` on the existing 6 collectors. No consumer changes yet. Gate: `refresh_index`/`index_status` behavior byte-identical.
- [ ] **Phase 2 — Doctor consumes the registry + MCP `health_check()`.** Move `_check_calendar`/`_check_sleuth`/`_check_gmail`/freshness onto each collector's `health_check`; have [doctor.py](../../src/rebalance/doctor.py) iterate `COLLECTORS`. Add a `health_check()` MCP tool in [mcp_server.py](../../src/rebalance/mcp_server.py) returning the structured report. Gate: `rebalance doctor` output unchanged; the new source's setup hint is now reachable via MCP. **This is the slice that fixes the gap that triggered this update.**
- [ ] **Phase 3 — Morning brief consumes the registry.** Replace the spike's hardcoded source reads with `read_for_brief` on each collector (folds into P1 Morning Briefing, Phase 1). Gate: brief output matches the spike for the current sources; a test source auto-appears.
- [ ] **Phase 4 — querier consumes the registry.** Drive `_gather_*_context` from `COLLECTORS`. Gate: `ask` answers unchanged on a fixed query set.
- [ ] **Phase 5 — audit + doc fanout from the registry.** Point [audit_modules](../../scripts/audit_modules.py) at the registry as source-of-truth (closes prototype findings #4/#5/#6 — classification is now a field, not an ignore-list). Optional: registry-driven ARCHITECTURE.md Signal-Sources / module-map writers. Update the ARCHITECTURE.md "Adding a New Source" SOP to "register a `Collector`, fill its fields" instead of the prose 8 steps.

## What this explicitly does not do

- **No scaffolder / codegen.** That was the heavy half of the original Approach B; it is not proposed. Authors still write collectors by hand; they just register one descriptor.
- **No uniform-shape mandate.** All new descriptor fields are optional callables/metadata. A collector that only refreshes (no brief read, no custom health check) stays a one-liner.
- **No blocking CI gate (yet).** Phase 5's audit stays advisory unless/until CI exists for this repo (original Open Question #4 is unchanged).
- **No 4X4/README auto-spam.** `strategic_alignment` / `user_facing` remain explicit opt-in fields, per the original "Required fan-out" caution.

---

> The sections below are the original 2026-05-08 proposal, retained verbatim for provenance. The 2026-05-31 update above supersedes the "Recommended next step."

## Trigger

While debugging why [web/pulse.html](../../web/pulse.html) was 10+ hours stale on the morning of 2026-05-08, three drift facts surfaced:

1. [scripts/pulse_web.py](../../scripts/pulse_web.py) (708 lines, generates the local web mirror of the dashboard) is **not** referenced anywhere in [ARCHITECTURE.md](../../ARCHITECTURE.md), nor in its `scripts/` module map.
2. There is no launchd plist or other scheduler that runs `pulse_web.py`. The three existing jobs (`daily-sync`, `vault-sync`, `pulse-sync`) cover daily full sync, hourly vault refresh, and hourly markdown→private-repo publish — none touch the local HTML mirror.
3. The script *is* mentioned in [CHANGELOG.md](../../CHANGELOG.md) under `[0.25.0]`, so the change wasn't invisible — it just didn't propagate to ARCHITECTURE.md, the module map, or the launchd inventory.

This is the canonical "new ETL/render module shipped, but the supporting docs and schedulers drifted" failure. The repo's existing 8-step *Adding a New Source* SOP in [ARCHITECTURE.md](../../ARCHITECTURE.md) covers the right beats but is prose-only and unverified.

## Problem statement

We add ingest collectors and render modules at a steady cadence (`github_scan`, `github_knowledge`, `calendar`, `sleuth_reminders`, `pulse_web`, future `email`, future `_gather_sleuth_context`). Each new module **should** trigger updates to:

- [ARCHITECTURE.md](../../ARCHITECTURE.md) — Signal Sources table, fanout diagram, module map, *Adding a New Source* SOP completion
- [CHANGELOG.md](../../CHANGELOG.md) — semver-style entry under the next version
- [4X4.md](../../4X4.md) — only if the module advances or shifts a strategic goal / current-week goal
- [README.md](../../README.md) — only when the module changes the user-facing capability surface
- A Pulse refresh — regenerate [web/pulse.html](../../web/pulse.html) via `pulse_web.py`, republish the markdown via the `publish_pulse` MCP tool. (The terminal dashboard at [scripts/dashboard.py](../../scripts/dashboard.py) auto-polls SQLite every 2s and does not need an explicit trigger.)

Today none of these is enforced. The 8-step SOP is a checklist humans either follow or don't.

## Required fan-out (shared by every approach)

Whatever approach we choose, it must end up touching all five targets above. The shape that varies is **when** the touch happens (after-the-fact audit vs. at-creation scaffold) and **how strict** it is (advisory report vs. blocking gate). Concretely, the writes look like:

| Target | What gets written | Trigger |
|---|---|---|
| ARCHITECTURE.md | Row in Signal Sources table; entry in module map; line in fanout diagram | Module added/changed |
| CHANGELOG.md | Entry under unreleased / next version | Module added/changed |
| 4X4.md | Optional — only if `strategic_alignment` field is set on the module | Module added with strategic intent |
| README.md | Optional — only if `user_facing: true` is declared | Module changes capability surface |
| Pulse refresh | Run `pulse_web.py` + invoke `publish_pulse(push=True)` | Any of the above writes succeed |

The "optional" rows matter: spamming 4X4 / README on every internal refactor would create noise that drowns out the meaningful changes. Whichever approach we pick needs an explicit **opt-in** signal for those two targets.

## Approach A — Post-hoc audit script

**Shape:** ~50–100 line `scripts/audit_modules.py`. Walks `src/rebalance/ingest/*.py` and `scripts/*.py`, compares each module name against ARCHITECTURE.md (grep), CHANGELOG.md (grep), and the launchd plist inventory. Emits a delta report. Optionally runs in CI as a non-blocking warning, or pre-release as a blocking gate.

### Pros

- Cheap to build (one afternoon). Cheap to delete if it doesn't earn its keep.
- Doesn't constrain how new modules are added. Authors keep using whatever shape fits the source (the eight existing collectors don't have a uniform shape and don't need one).
- Catches drift created by humans, agents, or merges from forks — anything ending up on disk gets seen.
- Failure mode is a noisy report, not a broken pipeline. Easy to reverse.

### Cons

- Reactive. The drift exists for some window before the audit catches it (the pulse_web case has been stale since 0.25.0 shipped).
- Doesn't help author at moment of creation; humans still have to know the SOP. Repeats existing 8-step prose, just behind a script.
- "Run before release" is itself a checklist item that can be forgotten. Putting it in CI fixes that but adds a dependency on having CI for this repo.
- Pulse refresh trigger is awkward: the audit runs *after* a module already shipped, so the "refresh on success" semantics are just "did the report pass? then regenerate." That's not unreasonable, but it's not coupled to anything.

### Scope of work

1. `scripts/audit_modules.py` — module-walk, doc-grep, plist-scan, report.
2. New entries in `ARCHITECTURE.md`'s SOP step 8 ("Tests") to mention `audit_modules`.
3. Optional: pre-commit hook or CI step.
4. One-time pass: run the script, file the deltas it surfaces (pulse_web at minimum).
5. Wire the post-pass refresh: `if exit_code == 0: pulse_web.py + publish_pulse`.

## Approach B — Proactive registry / scaffolder

**Shape:** A `module_registry.yaml` (or python registry module) that *declares* every ingest collector / render module with its metadata. A `rebalance scaffold-module <name>` CLI command that reads the registry, generates skeleton files (collector stub, schema fn, gatherer stub, CLI subcommand, MCP wrapper, plist if needed), and writes the doc/CHANGELOG/4X4/README/Pulse-refresh fanout in one shot. Re-runnable in update mode for existing modules.

### Pros

- Scaffolding catches the SOP at the right moment — when the module is being created, not after it has already drifted.
- Enforces a uniform metadata vocabulary (`priority`, `storage_tables`, `vectorized`, `status`, `strategic_alignment`, `user_facing`) — making the audit step trivial because the registry IS the source of truth.
- Pulse refresh trigger is natural: scaffolder finishes → register → run refresh.
- Future agents (Codex, Copilot, Claude) can read the registry as a structured handle on the module surface, reducing "what modules exist?" rediscovery.
- Forces clarity on the optional fan-out (4X4 / README) — author has to declare strategic alignment / user-facing-ness up front.

### Cons

- **Premature for current evidence.** N=1 drift incident (pulse_web) does not justify ~500–1000 lines of scaffolding/registry code. The cost-benefit is bad until the drift pattern recurs.
- Forces uniform shape on collectors that today are deliberately heterogeneous (`github_scan` vs. `note_ingester` vs. `sleuth_reminders` have different concurrency, secret stores, delta strategies). The registry abstraction has to either accommodate every dimension (becomes large) or constrain authors to a smaller shape (loses fit to source).
- Adds a step before adding a module. New ingestor friction goes up. For a project that emphasizes "keep adding sources cheap" in its 8-step SOP, that's a real cost.
- Registry stays accurate only if **every** module change updates it. So the registry itself becomes a thing that can drift, just one layer deeper. You still need an audit script (Approach A) to verify the registry matches reality.
- Risk of building the wrong abstraction. The eight existing collectors did not converge on a shape; a registry locks in a shape now and forces future modules to match it.

### Scope of work

1. Define `module_registry.yaml` schema (priority, source_name, collector_path, storage_tables, vectorized, secrets, cli_command, mcp_tool, daily_sync_step, strategic_alignment, user_facing, status).
2. Migrate the 8 existing modules into it (validate the schema fits them all).
3. `rebalance scaffold-module <name>` command — generates collector skeleton from a template.
4. `rebalance audit-modules` — verifies registry matches disk (Approach A in different clothing).
5. Doc-fanout writers: `_write_arch_entry()`, `_write_changelog_entry()`, optional `_write_4x4_alignment()`, optional `_write_readme_capability()`.
6. Pulse-refresh trigger: post-scaffold hook that runs `pulse_web.py` + `publish_pulse`.
7. Update [ARCHITECTURE.md](../../ARCHITECTURE.md) SOP to point to scaffolder instead of prose 8 steps.

## Approach C — Do nothing automated; tighten the SOP only

**Shape:** Patch [ARCHITECTURE.md](../../ARCHITECTURE.md) to add explicit checkpoints for "did you add this to the module map?", "did you write a CHANGELOG entry?", "does this need a launchd plist?" Add a release-checklist file (`docs/RELEASE-CHECKLIST.md`) with the five fan-out targets. Fix the immediate pulse_web.py drift as a one-time correction.

### Pros

- Zero new code. Lowest possible cost.
- Honest about the situation: N=1 evidence, prose SOP already exists, just needs sharper checkpoints.
- Doesn't constrain future architecture decisions.

### Cons

- Relies entirely on human (or agent) discipline. If the 8-step SOP didn't catch pulse_web, a 9-step SOP probably won't either.
- No mechanical signal when drift happens. The next stale module discovers itself the same way pulse_web did — by accident.
- 4X4 / README / Pulse-refresh fanout has no enforcement at all.

### Scope of work

1. Edit [ARCHITECTURE.md](../../ARCHITECTURE.md) SOP — add explicit "module map", "CHANGELOG", "launchd plist" checkpoints.
2. Add `docs/RELEASE-CHECKLIST.md` listing the five fan-out targets.
3. Fix the immediate pulse_web.py gap (add to ARCHITECTURE.md, schedule it, update CHANGELOG with the doc-only correction).

## Comparison

| Dimension | A (audit) | B (registry) | C (SOP only) |
|---|---|---|---|
| Lines of code | ~80 | ~600–1000 | 0 |
| Time to ship | Half day | 2–4 days | 1 hour |
| Catches existing drift | Yes | Yes (during migration) | Manual one-time |
| Catches new drift | Yes (post-hoc) | Yes (at creation) | No |
| Constrains module shape | No | Yes | No |
| Reversible cheaply | Yes | No (schema sticks) | Yes |
| Doc fanout enforcement | Advisory report | Generated writes | Manual |
| Pulse-refresh trigger | Awkward fit | Natural fit | None |
| Risk of being premature | Low | Moderate-to-high | Very low |

## Findings from Approach A prototype (2026-05-08)

A first pass at Approach A landed in [scripts/audit_modules.py](../../scripts/audit_modules.py) (~115 lines). It walks `src/rebalance/ingest/*.py` and `scripts/*.py`, and checks whether each module's filename or stem appears anywhere in [ARCHITECTURE.md](../../ARCHITECTURE.md) and [CHANGELOG.md](../../CHANGELOG.md). Building the prototype surfaced six concrete frictions that map cleanly to which approach handles them best.

| # | Friction | Genuinely favors B | Fixable in A | Notes |
|---|---|---|---|---|
| 1 | Hardcoded `IGNORED_FILES` list — every new helper must be added or audit fails noisily | No | N/A | Intrinsic to any list-based approach. B has the same shape (add to registry instead of add to ignore-list). Drift moves, doesn't disappear. |
| 2 | Plist 1:1 mapping breaks under valid piggybacking (`pulse_web.py` should ride `pulse_sync.sh`) | **Yes** | No (heuristics get gnarly fast) | Check is commented out in the prototype to avoid constant false positives. A registry's declarative `scheduler:` field handles piggybacking cleanly. |
| 3 | CHANGELOG presence ≠ recency — grep proves "mentioned at least once in history," not "documented under Unreleased" | Marginal | **Yes** (~10 LOC) | Parse the `## [Unreleased]` section specifically. Prototype is shallow, not the approach. |
| 4 | Grep false positives — searching for stem `calendar` matches the English word "calendar" in prose | **Yes** | Partially | Stricter matchers (filename-only, table-cell-only) help in A but never fully solve it. Registry sidesteps the question entirely. |
| 5 | `IGNORED_FILES` is doing implicit classification — `dashboard.py` excluded as "Poller", `pulse_web.py` included as render module. The list encodes a class taxonomy | **Yes** | No (without inventing a registry) | This is data wanting to be a field. Strong signal that *some* declarative metadata layer is needed regardless of which approach lives on top of it. |
| 6 | Presence-checking misses semantic drift — if `calendar.py` adds a new table, the audit still passes because the filename is still grep-mentioned | **Yes** | No (within A's design — checking semantic drift is not what A does) | A catches "module never documented." It does not catch "module changed, docs stale." That is a distinct problem class. |

### What the findings do and don't establish

- **Establish:** any list-based system needs a canonical metadata layer for module class (`source | render | helper`) and scheduler relationship (`own | piggyback`). Findings 2, 4, 5, 6 all converge on this. The registry's declarative posture solves them in one move; A's grep-and-suppress posture works around them piecemeal.
- **Do not establish:** that A is unsalvageable. Findings 1 and 3 are fixable or shape-intrinsic. The prototype was written deliberately shallow to surface friction; a slightly less shallow A (parsed CHANGELOG sections, stricter match patterns) closes finding 3 and reduces 4.
- **Do establish:** if the drift pattern recurs even once more after this round, the implicit-classification problem (finding 5) is the one that will keep growing — every new ignore-list entry encodes more taxonomy that should be data. That is the load-bearing argument for revisiting B.

### Suggested updates either way

Even if no further automation lands, the prototype's findings argue for two cheap moves:

1. **Document the module class taxonomy explicitly** in the [ARCHITECTURE.md](../../ARCHITECTURE.md) SOP — name the classes (`source`, `render`, `helper`) so future authors don't have to infer them from an ignore list.
2. **Add a `## [Unreleased]` discipline to CHANGELOG.md** if not already present, so any future audit (A or B) has a stable section to verify against rather than scanning the whole file.

## Open questions

1. **Has the drift pattern recurred?** Pulse_web is one. Are there others I haven't surfaced? An exploratory `find src/rebalance/ingest scripts -name '*.py' -newer ARCHITECTURE.md` would answer this and inform the cost-benefit.
2. **Is "scaffolder" the right framing for B?** A scaffolder (codegen) is heavier than a registry (declarative metadata). They could be split: declarative registry first, scaffolder later if it earns it.
3. **What's the right granularity for "module"?** `pulse_web.py` is a render module (read-only consumer of SQLite), not an ingest collector. A registry built around the 8-step *Adding a New Source* SOP may not naturally cover render modules. If yes, the registry needs at least two module classes (`source`, `render`).
4. **CI?** Approach A is most useful as a CI step. The repo doesn't appear to have CI today (only launchd jobs). Adding CI is its own decision with its own cost.
5. **Pulse refresh**: should the trigger happen on *every* successful audit/scaffold, or only on the ones that actually changed module-relevant state? The cheap answer is "every" — `pulse_web.py` regen on unchanged data is fast and idempotent. But running `publish_pulse(push=True)` produces a git commit in the private pulse repo every time, which would be noisy.

## Recommended next step

My read, presented as input rather than a decision:

**Start with Approach C, immediately, today.** It's a one-hour patch and unblocks the actual symptom (stale `web/pulse.html`). Specifically:

1. Add `web/pulse.html` and `scripts/pulse_web.py` to the [ARCHITECTURE.md](../../ARCHITECTURE.md) module map and Signal Sources commentary.
2. Decide whether `pulse_web.py` deserves its own launchd job or should piggyback on `pulse_sync.sh`. (Piggyback is probably right — same hourly cadence, same data.)
3. Patch the SOP to add a "render modules" checkpoint, since pulse_web revealed the SOP is collector-shaped.

**Then build Approach A as the next step**, only if it still feels needed after C ships. The audit script is a small commitment with reversible cost. It's where the Pulse-refresh-on-success trigger naturally fits.

**Defer Approach B until the drift pattern has recurred at least once more.** The registry/scaffolder is the correct end-state if drift becomes a frequent problem. It is not the correct starting state for a project with eight heterogeneous collectors and one render module that is missing from one document.

The mistake worth avoiding is shipping B first because it's the most "complete" answer, then discovering six months later that the abstraction it locks in doesn't fit the next module class (e.g., a streaming ingestor, or a write-back agent), and now there's a registry + a workaround for the registry. C → A → maybe-B keeps every step cheap and reversible.
