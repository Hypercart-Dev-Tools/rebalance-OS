# RELAY · HiQS plan — execution-doc QA
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-08-03.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 1 / 4

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). Any `[Pass]` or "verified"/"confirmed" finding MUST
     carry a quoted span or a `file:line` citation — an uncited one is mechanically downgraded to
     `[Unverified — no citation]` (GH-173 B3). Do **not** edit the artifact; only append findings here.
   - **Producer:** log a disposition for every open finding (Implemented / Modified / Declined + why),
     make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Escalated`.
6. **Commit only the relay file** (`relay(hiqs-plan-qa): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Artifact under review: `PROJECT/2-WORKING/HIQS-PROJECT.md` (repo-relative, read it in full — ~1,300 lines)
- Reviewer: agy   ·   Producer: claude-a
- Started: 2026-08-03
- Context: HiQS is a clean-room rebuild of this repo's work-signal pipeline. The plan is at rev 5.
  Today it gained PDDA lifecycle sections (frontmatter, Status table, ToC, per-phase QA gates) and a
  set of tenet-driven schema changes. Supporting context, do not review these: `PROJECT/PDDA.md`
  (the doc contract), `CHANGELOG.md` 0.68.2 (what landed today), `PROJECT/4-MISC/HiQS-ANTI-PATTERNS.md`
  (the superseded ledger that was folded in).

- Definition of Done — grade the artifact against these five, in this order:
  1. **Are the per-phase QA gates observable and binary?** Every phase 0–5 has a `### QA gate — Phase N`.
     A gate item must be checkable by someone who did not write it: it names an observable, and its
     failure is unambiguous. Flag any item that is really a sentiment ("is clean", "is good"), any that
     cannot be evaluated without re-deriving the author's intent, and any phase whose stated exit check
     (§12 table) and gate disagree.
  2. **Is §7.1's ranking detector as un-flatterable as §6.3's?** §6.3 is the retrieval eval; rev 5
     hardened it specifically so it could not be gamed (n sized to the threshold, ground truth built
     without running search, query set frozen with a recorded SHA, splits/ties to the incumbent, an
     absolute floor). §7.1 is the new ranking eval. Apply §6.3's own standards to it and say plainly
     where it is weaker. Is the sample size adequate for the thresholds it states? Can the judgment set
     be contaminated by seeing the output first? Is any gate unfalsifiable? Is the "restate the tenet"
     failure branch real or decorative?
  3. **Does §18's dogfooding audit hold up?** It claims the four tenets were audited against both the
     product and the process, that two failed in the same direction on both sides, and that the
     plan-side gap explains the product-side one. Is that argument sound or is it a narrative fitted
     after the fact? Is §18.4's "open gap" an honest disclosure or a way to avoid doing the work?
  4. **Internal contradictions after today's schema additions.** Today added `author`/`owed_by`/`due`
     to `Doc`/`Candidate` (§5), `activity_at` split from `updated_at` plus author/assignee/organizer
     columns (§9), `RankedAction` with `source_age_s`/`source_status` (§7), §7.1, and a second row in
     §2's non-negotiables. Cross-check §2 ↔ §5 ↔ §7 ↔ §9 ↔ §12 ↔ §14 for: a claim in one section the
     others do not carry; a §14 deletion-ledger row that contradicts what v1 now ships (this exact bug
     class is named in the doc as "rev-4-class"); LOC/dependency budget (§11) versus what the additions
     actually cost; and any lesson L1–L22 the new fields violate.
  5. **The strongest counter-argument.** Name the single most consequential thing this plan gets wrong
     or leaves unresolved that the four criteria above would not surface.

- Out of scope: prose style, section numbering, markdown formatting, and the PDDA contract itself.
  No code exists yet — do not review implementation, only the plan.

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
