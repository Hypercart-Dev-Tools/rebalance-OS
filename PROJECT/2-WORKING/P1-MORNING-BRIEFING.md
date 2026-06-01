---
title: Morning Briefing
status: Planning
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

> Status: **Planning.** No code yet. Phase 0 is a single-shot spike to see a real briefing *today*, not after a build-out.
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

- [ ] Write a scratch collector (`scripts/spike_morning_brief.py`) that, in a single run, pulls **today's** signals from already-populated local SQLite + live tool calls: top projects by `list_projects()` priority ⨯ `github_balance(since_days=1)`, open/overdue `sleuth_sync_reminders`, last-24h high-signal `ingest_gmail_messages`, and today's `list_events`.
- [ ] Dump the assembled candidate set to a single `temp/morning-brief-candidates.json` and eyeball it — confirm the rows are real and non-empty for each source (or explicitly note which source is dry today).
- [ ] Pipe that JSON to a one-shot Claude **Haiku** call with a draft synthesis prompt (group + suggest focus order + cite sources) and print the briefing to stdout.
- [ ] **Observe wall-clock:** confirm total run is seconds, not the 30–40 min the scheduled pulse path takes. Record the actual time in this doc.
- [ ] **Quality read:** does the briefing surface things you'd genuinely act on this morning? Note hits, misses, and any hallucinated/uncited lines.
- [ ] **Tune the "continue working on" heuristic** once against real output (priority-weighted vs recency-weighted vs nearly-shippable) and record which felt right.
- [ ] **Go/no-go gate:** update this doc with findings and a GO/NO-GO for Phase 1. Capture the winning candidate-JSON shape — it becomes the Phase 1 contract.

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
