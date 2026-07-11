# RELAY · GH-124 auto-promote plan review
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-07-10.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 2 / 4

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
Verdict: Changes requested

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

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
