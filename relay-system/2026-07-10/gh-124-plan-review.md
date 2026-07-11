# RELAY · GH-124 auto-promote plan review
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-07-10.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 3 / 4

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
6. **Commit only the relay file** (`relay(gh-124-auto-promote-plan-review): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Artifact under review: **.relay-artifacts/GH-124-AUTO-PROMOTE-WATCHED.md** — the read-only path that
  `relay-drive.sh --artifact-file /Users/noelsaw/Documents/GitHub Repos/rebalance-OS/PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md` seeds into the isolated worktree (read it there; do NOT edit it).
- Reviewer: codex   ·   Producer: claude-a
- Started: 2026-07-10
- Definition of Done: Plan names (1) an exact commit-counting contract (threshold, dedup rule, window),
  (2) the single owning orchestrator stage/path for the write, (3) durable-suppression precedence for
  `github_ignored_repos` vs. manual row deletion, and (4) the exact `project_registry` row shape /
  provenance marker auto-promotion writes — each phase carries QA gates a producer can execute
  mechanically.

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

### Reviewer — codex — 2026-07-10
VERDICT: Changes requested

- [Blocker] The relay still has no acceptance criteria: `"Definition of Done: _<fill in the acceptance criteria the Reviewer grades against>_"`. Without a filled DoD, the producer has no bounded target and approval cannot be mechanical. Fix: replace the placeholder with explicit acceptance criteria covering trigger semantics, write-path ownership, operator-visible surfacing, ignore/opt-out behavior, and required tests.
- [Pass] The plan correctly anchors promotion on actual operator commits and explicitly excludes fork/star-only discovery as sufficient evidence (`PROJECT/1-INBOX/GH-124-AUTO-PROMOTE-WATCHED.md:26-27`, `PROJECT/1-INBOX/GH-124-AUTO-PROMOTE-WATCHED.md:46-48`).
- [Should] The trigger is still materially underspecified. The doc says a repo should promote after `2-3` operator commits, but it never fixes the exact threshold, counting window, event source, or SHA de-duplication rule (`PROJECT/1-INBOX/GH-124-AUTO-PROMOTE-WATCHED.md:19-27`, `PROJECT/1-INBOX/GH-124-AUTO-PROMOTE-WATCHED.md:46-48`). Fix: choose one exact threshold and define the counting contract precisely enough that two implementations would promote the same repo on the same refresh.
- [Should] The execution path is still left open: `"whether this rides refresh_index() or stays a separate pass"` (`PROJECT/1-INBOX/GH-124-AUTO-PROMOTE-WATCHED.md:49-50`). In this repo that is a contract decision, not an implementation detail, because user-facing writes are supposed to route through one orchestrator-owned path. Fix: name the single owning stage/helper and say exactly when it runs relative to GitHub refresh.
- [Should] Opt-out precedence is unresolved. The plan calls out `github_ignored_repos` as an open question, but does not say whether ignored repos, manually demoted repos, or manually deleted machine-owned rows stay suppressed or get re-added on the next refresh (`PROJECT/1-INBOX/GH-124-AUTO-PROMOTE-WATCHED.md:49-50`). Fix: define a durable suppression rule and its precedence over auto-promotion.
- [Should] The write contract for promoted rows is missing. Existing machine-owned rows already have a concrete shape and provenance marker, and curated-name collisions are explicitly skipped rather than clobbered (`src/rebalance/ingest/project_inference.py:631-655`, `src/rebalance/ingest/project_inference.py:675-693`). Fix: specify the exact `project_registry` row shape and provenance metadata that auto-promotion will write so the producer can reuse that contract safely.

### Producer — claude-a — 2026-07-10

**Process note:** this review ran against an uncommitted working-tree version of the artifact, so
`relay-drive.sh`'s isolated worktree (built from `ROOT@HEAD`) seeded the *old* 1-INBOX stub — hence the
`PROJECT/1-INBOX/GH-124-...` citations above. The full plan doc has since been committed
(`4011e13`) at `PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md`; round 2 will see the real content.

Dispositions:
- [Blocker] DoD placeholder — **Implemented.** Filled in above (this Setup block).
- [Pass] operator-commits-only / fork-star exclusion — **Acknowledged**, unchanged in the committed doc.
- [Should] threshold/counting-window/SHA-dedup — **Implemented.** Committed doc's Phase 1 now specifies:
  cumulative all-time distinct-*full*-SHA count (not short-SHA — cites `PROJECT/1-INBOX/P1-SQLITE.md:147`'s
  canonical-identity lesson), default threshold 3, no rolling window.
- [Should] execution path (refresh_index vs. separate pass) — **Implemented.** Phase 3 Discuss now states
  a default recommendation (fold into `refresh_index(scope=["github"])`) rather than leaving it open,
  revisit-gated on measured cost.
- [Should] opt-out/suppression precedence — **Implemented.** Phase 1 now states `github_ignored_repos` is
  the only durable suppression; a manually deleted machine-owned row is NOT durable (recreated next pass,
  mirroring existing `_delete_stale_inferred_rows` semantics) — documented explicitly so it isn't a surprise.
- [Should] row shape / provenance contract — **Implemented.** Phase 1 now names the exact row shape
  (reusing `_seed_to_project_row`'s fields), a distinct `"commit_threshold_v1"` provenance marker, and
  the concrete change to generalize `_is_inference_owned()` to recognize it alongside the existing
  `activity_inference_v1` marker — reusing curated-collision-skip and stale-cleanup without a parallel
  implementation.

Requesting a fresh review pass against the now-committed `PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md`
(commit `4011e13`).

### Reviewer — codex — 2026-07-10
VERDICT: FAIL
Basis: The plan still leaves the owning orchestrator path conditional, and "operator-authored commit" still depends on an external GH-81 precedent instead of an inline counting contract.
Outcome: Changes requested

- [Pass] The plan now fixes the commit-counting contract itself: `">=3 distinct-SHA operator commits (all-time, not a rolling window)"` plus the explicit "`distinct full-SHA` ... `cumulative all-time`" rule make threshold, dedup, and window mechanical (`PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md:117-132`).
- [Pass] The row-write contract and suppression precedence are now concrete: the plan names the exact `project_registry` row shape/provenance to write and states that `github_ignored_repos` is the only durable suppression while manual deletion of a machine-owned row is not (`PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md:138-152`).
- [Blocker] The single owning orchestrator path is still not fully decided. The Discuss section says the default is to fold into `refresh_index(scope=["github"])`, but it still leaves a measured-cost escape hatch, and the Work item says to wire it there "`or document the deliberate decision not to`" (`PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md:201-209`). The relay DoD asked for the plan to name the exact owning stage/path now, not after implementation experience. Fix: choose one owner in the plan text outright, e.g. "`_refresh_github` in `index_ops.py` calls the auto-promotion helper after watched-repo sync`", and move any future re-evaluation to a follow-up note rather than leaving this plan conditional.
- [Should] "Operator-authored commit" is still defined by reference to GH-81's fallback ladder instead of by an inline contract, so two implementers still have room to count different commits (`PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md:105-109`, `PROJECT/2-WORKING/GH-124-AUTO-PROMOTE-WATCHED.md:134-137`). Fix: spell out the exact identity-resolution inputs and precedence in this plan (which table/fields are checked first, which fallbacks are allowed, and what happens when local identity evidence is absent) so the count contract is self-contained.

### Producer — claude-a — 2026-07-10

Dispositions:
- [Blocker] owning orchestrator path still conditional — **Implemented.** Decided outright: `_refresh_github`
  in `src/rebalance/ingest/index_ops.py` calls the Phase 1 helper immediately after the existing
  `WATCHLIST-COVERAGE-GUARD` snapshot/diff step (verified live at `index_ops.py:729` /
  `index_ops.py:828-837`). Removed the "or document the decision not to" escape hatch from the Work item.
- [Should] identity contract by reference to GH-81 — **Implemented.** Inlined the exact two-rung contract
  (`local_reflog` then `author_email`, both from GH-81's existing `recency_basis` ladder at
  `src/rebalance/ingest/focus5_scan.py:89,113-121`) directly into Phase 1's Discuss + Work sections, and
  explicitly excluded the third rung (`any_commit`) since it would defeat the operator-only requirement.

Committed as `dd89778`. Requesting final review pass.

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
