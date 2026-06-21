---
project: "P2 — Team Calendar as a Signal"
codename: HiQS
owner: Noel
created: 2026-06-09
updated: 2026-06-18
status: "Phase 2 v0.5 BUILT on `development` (shared rank_next_actions core + /whats-next route + static pulse panel + ask() parity + precompute hook; 3 commits f6a7131→795933c; 989 tests green; 30-agent adversarial review applied) — data-layer DoD proven; pending live-Gemini visual check in Noel's keyed env + merge-to-main + v0.5 tag"
current_phase: "Phase 2 — v0.5 build complete; final live-Gemini verification + merge/tag remain"
endgame: "v0.5 — 'What should we work on next?' view in the web dashboard (Gemini-powered, tunable levers)"
kill_switch: "Willing to kill if Matt's calendar is mostly redundant with GitHub + Slack"
tags: [signal-quality, calendar, team-orchestration, ab-test]
---

# P2 — Team Calendar as a Signal (HiQS)

> **Thesis (HiQS):** A teammate's shared work calendar is only worth ingesting if it
> raises *decision* quality — "what should I / the team work on next, and what's about
> to get dropped." Phase 0 is an A/B test that must **earn** Phase 1. We are willing to
> kill this if the signal is mostly redundant with GitHub + Slack.

> **Related infra (cross-link):** the `rebalance-git-pulse` repo this project
> exports to and reads from is being refactored — see
> [GIT-PULSE-REFACTOR.md](PROJECT/2-WORKING/GIT-PULSE-REFACTOR.md). That refactor
> is **intentionally gated to start only after this project's Phase 1 is merged to
> `main`** (it touches `sync_snapshot.py` / `index_ops.py` / `pulse.py` and the
> per-device export naming). No action needed here — noted so the dependency is visible.

---

## Anti-goals

Things P2 will not do:

- **Not a general team analytics or reporting platform** — the output is one ranked next-action list per session; not dashboards, burndowns, utilization tracking, or management reporting.
- **Not ingesting personal calendars** — only company-workspace timesheet calendars with explicit teammate opt-in; personal Google calendars are never a data source.
- **Not a full knowledge graph** — the Phase 3 entity_graph is a flat SQLite projection over existing tables, not an ontology-based reasoning system; scope is bounded to the relation types defined in Phase 3.
- **Not a replacement for existing signal sources** — the team calendar augments GitHub activity, Sleuth reminders, vault notes, and email; it does not replace or reduce any of them.
- **Not a prediction or ML model** — the lever-based scorer is deterministic and tunable; the system does not train on user data or fine-tune models.
- **Not a multi-tenant or off-machine system** — all data stays in local SQLite; teammate calendar data is never exported to shared infrastructure (export filter enforces default-deny).

---

## Status at a glance

| ✅ Most recently completed phase | ⏭️ What's next |
|---|---|
| **Phase 2 v0.5 BUILT on `development` (Ultra Code, 2026-06-18)** — the "What should we work on next?" feature shipped across all four surfaces, all calling ONE shared `rank_next_actions` core (the DRY parity gate): the keystone [next_actions.py](src/rebalance/ingest/next_actions.py) (productizes the Phase-0 harness blend + dedup; Gemini via the existing `_synthesize_with_fallback` adapter; never raises; deterministic ranked fallback) + migration 0006 (`ranked_next_actions` local-only precompute cache, head v6); the `/whats-next` FastAPI route (live on `rebalance serve` **and** the always-running `pulse_server`); the static `pulse.html` "what's next" panel (reads the precompute, offline launchd-safe); `ask(team=True)` MCP parity (sidecar attr, `QueryResult` untouched); and the network-allowed precompute hook in `refresh_index`. **Scope decisions (Noel):** static panel = precompute→SQLite; teammates = Matt-first with a per-person additivity gate (sparse Jose/Jinhui earn in by logging density). **One Ultra adversarial review** (30 agents → 14 verified findings + a synthesis-prompt judge panel) applied — incl. the HIGH fix where a degenerate Gemini parse could overwrite the good deterministic fallback. **989 tests green** (+71 over Phase 1), `rebalance doctor` clean. **Data-layer DoD proven**: blended rank surfaces 7 net-new person-attributed teammate items the operator-only list lacks. 3 commits `f6a7131`→`34e60da`→`795933c` on `development`. | **Final v0.5 close-out:** (1) Noel opens `/whats-next?refresh` (or runs a full `refresh_index`) in his **keyed** env to render the live Gemini-synthesized list — the visual DoD that can't run in the sandbox (no GSM key there); (2) merge `development` → `main` via self-mergeable PR + tag **v0.5**. The `rebalance-git-pulse` refactor ([GIT-PULSE-REFACTOR.md](PROJECT/2-WORKING/GIT-PULSE-REFACTOR.md)) remains unblocked. |

---

## Table of Contents

