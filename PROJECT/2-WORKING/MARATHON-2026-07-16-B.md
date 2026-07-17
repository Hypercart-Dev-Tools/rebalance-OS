---
title: MARATHON — 2026-07-16-B (5 lanes — GH issue triage sweep, last 10 days)
status: "All 5 lanes fired, shipped, and merged to development 2026-07-16 via PR #134. GH-120/GH-121/GH-129's follow-up are fully closed; GH-123 (Phase 0+1 of 4) and GH-127 (2 of 8 sources) have real remaining scope tracked against this file, since neither has its own project doc yet."
created: 2026-07-16
updated: 2026-07-16
owner: noel@neochro.me
branch: marathon/2026-07-16-b
roadmap_exempt: true
goal: >
  Triage every GH issue opened in the last 10 days (2026-07-07 through 2026-07-16, 11 total),
  keep only the ones that are valid, reproducible/concrete, and not already resolved or
  deliberately deferred, and fire them as one path-disjoint marathon. 5 of 11 pass the bar.

  Excluded, with reason (not carried into this file):
  - #131 (daily-sync lock), #130 (UTC/local time display) — already fixed, shipped, and merged
    to `development` earlier today (PRs #132, #133). Recommend closing both on GitHub.
  - #124 (auto-promote revisit) — all 3 phases already shipped 2026-07-11; issue was
    deliberately left open for operator review/close, not further build work.
  - #128 (Claude Code Cloud ingest) — Phase 0-1 shipped dormant behind a flag; Phase 2 is
    gated on watching a data-quality grade over time, not a code task ready to fire.
  - #122 (XYZ per-issue disposition overlay) — the issue's own text calls it "largely
    redundant" with data already ingested and says it's "carried opt-in behind the toggle,
    not built by default." Valid, but explicitly deferred by its author — not marathon material.
  - #125 (HiQS unify six signals) — Phases 0-3 already complete; Phase 4 (brand/surface) is a
    large, loosely-scoped follow-on already tracked in its own 2-WORKING doc, not a fresh
    10-day-old finding sized for a marathon lane.

  Included below: #120 (diagram spec), #121 Phase 2 (Focus5Float telemetry polish — Phase 1
  already shipped today), #123 (VS Code tree view extension, Phase 0+1), #127 (source health
  measures count not quality), #129 (git-pulse daily summary self-heal/no-clobber — the
  primary fix already shipped 2026-07-14; this is the one remaining concrete follow-up).
---

# MARATHON — 2026-07-16-B

## Status

