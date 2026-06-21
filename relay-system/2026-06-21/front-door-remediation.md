# RELAY · Front-Door Onboarding Remediation Plan Review
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Producer
STATUS: Open
ROUND: 1 / 3

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini)
The operator just said "take your turn on this file." Everything you need is **in this file**.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. If not your role → STOP and say so.
3. **Reviewer:** review the artifact against the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete proposed fix → set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the artifact. For this planning doc, re-read the artifact file itself before approving.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes the relay — Reviewer only).
6. **Commit** your turn, then fill the hash into your block's `Commit:` line.
7. **Stop.** Tell the operator your one-line result.

## Setup
- Artifact under review: PROJECT/2-WORKING/FRONT-DOOR-ONBOARDING-REMEDIATION.md
- Definition of Done: The plan is **complete** (covers every Bumpy item from the 2026-06-21 front-door audit), **actionable** (observable checklist items + a QA checklist per phase), **sound on the Calendar/Gmail MCP-connector steering** (recommends the host-connector path *with* the local-first cloud trade-off stated, never silently), correctly **keeps human-gated walls out of scope** (doesn't disguise a real wall as a doc fix), and **contradicts nothing** in the shipped auth-storage model (keyring + secret store + JSON OAuth).
- Producer: Claude (Opus 4.8)   ·   Reviewer: Codex CLI (codex-cli 0.139.0)
- Handoff: cli-driven (codex)   <!-- relay-xyz harness (relay-automation/) not present in this repo; using portable /relay CLI-driven mode -->
- Started: 2026-06-21

## Ground rules
1. This file is the single source of truth. The two agents never share memory.
2. Take a turn only if `NEXT` names your role.
3. One turn = one block appended at the bottom, above the marker. Never edit earlier turns.
4. Stay tight. Findings are bullets, not essays.
5. **The Reviewer never edits the artifact.** It proposes graded findings with concrete fixes; the Producer (with the operator) implements.
6. Grade every finding: `[Blocker]` must fix · `[Should]` strong rec · `[Nit]` optional · `[Pass]` checked + sound.
7. The Reviewer posts a Verdict every turn. The relay ends on **Approved**; to action proposals in-thread use `Changes requested`.
8. Evidence contract: the Reviewer logs a `Basis:` (textual for a non-executable doc); the Producer logs `Verification:`.
9. Reconcile claims against the artifact file, not this log.

## Roles
- **Producer** — author of the artifact; requests review, decides + implements proposals.
- **Reviewer** — reviews against the DoD, proposes graded findings, sets a verdict. Never edits the artifact.

---
## Log

### Round 1 · Producer · Claude · 2026-06-21 13:30 PDT
**Did:** Authored the front-door onboarding remediation plan ([PROJECT/2-WORKING/FRONT-DOOR-ONBOARDING-REMEDIATION.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-ONBOARDING-REMEDIATION.md), committed `858de7d`). It remediates the Bumpy items from the 2026-06-21 front-door audit across 4 phases — (1) README doc-drift quick wins, (2) install-path clarity (platform gate + cross-platform minimal subset + first-run egress), (3) lower the Calendar/Gmail wall via host MCP connectors with the local-first trade-off, (4) repo-root tidiness — each with observable checklist items + a QA checklist, plus cross-phase risks and a Definition of Done.
**Review this — scrutinize against the DoD, in priority order:**
- **Completeness:** does it cover every Bumpy item the audit named (README:262/:321 drift, MLX/Apple-Silicon platform gate, HuggingFace/GitHub/Google first-run egress, Calendar/Gmail OAuth wall, root-doc clutter)? Name any audit bump with no owning phase.
- **Scope honesty:** does any checklist item disguise a **human-gated wall** (GitHub PAT, Google account/consent, Apple-Silicon hardware, Obsidian vault) as an agent-soluble doc fix? Flag it.
- **MCP-connector soundness (load-bearing):** is the Calendar/Gmail host-connector steering correct and safe — does it state the cloud-vs-local-first trade-off *everywhere* the connector path is offered, keep local OAuth as the privacy-first default, and ground the Gmail `mcp`-mode + proposed Calendar `mcp`-mode claims in what actually exists? Flag any place a user could be silently routed to the cloud.
- **No contradiction with shipped auth model:** does anything contradict the keyring + secret-store + JSON-OAuth model that just shipped (Phases 0–3 of the auth-storage hardening)?
- **Actionability:** is every checklist item observable, and is each QA checklist a real gate (not a restatement of the deliverable)?
**Verification:** N/A — non-executable planning doc.
**Open questions:** Is the Phase 3 Calendar `mcp`-consumption mode right to leave as a spec-or-build decision, or should the plan commit to one now?
**Commit:** `858de7d` (artifact pre-committed; this turn requests review)

### Round 1 · Reviewer · Codex · 2026-06-21 13:47 PDT
**Verdict:** Changes requested
**Basis:** N/A — non-executable artifact (planning doc; reviewed textually)
**Findings & proposals:** (Reviewer proposes; does NOT edit the artifact)
- [Blocker] Phase 3 + Definition of Done — the plan treats Calendar host-connector consumption as both a current doc-path ("README presents two clearly-labeled consumption paths for both Calendar and Gmail") and a maybe-deferred build. That is not reality-safe: if `calendar_ingest_method = mcp` and `ingest_calendar_events` do not exist yet, docs cannot honestly present Calendar host-connector as an available path. Proposed fix: commit Phase 3 now to one branch. Either build Calendar `mcp` mode in-scope, or rewrite every doc-facing/DoD mention so Gmail is "available now" while Calendar is explicitly "planned, not yet supported" until the mode/tool ship, with a revisit trigger.
- [Should] Phase 3 "Promote Gmail `mcp` mode" / "Add a consumption-path decision callout" — the connector route still depends on a human-gated precondition: the host must actually ship Google connectors and the user must already have connected/consented their Google account there. As written, this can read like any agent user can skip local OAuth. Proposed fix: add that precondition anywhere the connector path is recommended, and make it a QA gate.
- [Should] Phase 3 "Add a consumption-path decision callout to README Steps 4 and 5" — "links the trade-off" is weaker than the DoD requirement that the cloud-vs-local warning be stated wherever the connector path is offered. A reader can miss the warning if it only lives behind a link. Proposed fix: require one inline sentence in each callout: connector path routes Google data through the host cloud; local OAuth + SQLite remains the local-only path. Keep the link as secondary detail.
- [Should] Definition of Done / Phase 3 QA — the current gates are partly restating the deliverable instead of proving the behavior. Proposed fix: add a concrete doc-walk gate such as "A reviewer starting from README can identify, for Gmail and Calendar separately, whether the host-connector path is available now, what host preconditions apply, and whether data stays local, without opening code."
- [Pass] Completeness: every audit bump named in the 2026-06-21 front-door audit has an owning phase: README drift in Phase 1, MLX/Apple-Silicon gate and first-run egress in Phase 2, Calendar/Gmail OAuth wall in Phase 3, root-doc clutter in Phase 4.
- [Pass] No contradiction found with the shipped auth-storage model in Phase 1: the plan preserves keyring + out-of-repo JSON secret store, removes the stale required `migrate-to-keyring` step, and does not reintroduce pickle as a live path.
- [Pass] Scope honesty is mostly sound: the plan explicitly keeps GitHub PAT, Google account/OAuth consent, Apple-Silicon hardware, and an Obsidian vault out of "doc fix" scope instead of pretending they are agent-solvable.
**Answers:** (the Producer's open question)
- Is the Phase 3 Calendar `mcp`-consumption mode right to leave as a spec-or-build decision, or commit now? → Commit now. For this remediation plan, the safer choice is "spec-and-defer" unless you are explicitly pulling implementation into scope; do not leave it open, and do not document Calendar host-connector consumption as a current path until the mode/tool exist.
**Commit:** none (comments only)

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->
