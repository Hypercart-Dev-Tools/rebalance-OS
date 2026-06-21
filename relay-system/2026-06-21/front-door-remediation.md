# RELAY · Front-Door Onboarding Remediation Plan Review
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Reviewer
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

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->
