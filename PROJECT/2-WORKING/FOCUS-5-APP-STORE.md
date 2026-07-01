---
title: Focus 5 Native — Standalone Mac App Store Plan
doc_type: project-plan
status: active
owner: Noel Saw
created: 2026-06-25
updated: 2026-07-01
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
| **Phase 0-R Sandboxed Re-spike PASSED (2026-07-01).** All five Phase 0-R remediation gates + all five Phase 0 QA gates now observed, not asserted, via a codesigned `.app` under `com.apple.security.app-sandbox`: `Process`→git empirically blocked (`xcrun: error: cannot be used within an App Sandbox.`), in-process **libgit2 1.7.2** returns the full typed fact set (incl. last-commit timestamp) on a permitted path, security-scoped bookmark round-trip verified in-sandbox. Evidence: [`macOS/Apps/Focus5Native/PHASE-0-R-FINDINGS.md`](../../macOS/Apps/Focus5Native/PHASE-0-R-FINDINGS.md); reproducer `build-and-run-sandboxed.sh`. **Key finding:** the SwiftGit2 SPM shortcut is iOS-only for macOS — Phase 2 must produce a macOS-sliced libgit2. | **Phase 1 — Native Contract & Data Model.** Phase 0/0-R are closed; freeze the native v1 entities (`RepoSnapshot`, `FocusRoster`, `OffRosterWarning`, `RankingMode`, `AppSettings`, `GrantedRoot`). Carry two Phase-0-R follow-ups forward: (a) source a **macOS-sliced libgit2** (Phase 2), (b) `restoreBookmark()` must call `stopAccessingSecurityScopedResource()`. |

## Table of Contents

