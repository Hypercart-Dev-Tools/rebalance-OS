---
title: Project Roadmap Ledger
status: Active
created: 2026-06-21
updated: 2026-06-29
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
| **Apple Reminders unified integration — write surface shipped + live-verified (2026-06-27).** Phases 0–5 complete: read-only SQLite collector + storage + query surface + schema-drift hardening, **plus** an EventKit write path through a signed LaunchServices helper (`rebalance apple-reminders` CLI, dry-run default; 57 tests). Focus 5 Float, its Telemetry tab, and offline-resilience are all **code-complete** (operator litmus / `.icns` / archive pending). | **Three path-disjoint build lanes** (see [the parallel queue](PROJECT/2-WORKING/MARATHON-2026-06-27.md)): (1) VS Code "focus-if-open" repo links — Phase 1 (Mac app); (2) Unified refresh **v1** (signed helper `list-active` → `/api/refresh` → reminders column); (3) Focus 5 standalone **App Store Phase 0** spike. _Prior track:_ front-door v0.41.1 — `migrate-secrets` on the ~2 remaining Macs, then a `development` → `main` PR. |

## Ledger

### In progress

- `Gemini "What to do next" → fixed vault file` — **Queued (intake, not started, 2026-06-29).** Two tasks: (1) make the daily "what to do next" actually Gemini-synthesized — Gemini reviews + rewrites the raw ranked candidates using the paid key file `/Users/noelsaw/secrets/gemini-paid-key.txt` wired into `get_gemini_api_key()`, deterministic fallback kept (today it silently runs on Qwen-0.6B and emits `<rank>. <title>` placeholder titles); (2) publish that markdown to the fixed vault file `Dashboards/What To Do Next.md`. Follow-on to the shipped next-action engine — not a competing plan. → [PROJECT/1-INBOX/GEMINI-WHATS-NEXT-VAULT.md](PROJECT/1-INBOX/GEMINI-WHATS-NEXT-VAULT.md)
- `Focus 5 Float — Apple Reminders bottom panel` — split the panel bottom into two sections: a live Apple Reminders list (10 most-recent active tasks from the default list, complete-checkbox write-back) above the relocated, now-scrollable `focus5.md` note viewer. **Decision:** the app reads/writes Reminders **directly via EventKit** (it's the signed LaunchServices bundle Phase 5.0 proved can hold the grant) — not the server (can't write, reads stale). Write scope v1 = complete-only. Phase 1 code-complete; **operator TCC litmus pending** (grant Reminders, confirm list + a working complete). → [PROJECT/2-WORKING/FOCUS5-REMINDERS-PANEL.md](PROJECT/2-WORKING/FOCUS5-REMINDERS-PANEL.md)
- `Repo links open VS Code with "focus-if-open"` — replace the window-hijacking `vscode://` URI on both surfaces so the card "Open ↗" button focuses an already-open VS Code window (or spawns exactly one). **Both phases code-complete 2026-06-29:** Phase 1 (Mac app `VSCodeLauncher`) + Phase 2 (web `POST /api/focus5/open` — server-side allowlist resolve id→path, direct-argv `code <path>`, two-layer loopback+same-origin guard, `vscode://` fallback). **agy relay QA: Approved (r2/4)** — hardened the local-only guard + `code` binary file-check per its findings; **91 tests passed**. **Next:** operator browser/GUI litmus on both surfaces. → [PROJECT/2-WORKING/VSCODE-OPEN-WORKSPACE.md](PROJECT/2-WORKING/VSCODE-OPEN-WORKSPACE.md)
- `Unified UI refresh + restart (system-wide)` — keep the always-on pulse-server as the source-freshness path so no source goes stale and no manual terminal sync is needed. **/ponytail-trimmed to a v1 (2026-06-27)** after a Codex consult QA: the `/api/restart` endpoint + Focus 5 Swift wiring are **deferred**. **v1 = make the existing Refresh button populate the reminders column via the signed EventKit helper (no FDA)** — 3 edits: helper `list-active` op → `/api/refresh` reads it (atomic, last-good-snapshot-wins, ~5s timeout) → column renders. **Next:** build v1. → [PROJECT/2-WORKING/UNIFIED-REFRESH-RESTART.md](PROJECT/2-WORKING/UNIFIED-REFRESH-RESTART.md)
- `Focus 5 Native (standalone Mac App Store track)` — new canonical rewrite plan for a truly standalone macOS app that keeps the Focus 5 UX but removes all runtime dependency on rebalance-OS, Python, localhost JSON, and repo scripts. **Phase 0 next:** prove sandboxed folder access, security-scoped bookmark restore, native repo probing, and the git implementation choice before rewriting the product around App Store constraints. → [PROJECT/2-WORKING/FOCUS-5-APP-STORE.md](PROJECT/2-WORKING/FOCUS-5-APP-STORE.md)
- `Focus 5 Float — reference-design UI refresh` — queued next pass for the floating Mac app: refresh the visual shell/card presentation against the reference set in `temp/Floating Mac app design refinement/` while preserving the current product contract (floating card stack, Focus 5 / Dirty Five / Telemetry modes, reminders panel, offline/start-server affordances). This is the same write surface as the app track, so do it only when no other `Focus5Float` writer is active. → [PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md](PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md)

