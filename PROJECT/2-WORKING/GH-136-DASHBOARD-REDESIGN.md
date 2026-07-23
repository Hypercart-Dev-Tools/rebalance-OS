---
title: Pulse dashboard redesign — master project (one module per day)
status: "Working — Day 0 (cross-module consistency, GH-135) merged 2026-07-18 via PR #143; Day 1 (Calendar, GH-137) shipped as 09be427, also on development. Remaining modules not started. This doc is the program ledger + the standing invariants each day inherits."
gh_issue: 136
owner: Noel
created: 2026-07-18
updated: 2026-07-22
branch: marathon/2026-07-17
supersedes: []
synthesizes:
  - PROJECT/3-COMPLETED/GH-135-PULSE-DASHBOARD-CONSISTENCY.md
  - PROJECT/1-INBOX/dashboard-redesign-2026-07-17/claude-code-cleanup-prompt.md
goal: >
  Redesign the Pulse "Today" dashboard one module per day, against design briefs and
  mockups produced by Claude Design ("Dashboard design consistency review - NN"). Each
  day gets its own GH issue and capture doc; this file is the program ledger and, more
  importantly, the home of the standing invariants — so each module starts from the
  accumulated rules rather than re-deriving or re-breaking them.
---

# Pulse dashboard redesign — master project (GH-136)

## Status

| What was just completed | What's next |
|---|---|
| **Day 0** (GH-135, cross-module consistency) merged to `development` 2026-07-18 via PR #143, and **Day 1** (GH-137, Calendar day-grid) shipped as `09be427` — both verified on `development`, correcting this doc's earlier "unmerged" claim. Day 0's 2 residual acceptance gaps were split out as [#189](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/189). | **Day 2 is [#154](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/154)** (theme colour picker) — P0–P5 built on `feat/theme-picker`, still unmerged. Every module after that is unstarted; each inherits the standing invariants below rather than re-deriving them. #189 is carried as marathon phase `p4-189-gh135-residual-gaps` (planned, not fired). |

