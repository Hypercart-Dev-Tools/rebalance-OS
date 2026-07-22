---
title: "MARATHON — 2026-07-21 (4 disjoint Python fixes + carried-forward Focus5Float lane)"
status: "Planned, not fired. Built 2026-07-21 by a marathon-triage + doc-hygiene pass that found every other 'active' marathon artifact in 2-WORKING had already fired and merged (see below) and only one lane (Focus5Float resolution resilience, ex-MARATHON-2026-07-07 Lane C) was genuinely un-fired. 4 new GH-issue-backed lanes added after a full open-issue backlog sweep."
created: 2026-07-21
updated: 2026-07-21
owner: noel@neochro.me
roadmap_exempt: true
goal: >
  Consolidate the one real un-fired lane in the repo (Focus5Float display-resolution resilience)
  with 4 newly-verified, disjoint, low-risk GH issues from a full backlog sweep, replacing the
  90%-dead MARATHON-2026-07-07.md. All 5 lanes verified path-disjoint against current code.
  roadmap_exempt: coordination artifact; the tracked deliverables are #8 / #171 / #167 / #189 and
  the Focus5Float resolution-resilience doc, each with their own ROADMAP.md queue pointer.
---

# MARATHON — 2026-07-21

## Status

| What was just completed | What's next |
|---|---|
| **Triage + doc-hygiene pass (2026-07-21):** every "active" marathon doc in `PROJECT/2-WORKING` except one turned out to already be merged — `MARATHON-2026-07-16-B` (PR #134), `MARATHON-2026-07-17`/GH-135 (PR #143), `MARATHON-2026-07-18-COLLECTORS` (PR #147), `SIGNAL-HEALTH-NUANCE`/2026-07-18-signal-health (PR #158), and `GH-156-CLIO-PROJECTION-MARATHON` (PR #176, a CRITICAL data-loss fix that was live-fixed but tracked as "not fired" in ROADMAP.md). All 5 archived to `3-COMPLETED` with corrected status text; `ROADMAP.md` pointers fixed. Only Focus5Float resolution resilience (`MARATHON-2026-07-07` Lane C) was genuinely un-fired — extracted here unchanged as p5. A full open-issue backlog sweep (2 parallel research agents, 26 untracked issues + re-verification of every issue named in an existing doc) surfaced 3 READY, verified-against-current-code candidates (#8, #171, #167) plus one newly-diagnosed-but-unfiled gap from GH-135's own acceptance notes, filed as #189. All 5 lanes confirmed mutually path-disjoint. | **Fire this plan.** Run `.xyz/relay-automation/marathon.sh --plan PROJECT/2-WORKING/MARATHON-2026-07-21/MARATHON.yaml --dry-run` first (see MARATHON.yaml header for the exact `--pre-advance-cmd`), then fire for real once dry-run is clean. On completion: update each lane's ROADMAP.md pointer, flip this file's Status table, and reconcile GH issue closure (operator action, per repo convention). |

## Lanes

| Lane | Issue | Why it's valid + reproducible | Why it's ready |
|---|---|---|---|
| p1 | [#8](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/8) | Verified live 2026-07-21: `daily_report.py:230` and `calendar.py:594` still filter with `DATE(start_time)`; `querier.py:107` still does naive string-boundary comparison. The issue's own suggested reference file (`simple_report.py`) no longer exists — brief flags this so the phase doesn't chase a dead pointer. | Small, 3 call sites, one fix pattern (UTC-range boundary via `tz_utils.local_tz()`), no storage/migration risk (Option B, not A). |
| p2 | [#171](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/171) | Verified live 2026-07-21: `sync_github_repo()` and 3 other `db_connection(...)` blocks in `github_knowledge.py` wrap network fetches inside the write transaction, matching the issue's `lsof`/`sample` evidence exactly. | Single-function-shaped fix (fetch-then-write), pattern already proven by GH-169's batch-commit backfill in the same module family. |
| p3 | [#167](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/167) | Verified live 2026-07-21: `backfill_semantic_documents()` (`semantic_index.py:484`) and the `github_documents_missing_from_semantic` drift counter (`index_ops.py:633`) both still exist and match the issue's evidence. | Bounded: characterize-then-fix-then-backfill, with an explicit "state findings before patching" invariant so it can't silently guess wrong. |
| p4 | [#189](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/189) | Filed today off GH-135's own "Residual gaps" acceptance notes — both defects re-confirmed live 2026-07-21 at current line numbers (`doctor.py:1192`, `pulse_web.py:1039`), which had shifted since GH-135 shipped. | Fully pre-diagnosed, small, reuses GH-135's own established patterns (`format_timestamp`, org-stripping convention). |
| p5 | — (Focus5Float resolution resilience) | Carried forward unchanged from `MARATHON-2026-07-07` Lane C. Root-caused with file:line detail in `FOCUS5-RESOLUTION-CHANGE-RESILIENCE.md`; `clampPanelToVisibleScreen()` confirmed still absent from `ContentView.swift` as of 2026-07-21. | Fully spec'd Phase 1 contract, no GH issue needed (predates issue-per-lane convention), different toolchain (Swift) guarantees disjointness from p1-p4. |

## Disjointness (tick literal-prefix rule)

| Lane | Paths |
|---|---|
| p1 | `src/rebalance/ingest/calendar.py`, `src/rebalance/ingest/daily_report.py`, `src/rebalance/ingest/querier.py` |
| p2 | `src/rebalance/ingest/github_knowledge.py`, `scripts/github_sync.sh` |
| p3 | `src/rebalance/ingest/semantic_index.py`, `src/rebalance/ingest/index_ops.py` |
| p4 | `src/rebalance/doctor.py`, `scripts/pulse_web.py` |
| p5 | `macOS/Apps/Focus5Float/Sources/Focus5Float/Focus5FloatApp.swift`, `.../ContentView.swift`, `.../SelfTest.swift` |

All five write surfaces are disjoint — different modules within `src/rebalance/ingest/` (p1/p2/p3
touch different files within that package, verified no shared file), a standalone doctor/dashboard
pair (p4), and a different language/toolchain entirely (p5, Swift/macOS). Per marathon.sh's actual
behavior (confirmed by every prior plan's header comment in this repo), phases still run **one at a
time in declared order** — there is no wave/parallel/worktree machinery — so this disjointness
buys correctness (safe to reorder, safe to skip a phase), not wall-clock.

## Firing

```bash
.xyz/relay-automation/marathon.sh \
  --plan PROJECT/2-WORKING/MARATHON-2026-07-21/MARATHON.yaml \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k "calendar or daily_report or querier or github_scan or github_client or github_knowledge or semantic_index or index_ops or doctor or pulse_web" -q && (cd macOS/Apps/Focus5Float && swift build 2>&1 | tail -20)' \
  --dry-run
```

Drop `--dry-run` to fire for real once the dry-run is clean. Run **vendored** (`.xyz/…`), matching
every prior plan in this repo — a non-vendored run cost the 2026-07-18 signal-health marathon its
P3 (see that plan's own header for the postmortem).

## Hard invariants (carry into the session prompt)

- [ ] p1 does not touch `sync_calendar()`'s storage format (Option B fix, not Option A/migration).
- [ ] p2 does not change what data is collected or how it's fetched — transaction-boundary fix only.
- [ ] p3 characterizes the 302-document gap with concrete evidence before patching — no blind fix.
- [ ] p4 reuses `format_timestamp()`/`tz_utils.py` and GH-135's existing org-stripping convention —
      no new time module, no new stripping rule. Sleuth reminder body text is explicitly untouched.
- [ ] p5 is Phase 1 only (core fix) — Phase 2 (multi-display edge cases) stays out of this fire.
      Autosave name unchanged; observer holds `[weak self]`.
- [ ] All 5 lanes stay disjoint per the table above — verify before firing if any brief changes.
- [ ] On finish: this file's Status table + `updated:` updated; ROADMAP.md pointers for #8/#171/
      #167/#189 added (queue entries, since none had a dedicated project doc before this plan) and
      the Focus5Float doc's own status table updated; GH issue closure stays an operator action.
