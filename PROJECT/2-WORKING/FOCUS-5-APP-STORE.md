---
title: Focus 5 Native — Standalone Mac App Store Plan
doc_type: project-plan
status: not-started
owner: Noel Saw
created: 2026-06-25
updated: 2026-06-25
goal: "Turn Focus 5 Float into a truly standalone macOS app that can ship through the Mac App Store, with no runtime dependency on rebalance-OS, Python, localhost servers, or repo scripts."
priority: P2
related:
  - PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md
  - PROJECT/2-WORKING/P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md
branch: feat/focus5-native-app-store
canonical_boundary: "Single-bundle native Swift app; scan, rank, cache, settings, and folder-access flows all live inside the app sandbox/container."
rollout_rule: "Each phase must leave a buildable, launchable app or a green `xcodebuild`/`swift build`; no phase may add a runtime dependency on `rebalance serve`, Python, or a rebalance-OS checkout."
---

## Status

| What was just completed | What's next |
|---|---|
| **Direction reset captured in one canonical doc (2026-06-25).** The current `Focus5Float` app proves the menu-bar shell, floating panel, and Focus 5 interaction model, but it is still a localhost thin client over `rebalance serve`. This plan replaces the old "sell the current build directly" framing with an App Store-ready native rewrite track. | **Phase 0 — App Store viability spike.** Prove the hard boundary first: sandboxed folder picking, security-scoped bookmark restore, native repo scan/probe on a clean Mac, and a written decision on git implementation (`Process` vs embedded library) before any product rewrite starts. |

## Table of Contents

