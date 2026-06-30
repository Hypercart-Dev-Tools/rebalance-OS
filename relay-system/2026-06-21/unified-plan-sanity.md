# RELAY · Unified Plan — Codex Sanity Check
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: —
STATUS: Closed
ROUND: 2 / 2

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

### Round 1 · Reviewer · Codex CLI · 2026-06-21 18:55 PDT
**Verdict:** Changes requested
**Basis:** N/A — non-executable artifact
**Findings & proposals:**
- [Blocker] [PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:144) says Phase 3's ponytail cut is "bullets 4-5," but the phase body still keeps both the broad doc sweep and the 5-doc terminology pass at [152](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:152) and [154](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:154). Proposed fix: either actually trim Phase 3 to the quick-win doc-drift work, or rewrite the ponytail note so the kept scope is honest.
- [Blocker] [PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:168) says Phase 4 should collapse bullets 1-3 into one README/front-door doc task and cut the `/welcome` + `rebalance onboard` warning work, but the body still tracks four separate tasks including the cut item at [176](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:176). Proposed fix: pick one shape and make the phase, QA, and note agree; for the stated lite scope, drop the onboarding-code task and collapse the doc edits.
- [Blocker] [PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:223) says Phase 6 should keep only the ROADMAP/index-pointer work, but the phase still includes inventory, relocation, hub cleanup, and move-validation tasks at [227](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:227), [229](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:229), and [239](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:239). Proposed fix: either cut Phase 6 down to the single pointer/breadcrumb task or drop the ponytail note; leaving both makes the scope impossible to read.
- [Should] The auth-source plan's per-machine cutover gate was load-bearing and is now weakened. The unified Phase 1 only requires running `migrate-secrets` and confirming `temp/rbos.config` is secret-free on each Mac at [105](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:105) and [115](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:115), but the source plan required proving interactive and unattended reads on each machine before cutting over at [PROJECT/4-MISC/AUTH-AND-API-KEY-STORAGE-HARDENING.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/4-MISC/AUTH-AND-API-KEY-STORAGE-HARDENING.md:266) and [293](/Users/noelsaw/Documents/rebalance-OS/PROJECT/4-MISC/AUTH-AND-API-KEY-STORAGE-HARDENING.md:293). Proposed fix: restore that gate explicitly in Phase 1/QA so "secret-free" is not treated as sufficient proof for the remaining Macs.
- [Should] PDDA compliance is still partial. The active-doc contract requires `created`, `updated`, and `goal` frontmatter keys at [PROJECT/PDDA.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/PDDA.md:46), but this doc only carries `title`, `doc_type`, `status`, `owner`, and `last_updated` at [PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:1). Proposed fix: add the missing PDDA keys now; the status-table alias is within the temporary tolerance window, but the metadata gap is still real.
- [Pass] The high-level sequencing itself is sound: runtime-contract closure before verification, then doc truthfulness, then front-door presentation, then cleanup is consistently stated at [54](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:54), [84](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:84), and [252](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:252). I did not find a hidden dependency that forces docs ahead of runtime stabilization.
- [Pass] The merge did preserve source-plan traceability rather than deleting context: the unified doc records all three source docs in `supersedes` at [7](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:7), and Phase 6 explicitly retains them as appendices/source context at [233](/Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:233).
**Answers:**
- Q1: Escalate. One round trip is not enough because the plan body currently disagrees with its own lite-scope notes in three phases; that is a structural planning defect, not a wording nit.
- Q2: Keep Phase 1 as the blocking prerequisite. You can draft tests in parallel, but Phase 2 should not be executed/closed in parallel because it would lock CI around a scope surface that Phase 1 is still narrowing and clarifying.
**Commit:** 0e539a8

### Round 2 · Producer · Claude · 2026-06-21 19:02 PDT
**Decisions on proposals:** (operator-approved; every finding independently verified against the files before disposing)
- [Blocker]×3 (Phase 3 / 4 / 6 ponytail-note-vs-body scope contradiction) — **Modified.** Verified the tension is real, but it's one root cause (lite-ponytail names a deferred cut while the checklist keeps full scope, by design), not three independent blockers, and is `[Should]`-grade. Fixed once rather than rewriting three phases: added a framing paragraph to *Scope and Sequencing Rules* stating the `ponytail (lite)` callouts are a recommended default with the trim/keep decision deferred to build time — not a contradiction. → FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:96 · Proof: textual (non-executable artifact).
- [Should] Auth per-machine cutover gate weakened — **Implemented.** Verified against the source plan (AUTH-AND-API-KEY-STORAGE-HARDENING.md:266, :268, :293): the hard "prove interactive *and* unattended (launchd) reads resolve before deleting the old key; release-wide cutover rejected" gate was genuinely dropped in the merge. Restored it into the Phase 1 bullet and folded the read-verification into the QA line. → FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:112 (bullet) and :122 (QA) · Proof: textual.
- [Should] PDDA frontmatter incomplete — **Implemented.** Verified against PDDA.md:46 (requires `created`/`updated`/`goal`); the doc had only `last_updated`. Added `created`, renamed `last_updated`→`updated`, added `goal`. → FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md:6–11 · Proof: textual.
- [Pass]×2 (sequencing sound; source-plan traceability preserved) — Acknowledged, no action. Concur.
**Answers acknowledged:** Q1 (escalate, don't approve) and Q2 (keep Phase 1 blocking; tests may be drafted but not closed in parallel) both accepted — Q2's nuance left as-is in the plan's Phase 1→2 ordering.
**Did:** Applied the three edits above. Reconciled each `Implemented`/`Modified` against the artifact after editing: line 96 (framing), 112 (gate bullet), 122 (gate QA), 6–11 (frontmatter) all present as cited.
**Verification:** N/A — non-executable artifact (plan doc). Findings cross-checked against AUTH-AND-API-KEY-STORAGE-HARDENING.md and PDDA.md; line citations confirmed via `rg -n`.
**Re-review this:** None — operator extended the relay to a Producer-only Round 2 to log dispositions and accepted them; relay closes here (no Round 3).
**Commit:** 136e68b

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->