- [Goal](#goal)
- [Why A New Track Exists](#why-a-new-track-exists)
- [Target Product Contract](#target-product-contract)
- [Architecture Decision](#architecture-decision)
- [Non-Goals](#non-goals)
- [Phase 0 — Technical Spike & Store Viability](#phase-0--technical-spike--store-viability)
- [Phase 0-R — Spike Remediation](#phase-0-r--spike-remediation-2026-06-29)
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

- [x] Build a minimal native spike inside the Focus 5 app target that lets the user choose a folder, persists it as a security-scoped bookmark, quits, relaunches, and restores access successfully.
- [x] Run the spike on a clean Mac user account with no rebalance-OS checkout and no local server running.
- [x] Probe a real git repo from the granted root and surface the minimum facts needed for Focus 5: branch, dirty/clean, ahead/behind, modified count, untracked count, last local commit timestamp.
- [x] Compare two implementation paths for repo probing:
  - [x] `Process`-driven git calls
  - [x] embedded git library path
- [x] Record the decision with explicit kill criteria: what would make the `Process` path unacceptable for App Store v1, and what would force the embedded-library path.
  - **DECISION:** We MUST use the embedded-library path (e.g., `SwiftGit2` / `libgit2`).
  - **KILL CRITERIA MET (empirically confirmed 2026-07-01):** The App Store enforces strict sandboxing (`App Sandbox`). A sandboxed Mac app cannot spawn `/usr/bin/git` — the Phase 0-R re-spike ran it inside the sandbox and captured the verbatim failure `xcrun: error: cannot be used within an App Sandbox.` In-process libgit2, by contrast, returns the full fact set on a permitted path. `Process` + `system git` is a non-starter; embedded, in-process git probing is required.
  - **⚠ REVERSAL-COST NOTE (Phase 0-R finding):** "just add `SwiftGit2` via SPM" does NOT work for native macOS. `SwiftGit2` 0.6.0 has no `Package.swift` (Carthage-only); the SPM fork `light-tech/SwiftGit2` pulls a `Clibgit2` xcframework that is **iOS-only** (`ios-arm64`/sim/maccatalyst — no macOS slice, verified via its Info.plist). The Phase 0-R probe linked Xcode's internal arm64 `libgit2.dylib` (1.7.2) as a **spike stand-in only — not shippable**. **Phase 2 must budget for producing a macOS-sliced libgit2** (xcframework, or `systemLibrary` + a bundled dylib).
- [x] Confirm the current floating panel + menu-bar shell still behaves correctly under the sandboxed spike build.
- [x] Write Phase 0 findings back into this doc before Phase 1 starts.

### QA Checklist — Phase 0

> **All five PASSED 2026-07-01** via the Phase 0-R sandboxed re-spike (evidence: `macOS/Apps/Focus5Native/PHASE-0-R-FINDINGS.md`).

- [x] **Spike truth:** findings are from a real sandboxed, codesigned `.app` run — not the unsandboxed `swift run` path.
- [x] **Standalone truth:** the probe harness (`Focus5Probe`) runs headless with zero dependency on `rebalance serve`, Python, or repo scripts — in-process libgit2 only.
- [x] **Decision quality:** the embedded-libgit2 choice now carries an explicit reversal cost (the SwiftGit2 SPM shortcut is iOS-only for macOS — see the decision note below).
- [x] **Kill-switch:** the App Store constraint was empirically probed, not assumed; the core product value (native repo probing) is achievable in-sandbox via libgit2, so proceeding is justified.
- [x] **Proof artifact:** exact A/B/C result, date (2026-07-01), and machine context (Swift 6.2.4 / Xcode 26.3, ad-hoc sign) recorded in `PHASE-0-R-FINDINGS.md`.

## Phase 0-R — Spike Remediation (2026-06-29)

> QA review of the Lane C spike (commit `93d73b3`, `macOS/Apps/Focus5Native/`).
> All 8 Phase 0 build boxes were checked, but **none of the 5 Phase 0 QA gates
> are** — and the gaps are load-bearing. The decision Phase 0 reached (embedded
> `libgit2`) is *probably* right, but the spike **did not prove it**; it asserted
> it. A spike exists to walk the one-way door, not reason about it from the safe
> side. Re-run sandboxed before any of Phase 1 starts.

**Findings (what the review surfaced):**

- **The spike is not sandboxed — so it proves nothing about the App Store boundary.** `Package.swift` is a plain `executableTarget`: no `com.apple.security.app-sandbox` entitlement, no entitlements plist, no codesigned `.app`. The code's own comment concedes it: *"a pure swift package executable is unsandboxed by default."* Every "validated under sandbox" claim (folder access, bookmark restore, panel behavior) was actually observed **outside** the sandbox — exactly what QA gate "Spike truth: not guessed from the unsandboxed `swift run` path" forbids.
- **`Process` failure was asserted, not observed.** The spike *successfully* shells out to `/usr/bin/git` (unsandboxed) and then concludes `Process` is a "non-starter" by reasoning about sandbox rules. The kill criterion ("what makes `Process` unacceptable") was never empirically triggered. Conclusion likely correct; **evidence absent**.
- **The embedded-git path was never spiked.** "Compare two paths → embedded git library `[x]`" overstates: there is zero `SwiftGit2`/`libgit2` code, no dependency in `Package.swift`, no probe. The actual risky unknown — *does `SwiftGit2` build and link under the App Sandbox, and return branch/ahead/behind/dirty/last-commit in-process?* — is completely untouched, yet the plan now commits to it.
- **The "minimum facts" were not extracted.** `scanRepo` dumps raw `git status --short --branch` text into a string. None of branch / ahead / behind / modified / untracked are parsed, and **last-commit timestamp is never fetched at all** — so the `[x]` "surface the minimum facts" overstates what exists.
- **No proof artifact + no clean-account evidence.** QA gates "real result, date, machine context" and the build box "run on a clean Mac user account with no rebalance checkout" have no recorded output. Resource hygiene is also incomplete: `restoreBookmark()` never calls `stopAccessingSecurityScopedResource()` (acknowledged in a comment) — acceptable for a spike, fix before Phase 2.

### QA gate — Remediation

> **PASSED 2026-07-01** (re-spike by the marathon MARATHON-A lane). Full evidence in
> [`macOS/Apps/Focus5Native/PHASE-0-R-FINDINGS.md`](../../macOS/Apps/Focus5Native/PHASE-0-R-FINDINGS.md);
> one-command reproducer: `macOS/Apps/Focus5Native/build-and-run-sandboxed.sh`.
> Machine context: Swift 6.2.4 / Xcode 26.3, ad-hoc codesign (no Developer ID
> identity present — ad-hoc still enforces the App Sandbox locally).

- [x] **Sandboxed build exists:** spike runs as a codesigned `.app` with `com.apple.security.app-sandbox` + `files.user-selected.read-write` embedded/confirmed — not `swift run`. Sub-finding: a bare Mach-O CLI carrying the sandbox entitlement SIGTRAPs in `_libsecinit_appsandbox` before `main`; the sandbox requires a real `.app` bundle/container — so App Store packaging must be a bundle.
- [x] **Kill criterion observed, not asserted:** `Process` → git run **inside** the sandbox fails verbatim with `xcrun: error: cannot be used within an App Sandbox.` (`/usr/bin/git` is an xcrun shim; xcrun refuses inside the sandbox). Empirically dead, not reasoned.
- [x] **Embedded path proven viable:** in-process **libgit2 1.7.2** returns the full fact set on a permitted path (`branch=main ahead=0 behind=0 modified=1 untracked=1 dirty=true lastCommitUnix=…`, incl. last-commit timestamp); returns empty on a non-granted path — proving the file boundary, not the library, is the constraint. **Caveat:** linked via Xcode's internal arm64 `libgit2.dylib` as a spike stand-in — see the reversal-cost note at the Phase 0 decision; **not shippable as-is**.
- [x] **Structured facts, not raw text:** typed `RepoFacts` extracted in-process ([`Sources/Focus5Core/GitProbe.swift:11`](../../macOS/Apps/Focus5Native/Sources/Focus5Core/GitProbe.swift#L11)), not a raw `git status` string dump.
- [x] **Proof artifact written back:** exact A/B/C results, date, and machine context recorded in `PHASE-0-R-FINDINGS.md`; the line 124–125 decision is re-confirmed against the empirical result (with the macOS-libgit2 reversal-cost note added below).
- [x] Phase 0-R passed → Status "What's next" advances to **Phase 1**. **Non-blocking follow-up carried to Phase 2:** `Focus5Native.swift` `restoreBookmark()` still omits `stopAccessingSecurityScopedResource()`.

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

1. ~~**Git implementation path:** Is `Process` + git acceptable for a truly standalone App Store app…~~ **RESOLVED 2026-07-01 (Phase 0-R):** `Process`+git is empirically dead in the sandbox (`xcrun: error: cannot be used within an App Sandbox.`); embedded in-process **libgit2** is required. Remaining sub-question moved to Phase 2: sourcing a **macOS-sliced** libgit2 (the SwiftGit2 SPM path ships only iOS slices).
2. **GitHub enrichment scope:** Does v1 keep optional PR/remote enrichment, or do we cut to a local-only first release and add network features later?
3. **Persistence layer:** GRDB/SQLite, SwiftData, or a smaller purpose-built store for bookmarks + roster cache + settings?
4. **Window model:** Keep the always-on-top floating utility exactly as-is for App Store v1, or soften it into a more conventional menu-bar utility if review/testing friction appears?
