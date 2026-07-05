# RELAY · Focus5Float — top-left hide button (rebalance-OS#113)
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Producer
STATUS: Open
ROUND: 1 / 5

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are the agent bound to it (see Setup) **and** the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup (read the real files / the latest `git show <last commit>` diff; cite `file:line`):
   - **Reviewer:** review vs the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete proposed fix → set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the artifact; you only append findings here. **Before you set `Approved`, re-read the artifact file itself** (not this log) and confirm every prior `Implemented` fix is actually present and complete — any that is missing or partial → set `Changes requested` with a `[Blocker] claimed-implemented-but-absent @ file:line` instead.
   - **Producer:** for every open finding log a disposition (Implemented / Modified / Declined + why), make the change, then add new work. **Before you flip `NEXT`, re-read the artifact and confirm each `Implemented → @ file:line` actually landed in the file** — cite the line as it appears in your commit diff. A claim you can't point to in the file is not done.
4. **Append ONE block** at the very bottom, directly **above** the marker line (`<!-- ↓↓↓ NEXT TURN ... -->`). Never edit earlier turns. Header it `### Round N · <Role> · <your-label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Findings & proposals:**` (graded bullets) + `**Commit:**`; a Producer block carries `**Decisions on proposals:**` + `**Did:**` + `**Re-review this:**` + `**Commit:**`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` (`Approved` closes the relay — Reviewer only; else leave `Open`); the Producer bumps `ROUND` when opening a new cycle.
6. **Commit only the files you touched** (artifact + this log): `git commit -m "relay(focus5-hide-button): <your-label> r<N>"`, then put the short hash in your block's `Commit:` line.
7. **Stop.** Report your one-line result.

## Setup
- Artifact under review: `macOS/Apps/Focus5Float/Sources/Focus5Float/ContentView.swift` and `macOS/Apps/Focus5Float/Sources/Focus5Float/Focus5FloatApp.swift`
- Definition of Done: A hide button rendered in the top-left corner of `ContentView`'s header calls the same hide path the menu-bar "F5" item uses (`hidePanel()` → `panel.orderOut(nil)` in `Focus5FloatApp.swift`); the menu-bar toggle and Esc-to-hide keep working unchanged; the native traffic-light close button stays hidden (unchanged); the project still builds (`swift build`).
- Producer: codex   ·   Reviewer: agy
- Handoff: cli-driven (relay-xyz — codex builds, agy reviews; single-session headless)
- Started: 2026-07-05

## Task brief (for the Producer's first turn)
Implements [rebalance-OS#113](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/113). Full spec + acceptance criteria: [PROJECT/1-INBOX/GH-113-...] — this repo's issue body, summarized:

- Add a small hide/close button to the **top-left** of `ContentView`'s `header` view (around the leading edge of its top `HStack`, near line 52 as of this writing — re-verify against the live file).
- Wire it to fire the exact same hide path as the menu-bar "F5" `NSStatusItem` — i.e. reach `AppDelegate.hidePanel()` (`panel.orderOut(nil)`), not a new/parallel hide implementation. A `Notification` post that `Focus5FloatApp`'s `AppDelegate` observes, or an `onHide` closure threaded from where `ContentView` is constructed, are both acceptable — prefer whichever is the smallest correct change.
- Do **not** re-enable the native traffic-light close button (`standardWindowButton(.closeButton)` is deliberately hidden — leave that as-is).
- Match existing header button styling (see the other `Button`s already in the header `HStack`, and `Theme.Space` spacing constants).
- This is a **hide**, not a quit — the app keeps running in the menu bar afterward, and clicking the menu-bar "F5" item must still reopen the panel.
- Verify the change builds: `swift build` from the `Focus5Float` package root (or the project's existing build entry point) before claiming done.

## Ground rules
1. This file is the single source of truth. If it isn't written here, assume the other agent doesn't know it. The two agents may be different tools and never share memory.
2. Read the whole file. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns. Then update `NEXT`, `STATUS`, `ROUND` at the top.
4. Stay tight. Requests and findings are bullets, not essays.
5. **The Reviewer never edits the artifact.** It proposes graded findings, each with a concrete suggested fix where possible. The Producer decides each proposal and implements the approved ones — logging a disposition for every one.
6. Grade every finding: `[Blocker]` must fix to ship · `[Should]` strong recommendation · `[Nit]` optional · `[Pass]` checked and sound.
7. The Reviewer posts a Verdict every turn. The relay ends on **Approved**. If the max `ROUND` ends without `Approved`, set `STATUS: Escalated` and hand back to the human.
8. End your turn by committing it: `relay(focus5-hide-button): <role> r<N>`, then fill the hash into your `Commit:` line.
9. **One window at a time, clean tree at every handoff.** Never flip `NEXT` with uncommitted changes left in the tree.
10. **Evidence contract — state your proof every turn.** Producer logs `Verification:`; Reviewer logs `Basis:` (`behaviorally proven` or `textual only`).
11. **Reconcile claims against the file, not this log**, before flipping `NEXT` (Producer) or setting `Approved` (Reviewer).

## Roles
- **Producer** — the only writer of the artifact: builds it, requests review, decides and implements proposals, updates.
- **Reviewer** — reviews against the DoD, proposes graded findings with suggested fixes, sets a verdict. Never edits the artifact.

---
## Log

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->
