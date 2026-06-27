---
title: Project Roadmap Ledger
status: Active
created: 2026-06-21
updated: 2026-06-25
branch: main
supersedes: []
synthesizes: []
goal: >
  Canonical pointer/ledger index for this repo's work. Track projects in progress, completed,
  attempted, and deferred here, and keep execution detail in the linked PROJECT/** docs.
---

<!-- PDDA ROADMAP CONTRACT — this file is a POINTER/LEDGER, not a plan body.
     Allowed: projects in progress / completed / attempted / deferred + links to PROJECT/** docs.
     NOT allowed: phase checklists, build steps, deep execution notes — put those in the project doc.
     Carve-out: a SHORT exception note is OK only when omitting it would hide an operationally critical fact.
     Enforced by utils/pdda-check-roadmap.sh (deterministic) + utils/pdda-doc-ready.sh ROADMAP rubric (LLM). -->

# Project Roadmap

> **Pointer/ledger only — not a plan body.** Execution detail lives in the linked `PROJECT/**` docs.

## Status

| What was just completed | What's next |
|---|---|
| **Focus 5 Float — Phases 0–5 complete (2026-06-25).** Read-only `GET /focus-5.json` + frozen contract (90 tests); `Focus5Float` SwiftPM package (harvested design system, `Codable` models); menu-bar agent + non-activating floating `NSPanel`; **live data** via `Focus5Client` (poll/refresh/mode/offline/tap-to-open, E2E-verified); **collapsible card UI**; and **Phase 5 packaging** — installed `/Applications` app, **launch-at-login** (`SMAppService`), READMEs, plus a top-right roster-health traffic light. Settings-window descoped (YAGNI); icon artwork pending (Figma Make). | **Next on the Mac track:** finish packaged developer install polish for the current app, then run the standalone App Store Phase 0 spike (sandboxed folder access, bookmark restore, native repo probing, and git-path decision). _Prior track:_ front-door v0.41.1 — run `rebalance config migrate-secrets` on the ~2 remaining Macs, then a `development` → `main` PR. |

## Ledger

### In progress

- `Watch-list coverage guard` — the watched-repos set is a recomputed union with no persisted history, so a repo held only by a rolling window (`activity` 14d / `pushed`) drops off the roster with no trace (the `BinoidCBD/LTVera-Pandas` "fell out" report — now confirmed `watched_and_fresh`). **COMPLETE (2026-06-26, ponytail-trimmed):** additive migration `0009` + isolated `watchlist_guard.py` (`classify_removal` + `snapshot_and_detect` single writer) at the end of `_refresh_github` (clean-sync only) + `log_watched_repos_reduced` helper + a one-line `_EVENT_BADGE` ⚠ chip on `/auth-log` (Phase 2 collapsed — the screen already renders any event). All 4 agy `[Should]` baked in. Ponytail cut the monotonic-id machinery and the `diff_watched_set` one-line wrapper + their tests. 11 guard tests; suite green; `doctor` clean; live baseline 59 watched / 24 durable-intent — LTVera-Pandas (`project`) now alarms on a silent drop. Reuses focus5 snapshot pattern / `auth_log` surface / `github-sync` piggyback — no new screen/job. **Pending:** merge PR #82, move doc to `3-COMPLETED`. → [PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md](PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md)
- `Apple Reminders unified integration plan` — read-only `apple_reminders` SQLite source, collector-first architecture with explicit QA gates. **Phases 0–1 in progress (started 2026-06-25):** access/schema spike + read-only extractor + snapshot pipeline; deliberately pausing after Phase 1, before collector registration (Phase 2). → [PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md](PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md)
- `Focus 5 Float (floating macOS card stack)` — native menu-bar app that renders the web Focus 5 roster as a vertical, collapsible card stack; reuses the `macOS/TextReplacementStudio` SwiftUI scaffolding. **Phases 0–4 complete (feature-complete):** read-only `GET /focus-5.json` + frozen contract (90 tests), `Focus5Float` SwiftPM package (harvested design system + `Codable` models), menu-bar agent + non-activating floating `NSPanel`, live data via `Focus5Client` (same `summarize_focus5()` as the web; poll/refresh/mode/offline/tap-to-open, E2E-verified), and collapsible card UI (Tree health / PR / activity, in-panel ranking toggle, ⚠ stale badge, off-roster footer). **Codex QA (2026-06-24) — 4 Should findings, fixed.** **Phase 5 complete (2026-06-25):** installed `/Applications` app (ad-hoc signed, `LSUIElement`), launch-at-login via `SMAppService` menu toggle, app + `macOS/` READMEs, icon wiring (artwork pending Figma Make), and a top-right roster-health traffic light (`FOCUS5_HEALTHTEST` self-check). Settings-window descoped (YAGNI; `FOCUS5_BASE_URL` covers config). All phases done; doc `status: complete`, pending merge to `development` + move to `3-COMPLETED`. → [PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md](PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md)
- `Focus 5 Float — Telemetry tab` — add a third tab reading health-annotated JSON from `~/Documents/telemetry/`; reuses `StatusDot`, `RosterHealth`, `Theme`; replaces binary `isDirtyView` toggle with a 3-case `ViewMode` enum. → [PROJECT/2-WORKING/P2-FOCUS5-TELEMETRY-TAB.md](PROJECT/2-WORKING/P2-FOCUS5-TELEMETRY-TAB.md)
- `Focus 5 Float — offline cache & manual server start` — resilience follow-on for when `rebalance serve` is down. **Both phases built:** (1) offline roster cache — `RosterCache` persists the last `/focus-5.json`, instant cold-start, "cached · {age}"; (2) one-click **Start server** — `ServerLauncher` resolves the binary via login-shell + spawns a detached `rebalance serve`, polls until healthy, refreshes (button in offline state/header/⌘S). Headless-verified (cache round-trip + binary resolution); `swift build` green. Operator litmus + bundled-`.app` re-verify pending. → [PROJECT/2-WORKING/P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md](PROJECT/2-WORKING/P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md)
- `Focus 5 Native (standalone Mac App Store track)` — new canonical rewrite plan for a truly standalone macOS app that keeps the Focus 5 UX but removes all runtime dependency on rebalance-OS, Python, localhost JSON, and repo scripts. **Phase 0 next:** prove sandboxed folder access, security-scoped bookmark restore, native repo probing, and the git implementation choice before rewriting the product around App Store constraints. → [PROJECT/2-WORKING/FOCUS-5-APP-STORE.md](PROJECT/2-WORKING/FOCUS-5-APP-STORE.md)

### Completed

- `Focus 5 — identity-agnostic ranking vector` ([GH-81](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/81)) — the headline board silently dropped repos whose recent local commits used a different author email. **Phases 1 & 2 complete (2026-06-24):** `rank_recent_activity` now ranks on local-commit reflog recency (`my_local_commit_ts` + recorded `recency_basis` fallback ladder, migration `0007`), and the off-roster strip + card badges explain *why* each repo ranks (recency vs the #5 cutoff, fallback basis shown). Suite green (1109); real-device proof = 24 repos no longer silently dropped. → [PROJECT/2-WORKING/GH-81-FOCUS5-RANK-VECTOR.md](PROJECT/2-WORKING/GH-81-FOCUS5-RANK-VECTOR.md)
- `Focus 5 active repos bug remediation` — root-cause trace + remediation implemented, tested, and verified live (transient Dirty Five mode, scan-root CLI setters); Phase 3 activated 2026-06-24 (`com.rebalance-os.github-sync` installed + firing hourly). → [PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md](PROJECT/3-COMPLETED/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md)
- `Team Calendar as a Signal (HiQS)` — Phase 2 v0.5 built on `development`, data-layer DoD proven, pending live validation and merge/tag. → [PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md](PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md)
- `Unified front-door, portability & auth hardening` — Phases 1–6 complete, merged to `development` (v0.41.1, PR #78). Operator-only per-machine `migrate-secrets` (~2 Macs) + deferred fleet/multi-operator scope remain; `development` → `main` PR pending. → [PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md](PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md)
- `AI-agent front door (ROUTER.md)` — added the canonical startup-order entry point (ROUTER → AGENTS → ARCHITECTURE → ROADMAP → PROJECT docs; run `rebalance doctor` / `pytest tests/` / `utils/pdda-run.sh` before claiming wins), completing the PDDA front-door layer alongside the installed `utils/pdda-*.sh` suite. → [ROUTER.md](ROUTER.md)

### Attempted

_None yet._

### Deferred

_None yet._

---

## Entry format

Use one flat bullet per item:

- `Project / track name` — one-line status summary. → `[linked project doc](PROJECT/...)`
