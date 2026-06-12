---
project: "P2 — Team Calendar as a Signal"
codename: HiQS
owner: Noel
created: 2026-06-09
updated: 2026-06-12
status: "Phase 0 PASSED (GO 2026-06-12) — Phase 1 next"
current_phase: "Phase 1 — Productize the second calendar"
endgame: "v0.5 — 'What should we work on next?' view in the web dashboard (Gemini-powered, tunable levers)"
kill_switch: "Willing to kill if Matt's calendar is mostly redundant with GitHub + Slack"
tags: [signal-quality, calendar, team-orchestration, ab-test]
---

# P2 — Team Calendar as a Signal (HiQS)

> **Thesis (HiQS):** A teammate's shared work calendar is only worth ingesting if it
> raises *decision* quality — "what should I / the team work on next, and what's about
> to get dropped." Phase 0 is an A/B test that must **earn** Phase 1. We are willing to
> kill this if the signal is mostly redundant with GitHub + Slack.

---

## Status at a glance

| ✅ Most recently completed phase | ⏭️ What's next |
|---|---|
| **Phase 0 PASSED — GO (2026-06-12).** All three gate criteria cleared: net-new median **~58%** (≥20%), **5/5 Noel-confirmed catches** + precision ≥50%, blinded preference **Noel 4/5 · Gemini 5/5** (both ≥3/5). Owner-bias finding strengthens it. Full scoring in the [progress log](#phase-0-progress-log). | **Phase 1 — productize Matt's calendar** (single agent, Sonnet High per the [mode policy](#execution-modes--ultra-code-vs-sonnet-high-decided-2026-06-12)): schema migration (composite PK + `person`), `team_calendars` list config, Gemini inference wired from GSM, then **Ultra Code** pre-merge review of the export seam. |

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
| **Drop sensitivity** | How aggressively to flag blocked/stale *delegated* work ("about to be dropped") | The NMI-vault blocker catch (06-11) is the canonical hit |

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
| 3 | **Privacy / export** | **Policy:** teammate calendar data is **never exported** to the pulse git repo — `export_calendar_snapshot` must filter `WHERE calendar_id = 'primary'` (default deny). **⚠️ NOT YET IMPLEMENTED (discovered 2026-06-12):** the live `export_calendar_snapshot` ([sync_snapshot.py:99-107](src/rebalance/ingest/sync_snapshot.py#L99-L107)) selects **all** rows — no filter — and the Phase-0 sync's Matt rows (155, never cleaned up) have already been exported + pushed to the pulse repo `rebalance-git-pulse`. That repo is **PRIVATE** (verified), so this is a policy violation, not a public exposure — but the filter is now a **blocking Phase-1 task**, not a done guarantee. |
| 4 | **Phase 1 scope** | **Matt only** — a single second calendar, not a full N-person list. Phase 2 generalizes to the rest of the [cohort](#cohort-defined-2026-06-12) (**Jose, Jinhui**) once their newer logging habit produces rich-enough data. |
| 5 | **Analysis/inference LLM** *(2026-06-12)* | **Gemini** (cloud) for all P2 analysis & inference — the Phase-0 LLM judge and the v0.5 dashboard synthesis. API key lives in **Google Secret Manager**, fetched via the gcloud CLI (same pattern as the existing `ltvera-gemini-api-key` secret); [repair.py](src/rebalance/repair.py) already calls `gemini-3.1-flash-lite`. Local Qwen stays embeddings/RAG-only. |
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

- [ ] **🔴 BLOCKING — close the export leak (decision #3, gap #4):** add `WHERE calendar_id = 'primary'` to `export_calendar_snapshot` ([sync_snapshot.py:99-107](src/rebalance/ingest/sync_snapshot.py#L99-L107)) so teammate rows never reach the pulse repo. Add a regression test asserting a non-primary row is absent from the export. *(Do this first — every pulse-sync run currently re-exports Matt's rows to `rebalance-git-pulse`.)*
- [ ] **🔴 BLOCKING — fix reader contamination (gap #5):** filter/segregate by `calendar_id` in `get_upcoming_events` / `get_recent_events` / `get_daily_totals` ([calendar.py:360-475](src/rebalance/ingest/calendar.py#L360-L475)) and `_gather_calendar_context` so Matt's blocks stop bleeding into Noel's *own* dashboard/`ask`/pulse views and double-counting daily totals.
- [ ] **Clean up the Phase-0 Matt rows** *(pending Noel's call — see progress log):* either `DELETE FROM calendar_events WHERE calendar_id='<matt>'` (reverse the spike; Phase 1 re-syncs cleanly) **or** keep them and rely on the filters above. Decide before Phase 1 ships.
- [ ] **Schema migration** (numbered `.sql` in [db/migrations/](src/rebalance/ingest/db/migrations/) — next is `0005`; **first table-rebuild in this repo**, no in-place PK ALTER in SQLite): composite PK `(id, calendar_id)`; add `person TEXT`; add index `(calendar_id, start_time)`. Standard create-new/copy/drop/rename per [migrations/README.md](src/rebalance/ingest/db/migrations/README.md). Only **1 real ID collision** exists today, so this is foundational, not urgent — sequence it *after* the two leaks are closed.
- [ ] **Config**: add `team_calendars: [{person, calendar_id}]` (a **list from day one**) to [calendar_config.py](src/rebalance/ingest/calendar_config.py); a 1-element list handles Matt now and makes Phase 2's N-person generalization config-only, not a second migration. Keep single `calendar_id` for back-compat.
- [ ] **Refresh**: `_refresh_calendar` syncs `primary` + the one team calendar; per-calendar timing/counts in the result envelope (window stays bounded).
- [x] **Pulse repo privacy confirmed (2026-06-12):** `Hypercart-Dev-Tools/rebalance-git-pulse` is **PRIVATE** (`gh repo view`). The gating concern (decision #3) is satisfied for visibility; the code-level export filter above is still required (default deny).
- [ ] **Read side**: `_gather_calendar_context()` attributes events by person and segregates *my calendar* vs *team calendar* in the prompt sections. *(Folds in the gap-#5 fix above.)*
- [ ] **Inference path (decision #5):** next-action synthesis calls **Gemini**; API key fetched at runtime from **Google Secret Manager** via the gcloud CLI (`gcloud secrets versions access latest --secret=<gemini-key-secret>`) — never hardcoded, never committed. Local Qwen remains embeddings/RAG-only.
- [ ] **Observability/tests from day one** (per AGENTS.md): structured per-person log lines; integration test stubbing the Calendar API for ≥2 calendars asserting insert/overwrite isolation by `calendar_id`; smoke test for the blended prompt.
- [ ] **SOLID + DRY gate** (see [standing constraints](#standing-design-constraints-phase-1-onward)): run `/phase-qa` before marking Phase 1 complete.

---

## Phase 2 — v0.5: "What should we work on next" dashboard + N teammates

**This is where P2 lands as a functional tool** (decision #6, [Endgame](#endgame--the-v05-functional-tool)) — a usable v0.5, not a report.

- [ ] **v0.5 dashboard view:** add a **"What should we work on next?"** page to the existing web dashboard — a route in [src/rebalance/web.py](src/rebalance/web.py) (`rebalance serve`, alongside `/focus-5`) **and** a panel in the launchd-regenerated [web/pulse.html](scripts/pulse_web.py). Ranked, person-attributed next actions from the Phase-1 blended signal, synthesized by **Gemini** (decision #5). The Phase-0 harness's bundle logic is the spec — productized via shared helpers, not copy-pasted (DRY).
- [ ] **`ask` parity:** expose the same team-level output through the `ask` MCP tool so agents see what the dashboard shows.
- [ ] **Onboard Jose + Jinhui** to `team_calendars` — each behind explicit opt-in (HiQS ethos) **and** a per-person mini additivity check (their logging habit is new and sparse; a still-mostly-empty calendar shouldn't dilute the blend). No config migration needed; Phase 1 already uses a list.
- [ ] Blend with the goal layer ([PROJECT/1-INBOX/P3-GOAL-LAYER.md](PROJECT/1-INBOX/P3-GOAL-LAYER.md)).
- [ ] **v0.5 definition of done:** Noel opens the dashboard in a browser and sees a ranked, person-attributed "what should we work on next" list containing ≥1 item his own signals would have missed.
- [ ] **SOLID + DRY gate** (see [standing constraints](#standing-design-constraints-phase-1-onward)): run `/phase-qa` before marking Phase 2 complete.

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

**2026-06-12 (Phase 1 pre-flight) — blast-radius check surfaced two LIVE gaps + the migration is low-risk.**
- **Schema migration scope (answers "what does it affect / will it break the dashboard"):** `calendar_events` schema lives in [db/schema.py:216-227](src/rebalance/ingest/db/schema.py#L216-L227) (PK = `id` alone); migrations are numbered `.sql` files ([db/migrations/](src/rebalance/ingest/db/migrations/), next = `0005`). The composite-PK change is the **first table-rebuild** in the repo (SQLite can't ALTER a PK in place). **It will NOT break the web dashboard** — `web.py` never queries `calendar_events` directly; it goes through `_gather_calendar_context` → `get_upcoming/recent_events`. No `SELECT *`, no positional row→struct unpacking, no dataclass hardcodes the column list ([sync_snapshot.py](src/rebalance/ingest/sync_snapshot.py) uses an explicit `_CALENDAR_COLUMNS` tuple), so a nullable `person` column + composite PK are safe. The only behavior change is `get_daily_totals` double-counting an event present under two `calendar_id`s — already true today (unfiltered), and only 1 real collision exists.
- **🔴 LIVE gap 1 — export leak:** decision #3's `WHERE calendar_id='primary'` filter was **never implemented**; `export_calendar_snapshot` exports all rows and `_refresh_sync` pushes them. Matt's 155 Phase-0 rows are already in `git-pulse-sync/sync/calendar/*.json` and pushed. **Mitigated:** `rebalance-git-pulse` is **PRIVATE** (verified) → not a public exposure. Filter is now a 🔴 blocking Phase-1 task.
- **🔴 LIVE gap 2 — reader contamination:** the dashboard/`ask`/pulse calendar readers don't filter `calendar_id`, so Matt's blocks are currently mixed into Noel's *own* views + double-counted. Blocking Phase-1 fix.
- **Doc corrected:** decision #3, gaps #4/#5, and the ethos "Locality" bullet now state the true (un-enforced) state and record that `rebalance-git-pulse` is PRIVATE so future sessions don't re-flag it.
- **Open decision for Noel:** delete the Phase-0 Matt rows now (clean reverse) vs keep them behind the new filters. Pulse-sync re-exports them each run until one of those lands.

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
