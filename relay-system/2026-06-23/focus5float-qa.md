# RELAY · Focus5Float — Codex QA Review
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 1 / 1

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are the agent bound to it (see Setup) **and** the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup. This is an **executable artifact (Swift code)** — read the real source files and cite `file:line`; `Basis:` must be `code read` (not textual-only):
   - **Reviewer (Codex):** review the Focus5Float sources vs the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each citing `file:line` with a concrete proposed fix. Set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the code; you only append findings here.
   - **Producer (Claude):** for every open finding log a disposition (Implemented / Modified / Declined + why), make the change, then re-verify.
4. **Append ONE block** at the very bottom, directly **above** the marker line (`<!-- ↓↓↓ NEXT TURN ... -->`). Never edit earlier turns. Header it `### Round N · <Role> · <your-label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Basis:**` + `**Findings & proposals:**` (graded bullets, each with `file:line`) + `**Answers:**` + `**Commit:**`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` — `Approved` closes the relay (Reviewer only). This relay is `ROUND: 1 / 1`: if you would request changes rather than approve, set `STATUS: Escalated` and hand back to the human (no second round).
6. **Commit only the files you touched** (this log): `git commit -m "relay(focus5float-qa): reviewer r1"`, then put the short hash in your block's `Commit:` line and `git commit --amend --no-edit`.
7. **Stop.** Tell the operator your one-line result (e.g. "Approved — QA clean" or "Escalated, 2 Blockers — back to Noel").

## Setup
- Artifact under review: the **Focus5Float** macOS app — `macOS/Apps/Focus5Float/` (a standalone SwiftPM package). Key files:
  - `Package.swift` — executable target, macOS 14, resources.
  - `Sources/Focus5Float/Focus5FloatApp.swift` — `@main` AppKit lifecycle, non-activating `NSPanel` + `NSStatusItem`, poll `Timer`, menu actions.
  - `Sources/Focus5Float/Focus5Model.swift` — `@Observable @MainActor` model, async `refresh()`/`setMode()`, offline/stale state.
  - `Sources/Focus5Float/Focus5Client.swift` — `URLSession` read-only GET of `/focus-5.json`.
  - `Sources/Focus5Float/Focus5JSON.swift` — shared `JSONDecoder` (snake_case).
  - `Sources/Focus5Float/Models.swift` — `Codable` wire models.
  - `Sources/Focus5Float/ContentView.swift` — SwiftUI collapsible card stack, in-panel controls.
  - `Sources/Focus5Float/Components.swift`, `Theme.swift`, `Toast.swift`, `Time.swift`, `SampleData.swift`, `SelfTest.swift`.
  - `Resources/sample-focus5.json` — fixture (previews/self-test only).
  - `CONTRACT.md` — the frozen data contract this app consumes.
  - Server side for context: `src/rebalance/web.py` `focus5_json()` (the read-only endpoint) and `src/rebalance/ingest/focus5_scan.py` `summarize_focus5()` (the shared source the web `/focus-5` also uses).
- Definition of Done — the app is correct and safe on these axes:
  1. **Swift correctness** — no logic bugs, force-unwraps that can crash, decode mismatches vs `CONTRACT.md`, or dead/incorrect optionals.
  2. **Concurrency / `@MainActor` safety** — `Task`/`Timer` closures capturing `self`, actor-isolation violations, data races, retain cycles, UI mutated off-main.
  3. **Read-only data contract** — the client only ever issues `GET`, performs **no** ranking/git/DB logic in Swift (server owns it), and honors the local-only field posture in `CONTRACT.md`.
  4. **SwiftUI / AppKit lifecycle** — `NSPanel`/`NSStatusItem`/`NSHostingView` setup, first-mouse/non-activating behavior, poll-timer lifecycle/teardown, view-state vs model-state separation.
- Producer: Claude (Opus 4.8)   ·   Reviewer: Codex CLI
- Handoff: automated (relay-drive.sh + codex-turn.sh)
- Started: 2026-06-23

## Ground rules
- Read the **real** Swift files under `macOS/Apps/Focus5Float/Sources/Focus5Float/` — cite `file:line`. `Basis: code read`.
- Grade every finding (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`) and give a concrete proposed fix.
- The reviewer does **not** edit code — append findings to this file only.
- One round trip. If not Approvable, set `STATUS: Escalated` and hand back to the human.
- Context: `swift build` is currently green; the live client was verified end-to-end (`FOCUS5_LIVETEST`) returning the same 5 repos as the browser `/focus-5`.

## Log

### Round 1 · Producer · Claude (Opus 4.8) · 2026-06-23
**Did:** Built Focus5Float Phases 0–4 — read-only `/focus-5.json` endpoint reusing `summarize_focus5()`, SwiftPM package harvesting the TextReplacementStudio design system, non-activating floating `NSPanel` + menu-bar agent, live `Focus5Client` (poll/refresh/mode/offline/tap-to-open), and the collapsible card UI. `swift build` green; headless live decode confirmed parity with the web `/focus-5`.
**For the reviewer (Codex):** Please QA the sources against the Definition of Done above — especially (2) `@MainActor`/Task/Timer concurrency + retain cycles, (3) the read-only/no-Swift-ranking contract, and (4) the AppKit panel/timer lifecycle. Cite `file:line` and propose concrete fixes. Verdict + Escalate if any `[Blocker]`/`[Should]` remain.
**Re-review this:** all of `macOS/Apps/Focus5Float/Sources/Focus5Float/*.swift` + `CONTRACT.md`.
**Commit:** (seed)

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->