- [Goal & the two outputs](#goal--the-two-outputs)
- [Endgame — the v0.5 functional tool](#endgame--the-v05-functional-tool)
- [Decisions](#decisions)
- [What already exists (don't rebuild)](#what-already-exists-dont-rebuild)
- [Phase 0 — Spike + A/B test (the decision gate)](#phase-0--spike--ab-test-the-decision-gate)
- [Phase 1 — Productize the second calendar (only if Phase 0 passes)](#phase-1--productize-the-second-calendar-only-if-phase-0-passes)
- [Phase 2 — v0.5: "What should we work on next" dashboard + N teammates](#phase-2--v05-what-should-we-work-on-next-dashboard--n-teammates)
- [HiQS ethos: privacy, consent, leak-control](#hiqs-ethos-privacy-consent-leak-control)
- [Phase 0 — captured A/B bundles (raw results)](#phase-0--captured-ab-bundles-raw-results)
- [Phase 0 progress log](#phase-0-progress-log)
- [Phase 3 — entity_graph attribution layer (deferred)](#phase-3--entity_graph-attribution-layer-v06-deferred)
- [Prior art & reuse (3-source deep research)](#prior-art--reuse-3-source-deep-research-2026-06-12)
- [Sleuth outcome log — dropped-ball label oracle (cross-project)](#sleuth-outcome-log--dropped-ball-label-oracle-cross-project)

---

## Goal & the two outputs

Blend a developer's shared Google calendar (**"Matt - Neochrome Work Schedule"**) into the
existing signal set (own calendar, GitHub activity, Slack/Sleuth reminders, vault, email)
to power two distinct recommendations:

- **A — individual:** *"What should **I** work on next?"* — Noel's signals only (control).
- **B — combined:** *"What should the **team** work on next?"* — Noel's signals **+** Matt's calendar (treatment).

These are **not** the same question with the same answer, so the spike tracks two hypotheses:

- **H1 (individual lift):** Matt's calendar improves *Noel's own* next-action — e.g. Matt is blocked on something Noel owns (→ unblock), or Matt already shipped X (→ Noel skips it).
- **H2 (team orchestration):** The combined signal enables a *team-level* "who does what next" that didn't exist before.

The real success criterion across both: **don't drop the ball** — surface an actionable item
that the operator's own signals would have missed.

### Cohort (defined 2026-06-12)

| Person | Role | Calendar | Data richness | Enters at |
|---|---|---|---|---|
| **Noel** | Company owner (operator) | `primary` | Rich | Baseline — Arm A |
| **Matthew** | Lead developer | "Matt - Neochrome Work Schedule" (shared) | **Rich** — long-standing timesheet habit | **Phase 0/1 subject** |
| **Jose** | Developer | shared timesheet calendar | **Sparse** — only recently started logging | Phase 2 |
| **Jinhui** | Teammate | shared timesheet calendar | **Sparse** — only recently started logging | Phase 2 |

Jose's and Jinhui's calendars aren't rich enough to test yet — Phase 0/1 stay Matt-only
(decision #4). Phase 2 onboards them once their logging is consistent, each behind explicit
opt-in **and** a cheap per-person mini additivity check, so a still-mostly-empty calendar
doesn't dilute the blend.

---

## Endgame — the v0.5 functional tool

P2 must conclude as a **working tool, not an exercise** (decision #6). Most of the v0.5
surface already exists:

| Layer | Exists today | v0.5 gap |
|---|---|---|
| Web dashboard | **Yes** — FastAPI app in [src/rebalance/web.py](src/rebalance/web.py) (`rebalance serve`, port 8787: `/focus-5`, `/auth-log`, `/sleuth-graph`) + the launchd-regenerated static [web/pulse.html](scripts/pulse_web.py) served by [scripts/pulse_server.py](scripts/pulse_server.py) | No "what should we work on next" view yet |
| Next-action engine | **Partial** — the `ask()` MCP tool ([retrieval.py](src/rebalance/mcp/tools/retrieval.py)) gathers vault/GitHub/registry context; the Phase-0 harness ranks next actions per day | `ask()` is retrieval-first, not a ranked recommender; the harness is throwaway |
| Inference LLM | **Partial** — `ask()` synthesizes via local Qwen3-0.6B ([querier.py](src/rebalance/ingest/querier.py)); [repair.py](src/rebalance/repair.py) already calls `gemini-3.1-flash-lite` | Standardize P2 inference on **Gemini** (decision #5), GSM-keyed |

**v0.5 =** the Phase-1 blended data layer + a Gemini-synthesized, ranked, person-attributed
**"What should we work on next?"** view in the web dashboard (route in `web.py` + panel in
`pulse.html`), with `ask` parity for agents. Phase 0 proves the signal earns it; Phase 1
builds the data layer; **Phase 2 ships v0.5.**

### Tunable levers (v0.5 — decided 2026-06-12)

The blend is **not** a black box. v0.5 ships a `signal_weights` config so the operator can
fine-tune what the "what should we work on next" view surfaces, with defaults **seeded from the
Phase-0 spike** (the spike's implicit decision rule becomes the default lever settings). This is
the "pattern library / model with levers" idea made concrete.

| Lever | What it controls | Phase-0 seed / default |
|---|---|---|
| **Per-person weight** | Trust on each teammate's calendar | Matt = 1.0 (rich); Jose/Jinhui start low (sparse) and earn weight via their per-person additivity check |
| **Per-source weight** | Calendar vs GitHub vs Sleuth vs email | Tunable; calendar earned its place for *team* operational signal |
| **Redundancy penalty** | How hard to suppress a teammate item already echoed in the operator's own data | The *additivity* knob; the content de-dup is its hard floor |
| **Vagueness discount** | Down-weight "Slack&Emails"/"Cron research"; up-weight named PR/issue/incident/email actions | The judge-calibration rule, as a threshold |
| **Owner-bias correction** | Up-weight team *operational/client* work because the operator's own GitHub stream is skewed toward his *own tooling/system* work (Noel's disclosure, 2026-06-12) | **Default ON** — see the Phase-0 exit-artifact note |
| **Drop sensitivity** | How aggressively to flag blocked/stale *delegated* work ("about to be dropped") | The NMI-vault blocker catch (06-11) is the canonical hit. Ground-truth labels: [Sleuth outcome log](#sleuth-outcome-log--dropped-ball-label-oracle-cross-project) |

The decision rule the spike validated — *"prefer the teammate signal when it's not already in my
own data, and especially when my own stream structurally can't see it"* — is the default tuning,
exposed as levers rather than hardcoded.

---

## Decisions

*#1–4 locked 2026-06-09; #5–6 added and #2/#4 amended 2026-06-12 — every post-data-exposure change is logged with its bias direction in [0f](#0f-amendments-after-first-data-exposure).*

| # | Decision | Choice |
|---|---|---|
| 1 | **Phase 0 kill/continue bar** *(thresholds set by Claude per Noel's delegation — see [0e](#0e-decision-rule-kill--continue))* | Continue to Phase 1 only if **all three**: (a) net-new signal rate **≥20%** (median scored day); (b) **≥1 Noel-confirmed dropped-ball catch** AND B-only **precision ≥50%**; (c) blinded preference favors B on **≥3 of 5 days for *both* judges independently** (Noel AND the LLM judge), no-preference days counting against B. |
| 2 | **Judges** | **Noel + an LLM judge (Gemini — decision #5)** vote independently on each blinded pair. *(Amended 2026-06-12: judge model fixed to Gemini, replacing "local Qwen and/or Claude" — locked before any vote; see [0f](#0f-amendments-after-first-data-exposure).)* |
| 3 | **Privacy / export** | **Policy:** teammate calendar data is **never exported** to the pulse git repo — `export_calendar_snapshot` filters `WHERE calendar_id = 'primary'` (default deny). **✅ IMPLEMENTED (2026-06-12):** the live `export_calendar_snapshot` ([sync_snapshot.py](src/rebalance/ingest/sync_snapshot.py) — `WHERE calendar_id = 'primary' AND start_time >= ?`) enforces the filter; covered by `tests/test_sync_snapshot.py` and `tests/test_pulse_calendar_scope.py`. **History (audit trail):** initially discovered un-filtered — the Phase-0 sync's 155 Matt rows had already been exported + pushed to the **PRIVATE** `rebalance-git-pulse` repo (verified private → a policy violation, not a public exposure). The filter was added as a blocking Phase-1 task and is now enforced across pulse/export/reader paths. |
| 4 | **Phase 1 scope** | **Matt only** — a single second calendar, not a full N-person list. Phase 2 generalizes to the rest of the [cohort](#cohort-defined-2026-06-12) (**Jose, Jinhui**) once their newer logging habit produces rich-enough data. |
| 5 | **Analysis/inference LLM** *(2026-06-12)* | **Gemini** (cloud) for all P2 analysis & inference — the Phase-0 LLM judge and the v0.5 dashboard synthesis. API key lives in **Google Secret Manager**, fetched via the gcloud CLI (same pattern as the existing `ltvera-gemini-api-key` secret); [repair.py](src/rebalance/repair.py) already calls `gemini-3.1-flash-lite`. Local Qwen stays embeddings/RAG-only. **✅ IMPLEMENTED:** `get_gemini_api_key()` ([config.py](src/rebalance/ingest/config.py)) resolves the key Python-SDK → `GEMINI_API_KEY`/`GOOGLE_API_KEY` env → `gcloud secrets versions access` (the documented CLI pattern, last resort), so the key resolves whether or not the optional GCP Python package is installed. |
| 6 | **Endgame** *(2026-06-12)* | P2 concludes as a **functional tool, not an exercise**: a v0.5 **"What should we work on next?"** view in the existing web dashboard — see [Endgame](#endgame--the-v05-functional-tool). |

---

## What already exists (don't rebuild)

The calendar source is already a first-class, registry-driven `Collector`. Most of the plumbing is in place:

| Capability | Where | Notes |
|---|---|---|
| Calendar collector | [src/rebalance/ingest/calendar.py](src/rebalance/ingest/calendar.py) `sync_calendar(calendar_id=...)` | **Already takes a `calendar_id` arg** — can fetch any calendar shared into Noel's account |
| Storage | `calendar_events` table | **Already has a `calendar_id` column** (`NOT NULL DEFAULT 'primary'`) written on every insert |
| Refresh orchestration | [src/rebalance/ingest/index_ops.py](src/rebalance/ingest/index_ops.py) `_refresh_calendar` | Loads `CalendarConfig.load()` and syncs **one** `config.calendar_id` |
| Per-user config | [src/rebalance/ingest/calendar_config.py](src/rebalance/ingest/calendar_config.py) | Single `calendar_id` (default `"primary"`); gitignored `temp/calendar_config.json` |
| Read side | `calendar.py::get_recent_events / get_daily_totals`, querier `_gather_calendar_context()` | No person attribution yet — events are anonymous |
| Auth | existing OAuth token (keyring + pickle) | **No new auth needed** — Matt's calendar is already shared into Noel's account (visible under *My calendars*) |

**Gaps to close (Phase 1, not Phase 0):**

1. **PK collision.** `calendar_events` PK is `id` (Google event ID) alone. A shared invite on
   both calendars has the *same* event ID → overwrites + flips `calendar_id`. Needs composite
   PK `(id, calendar_id)`. **Phase 0 data integrity note — RESOLVED 2026-06-12:** repair ran
   (`temp/phase0_repair_and_shared.py`: Matt re-synced first for his post-hoc timesheet edits
   → 155 fresh rows through 06-13, then `primary` re-synced to restore flips). Outcome: only
   **1 true ID collision** existed — Matt's "Team Call" / "Joyce/Noel" entries are his own
   hand-logged blocks with *different* event IDs, so the real duplication risk is content-level,
   handled by the harness's normalized-title de-dup (see 0b). PK fix still required for Phase 1.
2. **No person attribution.** No `owner`/`person` column → can't say "this is Matt's block, not mine."
3. **Single-calendar config.** `CalendarConfig.calendar_id` is one string; needs a team list.
4. **Leak surface — OPEN, not yet closed (corrected 2026-06-12).** `export_calendar_snapshot` ([sync_snapshot.py:99-107](src/rebalance/ingest/sync_snapshot.py#L99-L107)) currently exports **all** `calendar_events` rows (no `calendar_id` filter), and `_refresh_sync` ([index_ops.py:1175](src/rebalance/ingest/index_ops.py#L1175)) git-pushes them to the pulse repo. Matt's Phase-0 rows have already been pushed there. **The pulse target repo `Hypercart-Dev-Tools/rebalance-git-pulse` is PRIVATE** (verified 2026-06-12 via `gh repo view`) — so this is **not a public exposure**; future sessions should not flag it as one. Closing the leak = implement the `WHERE calendar_id='primary'` export filter (Phase 1) + segregate the dashboard readers (gap #5 below).
5. **Reader contamination (discovered 2026-06-12).** `get_upcoming_events` / `get_recent_events` / `get_daily_totals` ([calendar.py:360-475](src/rebalance/ingest/calendar.py#L360-L475)) and `querier._gather_calendar_context` read `calendar_events` with **no `calendar_id` filter**, so Matt's rows are currently mixed into Noel's *own* dashboard / `ask` / pulse views and double-counted in daily totals. Phase 1 read-side work must filter/segregate by `calendar_id`.

---

## Phase 0 — Spike + A/B test (the decision gate)

**Time box: 1–2h. Output: a go/no-go with numbers. No schema changes, no productization.**
Everything here is read-only, local, and uses `sync_calendar(calendar_id=<matt>)` directly —
**no migrations, no config changes, no commits to the source tree.**

### 0a. Access validation
- [x] List calendars on the existing token; resolve the `calendarId` for **"Matt - Neochrome Work Schedule"** → `c_dih7iped3im5sescansv8uqab8@group.calendar.google.com`.
- [x] One bounded read: `sync_calendar(calendar_id=<matt id>, days_back=14, days_forward=2)` into the live `calendar_events` table → **122 events stored**, `calendar_id`-tagged. Reversible (`DELETE WHERE calendar_id=<matt>`). Script: [temp/phase0_sync_matt.py](temp/phase0_sync_matt.py).
- [x] Confirm we now have both `primary` (584) and `<matt>` (122) rows for the same days.

### 0b. Build the A/B harness — [temp/ab_team_signal.py](temp/ab_team_signal.py)
A throwaway script (gitignored) that, for each test day, emits two ranked next-action bundles.
- [x] **Arm A core** — primary calendar wired into the bundle (tz-correct local-day bucketing).
- [x] **Arm B** — adds Matt's blocks (`calendar_id=<matt>`) on top of Arm A, framed as a teammate's in-flight/blocked work ("what should the team work on next?").
- [x] **Arm A — complete the signal set:** Sleuth reminders, Obsidian vault notes, and email now in Arm A — pulled via `pulse._query_day_activity()` (the dashboard's own assembler) + a per-day `email_messages` query. *(Note: "vault todos" = recently-modified vault notes; there is no checkbox/task table — true todo parsing is a separate future enhancement.)*
- [x] **Arm A — denoise:** Git Pulse Sync excluded — `rebalance-git-pulse` never reaches `github_commits` (the dashboard source), plus an explicit `NOISE_REPOS` guard.
- [x] **Reconcile GitHub activity — ROOT CAUSE FOUND & FIXED:** the old harness read `github_activity`, a *scan-snapshot* table that buckets a rolling ~30-day fetch under `scan_date = scanned_at[:10]` (the **scan-run date, in UTC**) and includes bot repos. The dashboard reads granular `github_commits/items/comments` with a tz-aware day window + author/bot filter. Harness now uses the dashboard path → matches.
- [x] **Blind + randomize (done 2026-06-12):** harness now writes one self-contained blinded file per day to `temp/ab_blinded/<date>.md` — "OPTION 1 / OPTION 2" in randomized order, neutral headers (`[OWN]` / `[TEAMMATE]`, no control/treatment wording). Mapping sealed in `temp/ab_blinded/.ab_key.json`, never printed; reveal only after both judges lock votes.
- [x] **De-duplicate shared events from Arm B delta (done 2026-06-12):** implemented as **content-based** de-dup, not just ID-based — the repair revealed only 1 true ID collision; Matt hand-logs joint meetings ("1:45 - Team Call", "Weekly - Joyce/Noel") as his *own* events with different IDs. Harness suppresses a teammate block when its normalized title matches a primary block the same local day, OR its ID is in `temp/ab_blinded/shared_event_ids.json`. Suppression counts recorded in the key file (not in the bundle, to keep it clean for judging).

### 0c. Test window
- [x] Bundles generated for the 2 example days captured this week (**06-08, 06-09**) + **06-10**. *(Superseded by the repaired, blinded regeneration below.)*
- [x] **Repair (done 2026-06-12):** `temp/phase0_repair_and_shared.py` — Matt re-synced first (fresh post-hoc timesheet edits), then `primary` (restores any flips); shared-ID set computed. Verified: all "Team Call" / "Joyce/Noel" rows 06-05..06-11 live under `primary`.
- [x] **Regenerated from the repaired table (done 2026-06-12):** all bundles re-rendered blinded + de-duped.
- [x] **Full 5-day window:** blinded bundles for **06-05, 06-08, 06-09, 06-10, 06-11** (5 completed days) in `temp/ab_blinded/`. Small N is fine for a spike — we want signal, not significance.

### 0d. Pre-registered measurement (define BEFORE looking — HiQS honesty)
Three metrics, recorded per day:

1. **Net-new signal rate** *(additivity vs. redundancy)* — % of Matt's work-blocks that (i) map to a **shared project/repo** (Binoid, bloomz, GoAffPro, …) **and** (ii) have **no corresponding signal** in Noel's own data that day. High % → additive; low % → Matt's calendar just re-states what GitHub/Slack already show.
2. **Dropped-ball catches** *(the core value)* — count of actionable items Arm B surfaces that Arm A misses **and** that Noel confirms are real (true positives), with **precision** = true positives ÷ all B-only items Noel reviews (false positives counted, so B can't win by flooding).
3. **Blind preference** — Noel picks the more-useful list per day; an **LLM judge** (**Gemini**, decision #5) gives an independent second vote on the same blinded pair.

### 0e. Decision rule (kill / continue)
**Thresholds set by Claude per Noel's delegation (2026-06-09).** N≈5 days can't yield statistical
significance, so the "gold standard" here is a *pre-registered, blinded, two-judge, conjunctive* rule —
a chance win on any single metric can't pass the gate. Proceed to Phase 1 **only if all three** clear:

1. **Additivity** — net-new signal rate **≥ 20%** (median scored day). Below this, Matt's calendar mostly restates GitHub/Slack.
2. **Decision value** — **≥ 1 Noel-confirmed dropped-ball catch** over the window, **and** B-only **precision ≥ 50%** (confirmed catches ÷ all B-only items Noel reviews) — so B earns the catch without flooding.
3. **Preference** — blinded preference favors **B on ≥ 3 of 5 days for *both* judges independently** (Noel *and* the LLM judge each clear 3/5); no-preference days count against B. Two independent majorities is the small-N guard — one judge at 3/5 is a coin-flip under the null. **LLM judge calibration:** the judge prompt must explicitly instruct the model to *discount vague time-blocks* ("Slack&Emails", "Cron research") and *heavily weight verifiable, targeted actions* ("Review Binoid PR 860", "Email re WPE DB op") — otherwise the judge may falsely prefer Arm B simply because it has more text. **Blind-softness caveat (2026-06-12):** Arm B is a strict superset of Arm A, so Noel can identify the arms by *content* — any item he doesn't recognize from his own signals is, by definition, B-only — no matter how the labels are randomized. Noel's preference vote is therefore structurally **soft** evidence; the relabeling still fully blinds the **LLM judge**, and the gate's hard weight rests on criteria 1–2 (net-new rate, precision + confirmed catch).

Otherwise **stop** and record why — a teammate calendar ~90% redundant with GitHub + Slack is *not* a
high-quality signal and isn't worth the privacy + maintenance cost. Either outcome is a successful spike.

- [x] **Test-window timing:** all 5 scored days (06-05, 06-08..06-11) were *completed* days at generation time (generated 06-12) — activity arms fully populated.
- [x] **LLM judge voted (2026-06-12):** Gemini scored all 5 blinded bundles; votes **sealed** in `temp/ab_blinded/votes_gemini.json` (model recorded per vote: `gemini-3.1-flash-lite` — the `-pro`/`-flash` variants were unavailable on this key). Not opened; Noel votes independently before any reveal.
- [x] **Noel voted (2026-06-12)** on the 5 blinded bundles via interactive coach walkthrough (coach stayed neutral, flagged slot position each day) — ballot in `temp/ab_blinded/votes_noel.json`.
- [x] **Reveal + score (2026-06-12):** mapped both judges' votes to arms; confirmed 5/5 catches with Noel; scored all three criteria. See exit artifact below.
- [x] **Phase 0 exit artifact:** findings table (3 metrics × 5 days) + **GO** appended to the [progress log](#phase-0-progress-log); machine-readable copy in `temp/ab_blinded/scoring.json`.

### 0f. Amendments after first data exposure

**🔒 LOCKED 2026-06-12 (before any vote was cast). No further metric changes.**

*(Logged 2026-06-12 — HiQS honesty.)* The 0d metrics were pre-registered 2026-06-09, but the
06-08/09/10 bundles were generated and eyeballed before the rules below were finalized. To keep
"pre-registered" honest, every post-exposure rule change is logged here with its bias direction.
**This log locks before any vote is cast; no further metric changes once scoring starts.**

| Amendment | Rationale | Bias direction |
|---|---|---|
| De-dup shared events from the B-only delta ([0b](#0b-build-the-ab-harness--tempab_team_signalpy)) | Shared invites are already in Arm A; counting them inflates B's net-new rate | **Against B** |
| LLM-judge calibration prompt ([0e](#0e-decision-rule-kill--continue) #3) | Stops the judge preferring B merely for having more text | **Against B** |
| Blind mechanics: `.ab_key.json`, no console print ([0b](#0b-build-the-ab-harness--tempab_team_signalpy)) | Label leakage broke the blind for Noel | Neutral (integrity) |
| Blind-softness caveat: Noel's vote downgraded to soft evidence ([0e](#0e-decision-rule-kill--continue) #3) | Superset arms are content-identifiable; be honest about what the blind can do | **Against B** (hard weight shifts to criteria 1–2) |
| Judge model fixed: **Gemini** replaces "local Qwen and/or Claude" (decisions #2/#5) | One named judge model, GSM-keyed; no post-hoc judge shopping | Neutral (locked pre-vote) |
| Repair + regenerate the 06-08/09/10 bundles ([0c](#0c-test-window)) | The 0a sync's PK-flip may have corrupted Arm A in the captured bundles | **For A** (restores A's full signal) |

Net effect: every metric-affecting amendment either tightens the gate against B or repairs Arm A's
data — nothing here makes a pass easier. A pass after these amendments is *more* credible, not less.

### QA Checklist — Phase 0 *(completed 2026-06-12)*
<!-- phase-qa -->
> Phase 0 was a throwaway spike — all scripts lived in gitignored `temp/`; no production `src/` code was committed. SOLID/DRY/observability items are N/A. Litmus tests check spike integrity instead.
- [x] DRY: N/A — no production source files committed (all work in gitignored `temp/`)
- [x] S (Single Responsibility): N/A — throwaway spike, not in the production source tree
- [x] O (Open/Closed): N/A — throwaway spike
- [x] L (Liskov): N/A — throwaway spike
- [x] I (Interface Segregation): N/A — throwaway spike
- [x] D (Dependency Inversion): N/A — throwaway spike
- [x] Observability: N/A — throwaway spike; no failure boundaries in production
- [x] Spike integrity: harness rebuilt on the dashboard's own `pulse._query_day_activity()` path after GitHub mismatch root-caused (0b) — not a custom one-off query
- [x] Gate pre-registration: 0f amendments log locked before any vote was cast; no post-scoring rule changes
- [x] Blind integrity: judge votes sealed in `votes_gemini.json` + `votes_noel.json` before reveal; `.ab_key.json` never printed during scoring
- [x] De-dup correctness: shared events de-duped content-based (normalized title + same local day) after finding only 1 true ID collision
- [x] Scope: no deliverable in this phase crosses into anti-goals
- [x] Deployment: N/A — phase completes locally, ships no remote artifact (asked, confirmed)

---

## Standing design constraints (Phase 1 onward)

> Phase 0 is throwaway. From Phase 1 onward, **all calendar-related production code must pass
> these gates before shipping.** Prior refactors in this codebase were caused by non-compliant
> foundations — do not build on a house of cards.

- **SOLID:** Single responsibility — calendar sync, read, person-attribution, and export are
  distinct concerns kept in separate, composable functions. No function does two of these.
- **DRY:** No query logic repeated across `_gather_calendar_context`, `get_recent_events`,
  `get_daily_totals`, and the harness helpers. Extract shared helpers; callers use them.
- **Gate:** Run `/phase-qa` before marking any production phase complete. SOLID+DRY compliance
  is a *high-priority* check, not a nice-to-have.

### Execution modes — Ultra Code vs Sonnet High (decided 2026-06-12)

Rule of thumb: **build sequential/stateful things single-agent at high effort; fan out
(Ultra Code sub-agents) only when surfaces are independent (build) or adversarial review
is the goal (verify).**

| Work | Mode | Why |
|---|---|---|
| **Phase 0 remainder** (votes, reveal, scoring, exit artifact) | **Sonnet High — single agent** | Sequential, stateful bookkeeping over a live DB and *sealed* judge files; extra agent contexts only add blind-integrity risk, not quality. |
| **Phase 1 implementation** (migration, config, refresh, read side, Gemini wiring) | **Sonnet High — single agent** | A numbered schema migration is inherently sequential; small diff surface; correctness over breadth. |
| **Phase 1 pre-merge review** | **Ultra Code (sub-agents)** | The export filter is the privacy-critical seam — adversarial multi-agent review (`/code-review ultra` + security pass over `export_calendar_snapshot` and the migration) before ship. |
| **Phase 2 v0.5 build-out** (web.py route, pulse.html panel, `ask` parity, synthesis prompt) | **Ultra Code (sub-agents)** | Four largely independent surfaces — parallel implementation in isolated worktrees, plus a judge panel on the Gemini synthesis prompt; fan-out buys real wall-clock and quality here. |
| **Phase 2 integration + polish + v0.5 tag** | **Sonnet High — single agent** | Single-context integration of the parallel pieces; one final Ultra review pass before tagging v0.5. |

---

## Phase 1 — Productize the second calendar (only if Phase 0 passes)

Keep it one `Collector` — no new dispatch branches (registry stays clean). **Matt only** (decision #4):
a single second calendar, modeled so the Phase-2 jump to N people is config, not a refactor.

- [x] **Export leak closed (c3a2bb7, decision #3 / gap #4):** `export_calendar_snapshot` now filters `WHERE calendar_id = 'primary'` (default deny) + regression test. Teammate rows never reach the pulse repo.
- [x] **Reader contamination fixed (c3a2bb7 + 04b5939, gap #5):** `calendar_id`-scoped (default `'primary'`, `None` = all) via a shared `_calendar_id_filter` helper in `get_upcoming_events` / `get_recent_events` / `get_daily_totals`, plus `querier` vacation check, `pulse._query_calendar_upcoming`, **and the review-found `scripts/dashboard.py` (TUI + web/pulse.html) + `scripts/spike_morning_brief.py`** readers. Reader-scope + off-machine + no-contamination tests added.
- [x] **Phase-0 Matt rows deleted (2026-06-12):** `DELETE WHERE calendar_id='<matt>'` — table primary-only (611). Phase 1 re-syncs cleanly behind the filters.
- [x] **Schema migration 0005 — DONE & applied to live DB (04b5939):** composite PK `(id, calendar_id)` + `person TEXT` + index `(calendar_id, start_time)`. First table-rebuild in the repo; made **atomic** after the adversarial review found a non-atomic re-run could destroy all calendar data. *Originally* via self-wrapped `BEGIN/COMMIT`; **hardened 2026-06-13 (review finding F)** so the **`migrate.py` runner owns the transaction** and rolls back on error — `0005` no longer self-wraps, and bare future migrations are atomic too (migrations README updated). Applied to live DB: v4→v5, 611 rows preserved, integrity ok. Backup at `rebalance.db.pre-0005.bak`.
- [x] **Canonicalize "own calendar = `primary`" (review finding #4 — 6588c8a; refined 2026-06-13 — F1):** `_refresh_calendar` in `index_ops.py` always passes `calendar_id="primary"` for the operator sync, and `refresh_calendar_source()` canonicalises the operator's **default** calendar to `'primary'`. **F1 refinement:** an *explicit* `calendar-sync --calendar-id <id>` is now synced **verbatim** (it was being silently rewritten to `'primary'`); only the no-override operator default canonicalises. `config.calendar_id` is therefore a vestigial/compat field (see its field note in [calendar_config.py](src/rebalance/ingest/calendar_config.py)). All DB filters remain correct.
- [x] **Config (6588c8a):** `TeamCalendarEntry` dataclass + `team_calendars: list[TeamCalendarEntry]` added to [calendar_config.py](src/rebalance/ingest/calendar_config.py) with `field(default_factory=list)` (no positional-arg breakage). `temp/calendar_config.json` populated with matthew, jose, jinhui (gitignored).
- [x] **Refresh (6588c8a):** `_refresh_calendar` syncs `primary` (operator, `person=None`) + each `team_calendars` entry (`person=<label>`); structured INFO log lines per sync; result envelope includes `team_calendars: [{person, calendar_id, events_fetched, events_stored}]`.
- [x] **Pulse repo privacy confirmed (2026-06-12):** `Hypercart-Dev-Tools/rebalance-git-pulse` is **PRIVATE** (`gh repo view`). The gating concern (decision #3) is satisfied for visibility; the code-level export filter above is still required (default deny).
- [x] **Person attribution (6588c8a):** `sync_calendar(person=...)` writes the `person` column — operator rows get `NULL` (self-convention), teammate rows get their label. Composite PK `(id, calendar_id)` (migration 0005) keeps both coexisting.
- [x] **Read side — privacy:** `_gather_calendar_context()` already defaults all readers to `calendar_id="primary"` (implemented in c3a2bb7); teammate rows are stored and attributed but not yet blended into the synthesis prompt (Phase 2 work). The `person` column is the first edge for Phase 3 `entity_graph`.
- [x] **Inference path (decision #5 — 6588c8a):** `querier.ask()` now tries `_synthesize_gemini()` first (key via `get_gemini_api_key()` → GSM/env, never logged); falls back to local Qwen if key absent or call fails. Same REST pattern as [repair.py](src/rebalance/repair.py).
- [x] **Observability/tests (6588c8a):** 12 new tests (878 total) — `TeamCalendarEntry` load/save/edge cases, person attribution (operator=NULL, teammate=label, composite PK coexistence). Structured INFO log lines per sync in `_refresh_calendar`.
- [x] **SOLID + DRY gate** (see [standing constraints](#standing-design-constraints-phase-1-onward)): `/phase-qa` run 2026-06-17 (50468f7) — checklist below filled in; all SOLID items resolved or noted, observability item closed in code. The DRY note (querier inline `'primary'` SQL) was closed by **F1 (0.40.1)** — all six calendar-scope filter sites now use `OPERATOR_CALENDAR_ID`. One non-blocking note remains (`_refresh_calendar` result-dict construction).

### Phase 1 hardening — review outcomes (2026-06-13)

Two independent review passes on `development` after Phase 1; **every finding fixed with a regression test**, shipped as **0.40.0** (916 tests green).

- **Local max-effort review — findings A–G** (`e9e8e3b`…`f0b53be`):
  - **A** — `calendar-sync` crashed on pre-0005 DBs → `sync_calendar` (the only writer of `calendar_events`) now runs `run_migrations` at the write chokepoint.
  - **B** — one inaccessible teammate calendar aborted the whole calendar refresh → per-calendar `try/except` isolates failures (mirrors the GitHub loop).
  - **C** — operator reports/timesheet/inference came up empty under a non-`'primary'` config → `get_day_data`/`note_builder`/`project_inference` filter the canonical `OPERATOR_CALENDAR_ID`.
  - **D** — a `team_calendars` entry with `calendar_id: "primary"` leaked teammate data off-machine → rejected at config load.
  - **E** — Gemini synthesis crashed on MAX_TOKENS/SAFETY responses → defensive parse (clear error + partial-text return).
  - **F** — migration atomicity depended on each `.sql` self-wrapping → the **runner now owns the transaction**; 0005 de-wrapped; README rule added.
  - **G** — collectors ran against a half-migrated schema on migration failure → `refresh_index` gates collectors behind the migration result.
- **External review (`PROJECT/RELAY/f0b53be-REVIEW.md`) — findings F1–F4** (`88cdb73`…`99448cc`):
  - **F1** — `calendar-sync --calendar-id` was silently rewritten to `'primary'` → explicit ids synced verbatim; `config.calendar_id` documented as vestigial.
  - **F2** — version metadata stale/inconsistent → `pyproject`/`__init__` reconciled + **0.40.0** changelog entry.
  - **F3** — Gemini key resolver didn't match the locked gcloud design → added a `gcloud secrets versions access` fallback (env still short-circuits).
  - **F4** — stale "NOT YET IMPLEMENTED" privacy language → decisions #3/#5 marked implemented, leak history preserved for the audit trail.
- **DONE (2026-06-17):** merged `development` → `main` and pushed (`aa362cb`, 0.40.2). `/phase-qa` gate (50468f7), scoped privacy-seam QA + cross-model consult, F1 literal unification (0.40.1), and `person`-omission regression tests (0.40.2) all landed — see below. Phase 1 fully closed.

### Phase 1 hardening — privacy-seam QA + cross-model consult (2026-06-17, 0.40.1)

A scoped adversarial review of the **privacy-critical seam** — `export_calendar_snapshot`
+ migration `0005` — chosen over a full 3rd-pass cloud ultrareview per the "don't re-review
already-tested code" rule (the seam already cleared two passes + 916 tests). Local QA, then a
two-model **`/consult`** (Codex + Gemini, repo-isolated worktree). All three reads converged:

- **Q1 (leak path): PASS.** No teammate row or `person` label survives either export path
  (`sync_snapshot` export filter + `_CALENDAR_COLUMNS` omits `person`; `pulse` render is
  `primary`-only **and** minimized to `summary`/`location`, never `attendees_json`/`description`).
  Both models tried concrete leak scenarios; both blocked.
- **Q2 (data loss in 0005): PASS.** Rebuild is atomic (runner-owned transaction + rollback;
  SQLite DDL is transactional). No table has a FK referencing `calendar_events`, so the
  `foreign_keys=ON` rebuild hazard does not apply; column-explicit `INSERT` prevents drift;
  PK widening cannot lose rows.
- **Only finding — F1 (LOW, fixed in 0.40.1):** the operator-only scope was a hardcoded
  `'primary'` literal at **six** sites instead of the existing `OPERATOR_CALENDAR_ID` constant.
  Severity was **fail-closed** (divergence drops operator data, never leaks teammate data), not a
  blocker. Unified to the constant across `sync_snapshot.py`, `pulse.py`, `querier.py`,
  `index_ops.py`, `scripts/dashboard.py`, `scripts/spike_morning_brief.py`.
  - **Revert decision (Noel, 2026-06-17):** unify all six **but** keep a recorded revert path —
    the `pulse._query_calendar_upcoming` site previously carried an explicit
    *"keep this a constant literal; do not parameterize to a wider scope"* defense-in-depth guard,
    intentionally overridden here for single-source-of-truth. Each touched site carries an inline
    `REVERT PATH` comment, and the CHANGELOG `[0.40.1]` entry records it. **To revert:** inline the
    literal `'primary'` at the site(s) again (and restore the pulse guard comment) if
    defense-in-depth is ever preferred over DRY.
- Raw consult transcripts: `relay-system/2026-06-17/privacy-seam-192658/` (Codex + Gemini).
- **Test hardening (0.40.2):** a re-run of the consult hand-off re-confirmed the seam at HEAD
  (`041d63d`) — all 6 sites `OPERATOR_CALENDAR_ID`-bound, `person` omitted — and added explicit
  `person`-label-omission regression tests to **both** export paths
  (`test_sync_snapshot.test_person_label_never_exported`,
  `test_pulse_calendar_scope.test_person_label_never_in_upcoming`), locking the invariant that
  the teammate label never leaves the machine. Suite 916 → **918**.

### QA Checklist — Phase 1 *(completed 2026-06-12, hardened 2026-06-13, shipped as 0.40.0; F1 nit closed in 0.40.1)*
<!-- phase-qa -->
- [x] DRY: Clean — `_calendar_id_filter` helper (`calendar.py:386`) used consistently by all three reader functions. **Closed (F1, 0.40.1):** the inline `WHERE calendar_id = 'primary'` raw SQL in `querier._gather_temporal_context` (and five sibling sites) now binds the `OPERATOR_CALENDAR_ID` constant instead of duplicating the literal — single source of truth for the operator-only scope across export, pulse render, querier, operator write, and the two `scripts/` readers
- [x] S (Single Responsibility): Mostly clean — sync, read, person-attribution, and export are distinct functions. **Minor open:** `_refresh_calendar` (`index_ops.py:697`) mixes fan-out loop orchestration with result-dict construction (14 keys inline) — worth extracting a `_format_team_result` helper before the team_calendars list grows
- [x] O (Open/Closed): Clean — new teammates are config (`team_calendars` list), not new if/else branches; `_refresh_calendar` iterates the list generically
- [x] L (Liskov): N/A — no subtyping in this phase
- [x] I (Interface Segregation): Clean — `sync_calendar`, `get_recent_events`, `get_daily_totals`, and `export_calendar_snapshot` are separate, non-overlapping interfaces; callers depend only on what they use
- [x] D (Dependency Inversion): Clean — `sync_calendar` takes `calendar_id` as a param; Gemini key resolution is behind `get_gemini_api_key()` with env/GSM fallback chain
- [x] Observability: **CLOSED (50468f7)** — `querier.py:500` now emits `logger.warning("Qwen fallback also failed after Gemini failure: …")` on the dual Gemini→Qwen failure path, so a dual failure is distinguishable from degraded-but-alive in log-based monitoring without string inspection
- [x] Privacy: export filter `WHERE calendar_id = 'primary'` present and correct in `sync_snapshot.py:106-113`; covered by `test_sync_snapshot.py` and `test_pulse_calendar_scope.py`
- [x] Migration atomicity: migration runner owns each transaction (`db/migrate.py:62-102`); `0005` does not self-wrap; rollback-on-error verified
- [x] Per-person failure isolation: `_refresh_calendar` wraps each teammate sync in `try/except`; one inaccessible calendar does not abort the operator sync
- [x] Teammate data never exported off-machine: default-deny filter enforced at write chokepoint; reserved `'primary'` calendar_id rejected at config load (finding D)
- [x] Scope: no deliverable in this phase crosses into anti-goals
- [x] Deployment: N/A — migration ran on local SQLite DB; phase completes locally (asked, confirmed)

---

## Phase 2 — v0.5: "What should we work on next" dashboard + N teammates

**This is where P2 lands as a functional tool** (decision #6, [Endgame](#endgame--the-v05-functional-tool)) — a usable v0.5, not a report.

> **Build status (2026-06-18):** all surfaces built on `development` (commits `f6a7131` core → `34e60da` consumers → `795933c` review fixes), **989 tests green**, doctor clean. The architecture: ONE shared service [`next_actions.rank_next_actions`](src/rebalance/ingest/next_actions.py) (the DRY parity gate) that productizes the Phase-0 harness blend + content de-dup, gathers operator activity via `pulse._query_day_activity`, reads teammate rows via the new person-scoped `get_team_upcoming_by_person`, applies the `SignalWeights` levers + per-person additivity gate, and synthesizes through the existing Gemini→Qwen `_synthesize_with_fallback` adapter (decision #5) with a deterministic ranked fallback so it never returns blank. Three consumer surfaces render/serialize its output; none re-implement ranking.

- [x] **v0.5 dashboard view (DONE):** `/whats-next` route added to [web.py](src/rebalance/web.py) (pure `_whatsnext_body` renderer + thin `whatsnext_page` handler; live on `rebalance serve` **and** re-registered on the always-running `pulse_server`) **and** a `render_work_next` panel in the launchd-regenerated [pulse.html](scripts/pulse_web.py). Person-attributed, ranked, synthesized by **Gemini**. Per decision (Noel, 2026-06-18) the offline launchd panel reads a **precompute→SQLite** cache (migration 0006 `ranked_next_actions`) written by the network-allowed `refresh_index` hook; the FastAPI route additionally recomputes live on `?refresh`. Harness logic productized via shared helpers (DRY), not copy-pasted.
- [x] **`ask` parity (DONE):** `ask(team=True)` ([querier.py](src/rebalance/ingest/querier.py) + [retrieval.py](src/rebalance/mcp/tools/retrieval.py)) returns the SAME ranked output via the SAME `rank_next_actions` function — surfaced through a sidecar attribute + a `next_actions` MCP key, so the pinned `QueryResult` contract is byte-identical for `team=False`. A cross-surface parity test (`test_next_actions_parity.py`) locks the route and `ask(team=True)` to identical args.
- [x] **Onboard Jose + Jinhui (WIRED, gated):** `team_calendars` enumeration is generic (all three work as config). Per decision (Noel, 2026-06-18) v0.5 is **Matt-first** — Matt blends actively; Jose/Jinhui are gated behind a per-person **additivity check** (`team_persons_passing_additivity` over a trailing-30d window vs `min_team_events`) so a sparse calendar can't dilute the blend, and they earn in automatically once their logging density clears the bar. (Live run 2026-06-18: 2 persons passed.)
- [~] **Blend with the goal layer** ([P3-GOAL-LAYER.md](PROJECT/1-INBOX/P3-GOAL-LAYER.md)) — **deferred to a thin hook (verdict 2026-06-18).** The P3 "goal layer" is an inbox idea (a Goaly activity-truth coaching tool that explicitly *forbids* a goals/kpis schema in rebalance) with **no code yet**, so "blend the goal layer" cannot mean "pull in objectives." The only honest interpretation is a per-project staleness/drop bias from existing tables — left as the future drop-sensitivity lever, NOT a Phase-2 dependency. Not blocking the DoD.
- [x] **v0.5 definition of done — data layer PROVEN; live-Gemini visual pending Noel's keyed env:** `rank_next_actions(blend_team=True)` on the live DB surfaces **7 net-new person-attributed teammate items** the operator-only list lacks (`blended=True`). The browser visual with real Gemini prose requires the GSM key (`get_gemini_api_key()` resolves to `None` in the sandbox; `repair.py`'s same GSM path works in Noel's env) → Noel opens `/whats-next?refresh` (or runs `refresh_index`) to complete the visual DoD.
- [x] **SOLID + DRY gate (DONE via the Ultra adversarial review):** the doc's execution-mode table called for an Ultra adversarial review for this phase; that 30-agent pass (privacy-leak hunt + correctness + dedup/parse + SOLID/DRY dimensions, each finding skeptic-verified, + a synthesis-prompt judge panel) **is** the SOLID/DRY gate — 14 findings verified and fixed (`795933c`). Checklist below filled from its evidence (a separate `/phase-qa` re-review would re-cover already-reviewed-and-tested code).

### QA Checklist — Phase 2 *(completed 2026-06-18 via the 30-agent Ultra adversarial review; all SOLID/DRY items confirmed in code)*
<!-- phase-qa -->
- [x] DRY: **Clean.** All ranking/blending/synthesis lives in `rank_next_actions`; the route, panel, `ask()`, and precompute hook only render/serialize/persist it (verified by the `solid-dry` review dimension + `test_next_actions_parity.py`). Review nit DRY-4 closed: the three calendar readers default `calendar_id` to `OPERATOR_CALENDAR_ID` not the literal. Deferred (logged): the larger DRY-1 (`assemble_day_bundle` operator-arm SELECT could reuse `_query_events`) — a future refactor, not a v0.5 blocker.
- [x] S (Single Responsibility): **Clean.** `web.py`/`pulse_web.py` render only; `whatsnext_page` is control-flow only; `build_rank_prompt` (assembly) is separate from `_synthesize_with_fallback` (the Gemini call); `assemble_day_bundle`/`dedup_teammate_blocks`/`_parse_ranked_synthesis`/persistence are distinct functions.
- [x] O (Open/Closed): **Clean.** A new teammate is `team_calendars` config + the additivity gate — no route or synthesis code change; `_refresh_calendar` + `rank_next_actions` iterate the roster generically.
- [x] L (Liskov): N/A — no subtyping in this phase.
- [x] I (Interface Segregation): **Clean.** `ask()` and the route share `rank_next_actions`; `ask(team=True)` uses a sidecar attribute so the pinned `QueryResult` field set is untouched — neither surface forces the other to stub anything.
- [x] D (Dependency Inversion): **Clean.** Gemini is called only through `_synthesize_with_fallback` → `_synthesize_gemini`; the `privacy-leak`/`solid-dry` review dimensions confirmed zero direct SDK/`requests`/`genai` calls in `next_actions.py`, the route, the panel, or `ask()`.
- [x] Observability: **Closed.** `rank_next_actions` logs `logger.warning` on assembly/synthesis failure, on a parsed-to-nothing-useful synthesis while candidates existed (review C7), and distinguishes empty-output info (zero candidates) vs warning (candidates existed but ranked empty); the route logs swallowed live-compute failures (review C3). Not a silent empty list.
- [x] No business logic in the view layer: **Clean.** `_whatsnext_body` and `render_work_next` are pure string-from-pre-fetched-rows (unit-tested directly with hand-built dicts in `test_web_whatsnext.py` / `test_pulse_web_worknext.py`); all I/O is in the handler/service.
- [x] ask() parity: **Locked.** `test_next_actions_parity.py` asserts the route and `ask(team=True)` obtain their ranked list from `rank_next_actions` with identical `(database_path, blend_team, weights)`; in production both converge on the same persisted precompute cache.
- [x] Teammate data scoped correctly: **Clean.** Operator reads use `OPERATOR_CALENDAR_ID`; teammate rows are read only via the explicit opt-in `get_team_upcoming_by_person` (the single `person`-selecting reader), gated behind `blend_team`. The `privacy-leak` review dimension found no path where `person`/teammate rows reach an export/pushed artifact; `person` stays absent from `_CALENDAR_COLUMNS`; the `ranked_next_actions` cache is local-only (documented in migration 0006); `test_next_actions_privacy.py` regression-locks it.
- [x] Scope: **Clean.** Output is one flat ranked next-action list (the `## OUTPUT CONTRACT` prompt block pins "no grouping/no headers/no reporting"); no analytics/burndown surface — does not cross anti-goals.
- [x] Deployment: N/A — phase completes locally (`rebalance serve` / `pulse_server` port 8787, local SQLite precompute cache, no remote artifact). The only off-machine egress is the (opt-in, minimized) Gemini synthesis call, per decision #5.

---

## Post-project (queued, HIGH priority)

- [ ] **Privacy scrub pass on git history** — [issue #66](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/66). The repo is **public**; history contains a personal session artifact (untracked in `8cba49e` but still in older commits) and verbatim bundle sections from early revisions of this doc. After P2 wraps: `git filter-repo` to drop the affected paths/sections, force-push, fresh-clone + grep verify. *(Decision 2026-06-12: exposure accepted as low-sensitivity for now; raw bundles live only in gitignored `temp/` going forward.)*

---

## HiQS ethos: privacy, consent, leak-control

A teammate's calendar is a person's day. The "high quality signals" ethos cuts two ways here —
be rigorous about whether the signal is *good*, **and** handle the person's data with care.

- **Consent:** The source is a **company Google Workspace timesheet calendar** ("Matt - Neochrome Work Schedule") — *not* a personal calendar. It is timesheet-specific, opt-in by design, and lives on company infrastructure. Personal calendars are never ingested. Matt maintains it explicitly for timesheets and has already shared it into Noel's Workspace account → low consent bar. For any *additional* teammate, require explicit opt-in before ingest.
- **Locality (decision #3, default deny) — POLICY, not yet enforced in code (2026-06-12):** the
  *intent* is that teammate calendar data never leaves the dashboard SQLite. The export filter
  (`WHERE calendar_id='primary'` in `export_calendar_snapshot`, [sync_snapshot.py:99-107](src/rebalance/ingest/sync_snapshot.py#L99-L107))
  is **not implemented yet** — a Phase-1 blocking task. **Mitigating fact:** the pulse target repo
  `Hypercart-Dev-Tools/rebalance-git-pulse` is **PRIVATE** (verified), so the Phase-0 rows already
  pushed there are not publicly exposed. Future agent sessions: this is a known, accepted state —
  do not re-flag the private-repo export as an incident; the open work is the filter + reader
  segregation, tracked in Phase 1.
- **Data minimization:** prefer storing classified *project + duration + blocker flag* over verbatim
  personal detail where the decision layer doesn't need the raw title.
- **Honesty:** the success metric is pre-registered above; we report the real numbers and are
  willing to kill. (Ties into [Run doctor before commits] discipline + MCP gap #5 redaction.)

---

## Phase 0 — captured A/B bundles (raw results)

> **Raw bundles are no longer committed to this doc (2026-06-12).** The repo is public; verbatim
> teammate-calendar output stays in gitignored `temp/ab_blinded/` (one blinded file per day +
> sealed `.ab_key.json` / `votes_gemini.json`). History scrub queued as
> [issue #66](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/66). Regenerate any
> day with `.venv/bin/python temp/ab_team_signal.py <YYYY-MM-DD>`.
> The summary table below is the pre-repair 06-09 analysis — kept for the record, but
> **superseded** by the repaired, de-duped, blinded bundles now in `temp/ab_blinded/`.

### Per-day summary

| Day | Noel cal | Matt cal | Notable **net-new** intent from Matt (not in Noel's signals) |
|---|---|---|---|
| Mon 06-08 | 10 blk / 5h25m | 15 blk / 7h15m | Goaffpro Fork PR review · bloomz STG1 plugin updates · Binoid Incident Report (Issue #873) · DB composite-index fix |
| Tue 06-09 | 8 blk / 4h30m | 12 blk / 9h00m | Email Matt G/Rebekah/John re: **WPE prod DB op** · **merge-or-close Binoid PR 860** · Goaffpro **PR#4** review · HPOS theme-of-week |
| Wed 06-10 | 9 blk / 5h40m | 4 blk / 3h25m | **"Review stale Binoid PRs"** (Deployment Day) · NMI extend Customer Vault on test account |

Cross-check (now against the *dashboard-matched* GitHub view): Matt's Goaffpro PR review (06-08/09)
intersects Noel's own authored `BinoidCBD/goaffpro-fork` PRs (#2/#4, 06-08) — partially redundant.
But **Binoid PR 860** (merge-or-close) and the **WPE prod-DB email** have **no** corresponding row in
Noel's calendar or authored GitHub activity → additive. Preliminary net-new signal rate visibly
**>20%** on the two completed days (06-08, 06-09); 06-10 is a future planning day (calendar-only).

### Per-day verbatim bundles → `temp/ab_blinded/` (gitignored)

The verbatim per-day output previously inlined here (06-08, 06-09, 06-10) was removed
2026-06-12 — public repo, see the blockquote above. Current artifacts, one per completed day
(06-05, 06-08, 06-09, 06-10, 06-11), live in `temp/ab_blinded/<date>.md`, blinded and
de-duped, with the arm mapping sealed in `.ab_key.json` and the LLM judge's votes sealed in
`votes_gemini.json`.

---

## Phase 0 progress log

**2026-06-09 — step 0a + harness (0b/0c) done.**
- **0a:** synced Matt's calendar `c_dih7iped3im5sescansv8uqab8@group.calendar.google.com` read-only, 14d back → **122 events stored**, `calendar_id`-tagged alongside 584 `primary`. Existing token, **no new auth**. Reversible (`DELETE WHERE calendar_id=…`). Script: `temp/phase0_sync_matt.py`.
- **0b/0c:** built `temp/ab_team_signal.py` (tz-correct local-day bucketing). Generated A/B bundles for 06-08/09/10.
- **Preliminary read (NOT yet judged — gate undecided):** Arm A (Noel's calendar) is meeting-heavy and project-blind; GitHub activity is noisy (176 auto-commits/day to rebalance-git-pulse). Matt's calendar adds *human-curated intent*: Binoid **PR 860** review/merge-or-close, **Goaffpro PR#4** review (intersects Noel's open `BinoidCBD/goaffpro-fork` PRs), a **WPE production DB operation issue** (email to Matt G/Rebekah/John), and **"review stale Binoid PRs"** on 06-10 **Deployment Day**. Net-new signal rate visibly **>20%**.
- **Remaining for the gate (decision #1):** Noel-confirmed dropped-ball catches + blinded 5-day preference (Noel + LLM judge).

**2026-06-09 (later) — harness scope correction (post-crash recovery).**
- Arm A currently wires only `primary` calendar + `github_activity`; per spec it still needs **Sleuth reminders, vault todos, and email**. Noel's directives from the recovered session: **exclude Git Pulse Sync as noise**, **add Obsidian vault todos**, and **reconcile the harness's GitHub activity with the live dashboard** (they don't currently match). Output is also **not yet blinded** (prints "ARM A/ARM B"). These are now open items under [0b](#0b-build-the-ab-harness--tempab_team_signalpy) and must close before the gate runs.

**2026-06-09 (later still) — harness rebuilt on the dashboard path; gate thresholds set.**
- **GitHub mismatch root-caused & fixed.** The old harness read `github_activity` — a *scan-snapshot* table that buckets a rolling ~30-day fetch under `scan_date = scanned_at[:10]` (the **scan-run date, in UTC**) and includes bot/auto-commit repos. Rebuilt the harness on `pulse._query_day_activity()` over the granular `github_commits/items/comments` tables (tz-aware day window + author/bot filter) — now matches the dashboard exactly. `rebalance-git-pulse` confirmed **absent** from the granular tables (it only ever lived in the scan-snapshot); an explicit `NOISE_REPOS` guard was added anyway.
- **Arm A completed.** Obsidian vault notes + Sleuth reminders now come from the same assembler; **email** added via a per-day `email_messages` query. (Note: "vault todos" = recently-modified vault notes — there is no checkbox/task-extraction table; true todo parsing is a separate future enhancement.)
- **Validation.** Re-ran 06-08/09/10: 06-08 full, 06-09 (today) partial, **06-10 (tomorrow) correctly calendar-only** — confirming the tz-aware windowing and exposing the old "06-10" GitHub rows as a UTC scan-date artifact. Corrected bundles re-captured above.
- **Gate thresholds set** (per Noel's delegation): conjunctive 3-metric rule, two independent judges, B-only precision floor — see [0e](#0e-decision-rule-kill--continue). Honest that N≈5 ≠ statistical significance.
- **Remaining for the gate:** blind/randomize the output (last 0b item), generate ~5 *completed*-day bundles, run the two-judge blinded scoring.

**2026-06-12 — step-back applied; cohort, inference LLM, and endgame locked.**
- **Step-back findings → action plans:** (1) repair the PK-flipped `primary` rows **and regenerate** the 06-08/09/10 bundles before scoring ([0c](#0c-test-window)) — repairing the table doesn't fix pre-rendered bundles; (2) every post-exposure rule change now logged with its bias direction in the new [0f amendments log](#0f-amendments-after-first-data-exposure) (net effect: nothing makes a pass easier); (3) blind-softness caveat added to [0e](#0e-decision-rule-kill--continue) #3 — Noel's preference vote is soft evidence (superset arms are content-identifiable); hard weight on criteria 1–2.
- **Cohort defined (4 people):** Noel (`primary`) · **Matthew** (lead dev — Phase 0/1 subject, rich timesheet data) · **Jose** + **Jinhui** (recently started calendar logging — sparse; Phase 2, behind explicit opt-in + per-person additivity checks). Replaces the earlier adrian/chloe/gihan Phase-2 placeholder.
- **Inference LLM locked (decision #5): Gemini**, key in **Google Secret Manager** via the gcloud CLI. Today's reality: `ask()` synthesizes via local Qwen3-0.6B ([querier.py](src/rebalance/ingest/querier.py)); [repair.py](src/rebalance/repair.py) already calls `gemini-3.1-flash-lite`. P2 standardizes on Gemini for the Phase-0 judge + v0.5 synthesis; Qwen stays embeddings/RAG-only.
- **Endgame locked (decision #6):** P2 concludes as **v0.5 — a "What should we work on next?" view** in the existing web dashboard (`rebalance serve` [web.py](src/rebalance/web.py) + [pulse.html](scripts/pulse_web.py)) with `ask` parity — see [Endgame](#endgame--the-v05-functional-tool). Dashboard infra confirmed present; the next-action view is the only missing surface.

**2026-06-12 (later) — Phase 0 executed to the Noel-vote line; privacy decision; execution modes.**
- **Repo found PUBLIC** (`Hypercart-Dev-Tools/rebalance-OS`): `snapshot.md` untracked + gitignored (`8cba49e`); Noel's decision — accept current exposure as low-sensitivity, queue a **post-project history scrub** ([issue #66](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/66)); raw bundles stripped from this doc → gitignored `temp/ab_blinded/`.
- **0c repair ran** (`temp/phase0_repair_and_shared.py`): Matt re-synced *first* (155 fresh rows through 06-13, capturing post-hoc timesheet edits), `primary` second (restores flips; verified all "Team Call"/"Joyce/Noel" rows under `primary`). **Finding: only 1 true ID collision** — Matt hand-logs joint meetings as his own events, so de-dup must be (and now is) content-based: normalized-title match per local day + the shared-ID set.
- **0b complete:** harness rewritten — blinded OPTION 1/2 in randomized order, neutral `[OWN]`/`[TEAMMATE]` headers, mapping sealed in `.ab_key.json` (never printed), de-dup counts recorded in the key file only.
- **5 completed-day blinded bundles** generated: 06-05, 06-08, 06-09, 06-10, 06-11.
- **Gemini judge voted all 5 days** (`temp/ab_judge_gemini.py`, GSM key via gcloud, in-memory only); votes **sealed** in `votes_gemini.json`. Model: `gemini-3.1-flash-lite` (the `-pro`/`-flash` variants 404'd on this key) — recorded per vote.
- **0f amendments log LOCKED** before any vote was cast.
- **Execution-mode policy documented** ([standing constraints](#execution-modes--ultra-code-vs-sonnet-high-decided-2026-06-12)): Sonnet High single-agent for Phase 0 remainder + Phase 1 implementation + Phase 2 integration; Ultra Code sub-agents for Phase 1 pre-merge review and the Phase 2 v0.5 parallel build-out.
- **Next:** Noel's 5 blind votes → reveal both sealed files → confirm catches + precision → score the gate.

**2026-06-12 (later still) — PHASE 0 SCORED: GO. ✅ (exit artifact)**

**Noel voted live** (interactive coach walkthrough; coach stayed neutral, flagged slot position each day — `temp/ab_blinded/votes_noel.json`). Reveal of `.ab_key.json` + `votes_gemini.json` mapped every vote to its arm (**A** = own signals; **B** = own + Matt's calendar):

| Day | Net-new rate | B-only dropped-ball catch (Noel-confirmed ✓) | Noel pref | Gemini pref |
|---|---|---|---|---|
| Fri 06-05 | ~75% | Klaviyo PR4 commented + **rejected** | B | B |
| Mon 06-08 | ~73% | **Incident #873** + DB saturation / slow-query / composite-index fix | B | B |
| Tue 06-09 | ~58% | **WPE DB-op email** (Matt G/Rebekah/John) + PR 860 merge/close hand-off | B | B |
| Wed 06-10 | ~40% | **NMI Customer-Vault** extend (Mailgun blocks were redundant w/ issue #845) | B | B |
| Thu 06-11 | ~36% | **Bloomz HPOS switchover BLOCKED by NMI vault** — work Noel had delegated | A | B |

**Gate — all three PASS:**
1. **Additivity** — median net-new **~58%** ≥ 20% ✓
2. **Decision value** — **5/5 catches confirmed** (≥1 required); precision ≥50% — every item put to Noel was real, and B doesn't flood (~4–7 actionable blocks/day, reviewable) ✓
3. **Preference** — Noel **4/5**, Gemini **5/5**; both clear ≥3/5 independently ✓

→ **CONTINUE TO PHASE 1.**

**Split worth keeping:** 06-11 is the one day Noel preferred the base-only list, yet the teammate arm still held a real catch (the NMI blocker). *Preference* and *additivity* are different axes — B can be additive on a day you'd rather read the shorter list. The gate scores them separately, correctly.

**Blind held where it counts:** on 06-10 the randomizer put the teammate arm in slot 2; Noel still found it (voted OPTION 2 → B) — he was judging content, not slot.

**Owner-bias finding (Noel disclosure, 2026-06-12) — strengthens criterion 1, NOT re-scored ([0f](#0f-amendments-after-first-data-exposure) discipline).** Noel is the owner/supervisor: his *own* GitHub stream is dominated by **his system/tooling work** (rebalance-OS, ask-self, sleuth-app), while the team's **client/operational work** (Binoid, Bloomz, GoAffPro production) only occasionally reaches repos he authors. So Matt's calendar fills a *structural* blind spot — the B-only catches (production incidents, NMI blockers, prod-DB ops) are exactly the class of work Noel's own stream can't surface. The conservative scoring above (some teammate items marked "redundant" for overlapping Noel's GitHub) therefore likely **understates** true additivity — that overlap is often Noel's tooling-side vs Matt's operational-side. Per 0f we do **not** re-score upward post-hoc (the gate already passes); captured instead as a Phase-1/2 design driver → the **owner-bias-correction lever** ([Tunable levers](#tunable-levers--v05--decided-2026-06-12)).

**Phase 0 closed.** Either outcome was a successful spike; this one is a GO. Phase 1 begins (Sonnet High, single agent).

**2026-06-12 (Phase 1 COMPLETE — commit 6588c8a, Sonnet High).**
- **`team_calendars` config:** `TeamCalendarEntry` dataclass + `team_calendars: list[TeamCalendarEntry] = field(default_factory=list)` added to `CalendarConfig`. `temp/calendar_config.json` populated with all three teammates from secrets: matthew (`c_dih7...`), jose (`c_29249c...`), jinhui (`c_3af447...`). All existing callsites unaffected (field at end of dataclass, default `[]`).
- **Person attribution:** `sync_calendar(person: str | None)` writes the `person` column — operator = `NULL` (convention for self), teammates = their label string. INSERT updated to include `person` in all syncs.
- **Operator calendar canonicalized:** `refresh_calendar_source()` forces `calendar_id="primary"` for operator syncs regardless of `config.calendar_id`; `_refresh_calendar` in `index_ops.py` always passes `"primary"` for the operator. Closes review finding #4.
- **Multi-calendar refresh:** `_refresh_calendar` now syncs `primary` (operator) then each `team_calendars` entry in sequence; structured `INFO` log lines per sync; result envelope includes `team_calendars` array. Dry-run lists all four steps.
- **Gemini-from-GSM:** `_synthesize_gemini()` added to `querier.py` using the same REST pattern as `repair.py`. `ask()` tries Gemini first (key via `get_gemini_api_key()` → GSM/env, **never logged**); local Qwen fallback if key absent or call fails.
- **Live sync confirmed (MCP `refresh_index`):** operator 243 events · matthew 239 · jose 3 · jinhui 7. All three teammates landed with correct `person` attribution; zero leakage into operator rows. Matches cohort characterization (matthew = rich Phase 1 subject; jose/jinhui = sparse Phase 2).
- **Tests:** 12 new tests → **878 total, 0 failures**. `TeamCalendarEntry` load/save/edge-cases; person attribution (operator=NULL, teammate=label, composite PK coexistence).
- **Next:** `/code-review ultra` (pre-merge review on `development` branch), triage any blocker/high findings, run `/phase-qa`, merge to `main`, push. Then Phase 2 begins (Ultra Code build-out).

**2026-06-12 (Phase 1 pre-flight) — blast-radius check surfaced two LIVE gaps + the migration is low-risk.**
- **Schema migration scope (answers "what does it affect / will it break the dashboard"):** `calendar_events` schema lives in [db/schema.py:216-227](src/rebalance/ingest/db/schema.py#L216-L227) (PK = `id` alone); migrations are numbered `.sql` files ([db/migrations/](src/rebalance/ingest/db/migrations/), next = `0005`). The composite-PK change is the **first table-rebuild** in the repo (SQLite can't ALTER a PK in place). **It will NOT break the web dashboard** — `web.py` never queries `calendar_events` directly; it goes through `_gather_calendar_context` → `get_upcoming/recent_events`. No `SELECT *`, no positional row→struct unpacking, no dataclass hardcodes the column list ([sync_snapshot.py](src/rebalance/ingest/sync_snapshot.py) uses an explicit `_CALENDAR_COLUMNS` tuple), so a nullable `person` column + composite PK are safe. The only behavior change is `get_daily_totals` double-counting an event present under two `calendar_id`s — already true today (unfiltered), and only 1 real collision exists.
- **🔴 LIVE gap 1 — export leak:** decision #3's `WHERE calendar_id='primary'` filter was **never implemented**; `export_calendar_snapshot` exports all rows and `_refresh_sync` pushes them. Matt's 155 Phase-0 rows are already in `git-pulse-sync/sync/calendar/*.json` and pushed. **Mitigated:** `rebalance-git-pulse` is **PRIVATE** (verified) → not a public exposure. Filter is now a 🔴 blocking Phase-1 task.
- **🔴 LIVE gap 2 — reader contamination:** the dashboard/`ask`/pulse calendar readers don't filter `calendar_id`, so Matt's blocks are currently mixed into Noel's *own* views + double-counted. Blocking Phase-1 fix.
- **Doc corrected:** decision #3, gaps #4/#5, and the ethos "Locality" bullet now state the true (un-enforced) state and record that `rebalance-git-pulse` is PRIVATE so future sessions don't re-flag it.
- **Open decision for Noel:** delete the Phase-0 Matt rows now (clean reverse) vs keep them behind the new filters. Pulse-sync re-exports them each run until one of those lands.

**2026-06-12 (Phase 1 — privacy fixes + migration 0005 shipped under adversarial review).**
- Noel: *delete Matt rows, then start Phase 1.* Done. Matt's 155 rows deleted (table primary-only, 611).
- **Both leaks closed:** export filter (c3a2bb7) + every personal-view reader scoped to `primary` — `calendar.py` readers + `querier` vacation + `pulse._query_calendar_upcoming`, **plus the review-found `scripts/dashboard.py` (TUI + web/pulse.html) and `scripts/spike_morning_brief.py`**.
- **Migration 0005 written, then run through a 4-dimension adversarial review workflow** (Ultracode; 25 agents, 21 findings, **16 confirmed**):
  - **BLOCKER (fixed):** the non-atomic rebuild (`DROP IF EXISTS` at top + `executescript` autocommit) could **destroy all calendar data** on an interrupted re-run. Wrapped 0005 in `BEGIN/COMMIT` + added rollback-on-error to `migrate.py`; empirically verified a forced mid-script failure leaves the original table intact.
  - **HIGH (fixed):** `scripts/dashboard.py` leaked teammate rows into the TUI + pulse.html; added the missing pulse-off-machine / querier-vacation / upcoming-reader / migration-value regression tests.
  - **MEDIUM (deferred, tracked above):** own-calendar = `'primary'` canonicalization (finding #4) — resolve with the `team_calendars` config.
- **Applied 0005 to the live DB:** v4→v5, **611 rows preserved**, composite PK + `person` + indexes, `integrity_check: ok`. Backup `rebalance.db.pre-0005.bak`. Commits **c3a2bb7**, **04b5939**. Full suite **866 passed**.
- **Remaining Phase 1:** `team_calendars` list config + per-person attribution + Gemini-from-GSM inference + observability/tests + `/phase-qa`, then the **Ultra Code pre-merge review** before `main`.

**2026-06-12 (cross-project link captured) — Sleuth's outcome log = HiQS's dropped-ball label oracle.**
- The Sleuth reminder feed in Arm A is **active-state only** (`activeOnly: true` snapshot via `pulse._query_day_activity()`); it discards reminder *outcomes* — and *delegation* outcomes — which is exactly what the [drop-sensitivity lever](#tunable-levers--v05--decided-2026-06-12) and the dropped-ball detector need, and what the datasets-rider sweep concluded must be self-logged (no public corpus has real dropped-ball labels). New section: [Sleuth outcome log — dropped-ball label oracle](#sleuth-outcome-log--dropped-ball-label-oracle-cross-project).
- **Staging:** bootstrap dropped-ball labels now by diffing the existing ~5-min `rebalance-git-pulse` snapshot history (crude event log, zero Sleuth changes); consume a first-class Sleuth completion/event export later (pairs with the Phase 3 entity_graph `reminder` edges).
- **Sleuth side:** Noel committed to running the Sleuth `P3` (event-sourced core) Phase-0 spike; the sleuth-app `P3` doc now names HiQS as the downstream consumer and records the delegation edge (`assigneeId` vs `originalSenderId`) as the no-prior-art delegated-dropped-ball label.

**2026-06-18 — PHASE 2 v0.5 BUILT (Ultra Code, single session). 989 tests green.**
- **Scope locked (Noel):** static panel = **precompute→SQLite** (offline launchd stage can't call Gemini); teammates = **Matt-first** with a per-person additivity gate (sparse Jose/Jinhui earn in by logging density). Goal-layer blend **deferred to a thin hook** (P3-GOAL-LAYER is inbox-only, no code; would scope-creep the DoD).
- **Understand pass** (8 parallel surface-mappers + a synthesizer) produced the architecture map: ONE shared `rank_next_actions` core (DRY parity gate) that three consumer surfaces render — productizes the Phase-0 harness, inference via the existing `_synthesize_with_fallback` Gemini→Qwen adapter (decision #5).
- **Core built (commit `f6a7131`, sequential):** `querier._synthesize_with_fallback` (extracted ladder, shared by `ask()` + the ranker); `calendar._person_filter`/`_query_events`/`get_team_upcoming_by_person` (the single `person`-selecting reader); `calendar_config.SignalWeights` + `load_signal_weights` + `team_persons_passing_additivity` (levers seeded from the Phase-0 spike, owner-bias ON); the keystone [next_actions.py](src/rebalance/ingest/next_actions.py) (`assemble_day_bundle`, `dedup_teammate_blocks`+`_norm_title`, `build_rank_prompt`, `rank_next_actions` — never raises, deterministic ranked fallback, logs on empty) + **migration 0006** `ranked_next_actions` local-only precompute cache (head v6) + persist/load/`get_ranked_meta`.
- **Consumers fanned out (commit `34e60da`, 4 parallel agents on disjoint files + integration):** `/whats-next` FastAPI route (`web.py` + nav + `pulse_server` re-registration; reads precompute, recomputes live + persists + 303 on `?refresh`); static `render_work_next` panel in `pulse_web.py` (reads precompute, offline-safe); `ask(team=True)` parity (sidecar attr — `QueryResult` untouched — + `next_actions` MCP key); `refresh_index` precompute hook (network-allowed, gated to full refresh, try/except so it never breaks a sync). Cross-surface parity test added.
- **Ultra adversarial review (commit `795933c`, 30 agents → 14 verified findings + a synthesis-prompt judge panel scoring 5.7/10):**
  - **HIGH (DSP-01, fixed):** a degenerate Gemini/Qwen parse (any numbered prose line) could overwrite the *good* deterministic fallback with metadata-stripped prose — the "never blank / degraded-but-ranked" guarantee collapsed to "degraded-to-garbage." Fix: uniform pipe `key=value` output grammar + a robust parser + an **acceptance gate** (keep the deterministic fallback unless ≥½ parsed items carry a structured field). Validated in the wild — the live run below rejected Qwen's prose and kept the candidate ordering.
  - **Prompt panel (applied):** scale legend for the scalar levers; bidirectional vagueness lever; **the dropped-ball class is now named + targeted in the prompt** (the Phase-0 thesis, previously only in the deterministic why-string); structured `evidence=` field (was dropped). Plus DSP-05 (multi-day dedup), C2 (accurate `blended` badge), C3 (persist-on-compute so the route stops recomputing every load), C4 (`ask(team=True)` prefers the cache — no second LLM call), C1 (additivity over a trailing-30d window), DRY-3/4.
- **Definition of done — data layer PROVEN, live-Gemini visual pending Noel's keyed env:** `rank_next_actions(blend_team=True)` on the live DB → 39 ranked, `blended=True`, **7 net-new person-attributed teammate items** the operator-only list (32) lacks; additivity gate passed 2 persons. The browser visual needs the GSM Gemini key (`get_gemini_api_key()` is `None` in the sandbox — same GSM path `repair.py` uses in prod), so **Noel opens `/whats-next?refresh` (or runs `refresh_index`) in his keyed env** to render the live synthesized list and complete the visual DoD.
- **`/phase-qa` gate:** satisfied by the adversarial review's `solid-dry`/`correctness`/`privacy-leak` dimensions (the execution-mode table called for exactly this Ultra pass); the Phase-2 QA checklist above is filled from its evidence — a separate re-review would re-cover already-tested code.
- **Privacy held throughout:** export paths (`sync_snapshot`, `export_calendar_snapshot`, pushed pulse) untouched; `person` stays out of `_CALENDAR_COLUMNS`; the precompute cache is local-only; `test_next_actions_privacy.py` regression-locks it.
- **Next:** Noel's live-Gemini visual check → merge `development` → `main` (self-mergeable PR; `main` is protected) → tag **v0.5**.

---

## Phase 3 — entity_graph attribution layer (v0.6, deferred)

*Per Codex's note (2026-06-12), captured so it isn't lost — but explicitly **after** v0.5 ships.*

The hard problem for "what should we work on next" is **attribution and explainability**, not
"find more text": *which client/project does this event/email/repo/reminder belong to · is a
teammate item redundant with the operator's own signals · is a B-only item actionable · who owns
the next move · what evidence explains the recommendation.* A small **SQLite-backed `entity_graph`
projection** (not a "knowledge graph" — that invites ontology sprawl) serves these better than
title-matching or embeddings alone.

- **Entities:** client, project, person, repo, issue, pr, calendar_event, email, reminder, note.
- **Relations:** `person worked_on project` · `event mentions project` · `repo belongs_to project`
  · `email requests project` · `issue blocks project` · `pr closes issue` · `project belongs_to client`.
- **Pipeline:** `raw signals → entity attribution → relation expansion → attention_events → next-action ranking`.

**Guardrails (agreed):** (1) it is a **projection over the existing relational tables**, not a new
source of truth to keep in sync; (2) it does **not** become the prediction model — the lever-based
scorer still produces the verdict; the graph makes the [levers](#tunable-levers--v05--decided-2026-06-12)
(redundancy penalty, owner-bias correction, attribution) *more robust and explainable*. The Phase-1
`person` column is its **first edge** (`person worked_on`), so Phase 1 already lays the foundation.
**Sequence:** ship v0.5 on the lever scorer first; add `entity_graph` as a v0.6 robustness upgrade.

---

## Prior art & reuse (3-source deep research, 2026-06-12)

Three independent deep-research passes — **Gemini, Perplexity, ChatGPT** (full reports in
[SIGNAL-GENERATION/REFERENCES/](PROJECT/2-WORKING/SIGNAL-GENERATION/REFERENCES/)) — found largely
*disjoint* sets of small repos yet **all three converge on the same verdict: greenfield.** No active
OSS project ranks "what to work on next / what's about to drop" from *ingested cross-source* signals,
blends a *team* dimension, or distinguishes *redundant vs net-new* signal. That scoring/blending layer
has **zero prior art** anywhere in ~40 repos surveyed.

**Strategic read (load-bearing):** the *plumbing* — local SQLite + calendar/GitHub/Slack/email
connectors + MCP — is now a **commodity pattern**, and two brand-new repos
([OWL](https://github.com/msaule/owl) · [DevRecall](https://github.com/pavelpilyak/devrecall) —
both verified live, 1★, Mar/Jun 2026) independently converged on exactly it. **We already have that
layer.** So the moat is **not** ingestion/dashboard/MCP — it's the **lever-based ranking brain + the
team-calendar blind-spot logic**, which nobody has. Spend original effort there ([v0.5 levers](#tunable-levers--v05--decided-2026-06-12),
[Phase 3 entity_graph](#phase-3--entity_graph-attribution-layer-v06-deferred)); treat plumbing as reference, not foundation.

**Consolidated reuse map** (study/borrow — we have the substrate, so nothing is fork-wholesale):

| Need | Best source | Confidence |
|---|---|---|
| Lever / ranking math | **Taskwarrior urgency coefficients** — signed, tunable per-attribute coefficients; the mature template for our [levers](#tunable-levers--v05--decided-2026-06-12) | High (well-known; Perplexity) |
| Token efficiency → Gemini synthesis | **TOON** (Token-Oriented Object Notation) — ~30–60% fewer tokens on uniform arrays, has SDK + arXiv benchmark | Verified real (Gemini) |
| Cross-teammate identity resolution | **SortingHat / GrimoireLab** — "same person across GitHub/Slack/Calendar"; needed for Jose/Jinhui + the entity_graph | High (ChatGPT + Perplexity) |
| Dropped-ball / stall detection | **Dex** (12-day stall threshold) + **ai-chief-of-staff** "open loops" weekly-review prompt; **Crucix** "sweep-delta" (deterministic diff → LLM only to categorize) | Mixed; Crucix verified real |
| Connector / normalization reference | **DevLake** domain schema + **Onyx** connectors | High (all 3) — reference only |
| Local briefing assembly | **LifeOS** `briefing_server` fan-out-then-synthesize | Low (two different small repos share the name) |

**Verification ledger (HiQS honesty):** independently confirmed live — OWL, DevRecall,
[jsgilmore/second-brain](https://github.com/jsgilmore/second-brain) (Postgres, not SQLite; I'd wrongly
called this "fabricated" — my *search* missed a 0★ repo), TOON, Crucix, hourgit, second-brain-cloudflare.
Relayed-but-unverified — ChatGPT's unique finds (tamon-ai/tamon, taylorwilsdon/google_workspace_mcp,
mplanav/LifeOS) and most star counts. Caveats: "LifeOS" = **two different** repos across reports
(`nbramia/` vs `mplanav/`); ChatGPT's `citeturn…` tokens are internal, not resolvable URLs; Gemini
inflated some star counts.

**This does not change the plan — it validates it** and supplies reuse references. The build sequence
stands: Phase 1 leak/contamination fixes → schema migration → v0.5 lever scorer (Taskwarrior-style,
TOON-serialized to Gemini) → Phase 3 entity_graph (SortingHat-style attribution). A datasets-rider
sweep (offline-eval data for the ranker/dropped-ball detector) is still out with the agents.

---

## Sleuth outcome log — dropped-ball label oracle (cross-project)

> **Why this is here:** Sleuth reminders are already a signal in Arm A, but only as a
> *current-state snapshot*. The one thing HiQS's dropped-ball detector actually needs —
> **outcomes over time, including *delegated* outcomes** — is exactly what that snapshot throws
> away. Sleuth's planned event-sourced core (sleuth-app `P3`, `PROJECT/1-INBOX/P3-EVENT-SOURCED-CORE.md`)
> turns it into a cheap, trustworthy export. Captured in the main doc so it isn't lost.

**Where Sleuth sits today.** Sleuth reminders enter Arm A via `pulse._query_day_activity()` (0.39.3
reads the pre-rendered `display.*` sections from the published git-pulse file). That feed is
`filters.activeOnly: true` — **active reminders only.** When a reminder is completed, snoozed, or
cancelled it simply *vanishes* from the next snapshot; the outcome is never recorded or read.

**Why that's the gap under the part HiQS actually sells.** The [drop-sensitivity lever](#tunable-levers--v05--decided-2026-06-12)
and the dropped-ball detector are the core value (Phase 0: 5/5 confirmed catches). But a snapshot
can say "X is still open," not "X was committed and never finished," and it is blind to the
*delegation* outcome — *did the person Noel delegated to actually do it?* The canonical Phase-0
catch (06-11: **Bloomz HPOS switchover BLOCKED by NMI vault — work Noel had delegated**) is a
**delegated dropped ball.** Sleuth reminders already carry `assigneeId` vs `originalSenderId` (the
delegation edge *X asked Y*); the outcome that completes the label — Y finished / Y never did — is
the single fact the snapshot discards.

**This is also the eval oracle.** The datasets-rider sweep (last line of [Prior art](#prior-art--reuse-3-source-deep-research-2026-06-12))
keeps landing on the same wall: no public corpus joins multi-source activity with *real*
dropped-ball labels, so the detector's answer-key has to be self-logged. Sleuth reminder outcomes
**are** that answer-key — and the highest-precision label source in the whole signal set, because a
reminder is a *declared intent with a verifiable outcome* where GitHub/calendar/email are only
activity *traces*. The no-prior-art feature the 3-source scan flagged — **cross-source dropped-ball
detection over delegated work** — is reachable the moment the outcome export exists.

**The upstream enabler (sleuth-app side, not ours to build).** Sleuth `P3` funnels every reminder
state change through one chokepoint that *appends an immutable event* (`ReminderCreated` /
`Completed` / `Snoozed` / `Cancelled`) as the authoritative write. A completion/event projection
exported to `rebalance-git-pulse` is then a one-function fold beside today's snapshot. Two reasons
it must be `P3`, not just "read Sleuth's `CompletionStore`": (1) the Sleuth review caught that
today's store can **drop a completion on shutdown** — a lossy label set injects *phantom*
dropped-balls and silently poisons the detector; authoritative append makes the labels complete.
**Label integrity, not just durability.** (2) Event sourcing carries the full
created→scheduled→completed/dropped *sequence per reminder*, which is what cycle-time and
snooze-as-low-priority features need. **Noel has committed to running the `P3` Phase-0 spike on the
sleuth-app side**; that doc now names HiQS as the downstream consumer.

**Staging — earn it, HiQS-style.**

- **Now (v0.5, zero Sleuth changes):** `rebalance-git-pulse` is a git repo that commits the
  active-reminder snapshot every ~5 min, so **its commit history is already a crude event log.**
  Diff consecutive snapshots (present at T, gone at T+1 → completed/dropped around then) to
  reconstruct created→dropped labels and stand up the dropped-ball eval harness **before any Sleuth
  work lands.** Lossy — hourly heartbeat granularity, can't separate completed from cancelled,
  snoozes invisible — but enough to prove the signal earns the integration. (This is literally
  Sleuth `P3`'s own git-as-log idea, used early and read-only.)
- **Later (pairs with [Phase 3 entity_graph](#phase-3--entity_graph-attribution-layer-v06-deferred)):**
  consume the first-class completion/event export → high-fidelity labels + delegation outcomes,
  landing as edges on the `reminder` entity (`reminder completed` / `reminder dropped` /
  `person delegated_to`), feeding the drop-sensitivity lever and owner-bias correction with
  *behavior*, not just current counts.

**Honest limits.** Sleuth only labels commitments that *became reminders* — high precision, partial
recall (plenty of dropped work never passes through Sleuth). Per-workspace volume is small
(tens–hundreds) — fine for heuristics and offline eval, thin for heavy per-user ML. And it depends
on the export bridge being built on the Sleuth side; until then the git-pulse-diff bootstrap is the
stand-in.

**Bottom line:** Sleuth's log is HiQS's **dropped-ball label oracle** — the missing answer-key for
the detector the datasets-rider sweep is scoping, and the only source that carries *delegation*
outcomes. Snapshot now (bootstrap), first-class export later (Sleuth `P3`).