### Completed

- `Apple Reminders unified integration` — read-only `apple_reminders` SQLite collector **plus** an EventKit write surface, both **shipped + live-verified (2026-06-27)**. Phases 0–4: deterministic store discovery, WAL-safe snapshot extractor (`src/rebalance/ingest/apple_reminders.py`), dynamic REMCD mapper, collector registration in `index_ops.py` + reconcile-don't-delete storage, read accessor + read-only pulse "Today" column, schema-drift health. Phase 5: signed LaunchServices helper performs EventKit create/update/complete/delete via `rebalance apple-reminders` (dry-run default, `request_id` idempotency, write serialization, three-state audit); **57 tests green**, full CRUD proven live. Deferred by choice: cross-version validation (2nd Mac), snapshot perf, notes/sections decode, Phase 6 dashboard write-back. → [PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md](PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md)
- `Focus 5 Float (floating macOS card stack)` — native menu-bar app rendering the Focus 5 roster as a collapsible card stack over live `GET /focus-5.json`. **All phases 0–5 done** (frozen contract + 90 tests, `Focus5Float` SwiftPM package, floating `NSPanel`, `Focus5Client` live data, collapsible card UI, packaged `/Applications` app + launch-at-login + roster-health light) plus a post-1.0 read-only bottom-note from vault `focus5.md`. Ready to move to `3-COMPLETED` once the `.icns` artwork lands. → [PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md](PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md)
- `Focus 5 Float — Telemetry tab` — third tab reading health-annotated JSON from `~/Documents/telemetry/`; `ViewMode` enum + orange-capable `HealthDot` + reader/model/view all shipped through Phase 2 (explicit file selection + visible decode errors). `swift build` green, `FOCUS5_SELFTEST` passes. **Operator litmus pending** (eyeball 3 demo rows), then archive. → [PROJECT/2-WORKING/P2-FOCUS5-TELEMETRY-TAB.md](PROJECT/2-WORKING/P2-FOCUS5-TELEMETRY-TAB.md)
- `Focus 5 Float — offline cache & manual server start` — resilience follow-on: offline roster cache (instant cold-start, "cached · {age}") + one-click "Start server" (detached `Process`, login-shell binary resolution, poll-until-healthy). Both phases built, `swift build` green, binary-resolution root-caused (`pipx install -e .` → `~/.local/bin/rebalance`), app icon shipped. **Operator litmus pending.** → [PROJECT/2-WORKING/P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md](PROJECT/2-WORKING/P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md)
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
