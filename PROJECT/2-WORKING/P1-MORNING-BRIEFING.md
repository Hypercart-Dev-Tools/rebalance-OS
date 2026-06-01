---
title: Morning Briefing
status: Phase 0 complete (GO) — 2026-05-31
priority: P1
owner: Noel
created: 2026-05-31
updated: 2026-05-31
model: claude-haiku-4-5
targets:
  - GitPulse repo README (read 2–3×/day)
  - Web app dashboard (top of page)
depends_on:
  - GitHub balance + project registry (priority tiers)
  - Sleuth/Slack reminders sync
  - Gmail ingest
  - Calendar sync
design_principle: >
  Deterministic script owns facts and recall. The LLM owns ranking, judgment,
  and prose. The LLM never invents a task, a deadline, a commit, or an email —
  it only ranks and narrates rows the collector handed it, and cites the source
  of every line.
---

# Morning Briefing

> Status: **Phase 0 complete (GO).** Single-shot collector spike runs in ~0.04s and produces a real multi-source briefing; see Phase 0 findings. Synthesis seam wired for Haiku (pending API key). Next: Phase 1 deterministic collector + closing the sleuth/calendar/email sync gaps.
> Goal: every morning, surface what to pick back up, what's due, and what came in overnight — a forward-looking sibling of the backward-looking Git Pulse recap. Suggestions are grounded in the high-quality signals the apps already produce (project priority tiers, GitHub momentum, Sleuth/Slack tasks, important email, calendar).
> Reading order: Phase 0 → gate → Phase 1 → Phase 2 → delivery (Phase 3 GitPulse README, Phase 4 dashboard). Each phase has a go/no-go gate; nothing downstream starts until the prior phase lands and this doc is updated with findings.
> Architecture in one line: **deterministic collector (facts) → ranked candidate JSON → Haiku synthesis (judgment + prose) → render target.**

## Table of Contents

