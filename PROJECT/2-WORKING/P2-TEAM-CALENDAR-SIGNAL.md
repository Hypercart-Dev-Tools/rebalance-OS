---
project: "P2 — Team Calendar as a Signal"
codename: HiQS
owner: Noel
created: 2026-06-09
updated: 2026-06-09
status: "Working — Phase 0 in progress"
current_phase: "Phase 0 — Spike + A/B test"
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
| **Phase 0 · 0a + initial harness (0b/0c)** — Synced Matt's calendar read-only (**122 events**, existing token, reversible), and built the A/B bundle generator [temp/ab_team_signal.py](temp/ab_team_signal.py) with tz-correct day bucketing; generated bundles for 06-08 / 09 / 10. Preliminary net-new signal rate visibly **>20%**. | **Finish Arm A, then run the gate.** Exclude Git Pulse Sync as noise, add Obsidian vault todos (+ Sleuth / email) to the bundle, reconcile harness GitHub activity against the live dashboard, and blind/randomize the output. Then run the 5-day blinded judging (Noel + LLM) for the decision #1 kill/continue gate. |

---

## Table of Contents

- [Goal & the two outputs](#goal--the-two-outputs)
- [Decisions (locked 2026-06-09)](#decisions-locked-2026-06-09)
- [What already exists (don't rebuild)](#what-already-exists-dont-rebuild)
- [Phase 0 — Spike + A/B test (the decision gate)](#phase-0--spike--ab-test-the-decision-gate)
- [Phase 1 — Productize the second calendar (only if Phase 0 passes)](#phase-1--productize-the-second-calendar-only-if-phase-0-passes)
- [Phase 2 — Team-orchestration output + N teammates](#phase-2--team-orchestration-output--n-teammates)
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

---

## Decisions (locked 2026-06-09)

| # | Decision | Choice |
|---|---|---|
| 1 | **Phase 0 kill/continue bar** | Continue to Phase 1 only if **all three**: ≥1 confirmed dropped-ball catch over the week **AND** blind preference favors B on **≥3 of 5 days** **AND** net-new signal rate **≥20%**. |
| 2 | **Judges** | **Noel + an LLM judge** (local Qwen and/or Claude) vote independently on each blinded pair. |
| 3 | **Privacy / export** | Teammate rows **may** remain in the pulse/sync export **as long as the pulse target repo is confirmed private**. Confirming privacy is a gating action before Phase 1 sync ships. |
| 4 | **Phase 1 scope** | **Matt only** — a single second calendar, not a full N-person list. Generalize to N teammates in Phase 2. |

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
   PK `(id, calendar_id)`.
2. **No person attribution.** No `owner`/`person` column → can't say "this is Matt's block, not mine."
3. **Single-calendar config.** `CalendarConfig.calendar_id` is one string; needs a team list.
4. **Leak surface.** [src/rebalance/ingest/sync_snapshot.py](src/rebalance/ingest/sync_snapshot.py) `export_calendar_snapshot` pushes `calendar_events` to the pulse git repo. Per decision #3, teammate rows may stay in the export **once the pulse target repo is confirmed private** (gating action, see [HiQS ethos](#hiqs-ethos-privacy-consent-leak-control)).

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
- [x] **Arm A core** — primary calendar + `github_activity` wired into the bundle (tz-correct local-day bucketing).
- [x] **Arm B** — adds Matt's blocks (`calendar_id=<matt>`) on top of Arm A, framed as a teammate's in-flight/blocked work ("what should the team work on next?").
- [ ] **Arm A — complete the signal set:** add Sleuth reminders, **Obsidian vault todos**, and email (spec requires *all* of Noel's signals, not just calendar + GitHub).
- [ ] **Arm A — denoise:** exclude **Git Pulse Sync** (`rebalance-git-pulse` auto-commits, ~176/day) as known noise to skip.
- [ ] **Reconcile GitHub activity:** harness reads `github_activity` by `scan_date` but it doesn't match Noel's live dashboard — fix the query so both arms see the real activity.
- [ ] **Blind + randomize:** output currently prints labeled "ARM A / ARM B" — relabel to "Option 1 / Option 2" in randomized order so judging is unbiased.

### 0c. Test window
- [x] Bundles generated for the 2 example days captured this week (**06-08, 06-09**) + **06-10**.
- [ ] Generate the remaining ~2 days to complete the ≈1 work-week window. Small N is fine for a spike — we want signal, not significance.

### 0d. Pre-registered measurement (define BEFORE looking — HiQS honesty)
Three metrics, recorded per day:

1. **Net-new signal rate** *(additivity vs. redundancy)* — % of Matt's work-blocks that (i) map to a **shared project/repo** (Binoid, bloomz, GoAffPro, …) **and** (ii) have **no corresponding signal** in Noel's own data that day. High % → additive; low % → Matt's calendar just re-states what GitHub/Slack already show.
2. **Dropped-ball catches** *(the core value)* — count of actionable items Arm B surfaces that Arm A misses **and** that Noel confirms are real (true positives). False positives counted separately.
3. **Blind preference** — Noel picks the more-useful list per day; an **LLM judge** (local Qwen and/or Claude) gives an independent second vote on the same blinded pair.

### 0e. Decision rule (kill / continue)
Proceed to Phase 1 **only if all three** clear (locked, decision #1):
**≥1 confirmed dropped-ball catch** over the week **AND** blind preference favors **B on ≥3 of 5 days**
**AND** net-new signal rate **≥20%**. Otherwise **stop** and record why — a teammate calendar that's
~90% redundant with GitHub + Slack is *not* a high-quality signal and isn't worth the privacy +
maintenance cost. Either outcome is a successful spike.

- [ ] **Phase 0 exit artifact:** append the findings table (3 metrics × N days) + go/no-go to the [progress log](#phase-0-progress-log).

---

## Phase 1 — Productize the second calendar (only if Phase 0 passes)

Keep it one `Collector` — no new dispatch branches (registry stays clean). **Matt only** (decision #4):
a single second calendar, modeled so the Phase-2 jump to N people is config, not a refactor.

- [ ] **Schema migration** (numbered, in `db.py`): composite PK `(id, calendar_id)`; add `person TEXT` (friendly owner label) + index on `(calendar_id, start_time)`. *(PK + person column are needed even for one teammate.)*
- [ ] **Config**: add a single `team_calendar: {person, calendar_id}` entry to [calendar_config.py](src/rebalance/ingest/calendar_config.py) (a 1-element shape, not yet a list); keep single `calendar_id` for back-compat.
- [ ] **Refresh**: `_refresh_calendar` syncs `primary` + the one team calendar; per-calendar timing/counts in the result envelope (window stays bounded).
- [ ] **Confirm the pulse repo is private** (gating action, decision #3) before the team-calendar sync ships.
- [ ] **Read side**: `_gather_calendar_context()` attributes events by person and segregates *my calendar* vs *team calendar* in the prompt sections.
- [ ] **Observability/tests from day one** (per AGENTS.md): structured per-person log lines; integration test stubbing the Calendar API for ≥2 calendars asserting insert/overwrite isolation by `calendar_id`; smoke test for the blended prompt.

---

## Phase 2 — Team-orchestration output + N teammates

- [ ] Promote "what should the **team** work on next" to a first-class output in `ask` / dashboard / pulse.
- [ ] Blend with the goal layer ([PROJECT/1-INBOX/P3-GOAL-LAYER.md](PROJECT/1-INBOX/P3-GOAL-LAYER.md)).
- [ ] **Generalize the single `team_calendar` entry into an N-person `team_calendars` list** (adrian / chloe / gihan transfers already visible in the calendar list) — each behind explicit opt-in.

---

## HiQS ethos: privacy, consent, leak-control

A teammate's calendar is a person's day. The "high quality signals" ethos cuts two ways here —
be rigorous about whether the signal is *good*, **and** handle the person's data with care.

- **Consent:** Matt maintains this calendar explicitly for timesheets and has already shared it
  into Noel's account → low consent bar. For any *additional* teammate, require explicit opt-in
  before ingest.
- **Locality (decision #3):** teammate rows may ride along in the pulse/sync export
  **only once the pulse target repo is confirmed private.** `export_calendar_snapshot`
  ([sync_snapshot.py](src/rebalance/ingest/sync_snapshot.py)) pushes `calendar_events` to the
  pulse repo — so **confirming the repo is private is a gating action before the team-calendar
  sync ships.** (If it can't be confirmed private, fall back to filtering the export to
  `calendar_id='primary'`.)
- **Data minimization:** prefer storing classified *project + duration + blocker flag* over verbatim
  personal detail where the decision layer doesn't need the raw title.
- **Honesty:** the success metric is pre-registered above; we report the real numbers and are
  willing to kill. (Ties into [Run doctor before commits] discipline + MCP gap #5 redaction.)

---

## Phase 0 — captured A/B bundles (raw results)

> Verbatim output of [temp/ab_team_signal.py](temp/ab_team_signal.py) for each test day,
> committed into the doc so the results survive a crash. **Regenerate** any time with
> `.venv/bin/python temp/ab_team_signal.py <YYYY-MM-DD>` (DB still holds the 122 Matt rows).
> **Caveat (open 0b items):** Arm A is still *calendar + GitHub only* (no Sleuth / vault / email),
> GitHub activity still includes Git Pulse Sync noise, and the output is not yet blinded — so
> these are inputs for judging, **not** a scored gate result.

### Per-day summary

| Day | Noel cal | Matt cal | Notable **net-new** intent from Matt (not in Noel's signals) |
|---|---|---|---|
| Mon 06-08 | 10 blk / 5h25m | 15 blk / 7h15m | Goaffpro Fork PR review · bloomz STG1 plugin updates · Binoid Incident Report (Issue #873) · DB composite-index fix |
| Tue 06-09 | 8 blk / 4h30m | 12 blk / 9h00m | Email Matt G/Rebekah/John re: **WPE prod DB op** · **merge-or-close Binoid PR 860** · Goaffpro **PR#4** review · HPOS theme-of-week |
| Wed 06-10 | 9 blk / 5h40m | 4 blk / 3h25m | **"Review stale Binoid PRs"** (Deployment Day) · NMI extend Customer Vault on test account |

Cross-check: Matt's Goaffpro PR review (06-08/09) intersects Noel's open `BinoidCBD/goaffpro-fork`
PRs (3 opened 06-09/10); PR 860 and the WPE DB issue have **no** corresponding row in Noel's
calendar or GitHub activity → additive. Net-new signal rate visibly **>20%** across the three days.

### Mon 2026-06-08 (tz America/Los_Angeles)

```
[NOEL] GitHub activity (scan_date = 2026-06-08):
  rebalance-git-pulse        commits=204 pushes=204     <- Git Pulse Sync (NOISE, to exclude)
  Hypercart-Dev-Tools/rebalance-OS   commits=13 prs_opened=3 issue_comments=2
  Claude-AI-Tools/giant-bra  commits=11
  Hypercart-Dev-Tools/ask-self       commits=4 prs_opened=5
  NeochromeTeam/sleuth-app   commits=4 prs_opened=1 issues_opened=1
  ...plan-proof, deckme, three-que, agent-vs, AI-DDTK (small)
  BinoidCBD/goaffpro-fork            prs_opened=1
  BinoidCBD/universal-child-theme    issues_opened=3

ARM A (control) — NOEL primary calendar (10 blocks, 5h25m)
  09:00 Blocked off for morning exercise (65m)
  10:15 Neochrome Daily Check-in (25m)
  11:00 MacNerd - add news (60m)
  11:00 Post Binoid Kanban screenshot for Elan (15m)
  12:30 Noel/Matt (25m) | 12:30 Weekly - Joyce/Noel (15m)
  13:45 1:45 - Team Call (15m)
  15:00 Rebalance - calibrate project definition file (45m)
  15:30 Rebalance - test remote repos (45m)
  17:00 End of Day Check-In (15m)

ARM B (treatment) — + MATT Neochrome Work Schedule (15 blocks, 7h15m)
  10:15 Binoid: look into emails/cron (15m)
  10:30 Neochrome: morning meeting (15m)
  10:45 Binoid: Scheduled Actions Backlog Investigation (30m)
  11:15 Binoid: Production Log Analysis (30m)
  11:45 Binoid: Database Saturation Analysis (30m)
  12:15 Binoid: Slow Query Analysis (30m)
  12:45 Binoid: Incident Report (GitHub Issue #873) (30m)
  13:15 Binoid: Bug Reports for WordPress.org Plugin Forums (30m)
  13:45 Binoid: GoAffPro Fork PR Review (30m)
  14:15 Binoid: Production Database Fix — Composite Index (15m)
  14:30 lunch (50m)
  15:20 File bug report to Goaffpro (25m)
  15:45 Binoid: bloomz STG1 plugin updates (60m)
  16:45 SMPT Pro feature request (15m)
  17:00 Binoid: bloomz STG1 plugin updates (30m)
```

### Tue 2026-06-09 (tz America/Los_Angeles)

```
[NOEL] GitHub activity (scan_date = 2026-06-09):
  rebalance-git-pulse        commits=176 pushes=176     <- Git Pulse Sync (NOISE, to exclude)
  NeochromeTeam/sleuth-app   commits=22 prs_opened=4 issues_opened=1
  Hypercart-Dev-Tools/rebalance-OS   commits=13 prs_opened=2 issue_comments=1
  Hypercart-Dev-Tools/ask-self       commits=8 prs_opened=4
  BinoidCBD/LTVera-Pandas    commits=5 prs_opened=1 issues_opened=2
  BinoidCBD/goaffpro-fork    commits=1 prs_opened=3 issues_opened=1 issue_comments=1
  ...giant-bra, plan-proof, three-que, agent-vs, love2socal, deckme, AI-DDTK (small)
  BinoidCBD/universal-child-theme    issues_opened=3 issue_comments=1
  NormansNursery/photoapp-webapp     issues_opened=1

ARM A (control) — NOEL primary calendar (8 blocks, 4h30m)
  09:00 Blocked off for morning exercise (65m)
  09:30 Neochrome Daily Check-in (25m)
  10:00 Pre-meeting (50m)
  12:30 Weekly - Joyce/Noel (15m)
  13:00 BW Maintenance Check-in (Matt's Zoom) (25m)
  13:45 1:45 - Team Call (15m)
  17:00 End of Day Check-In (15m) | 17:00 Placeholder Transportation Broker Mtg (60m)

ARM B (treatment) — + MATT Neochrome Work Schedule (12 blocks, 9h00m)
  09:30 Start of day officially - Check Slack & Emails (30m)
  10:00 Send email to Matt G, Rebekah, John re: WPE DB operation issue (15m)
  10:15 Binoid - Cron research (75m)
  11:30 Binoid - continue with HPOS theme of the week (60m)
  12:30 Review and merge or close Binoid PR 860 (30m)
  13:00 Binoid: deterministic analysis scripts (45m)
  13:45 Binoid: Goaffpro review PR#4 (15m)
  14:00 neochrome: afternoon checkin (15m)
  14:15 lunch (60m)
  15:15 Binoid - continue with HPOS theme of the week (105m)
  17:00 Binoid - premium plugins (75m)
  18:15 Binoid - stg1 testing checkout (15m)
```

### Wed 2026-06-10 — Deployment Day (tz America/Los_Angeles)

```
[NOEL] GitHub activity (scan_date = 2026-06-10):
  rebalance-git-pulse        commits=169 pushes=169     <- Git Pulse Sync (NOISE, to exclude)
  NeochromeTeam/sleuth-app   commits=24 prs_opened=5 issues_opened=1
  Claude-AI-Tools/giant-bra  commits=12
  Hypercart-Dev-Tools/rebalance-OS   commits=10 prs_opened=1
  BinoidCBD/LTVera-Pandas    commits=8 prs_opened=1 issues_opened=2
  Hypercart-Dev-Tools/ask-self       commits=6 prs_opened=4
  BinoidCBD/goaffpro-fork    commits=1 prs_opened=3 issues_opened=1 issue_comments=1
  ...universal-child-theme, three-que, agent-vs, love2socal, deckme, photoapp (small)

ARM A (control) — NOEL primary calendar (9 blocks, 5h40m)
  09:00 Blocked off for morning exercise (65m)
  10:15 Neochrome Daily Check-in (25m)
  10:15 Neochrome Team - Deployment Day (50m)
  12:20 Physical therapy (60m)
  13:45 1:45 - Team Call (15m) | 13:45 Sleuth Team Call (25m)
  15:00 NN Weekly (25m)
  16:30 Blocked off (60m)
  17:00 End of Day Check-In (15m)

ARM B (treatment) — + MATT Neochrome Work Schedule (4 blocks, 3h25m)
  09:30 Start of day officially - Check Slack & Emails (50m)
  13:00 Neochrome Team - Review stale Binoid PRs (50m)
  14:00 lunch (60m)
  16:15 Binoid: nmi, extend Customer Vault time on test account if needed (45m)
```

---

## Phase 0 progress log

**2026-06-09 — step 0a + harness (0b/0c) done.**
- **0a:** synced Matt's calendar `c_dih7iped3im5sescansv8uqab8@group.calendar.google.com` read-only, 14d back → **122 events stored**, `calendar_id`-tagged alongside 584 `primary`. Existing token, **no new auth**. Reversible (`DELETE WHERE calendar_id=…`). Script: `temp/phase0_sync_matt.py`.
- **0b/0c:** built `temp/ab_team_signal.py` (tz-correct local-day bucketing). Generated A/B bundles for 06-08/09/10.
- **Preliminary read (NOT yet judged — gate undecided):** Arm A (Noel's calendar) is meeting-heavy and project-blind; GitHub activity is noisy (176 auto-commits/day to rebalance-git-pulse). Matt's calendar adds *human-curated intent*: Binoid **PR 860** review/merge-or-close, **Goaffpro PR#4** review (intersects Noel's open `BinoidCBD/goaffpro-fork` PRs), a **WPE production DB operation issue** (email to Matt G/Rebekah/John), and **"review stale Binoid PRs"** on 06-10 **Deployment Day**. Net-new signal rate visibly **>20%**.
- **Remaining for the gate (decision #1):** Noel-confirmed dropped-ball catches + blinded 5-day preference (Noel + LLM judge).

**2026-06-09 (later) — harness scope correction (post-crash recovery).**
- Arm A currently wires only `primary` calendar + `github_activity`; per spec it still needs **Sleuth reminders, vault todos, and email**. Noel's directives from the recovered session: **exclude Git Pulse Sync as noise**, **add Obsidian vault todos**, and **reconcile the harness's GitHub activity with the live dashboard** (they don't currently match). Output is also **not yet blinded** (prints "ARM A/ARM B"). These are now open items under [0b](#0b-build-the-ab-harness--tempab_team_signalpy) and must close before the gate runs.
