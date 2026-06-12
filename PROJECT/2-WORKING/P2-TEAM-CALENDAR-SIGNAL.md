---
project: "P2 — Team Calendar as a Signal"
codename: HiQS
owner: Noel
created: 2026-06-09
updated: 2026-06-12
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
| **Phase 0 · 0a–0c complete + dashboard-matched** — Matt's calendar synced (**122 events**, reversible). Harness [temp/ab_team_signal.py](temp/ab_team_signal.py) now builds Arm A from the dashboard's own per-day assembler: authored GitHub (Git Pulse Sync **excluded**, root-cause fixed), Obsidian vault, Sleuth, email. Gate thresholds set ([0e](#0e-decision-rule-kill--continue)). | **Blind the output, then run the gate.** Relabel ARM A/B → "Option 1/2" randomized (last 0b item); generate one bundle *per completed day* across ~5 days; then run the blinded two-judge scoring (Noel + LLM) against the [0e](#0e-decision-rule-kill--continue) gate. |

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
| 1 | **Phase 0 kill/continue bar** *(thresholds set by Claude per Noel's delegation — see [0e](#0e-decision-rule-kill--continue))* | Continue to Phase 1 only if **all three**: (a) net-new signal rate **≥20%** (median scored day); (b) **≥1 Noel-confirmed dropped-ball catch** AND B-only **precision ≥50%**; (c) blinded preference favors B on **≥3 of 5 days for *both* judges independently** (Noel AND the LLM judge), no-preference days counting against B. |
| 2 | **Judges** | **Noel + an LLM judge** (local Qwen and/or Claude) vote independently on each blinded pair. |
| 3 | **Privacy / export** | Teammate calendar data is **never exported** to the pulse git repo. `export_calendar_snapshot` always filters `WHERE calendar_id = 'primary'`. Teammate data stays purely local to the dashboard SQLite. Default deny — no repo-visibility gate required. |
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
   PK `(id, calendar_id)`. **Phase 0 data integrity note:** syncing Matt's calendar in 0a may
   have overwritten shared-invite rows from `calendar_id='primary'` to `calendar_id='<matt>'`
   (e.g., "1:45 Team Call", "Weekly Joyce/Noel"). Before scoring, run a repair query or re-ingest
   `primary` to restore any flipped rows — Arm A's `WHERE calendar_id='primary'` filter silently
   drops those events if corrupted.
2. **No person attribution.** No `owner`/`person` column → can't say "this is Matt's block, not mine."
3. **Single-calendar config.** `CalendarConfig.calendar_id` is one string; needs a team list.
4. **Leak surface (closed by design).** `export_calendar_snapshot` ([sync_snapshot.py](src/rebalance/ingest/sync_snapshot.py)) must always filter `WHERE calendar_id = 'primary'` — teammate rows are never exported to the pulse git repo (decision #3, default deny).

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
- [ ] **Blind + randomize:** output still prints labeled "ARM A / ARM B" — relabel to "Option 1 / Option 2" in randomized order so judging is unbiased. Write the mapping to a hidden `.ab_key.json` file (gitignored); **do not print to console** — Noel is a judge and seeing the key before voting breaks the blind. Reveal only after both judges have locked votes. *(Last remaining 0b item.)*
- [ ] **De-duplicate shared events from Arm B delta:** query for event IDs present in *both* `calendar_id='primary'` and `calendar_id='<matt>'` (shared invites: "1:45 Team Call", "Weekly Joyce/Noel", etc.). These are already in Arm A — suppress them from the Arm B-only delta display and exclude them from the net-new signal rate count. The A→B delta must surface only blocks *unique* to Matt's calendar. Also reduces over-counting of joint meetings in the block totals.

### 0c. Test window
- [x] Bundles generated for the 2 example days captured this week (**06-08, 06-09**) + **06-10**.
- [ ] Generate the remaining ~2 days to complete the ≈1 work-week window. Small N is fine for a spike — we want signal, not significance.

### 0d. Pre-registered measurement (define BEFORE looking — HiQS honesty)
Three metrics, recorded per day:

1. **Net-new signal rate** *(additivity vs. redundancy)* — % of Matt's work-blocks that (i) map to a **shared project/repo** (Binoid, bloomz, GoAffPro, …) **and** (ii) have **no corresponding signal** in Noel's own data that day. High % → additive; low % → Matt's calendar just re-states what GitHub/Slack already show.
2. **Dropped-ball catches** *(the core value)* — count of actionable items Arm B surfaces that Arm A misses **and** that Noel confirms are real (true positives), with **precision** = true positives ÷ all B-only items Noel reviews (false positives counted, so B can't win by flooding).
3. **Blind preference** — Noel picks the more-useful list per day; an **LLM judge** (local Qwen and/or Claude) gives an independent second vote on the same blinded pair.

### 0e. Decision rule (kill / continue)
**Thresholds set by Claude per Noel's delegation (2026-06-09).** N≈5 days can't yield statistical
significance, so the "gold standard" here is a *pre-registered, blinded, two-judge, conjunctive* rule —
a chance win on any single metric can't pass the gate. Proceed to Phase 1 **only if all three** clear:

1. **Additivity** — net-new signal rate **≥ 20%** (median scored day). Below this, Matt's calendar mostly restates GitHub/Slack.
2. **Decision value** — **≥ 1 Noel-confirmed dropped-ball catch** over the window, **and** B-only **precision ≥ 50%** (confirmed catches ÷ all B-only items Noel reviews) — so B earns the catch without flooding.
3. **Preference** — blinded preference favors **B on ≥ 3 of 5 days for *both* judges independently** (Noel *and* the LLM judge each clear 3/5); no-preference days count against B. Two independent majorities is the small-N guard — one judge at 3/5 is a coin-flip under the null. **LLM judge calibration:** the judge prompt must explicitly instruct the model to *discount vague time-blocks* ("Slack&Emails", "Cron research") and *heavily weight verifiable, targeted actions* ("Review Binoid PR 860", "Email re WPE DB op") — otherwise the judge may falsely prefer Arm B simply because it has more text.

Otherwise **stop** and record why — a teammate calendar ~90% redundant with GitHub + Slack is *not* a
high-quality signal and isn't worth the privacy + maintenance cost. Either outcome is a successful spike.

- [ ] **Test-window timing:** generate each day's bundle *after that day completes* — activity tables only fill once work has happened, so a same-day/future bundle is calendar-only (see 06-10). Score completed days; future days exercise only the planning/orchestration value (H2).
- [ ] **Phase 0 exit artifact:** append the findings table (3 metrics × N days) + go/no-go to the [progress log](#phase-0-progress-log).

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

---

## Phase 1 — Productize the second calendar (only if Phase 0 passes)

Keep it one `Collector` — no new dispatch branches (registry stays clean). **Matt only** (decision #4):
a single second calendar, modeled so the Phase-2 jump to N people is config, not a refactor.

- [ ] **Schema migration** (numbered, in `db.py`): composite PK `(id, calendar_id)`; add `person TEXT` (friendly owner label) + index on `(calendar_id, start_time)`. *(PK + person column are needed even for one teammate.)*
- [ ] **Config**: add `team_calendars: [{person, calendar_id}]` (a **list from day one**) to [calendar_config.py](src/rebalance/ingest/calendar_config.py); a 1-element list handles Matt now and makes Phase 2's N-person generalization config-only, not a second migration. Keep single `calendar_id` for back-compat.
- [ ] **Refresh**: `_refresh_calendar` syncs `primary` + the one team calendar; per-calendar timing/counts in the result envelope (window stays bounded).
- [ ] **Confirm the pulse repo is private** (gating action, decision #3) before the team-calendar sync ships.
- [ ] **Read side**: `_gather_calendar_context()` attributes events by person and segregates *my calendar* vs *team calendar* in the prompt sections.
- [ ] **Observability/tests from day one** (per AGENTS.md): structured per-person log lines; integration test stubbing the Calendar API for ≥2 calendars asserting insert/overwrite isolation by `calendar_id`; smoke test for the blended prompt.
- [ ] **SOLID + DRY gate** (see [standing constraints](#standing-design-constraints-phase-1-onward)): run `/phase-qa` before marking Phase 1 complete.

---

## Phase 2 — Team-orchestration output + N teammates

- [ ] Promote "what should the **team** work on next" to a first-class output in `ask` / dashboard / pulse.
- [ ] Blend with the goal layer ([PROJECT/1-INBOX/P3-GOAL-LAYER.md](PROJECT/1-INBOX/P3-GOAL-LAYER.md)).
- [ ] **Extend `team_calendars` list to N teammates** (adrian / chloe / gihan already visible in the calendar list) — each behind explicit opt-in. No config migration needed; Phase 1 already uses a list.
- [ ] **SOLID + DRY gate** (see [standing constraints](#standing-design-constraints-phase-1-onward)): run `/phase-qa` before marking Phase 2 complete.

---

## HiQS ethos: privacy, consent, leak-control

A teammate's calendar is a person's day. The "high quality signals" ethos cuts two ways here —
be rigorous about whether the signal is *good*, **and** handle the person's data with care.

- **Consent:** The source is a **company Google Workspace timesheet calendar** ("Matt - Neochrome Work Schedule") — *not* a personal calendar. It is timesheet-specific, opt-in by design, and lives on company infrastructure. Personal calendars are never ingested. Matt maintains it explicitly for timesheets and has already shared it into Noel's Workspace account → low consent bar. For any *additional* teammate, require explicit opt-in before ingest.
- **Locality (decision #3, default deny):** teammate calendar data is **never exported** to the
  pulse git repo. `export_calendar_snapshot` ([sync_snapshot.py](src/rebalance/ingest/sync_snapshot.py))
  must always filter `WHERE calendar_id = 'primary'` — teammate rows stay purely local to the
  dashboard SQLite. This eliminates the leak surface entirely; no repo-visibility gate is required.
- **Data minimization:** prefer storing classified *project + duration + blocker flag* over verbatim
  personal detail where the decision layer doesn't need the raw title.
- **Honesty:** the success metric is pre-registered above; we report the real numbers and are
  willing to kill. (Ties into [Run doctor before commits] discipline + MCP gap #5 redaction.)

---

## Phase 0 — captured A/B bundles (raw results)

> Verbatim output of [temp/ab_team_signal.py](temp/ab_team_signal.py) for each test day,
> committed into the doc so the results survive a crash. **Regenerate** any time with
> `.venv/bin/python temp/ab_team_signal.py <YYYY-MM-DD>` (DB still holds the 122 Matt rows).
> **Status:** GitHub now matches the dashboard — pulled via `pulse._query_day_activity()` over
> the granular `github_commits/items/comments` tables (author + bot filter, tz-aware day window).
> **Git Pulse Sync is excluded**, and **vault + Sleuth + email are now in Arm A**. **Still open:**
> the output isn't blinded yet (labels ARM A/B) — so these remain judging *inputs*, **not** a scored
> gate result. **Freshness caveat:** activity signals are real only *after* a day completes; a bundle
> generated for *today/tomorrow* is partial or calendar-only (see 06-10 below).

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

### Mon 2026-06-08 (tz America/Los_Angeles) — full completed day

```
ARM A (control) — NOEL-ONLY · "what should I work on next?"
  primary calendar (10 blk, 5h25m): morning exercise · Neochrome check-ins ·
    MacNerd add news · Post Binoid Kanban for Elan · Noel/Matt · Weekly Joyce/Noel ·
    1:45 Team Call · Rebalance calibrate project-def · Rebalance test remote repos · EOD
  GitHub authored (login=noelsaw1, git-pulse EXCLUDED, dashboard-matched):
    ask-self          9 commits  🤖claude  PRs #38/#37/#36/#35/#33
    sleuth-app       15 commits  🤖claude  PRs #310/#309/#308, issue #307
    goaffpro-fork     4 commits  🤖claude  PR #4(open)/#2/#1, issue #3 (HPOS incompat)
    LTVera-Pandas     4 commits  🤖claude  PR #17 (P20 Customer Decisioning), issues #16/#15
    rebalance-OS      2 commits +1 comment  🤖claude 🤖codex  PRs #58/#57/#49
    universal-child-theme               issues #874/#872/#871
  Vault notes (3): 0. Incoming · Ltvera Reference Model · Love2learn.xyz
  Sleuth (5, →by me / stale): @Matthew Mini-Cart Upsell deploy · Product Upsell→Minicart ·
    @Jose 3 LTVera WP pages · @Matthew CR CC Tenant→Landlord (workflow + UI sketch)
  Email in-window: 0

ARM B = ARM A + MATT Neochrome Work Schedule (15 blk, 7h15m):
  Binoid emails/cron · Scheduled Actions Backlog · Prod Log Analysis · DB Saturation ·
  Slow Query · Incident Report (Issue #873) · WP.org forum bug reports ·
  GoAffPro Fork PR Review · Prod DB Fix—Composite Index · File Goaffpro bug ·
  bloomz STG1 plugin updates ×2 · SMTP Pro feature request
```

### Tue 2026-06-09 (tz America/Los_Angeles) — TODAY, partial (day not yet over)

```
ARM A (control) — NOEL-ONLY
  primary calendar (8 blk, 4h30m): exercise · Neochrome check-in · Pre-meeting ·
    Weekly Joyce/Noel · BW Maintenance (Matt's Zoom) · 1:45 Team Call · EOD · Broker placeholder
  GitHub authored (git-pulse excluded, dashboard-matched):
    sleuth-app       2 commits  🤖claude  PR #312 (Fable 5 aliases), #311 (memories export)
    LTVera-Pandas    6 commits  🤖claude  PR #17 (P20)
    universal-child-theme  2 commits +1 comment  🤖claude  PR #860 (/rca skill — WPE incident RCA)
    photoapp-webapp-new                  issue #171 (login error, Mac Safari)
    goaffpro-fork    1 comment            PR #2
  Vault notes (6): 0. Goals · 0. Today's Notes · Project Registry · Meetup Group · rebalanceOS Dashboard · Yesterday
  Sleuth (27 active): @Mike category bubbles · review PR→push Binoid · restore Prod→Dev ·
    Shipping Tracker plugin · @Samuel WP→BigQuery sync bundle (LTVera-Pandas) · …(27 total)
  Email in-window: 0

ARM B = ARM A + MATT Neochrome Work Schedule (12 blk, 9h00m):
  Slack&Emails · Email Matt G/Rebekah/John re WPE DB op · Cron research ·
  HPOS theme-of-week ×2 · Review+merge/close Binoid PR 860 · deterministic analysis scripts ·
  Goaffpro review PR#4 · premium plugins · stg1 checkout testing
```

### Wed 2026-06-10 (tz America/Los_Angeles) — TOMORROW, calendar-only (no activity yet)

```
ARM A (control) — NOEL-ONLY
  primary calendar (9 blk, 5h40m): exercise · Neochrome check-in · **Deployment Day** ·
    Physical therapy · 1:45 Team Call · Sleuth Team Call · NN Weekly · Blocked · EOD
  GitHub authored: (none)   Vault: (none)   Sleuth: (none)   Email: (none)
  ^ Correct & expected — 06-10 hasn't happened yet. (The OLD harness wrongly showed 169
    git-pulse + repo commits here; that was github_activity.scan_date stamped in UTC
    on the 06-09-evening scan, NOT real 06-10 work.)

ARM B = ARM A + MATT Neochrome Work Schedule (4 blk, 3h25m):
  Slack&Emails · **Neochrome Team — Review stale Binoid PRs** · Binoid NMI extend Customer Vault
  ^ On a planning day, Matt's calendar is the ONLY actionable team signal — strong for H2.
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

**2026-06-09 (later still) — harness rebuilt on the dashboard path; gate thresholds set.**
- **GitHub mismatch root-caused & fixed.** The old harness read `github_activity` — a *scan-snapshot* table that buckets a rolling ~30-day fetch under `scan_date = scanned_at[:10]` (the **scan-run date, in UTC**) and includes bot/auto-commit repos. Rebuilt the harness on `pulse._query_day_activity()` over the granular `github_commits/items/comments` tables (tz-aware day window + author/bot filter) — now matches the dashboard exactly. `rebalance-git-pulse` confirmed **absent** from the granular tables (it only ever lived in the scan-snapshot); an explicit `NOISE_REPOS` guard was added anyway.
- **Arm A completed.** Obsidian vault notes + Sleuth reminders now come from the same assembler; **email** added via a per-day `email_messages` query. (Note: "vault todos" = recently-modified vault notes — there is no checkbox/task-extraction table; true todo parsing is a separate future enhancement.)
- **Validation.** Re-ran 06-08/09/10: 06-08 full, 06-09 (today) partial, **06-10 (tomorrow) correctly calendar-only** — confirming the tz-aware windowing and exposing the old "06-10" GitHub rows as a UTC scan-date artifact. Corrected bundles re-captured above.
- **Gate thresholds set** (per Noel's delegation): conjunctive 3-metric rule, two independent judges, B-only precision floor — see [0e](#0e-decision-rule-kill--continue). Honest that N≈5 ≠ statistical significance.
- **Remaining for the gate:** blind/randomize the output (last 0b item), generate ~5 *completed*-day bundles, run the two-judge blinded scoring.