| What was just completed | What's next |
|---|---|
| **All 5 lanes fired and shipped 2026-07-16** on branch `marathon/2026-07-16-b` (5 parallel isolated worktrees, merged back with zero conflicts — path-disjointness held exactly as designed). **Lane A (GH-120):** staged `xyz_hq` + `xyz_disposition_collector` nodes added to both diagram specs, verified byte-identical, PDDA clean. **Lane B (GH-121 Phase 2):** telemetry header now labels file kind, kind-discriminator self-test added, 26/26 `swift test` green, `make-app.sh` reinstalled. **Lane C (GH-123):** new `vscode-extension/pulse-tree-view/` — TypeScript compiles clean, 9/9 mocha tests pass (corrected the lane brief's own wrong pulse-file-format assumption using the real generator source). **Lane D (GH-127):** `content_predicate` added for `email`/`github` in `_SIGNAL_HEALTH_RULES`, 3 new regression tests including the exact #125 dead-row scenario. **Lane E (GH-129):** no-clobber guard added to both `upsert_block`/`upsert_clio_block` paths, 12 new tests. Post-merge full verification on the actual merged branch (not individual lane self-reports): `pytest tests/` 1411 passed / 15 failed (pre-existing, unrelated — same `test_auto_promote.py`/`test_hiqs_pipeline.py` baseline as this morning) / 10 skipped; `rebalance doctor` clean; `pdda.sh run` clean; `swift build`+`swift test` (26/26) green; `npm run compile`+`npm test` (9/9) green. One minor housekeeping note: the VS Code extension's `mocha` dev-dependency carries a transitive high-severity advisory (`serialize-javascript`) — dev/test-tooling only, not shipped in the extension bundle, worth a `mocha` version bump later. | **Merged to `development` via PR #134 (2026-07-16).** ROADMAP.md pointers for all 5 lanes reconciled same day: GH-120, GH-121, and GH-129's shipped follow-up moved to Completed; GH-123 and GH-127 kept In progress (real remaining scope — Phase 2/3 and the other 6 sources respectively) and point at this file since neither has an individual project doc. GH-120/GH-121's own docs archived to `3-COMPLETED`. `marathon/2026-07-16-b` branch cleanup pending. |

## Why these 5 lanes

Each was independently verified against the current code, not just read off the issue text:

| Lane | Issue | Why it's valid + reproducible | Why it's ready |
|---|---|---|---|
| A | [#120](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/120) | Confirmed `ARCHITECTURE/system-diagram.json` has no `xyz_hq` node today (`grep xyz_hq` = 0 hits). Spec-only ask, no ambiguity. | Already preflighted once (2026-07-16, as part of MARATHON-2026-07-07's re-check) — carried forward since it was never fired. |
| B | [#121](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/121) Phase 2 | Phase 1 shipped today (base viewer + size ceiling, merged via PR #133). Phase 2's 3 items are already itemized in the project doc's own checklist, not re-derived here. | Small, self-contained, Swift-only — same subsystem as Phase 1, no new design questions. |
| C | [#123](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/123) | No existing `vscode-extension/` or similar directory in the repo (confirmed) — greenfield, no conflicting prior art to reconcile. The issue itself is a complete phased plan, not a vague ask. | Phase 0 (spike) + Phase 1 (MVP) scoped together below since Phase 0 alone is too thin to be a useful lane on its own. |
| D | [#127](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/127) | Verified the exact defect: `_derive_signal_health()` (`src/rebalance/ingest/index_ops.py:248`) and `_check_collector_freshness()` (`src/rebalance/doctor.py:330`) both branch only on row **count** and timestamp **age** — neither reads row content. The registry seam the issue proposes reusing (`candidates=`, `semantic_docs=`) is real and already in use 3x (`index_ops.py:1737-1787`). | Issue includes a concrete "shape of the fix" pointing at the exact right seam; one open design question (which surface reports it) resolved below rather than left blocking. |
| E | [#129](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/129) follow-up #3 only | Primary fix (day-boundary tz pin) already shipped + live-verified 2026-07-14 per ROADMAP.md. Verified the remaining gap: `synthesize()` (`utils/git_pulse_daily_synthesis.py:181`) unconditionally returns the zero-row fallback string, and `upsert_block()`/`upsert_clio_block()` (lines 88, 122) unconditionally overwrite whatever block currently exists — no check for "would this clobber a real summary with an empty one." | Concrete, testable behavior change confined to one file. Follow-up #2 (pull-before-read) deliberately **excluded** — it requires a design call on git-pull failure handling from a scheduled script that shouldn't be made unilaterally; flagging for the operator separately. |

## Disjointness (tick literal-prefix rule)

| Lane | Paths |
|---|---|
| A | `ARCHITECTURE/system-diagram.json`, `ARCHITECTURE/system-diagram.html`, `PROJECT/2-WORKING/GH-120-DIAGRAM-XYZ-INCOMING.md` |
| B | `macOS/Apps/Focus5Float/Sources/Focus5Float/ContentView.swift`, `.../SelfTest.swift`, `.../Focus5Model.swift`, `PROJECT/2-WORKING/GH-121-FOCUS5-TELEMETRY-MD-VIEWER.md` |
| C | `vscode-extension/pulse-tree-view/**` (new directory) |
| D | `src/rebalance/ingest/index_ops.py`, `tests/test_index_ops.py` |
| E | `utils/git_pulse_daily_synthesis.py`, `tests/test_git_pulse_daily_synthesis.py` |

All five write surfaces are disjoint — different subsystems (diagram JSON/HTML, Swift macOS app, a new TS extension, Python collector registry, a standalone Python utility script). Safe to run fully concurrently.

## Lane A — GH-120 architecture diagram (incoming XYZ HQ, not-active)

- **Paths:** `ARCHITECTURE/system-diagram.json`, `ARCHITECTURE/system-diagram.html`
- **Contract:** add an `xyz_hq` external source node + a staged collector/overlay node to `system-diagram.json`, marked not-yet-active (dashed/"planned" edge convention the renderer already supports), and mirror the same node set into the inlined `renderDiagram({...})` spec in `system-diagram.html` so the two don't drift. Spec only, no collector activation.
- **Acceptance:** rendered diagram shows XYZ HQ as staged/distinct, the `.json` and inlined `.html` specs match, the node is clearly not-live, only the two diagram files touched, `pdda.sh run` clean.

## Lane B — GH-121 Phase 2 (Focus5Float telemetry viewer polish)

- **Paths:** `macOS/Apps/Focus5Float/Sources/Focus5Float/ContentView.swift`, `.../SelfTest.swift`, `.../Focus5Model.swift`
- **Contract** (per the existing Phase 2 checklist in `GH-121-FOCUS5-TELEMETRY-MD-VIEWER.md`, not re-derived):
  - Header/status line names the file and its kind ("signals · N" for JSON, "markdown" for `.md`).
  - Confirm large-`.md` rendering doesn't block the main thread beyond the existing 1MB read ceiling — document the assumption if the ceiling is the actual safety mechanism.
  - Extend `SelfTest.swift` with a pure assertion mapping `foo.json` → structured and `foo.md` → text (extension-only logic, no file dialog needed).
- **Acceptance:** `swift build` green; self-test assertion passes; manual: a multi-KB `.md` renders fully and scrolls, a `.json` with many rows still renders structured; ship via `make-app.sh`.

## Lane C — GH-123 VS Code extension: native Tree View for pulse data (Phase 0 + Phase 1)

- **Paths:** `vscode-extension/pulse-tree-view/**` (new: `package.json`, `tsconfig.json`, `src/extension.ts`, `src/pulseTreeProvider.ts`, `src/pulseParser.ts`)
- **Contract:**
  - Phase 0: confirm the local pulse markdown file (from a configured `git-pulse-sync` clone path) as the data source — per the issue's own stated default, no runtime dependency on the Python venv or the `pulse-server` daemon. Validate the shape of a real pulse `.md` file against a `TreeDataProvider` design (sections: Today / Yesterday / Upcoming Meetings / Assigned Issues).
  - Phase 1 MVP: parse the local pulse file into that 4-section tree, render in a sidebar `TreeView`, add a manual "Refresh" command. No file watcher yet (Phase 2, not in scope here), no click-through to open source items yet (Phase 3, not in scope here).
- **Acceptance:** extension activates in the VS Code Extension Development Host (F5); sidebar shows the 4 sections populated from a real local pulse `.md` fixture; manual refresh re-parses; `npm run compile` (or equivalent) green; no dependency on `pulse-server` being up.
- **Out of scope:** live file-watcher refresh, click-through navigation, `.vsix` packaging — all explicitly Phase 2/3 in the issue, not this lane.

## Lane D — GH-127 source health: measure content quality, not just row count

- **Paths:** `src/rebalance/ingest/index_ops.py` (`_SIGNAL_HEALTH_RULES` at line 194, `_derive_signal_health()` at line 248), `tests/test_index_ops.py`
- **Design decision (resolving the issue's own open question):** surface this via the existing `signal_health` / freshness-status contract (`_derive_signal_health`), not a new doctor warning or auth-log badge — the issue's own text names this as "the right home." A registry-driven `content_predicate` key is added to `_SIGNAL_HEALTH_RULES`, the third use of the same collector-registry seam as `candidates=`/`semantic_docs=` (Principle 3: adding a source's predicate must not require editing `_derive_signal_health` itself).
- **Contract:**
  - Add an optional `content_predicate` (a SQL WHERE-clause fragment, e.g. `"sender_email IS NOT NULL OR subject IS NOT NULL"`) to the rule dict for **email** and **github** only — the two sources with an unambiguous "meaningful row" definition and the ones the original defect (#125's 119/124 dead email rows) actually hit. The other 6 sources are deliberately left out of this pass — noted below as a follow-up, not silently incomplete.
  - `_derive_signal_health()` runs the predicate against the same recent-rows window it already uses for `recent_row_count_7d`; if a material share (>50%, matching the "96% dead" scale that motivated the issue) of recent rows fail the predicate, status becomes `degraded` with a reason naming the fraction, overriding an otherwise-`ok` freshness verdict.
  - Sources without a `content_predicate` behave exactly as today (no behavior change) — this is additive, not a rewrite of the existing freshness logic.
- **Acceptance:** a new regression test seeds `email_messages` with rows that have fresh timestamps and high count but no sender/subject, and asserts `_derive_signal_health()` reports `degraded`, not `ok` — the exact scenario that hid for 3 weeks in #125's discovery. A second test confirms a source with real content still reports `ok`. `pytest tests/` green, `rebalance doctor` clean.
- **Explicitly not in this pass:** predicates for the other 6 sources (vault, calendar, sleuth, apple_reminders, figma, ask_self) — flagged as a natural Phase 2 once the pattern is proven on 2 sources, not built speculatively here.

## Lane E — GH-129 follow-up #3: git-pulse daily summary self-heal (no-clobber only)

- **Paths:** `utils/git_pulse_daily_synthesis.py` (`synthesize()` at line 181, `upsert_block()` at line 88, `upsert_clio_block()` at line 122), `tests/test_git_pulse_daily_synthesis.py`
- **Contract:** when `synthesize()` is about to return the zero-row fallback string (`"No git activity found today."`), and the vault file's existing block (parsed via the same `MARKER_START`/`MARKER_END` sentinels `upsert_block` already uses) is non-empty and is *not itself* the fallback string, skip the write and log a `SKIP: zero-row rerun would clobber an existing non-empty summary` instead of upserting. A first-write-of-the-day (no existing block, or an existing block that's already the fallback) is unaffected — this only guards against a **later, transient** empty run overwriting an **earlier, real** summary from the same day.
- **Acceptance:** new test — seed a vault file with a real (non-fallback) block already present, simulate a zero-row rerun, assert the file is unchanged and a SKIP is logged. A second test confirms a genuinely-first zero-row run of the day still writes the fallback normally (no regression on the documented existing behavior). `pytest tests/` green.
- **Out of scope (deliberately excluded from this marathon):** follow-up #2, "no pull-before-read" — `collect_today_activity()` shells `view.sh` with no `git pull`, so freshness depends on external sync cadence. Fixing this means deciding how a scheduled script should handle a failed/slow `git pull` (retry? skip? block?), which is a design call for the operator, not something to assume inside a marathon lane.

## Seed (coordinator — run once, after promotion)

```bash
tick log task.created MARATHON0716B-GH120-DIAGRAM --agent dispatcher --priority 20 \
  --paths "ARCHITECTURE/system-diagram.json,ARCHITECTURE/system-diagram.html" \
  --note "GH-120: add staged not-active xyz_hq node to system-diagram.json + inlined .html spec. Diagram only."
tick log task.created MARATHON0716B-GH121-PHASE2 --agent dispatcher --priority 20 \
  --paths "macOS/Apps/Focus5Float/Sources/Focus5Float" \
  --note "GH-121 Phase 2: header/status reflects kind, large-file safety note, kind-discriminator self-test. See GH-121-FOCUS5-TELEMETRY-MD-VIEWER.md Phase 2 checklist."
tick log task.created MARATHON0716B-GH123-VSCODE --agent dispatcher --priority 20 \
  --paths "vscode-extension/pulse-tree-view" \
  --note "GH-123 Phase 0+1: VS Code Tree View reading local pulse .md into a 4-section sidebar tree. Greenfield extension."
tick log task.created MARATHON0716B-GH127-SIGNALHEALTH --agent dispatcher --priority 20 \
  --paths "src/rebalance/ingest/index_ops.py" \
  --note "GH-127: add content_predicate= to _SIGNAL_HEALTH_RULES for email+github only; _derive_signal_health degrades when >50% of recent rows fail it. Registry-driven, no edit to the derive function's dispatch."
tick log task.created MARATHON0716B-GH129-SELFHEAL --agent dispatcher --priority 20 \
  --paths "utils/git_pulse_daily_synthesis.py" \
  --note "GH-129 follow-up #3 only: don't let a later zero-row rerun clobber an earlier real summary the same day. Follow-up #2 (pull-before-read) explicitly out of scope."
tick project
```

## Hard invariants (carry into the session prompt)

- [x] **Lane A** — no `src/`, no `macOS/*` — diagram files only (confirmed, only `system-diagram.{json,html}` touched); the XYZ HQ node renders as **not-active** (dashed `async` edge convention + `(planned)` labels).
- [x] **Lane B** — no change to the `.json` structured telemetry path (`JSONDecoder`/`telemetryEntries` diff-free); Phase 1's byte-ceiling behavior stays byte-for-byte unchanged.
- [x] **Lane C** — new directory only (`vscode-extension/pulse-tree-view/**`), no edits anywhere else; no dependency on `pulse-server` being up or the Python venv (reads the local rendered pulse file directly).
- [x] **Lane D** — `content_predicate` is additive (sources without one verified unaffected by 3 new tests); only `email` + `github` get one in this pass.
- [x] **Lane E** — only guards the zero-row-clobbers-real-summary case (both `upsert_block` and `upsert_clio_block` paths); does not touch the day-boundary tz fix already shipped, does not add a `git pull` call.
- [x] All 5 lanes were path-disjoint — merged back into `marathon/2026-07-16-b` from 5 isolated worktrees with **zero conflicts**.
- [x] On finish: this file's Status table + `updated:` updated. **Not yet done:** ROADMAP.md pointers for #120/#121/#123/#127/#129 (left for the operator's merge-to-development pass, matching how GH-130/GH-131's ROADMAP entries were only finalized after their own merge, to avoid re-litigating the same doc twice); GH issue closure stays an operator action per this repo's convention.