- [Background](#background)
- [Success criteria](#success-criteria)
- [Architecture](#architecture)
- [Phase 0 — Single-shot spike (simulate tomorrow from today)](#phase-0--single-shot-spike-simulate-tomorrow-from-today)
- [Phase 1 — Deterministic collector (`rebalance morning-brief --json`)](#phase-1--deterministic-collector-rebalance-morning-brief---json)
- [Phase 2 — Haiku synthesis layer](#phase-2--haiku-synthesis-layer)
- [Phase 3 — Delivery target: GitPulse README](#phase-3--delivery-target-gitpulse-readme)
- [Phase 4 — Delivery target: web app dashboard](#phase-4--delivery-target-web-app-dashboard)
- [Phase 5 — Scheduling & operations](#phase-5--scheduling--operations)
- [Open questions](#open-questions)
- [Risks to surface early](#risks-to-surface-early)

## Background

The repo already produces the hard parts; the briefing is mostly *assembly + judgment*, not new infrastructure. Reusable signal sources, all already wired as MCP tools / local SQLite:

- **What to work on** — `list_projects()` (priority_tier) ⨯ `github_balance(since_days)` for momentum. High tier + recent activity + not-yet-shipped = a strong "continue this" candidate.
- **Due / overdue** — `sleuth_sync_reminders` (Slack/Sleuth tasks with due dates).
- **Overnight inbox** — `ingest_gmail_messages`, filtered to high-signal senders/threads.
- **Today's commitments** — calendar `list_events` for the day.
- **Activity context** — `publish_pulse` already aggregates today's + yesterday's activity by source; the git-pulse exec-recap skill already turns activity into narrative. The morning brief is the *forward-looking* counterpart.

Existing render surfaces to reuse rather than reinvent: [scripts/dashboard.py](../../scripts/dashboard.py) (terminal), [scripts/pulse_web.py](../../scripts/pulse_web.py) → [web/pulse.html](../../web/pulse.html) (web), and the GitPulse repo README that publish_pulse pushes to (`pulse_target_path` in `temp/rbos.config`).

## Success criteria

- A briefing can be produced **on demand in seconds** from current local data — no waiting on a 30–40 min scheduled refresh or a slow re-embed.
- The briefing groups items into **Pick back up / Due today / Worth a look / On your calendar**, with a suggested focus order.
- **Every line cites its source row** (project, reminder id, email thread, event) — zero invented tasks or deadlines. A briefing that hallucinates a due date is a defect, not a rough edge.
- Runs on **Haiku** for cost/latency; the deterministic collector is fully testable in isolation.
- Lands at the two surfaces the user actually looks at: the **GitPulse README (2–3×/day)** and the **web dashboard top-of-page**.

## Architecture

Two layers, hard boundary between them:

1. **Collector (deterministic, no LLM):** pulls candidate signals from the sources above, applies hard rules (what's overdue, who the sender is, what changed), scores each row for salience, dedups, and emits a stable ranked JSON candidate set with `source`, `timestamp`, and numeric `salience` on every row. Testable; never lies.
2. **Synthesizer (Haiku):** consumes that JSON only, groups/ranks/narrates, proposes a focus order, and cites the source row for each line. Constrained so it can only reference rows present in the input.

Why this split: determinism where correctness matters (deadlines, senders, overdue), LLM only where fuzzy judgment helps (what's *worth* surfacing, phrasing, what to do first). Cheap and fast enough to run every morning.

## Phase 0 — Single-shot spike (simulate tomorrow from today)

**Intent:** prove the whole idea end-to-end *today*, in one shot, using existing data + the smallest possible glue. Treat "today's activity" as the stand-in for "what you'd see tomorrow morning." Optimize for seeing a real briefing in **under a minute**, not for clean code. Throwaway-friendly.

- [x] Write a scratch collector ([scripts/spike_morning_brief.py](../../scripts/spike_morning_brief.py)) that, in a single run, pulls signals from local SQLite via the canonical read paths: `registry.get_projects` ⨯ `github_scan.get_github_balance`, `sleuth_reminders` table, `email_messages` table, `calendar.get_upcoming_events`.
- [x] Dump the assembled candidate set to `temp/morning-brief-candidates.json` and eyeball it — rows confirmed real; dry/stale sources flagged explicitly (not silently emptied).
- [~] Pipe that JSON to a one-shot Claude **Haiku** call — **blocked**: no `anthropic` SDK / `ANTHROPIC_API_KEY` / `claude` CLI in this environment. The script has the Haiku seam wired (`render_haiku`, model `claude-haiku-4-5`) and falls back to a deterministic grouped render. Synthesis was validated by an agent acting as the Haiku stand-in.
- [x] **Observe wall-clock:** collector runs in **~0.03–0.04s** (vs the 30–40 min scheduled pulse path). Goal met decisively.
- [x] **Quality read:** with a 14-day window the briefing surfaced 12 projects + 30 emails (42 candidates) and correctly elevated real open PRs (sleuth-app-wp-plugin #1/#2, queryguard #34) and a Basecamp @mention. No hallucinated/uncited lines.
- [x] **Tune the "continue working on" heuristic:** momentum (commits+PRs) is currently doing all the ranking work because **every active project is `priority_tier 3`** — the tier signal isn't differentiated in the registry yet. Recorded below as the top Phase 1 knob.
- [x] **Go/no-go gate:** see findings below.

### Phase 0 findings (2026-05-31)

**Recommendation: GO for Phase 1.** The collector→candidate→render pipeline works end-to-end in well under a second; the architecture holds.

What works now:
- `github_activity` (131 rows, scanned today) + `project_registry` (12 active) → real project momentum ranking.
- `email_messages` path works; important/starred GitHub-PR notifications and @mentions surface correctly.

Gaps to close before this is a *daily* briefing (data freshness, not spike-code bugs):
- **Sleuth reminders: 0 rows** — never synced locally. "Due today / overdue" is empty. Needs `sleuth_sync_reminders` running on a schedule.
- **Calendar: 0 rows** — never synced. "On your calendar" is empty.
- **Email is stale** — latest `received_at` is 2026-05-21 (10 days old). Needs the Gmail ingest running fresh for a true overnight view.
- **Priority tiers undifferentiated** — all active projects are tier 3, so momentum dominates. Pinning a real "continue working on" score (priority ⨯ momentum ⨯ nearly-shippable) is the highest-leverage Phase 1 task.

Candidate-JSON shape (the Phase 1 contract): top-level `generated_at` / `reference_date` / `timezone` / `since_days` / `counts` / `dropped` / `source_errors` / `candidates[]`, where each candidate is `{source, id, label, salience, timestamp, detail{}}`, sorted by `salience` desc. `source_errors` is always present and explicit so a broken source is never read as "nothing to do."

## Phase 1 — Deterministic collector (`rebalance morning-brief --json`)

**Intent:** harden the spike's data-gathering into a real, tested CLI command with a stable JSON contract. No LLM in this layer.

- [ ] Add a `rebalance morning-brief --json` subcommand that emits the ranked candidate set (promote the Phase 0 shape to the documented schema).
- [ ] Implement per-source collectors with hard rules: project-momentum score, overdue/due-today reminder flags, high-signal email filter (known senders, threads you're on, keywords), today's events.
- [ ] Implement a single `salience` score per row and a deterministic sort + dedup across sources.
- [ ] Emit `source`, `id`, `timestamp`, `salience`, and a human label on every row; never drop a row silently — items filtered out are counted in a `dropped` summary.
- [ ] Unit tests: each collector against mocked source data; salience ordering; dedup; empty-source handling (briefing still renders with "nothing due" rather than crashing).
- [ ] `--since` / `--as-of` flags so the command can reproduce "what tomorrow morning would show" from any reference time (makes the simulation repeatable).

## Phase 2 — Haiku synthesis layer

**Intent:** stable, guard-railed synthesis from the Phase 1 JSON.

- [ ] Pin the synthesis prompt: groups (Pick back up / Due today / Worth a look / On your calendar), a suggested focus order, and a one-line "why" per item.
- [ ] Constrain Haiku to only reference rows present in the input; every line carries a source citation (project name / reminder id / email subject / event title).
- [ ] Add a deterministic fallback render (plain grouped list, no prose) when the model call fails or truncates — never emit a blank briefing.
- [ ] Capture cost + latency per run; confirm Haiku tier is adequate (escalate only if judgment quality demands it).
- [ ] Validation pass: run against several days of real candidate JSON and confirm zero invented items/deadlines.

## Phase 3 — Delivery target: GitPulse README

**Intent:** put the briefing where it's already seen 2–3×/day — the GitPulse repo README.

- [ ] Render the briefing to a markdown block and write it into the GitPulse README at the configured `pulse_target_path` (reuse the publish_pulse push path rather than a new mechanism).
- [ ] Place the briefing **at the very top** of the README, above the existing pulse content, with a "generated at" timestamp + timezone.
- [ ] Idempotent update: re-running replaces the prior briefing block cleanly (delimited markers), no duplication.
- [ ] Confirm a fresh pull of the GitPulse repo shows the current briefing at top.

## Phase 4 — Delivery target: web app dashboard

**Intent:** surface the same briefing at the top of the web dashboard page.

- [ ] Render the briefing block at the **top** of [web/pulse.html](../../web/pulse.html) (above existing panels), sourced from the same collector + synthesizer output — no second data path.
- [ ] Wire it into the existing [scripts/pulse_web.py](../../scripts/pulse_web.py) generation so it refreshes with the page; degrade gracefully if the briefing is missing/stale.
- [ ] Show the briefing's "generated at" time so staleness is visible.
- [ ] (Stretch) mirror into the SwiftUI dashboard once [MAC-DASHBOARD-PORT.md](MAC-DASHBOARD-PORT.md) lands — same JSON, native render.

## Phase 5 — Scheduling & operations

- [ ] Add an early-morning trigger (launchd, consistent with existing jobs, or a `/schedule` cron) that runs collector → synthesis → both render targets.
- [ ] Make the job fail loud: a collection or synthesis failure logs an explicit error and leaves the prior briefing intact rather than blanking it.
- [ ] Document the one-command manual run for on-demand briefings.
- [ ] Record run time + cost in a small log so drift is visible.

## Open questions

- **Delivery beyond README + dashboard:** also a Slack DM / email to self, or are those two surfaces enough?
- **"Continue working on" scoring:** priority-tier-driven, recency-driven, or "what's nearly shippable"? (Highest-leverage knob — pin in Phase 0.)
- **Email signal definition:** what makes an email "important" — explicit sender allowlist, threads you've replied to, or a learned signal later?
- **Timezone / run time:** what local hour is "morning," and which timezone (`pulse_timezone` in `temp/rbos.config`)?
- **History/feedback loop:** do we record which suggestions you acted on to improve ranking over time, or keep it stateless to start?

## Risks to surface early

- **Hallucinated obligations.** A made-up deadline/task is worse than omission. Hard requirement: synthesizer can only cite input rows; collector is the single source of truth.
- **Stale-but-confident briefing.** If a source is dry/unsynced, say so explicitly rather than implying "nothing to do." Show generation time everywhere.
- **Two data paths drifting.** README and dashboard must render the *same* collector+synthesizer output, not re-derive independently.
- **Cost/latency creep.** Keep synthesis on Haiku and the input pre-filtered; don't let the candidate set balloon into an expensive prompt.
- **Noise fatigue.** If the briefing surfaces too much, it gets ignored like any over-long status report. Bias toward a short, ranked, act-on-it-now list.