## Contents
- [Why a master doc](#why-a-master-doc)
- [Standing invariants](#standing-invariants)
- [Verification gate](#verification-gate)
- [Module ledger](#module-ledger)
- [Carried residual gaps](#carried-residual-gaps)
- [Working method](#working-method)
- [Progress log](#progress-log)

## Why a master doc

A module-per-day cadence has a specific failure mode: each day is a fresh context, so
the same mistakes recur. Day 0 alone produced a shipped-and-reverted import shim, a
zero-width row layout that passed every test, and a reviewer that approved both. Those
aren't module-specific lessons — they're rules the *next* module needs on day one.

So this file is deliberately not a plan. It is the invariant set plus a ledger. The
execution detail for any given day lives in that day's own capture doc.

## Standing invariants

Every module's work must hold these. Each was learned from a specific incident, noted in
parentheses — the incident is the reason the rule is worth its line.

1. **One timestamp helper.** All time display goes through `format_timestamp()` in
   `src/rebalance/tz_utils.py`, composing `format_local` / `format_relative` /
   `parse_utc_iso`. Add a *variant* (as `month_day` was added for the calendar) rather
   than an inline `strftime` at a call site. Never a second time module.
   *(GH-130 centralized this; GH-135's builder nearly forked it.)*
2. **Absolute anchors a relative.** `2026-07-17 8:02 PM · 2h ago`. A bare relative never
   ships — on a static page it silently ages and a stale render is indistinguishable
   from a fresh one.
3. **One shared row.** Lists render through the shared row primitive in
   `web_components.py` with its zebra striping — not per-module markup and CSS.
   *(Pre-GH-135 there were five independent row CSS blocks in one `PAGE_CSS` literal.)*
4. **Narrow containers stack.** The 3-column anatomy (marker │ body │ right-aligned
   time) only survives above ~500px; a container query handles the rest. Do not add
   per-surface overrides. *(The nowrap timestamp starved the body column to literally
   `0px` — `grid-template-columns` resolved to `28px 0px 215.344px` in the Figma card.)*
5. **No import workarounds.** No `sys.path` manipulation, no
   `importlib.spec_from_file_location`. An import resolving to the wrong module copy is
   a worktree artifact, not a code defect. *(Shipped once, reverted in `c0d8053`.)*
6. **`web/pulse.html` is a build artifact.** Everything goes through
   `scripts/pulse_web.py` + regeneration; direct edits are silently overwritten by
   `scripts/install_pulse_web_scheduler.sh`.
7. **Geometry in constants.** Layout math (hour heights, gutters, caps) lives in named
   constants and reaches the client via `data-*` attributes, so a value has one home.
8. **Verify by rendering.** Screenshot with Playwright and *look at it*. Tests and DOM
   assertions both passed a sidebar in which every linked row had a zero-width body;
   only rendering caught it. See [[reference-playwright-install]].
9. **Presentation-only — and say so loudly when it isn't.** If a module genuinely cannot
   meet its brief without a data change, make the smallest read-only addition and flag
   it explicitly, rather than shipping a module that structurally cannot work.
   *(The calendar day grid needed today's finished events; an upcoming-only fetch could
   not supply them.)*
10. **A reviewer's approval is necessary, not sufficient.** On Day 0 the automated
    reviewer approved both defects later caught downstream. Independently verify the
    acceptance criteria against the generated artifact before calling a day done.

## Verification gate

`pytest tests/` carries **15 pre-existing failures**, all in `test_auto_promote.py` +
`test_hiqs_pipeline.py` (the documented baseline from MARATHON-2026-07-16-B). Gate on
the dashboard modules instead — a full-suite gate would block every day on unrelated debt:

```bash
python3 -m pytest tests/test_tz_utils.py tests/test_pulse_web_calendar.py \
  tests/test_pulse_web_goals.py tests/test_pulse_web_worknext.py \
  tests/test_pulse_server_figma.py tests/test_pulse_server_apple_reminders.py -q \
  && python3 scripts/pulse_web.py
```

Plus `rebalance doctor` and `utils/pdda/pdda.sh run` clean. Add each new day's test
module to the list as it lands.

## Module ledger

| Day | Module | Issue | Doc | State |
|---|---|---|---|---|
| 00 | Cross-module consistency (timestamps, shared row, headers) | [#135](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/135) | [GH-135](GH-135-PULSE-DASHBOARD-CONSISTENCY.md) | Complete, unmerged |
| 01 | Calendar | [#137](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/137) | this file | Complete, unmerged |
| 02 | Theme color picker (cross-cutting: tokenizes all pages) | [#154](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/154) | [GH-154](GH-154-THEME-COLOR-PICKER.md) | Planning |
| — | Today's Goals (3 columns) | — | — | Not started |
| — | What's Next | — | — | Not started |
| — | Recent GitHub activity | — | — | Not started |
| — | Recent Figma comments | — | — | Not started |
| — | Recently Completed | — | — | Not started |
| — | Reminders (sidebar) | — | — | Not started |
| — | Health banner | — | — | Not started |
| — | Watched repos / repo pie / open PRs | — | — | Not started |
| — | Recent emails / streams | — | — | Not started |

Module order is operator-driven — this is the surface inventory, not a committed sequence.

## Carried residual gaps

Open across days, neither owned by a completed module:

1. **Health banner emits bare relatives** (violates invariant #2). `src/rebalance/doctor.py:751`
   builds `f"last scan {age_hours/24:.1f}d ago"` as a string and hands it to the banner
   pre-formatted. `doctor.py` is not a dashboard module, so no day's brief has covered it;
   fixing it means moving that formatting decision into the render layer.
2. **Org prefixes outside GitHub activity rows.** The activity rows themselves are clean.
   What remains is in Sleuth reminder *body text* (part of the reminder's own content,
   i.e. data rather than a rendered repo label) and the repo-pie chart's legend labels.

Both are places the Day 0 brief's page-wide acceptance language reached further than the
per-module briefs it was translated into. Neither is a regression.

## Working method

- Each day: design brief + mockup → GH issue under epic #136 → build → **render and look**
  → gate → commit → update this ledger.
- Briefs live with their design assets under `PROJECT/1-INBOX/<review-folder>/`.
- A day's capture doc is only warranted when the module carries real phase structure;
  a single-module day can be recorded in its GH issue plus this ledger.
- All work currently accumulates on `marathon/2026-07-17`. `main` is protected — land via
  PR to `development`.

## Progress log

- **2026-07-18** — Master project created after Day 1, retroactively. Epic [#136](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/136)
  and Day 1 issue [#137](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/137) filed.
  Day 0 (GH-135) had run as a 4-phase marathon; Day 1 (Calendar) was built directly, since a
  single module doesn't justify the harness overhead — and the harness cost seven
  environmental failures across Day 0 for four phases of actual work. Invariants 1–10
  distilled from Day 0 + Day 1 incidents. Both days complete and pushed, neither merged.
