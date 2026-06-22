# RELAY · Unified Plan — Codex Sanity Check
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
3. **Do your role's work** on the artifact named in Setup (read the real file; cite `file:line`):
   - **Reviewer:** review vs the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete proposed fix → set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the artifact; you only append findings here. This is a **non-executable artifact (a plan doc)** — read the artifact file itself, cite real line numbers, and answer `Basis: textual only` or `N/A — non-executable artifact`.
   - **Producer:** for every open finding log a disposition (Implemented / Modified / Declined + why), make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line (`<!-- ↓↓↓ NEXT TURN ... -->`). Never edit earlier turns. Header it `### Round N · <Role> · <your-label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Basis:**` + `**Findings & proposals:**` (graded bullets) + `**Answers:**` + `**Commit:**`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` (`Approved` closes the relay — Reviewer only; else leave `Open`). This relay is `ROUND: 1 / 1` — a single round trip; if you would request changes rather than approve, set `STATUS: Escalated` and hand back to the human (no second round).
6. **Commit only the files you touched** (this log): `git commit -m "relay(unified-plan-sanity): reviewer r1"`, then put the short hash in your block's `Commit:` line and `git commit --amend --no-edit`.
7. **Stop.** Tell the operator your one-line result (e.g. "Approved — sanity check clean" or "Escalated, 2 Blockers — back to Noel").

## Setup
- Artifact under review: PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md
- Definition of Done: The plan is internally consistent, correctly sequenced, scoped (no YAGNI bloat), and PDDA-compliant — ready to start Phase 1 with no blocking gaps.
- Producer: Claude (Opus 4.8)   ·   Reviewer: Codex CLI
- Handoff: manual nudge
- Started: 2026-06-21

## Ground rules
1. This file is the single source of truth. If it isn't written here, assume the other agent doesn't know it. The two agents are different tools (Claude and Codex) and never share memory.
2. Read the whole file. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns. Then update `NEXT`, `STATUS` at the top. (Only exception: right after committing, fill the hash into your own just-written turn's `Commit:` line.)
4. Stay tight. Requests and findings are bullets, not essays.
5. **The Reviewer never edits the artifact.** It proposes graded findings, each with a concrete suggested fix where possible. The Producer (the original author), with the operator, decides each proposal after the relay.
6. Grade every finding:  `[Blocker]` must fix before executing the plan · `[Should]` strong recommendation · `[Nit]` optional · `[Pass]` checked and sound (records what was verified, not assumed). Answer the Producer's open questions in an `Answers:` block.
7. The Reviewer posts a Verdict. This relay is one round trip (`ROUND: 1 / 1`): the Reviewer either closes it `Approved`, or sets `STATUS: Escalated` and hands findings back to the human — there is no Producer round 2 in-thread.
8. End your turn by committing it: `relay(unified-plan-sanity): reviewer r1`, then fill the hash into your `Commit:` line.
9. **One window at a time, clean tree at every handoff.** Both agents share one working tree; the `NEXT` pointer is honor-system, not a lock. Don't start until the tree is clean.
10. **Evidence contract.** The Reviewer logs a verdict `Basis:` — for this plan doc, `textual only` (read, not run) or `N/A — non-executable artifact` is expected and correct.
11. **Reconcile claims against the file, not this log.** Read the artifact itself, cite real `file:line`. The completeness angle matters here: this unified plan is a *merge* of three source docs (listed in its frontmatter `supersedes:`). Beyond finding errors, check for silent **drops** — load-bearing scope or constraints that existed in the source plans but have no equivalent here. Report the gap; don't just summarize what's present.

## Roles
- **Producer** — Claude: authored the artifact, requests review, decides/implements proposals (with the operator) after the relay.
- **Reviewer** — Codex: reviews against the DoD, proposes graded findings with suggested fixes, sets a verdict. Never edits the artifact.

---
## Log

### Round 1 · Producer · Claude · 2026-06-21 18:49 PDT
**Did:** Finalized the unified front-door/portability/auth plan (one canonical doc that supersedes three overlapping ones); added lite-ponytail scope-challenge notes to Phases 3–6; registered it as the single In-progress entry in `ROADMAP.md`.
**Review this:** Sanity-check the **plan only** — not code. Focus:
  - **Sequencing soundness** — is "runtime contract → verification → docs → repo-surface cleanup" the right order, and are there hidden cross-phase dependencies that break it (e.g. a Phase 3/5 doc claim that can't be true until a Phase 1 item lands)?
  - **Scope / YAGNI** — for a single-operator tool (~2 Macs), is any phase over-built? The Phase 3–6 `ponytail (lite)` callouts already flag candidates; agree, push further, or push back.
  - **Internal contradictions** — anything in the phases, Cross-Phase Risks, or Definition of Done that conflicts (e.g. a DoD line with no owning phase, or a phase task no DoD line covers).
  - **Completeness vs the 3 source docs** — see Ground rule 11. The `supersedes:` frontmatter names them; the Phase 6 last bullet claims they're retained in-tree as appendices. Flag any load-bearing detail silently dropped in the merge.
  - **PDDA compliance** — frontmatter present, exact `## Status`-style table (note: this doc uses a "Most recently completed phase | What's next" header — a tolerated alias only through 2026-07-31), repo-relative paths only, QA gates after each phase.
**Verification:** N/A — non-executable artifact (plan doc). No commands to run; review is textual against the artifact and the three source docs in `PROJECT/4-MISC/`.
**Open questions:**
  - Q1: Is one round trip enough, or does the plan have a structural gap that needs a real fix-and-re-review cycle (i.e. should you escalate rather than approve)?
  - Q2: Phase 1 is the next action — is its scope correctly the *blocking* prerequisite for everything else, or could verification (Phase 2) safely run in parallel?
**Commit:** 2437ec9

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->