- [Goal](#goal)
- [Why A New Track Exists](#why-a-new-track-exists)
- [Target Product Contract](#target-product-contract)
- [Architecture Decision](#architecture-decision)
- [Non-Goals](#non-goals)
- [Phase 0 — Technical Spike & Store Viability](#phase-0--technical-spike--store-viability)
- [Phase 1 — Native Contract & Data Model](#phase-1--native-contract--data-model)
- [Phase 2 — Native Scan Engine & Persistence](#phase-2--native-scan-engine--persistence)
- [Phase 3 — Product Shell & Focus 5 UX Port](#phase-3--product-shell--focus-5-ux-port)
- [Phase 4 — Sandbox Hardening, Privacy & Resilience](#phase-4--sandbox-hardening-privacy--resilience)
- [Phase 5 — Store Packaging, Metadata & Submission](#phase-5--store-packaging-metadata--submission)
- [Phase 6 — Review Loop & Launch Readiness](#phase-6--review-loop--launch-readiness)
- [Open Questions](#open-questions)

## Goal

Build a **truly standalone** Focus 5 Mac app that keeps the current floating-card experience but no longer depends on any rebalance-OS runtime surface. The shipped product must be a single App Store-submittable macOS app:

- no `rebalance serve`
- no `focus5_scan.py`
- no `summarize_focus5()`
- no local `GET /focus-5.json`
- no Python runtime
- no dependency on a rebalance-OS checkout
- no runtime shell-outs to repo scripts

The current Focus 5 Float app is the **UX reference and code-harvest source**, not the runtime architecture.

## Why A New Track Exists

The current app in [PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md](PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md) is feature-complete as a local projection, but it is still a thin client. It polls `http://localhost:8787/focus-5.json`, and all meaningful work still lives in Python inside rebalance-OS.

That is the exact coupling this plan removes.

What the standalone App Store product must own itself:

- user-selected repo-root access and persistence
- repo discovery
- git status probing
- local ranking and roster generation
- local cache/state
- settings, onboarding, and failure handling

What can still be reused:

- the current SwiftUI panel/menu-bar shell
- the Focus 5 card hierarchy and interaction model
- visual tokens/components harvested from the existing macOS app
- Python behavior as a **reference implementation** for parity tests only

## Target Product Contract

The v1 product contract is intentionally narrower and more productized than the current localhost JSON mirror.

- **Single-bundle app:** one installable macOS app, no sidecar backend.
- **Local-first:** the core experience works from local repos only.
- **Sandbox-compliant access:** the user grants folder access explicitly with `NSOpenPanel`; the app persists access with security-scoped bookmarks.
- **Native storage:** app-owned local persistence inside the app container for bookmarks, cache, settings, and last-known roster.
- **No rebalance-only affordances:** no `vscode_url`, no server-start button, no assumption that the user has the repo, the CLI, or Python installed.
- **Graceful scope limits:** if optional GitHub enrichment exists later, the local ranking path still works with zero network.

## Architecture Decision

**Chosen direction: native Swift runtime, not a bundled rebalance-OS backend.**

This plan treats the Python implementation as a specification to learn from, not something to ship inside the `.app`. The shipped product should be a native Swift app that computes Focus 5 directly from user-granted folders.

Why this is the right track for the App Store build:

- bundling Python and a localhost server would keep the architectural coupling the user explicitly wants removed
- a native runtime fits the App Store review story much better than "the app launches a local web backend"
- user-selected folder access plus security-scoped bookmarks is the right macOS access model for scanning repos the user chooses
- if a helper tool is needed, Apple documents a sandboxed embedded-tool path, but the plan should prefer a single-process app unless the spike proves otherwise

**Critical gate:** do not keep any runtime dependency on rebalance-OS "just for v1." That would create a second thin-client product, not a standalone app.

## Non-Goals

- No runtime use of `rebalance serve`, `refresh_index`, `sync_focus5`, `publish_pulse`, or any other rebalance-OS script/entrypoint.
- No bundled Python interpreter, FastAPI server, or localhost HTTP dependency.
- No requirement that the user install Xcode Command Line Tools, Homebrew, or a rebalance-OS checkout.
- No cloud sync or multi-device sync in v1.
- No attempt to preserve every current card field if that field only exists because of the old server boundary.
- No "ship direct first, App Store later" split in this doc. This plan is specifically for the App Store-native track.

---

## Phase 0 — Technical Spike & Store Viability

> **Phase 0 max: 1-2 hours.** Validate the one-way doors before we rewrite anything.

- [ ] Build a minimal native spike inside the Focus 5 app target that lets the user choose a folder, persists it as a security-scoped bookmark, quits, relaunches, and restores access successfully.
- [ ] Run the spike on a clean Mac user account with no rebalance-OS checkout and no local server running.
- [ ] Probe a real git repo from the granted root and surface the minimum facts needed for Focus 5: branch, dirty/clean, ahead/behind, modified count, untracked count, last local commit timestamp.
- [ ] Compare two implementation paths for repo probing:
  - [ ] `Process`-driven git calls
  - [ ] embedded git library path
- [ ] Record the decision with explicit kill criteria: what would make the `Process` path unacceptable for App Store v1, and what would force the embedded-library path.
- [ ] Confirm the current floating panel + menu-bar shell still behaves correctly under the sandboxed spike build.
- [ ] Write Phase 0 findings back into this doc before Phase 1 starts.

### QA Checklist — Phase 0

- [ ] **Spike truth:** findings are based on a real sandboxed app run, not guessed from the current unsandboxed `swift run` path.
- [ ] **Standalone truth:** the spike proves zero dependency on `rebalance serve`, Python, or repo scripts.
- [ ] **Decision quality:** the git implementation choice is written with reversal cost, not left as a hand-wave.
- [ ] **Kill-switch:** if the spike shows App Store constraints break the core product value, pause here instead of carrying bad assumptions into Phase 1.
- [ ] **Proof artifact:** this doc includes the exact result, date, and machine context from the spike.

## Phase 1 — Native Contract & Data Model

> Freeze the product's own contract so we stop inheriting the Python route shape by accident.

- [ ] Define the native v1 entities in Swift: `RepoSnapshot`, `FocusRoster`, `OffRosterWarning`, `RankingMode`, `AppSettings`, and `GrantedRoot`.
- [ ] Declare one canonical writer for each persistence concern:
  - [ ] bookmarks/settings writer
  - [ ] local scan cache writer
  - [ ] roster/ranking writer
- [ ] Decide the v1 field set the app actually owns, including which current server-era fields disappear (`vscode_url`, server-only timestamps, rebalance-specific metadata).
- [ ] Freeze ranking semantics for the standalone app:
  - [ ] Focus 5
  - [ ] Dirty Five
  - [ ] my work / any touch if retained
- [ ] Create fixture-driven tests under `/fixtures/` for clean repo, dirty repo, ahead/behind repo, non-GitHub repo, missing remote, and empty root cases.
- [ ] Write a short parity rubric against the current Python implementation so "same behavior" is observable without making Python a runtime dependency.

### QA Checklist — Phase 1

- [ ] **Single-writer discipline:** each persisted contract has one owner in code.
- [ ] **DRY:** the native contract does not duplicate the old JSON contract field-for-field without a product reason.
- [ ] **Observable parity:** fixtures make it obvious where the Swift model matches or intentionally diverges from the Python reference.
- [ ] **Scope honesty:** any dropped field or behavior is listed here, not discovered later in UI work.
- [ ] **Proof:** tests exist before the first real scan-engine implementation starts.

## Phase 2 — Native Scan Engine & Persistence

> Replace the old Python data plane with a native local pipeline.

- [ ] Implement granted-root persistence with security-scoped bookmarks and restore on launch.
- [ ] Implement repo discovery under the granted roots with explicit bounds, ignore rules, and instrumentation.
- [ ] Implement git probing using the Phase 0 decision path.
- [ ] Build the local ranking pipeline that produces the Focus 5 roster from native scan results.
- [ ] Persist the last successful scan and last successful roster locally so the UI can cold-start instantly.
- [ ] Add structured logging/timing for root scan time, repo count, probe failures, and ranking latency.
- [ ] Add integration tests that assert on side effects, not just return values:
  - [ ] bookmark restore
  - [ ] cache write/read
  - [ ] ranking output
  - [ ] partial scan failures

### QA Checklist — Phase 2

- [ ] **No rebalance backdoor:** no code path imports, shells into, or HTTP-calls rebalance-OS at runtime.
- [ ] **Bounded behavior:** repo discovery is bounded and diagnosable; no accidental unbounded disk walk.
- [ ] **Resilience:** partial scan failures preserve good rows and surface failure examples instead of blanking the roster.
- [ ] **Observability:** timing/counters exist from day one for the critical scan path.
- [ ] **Proof:** the app can generate a roster from local repos on a clean machine with no repo checkout of rebalance-OS present.

## Phase 3 — Product Shell & Focus 5 UX Port

> Move the working UI shell onto the native data plane and remove server-era assumptions.

- [ ] Port the current floating panel/menu-bar shell onto the native model/store.
- [ ] Keep the existing high-signal Focus 5 card stack interaction model unless a product reason forces a change.
- [ ] Replace server-era empty/offline copy with standalone product copy.
- [ ] Replace rebalance-specific actions with product actions:
  - [ ] pick folders
  - [ ] rescan now
  - [ ] reveal repo in Finder
  - [ ] open remote only when one exists
- [ ] Add first-run onboarding that explains what the app reads and asks for repo-root access.
- [ ] Add settings for granted roots, ranking mode default, refresh cadence, launch at login, and optional GitHub enrichment if that scope survives.
- [ ] Keep the app buildable as a regular development build while adding the App Store target configuration.

### QA Checklist — Phase 3

- [ ] **Standalone UX truth:** no UI copy tells the user to start `rebalance serve`, run a script, or install another tool.
- [ ] **Decision-sequence design:** every repeated card/panel remains self-describing without surrounding context.
- [ ] **Accessibility:** onboarding, cards, and controls remain legible and keyboard-usable in the sandboxed build.
- [ ] **Reusability honesty:** copied SwiftUI assets remain intentional reuse, not a half-shared dependency knot.
- [ ] **Proof:** a fresh user can install the build, grant a folder, and see a real roster without outside setup.

## Phase 4 — Sandbox Hardening, Privacy & Resilience

> Turn the native build into a safe product rather than just a working prototype.

- [ ] Finalize entitlements for the App Store target and document why each one exists.
- [ ] Add explicit privacy copy for local repo paths, commit metadata, and optional GitHub tokens if network enrichment is included.
- [ ] Ensure bookmarks, settings, and cache stay inside the app container and never leak absolute paths into exported logs.
- [ ] Add failure modes for revoked bookmarks, deleted repos, permission loss, and probe failures.
- [ ] Add an offline/local-only mode guarantee: the core roster still works without network.
- [ ] Add a lightweight diagnostics surface or export path that helps debug scan failures without exposing sensitive content.
- [ ] Run a security pass for token/path masking in logs, crash output, and support exports.

### QA Checklist — Phase 4

- [ ] **Privacy truth:** the product only claims behaviors the code now enforces.
- [ ] **Sandbox truth:** access comes from user-granted roots and persisted bookmarks, not undeclared file reach.
- [ ] **No sensitive leakage:** logs and diagnostics mask paths, tokens, and email-like identifiers where appropriate.
- [ ] **Resilience:** revoked permissions or missing repos degrade into actionable states, not silent emptiness.
- [ ] **Proof:** one end-to-end permission-revocation test and one cold-start-offline test pass.

## Phase 5 — Store Packaging, Metadata & Submission

> Replace the dev bundling path with an App Store delivery path.

- [ ] Create the Xcode/App Store archive path for the native app target; the current `make-app.sh` remains a dev convenience, not the release pipeline.
- [ ] Add production app assets: icon, screenshots, menu-bar visuals, app metadata, and localized strings if needed for review readiness.
- [ ] Configure App Store Connect metadata, privacy answers, support URL, and review notes.
- [ ] Add Mac App Store packaging checks to CI or a repeatable release script.
- [ ] Run a TestFlight/internal distribution pass before submission.
- [ ] Confirm the release artifact contains no rebalance-OS codepath assumptions, localhost defaults, or developer-machine absolute paths.

### QA Checklist — Phase 5

- [ ] **Release-path truth:** the submission artifact is produced from the App Store archive path, not the ad-hoc local bundle script.
- [ ] **Metadata honesty:** App Store copy, privacy disclosures, and review notes match the shipped behavior exactly.
- [ ] **No localhost fossil:** no `127.0.0.1`, `localhost`, `rebalance`, or repo-root assumptions survive in the release config.
- [ ] **Repeatability:** another maintainer can produce the same release build from documented steps.
- [ ] **Proof:** a TestFlight/internal tester install succeeds on a Mac that never had the dev repo.

## Phase 6 — Review Loop & Launch Readiness

> Finish the human parts of shipping, not just the binary.

- [ ] Submit the app for review with a reviewer note that explains the folder-selection flow and why repo access is required.
- [ ] Triage any App Review feedback in this doc with explicit fix/no-fix decisions.
- [ ] Prepare support docs for first-run setup, permissions, and troubleshooting.
- [ ] Decide the launch policy for optional paid distribution mechanics inside the Mac App Store model.
- [ ] Run a pre-launch checklist over crash reporting, support contact, versioning, and rollback plan.

### QA Checklist — Phase 6

- [ ] **Review readiness:** reviewer instructions are specific enough that App Review can exercise the app without guesswork.
- [ ] **Support readiness:** the first support response for permission trouble or empty-state trouble is already documented.
- [ ] **Versioning:** the shipping build has the correct semver bump and changelog entry when implementation begins.
- [ ] **Proof:** the launch checklist is completed before calling the track ready.

## Open Questions

1. **Git implementation path:** Is `Process` + git acceptable for a truly standalone App Store app, or should Phase 0 force an embedded library so the app does not depend on user toolchain state?
2. **GitHub enrichment scope:** Does v1 keep optional PR/remote enrichment, or do we cut to a local-only first release and add network features later?
3. **Persistence layer:** GRDB/SQLite, SwiftData, or a smaller purpose-built store for bookmarks + roster cache + settings?
4. **Window model:** Keep the always-on-top floating utility exactly as-is for App Store v1, or soften it into a more conventional menu-bar utility if review/testing friction appears?
