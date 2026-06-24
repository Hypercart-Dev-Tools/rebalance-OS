---
gh_issue: 81
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/81
title: "Focus 5 — identity-agnostic ranking vector (local-commit recency)"
status: draft
doc_type: bug-fix + plan
owner: noel@neochro.me
created: 2026-06-24
updated: 2026-06-24
goal: "Rank the headline Focus 5 on whether MY local checkout committed recently (HEAD reflog), not on a single git user.email match — so multi-identity local work never silently drops off the roster."
priority: P2
branch: development
rollout_rule: each phase leaves the system runnable (`pytest tests/` green, `rebalance doctor` clean) and the change is a reversible pure-function/additive-column swap
---

## Status

| What was just completed | What's next |
|---|---|
| _None — plan drafted 2026-06-24 from [GH-81](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/81); pending Codex relay review._ | **Phase 1 — Identity-agnostic ranking vector:** probe `my_local_commit_ts` from the HEAD reflog (local commit ops only) and rank `rank_recent_activity` on it. |

## Table of Contents

- [Problem](#problem)
- [Decision (why reflog, not email)](#decision-why-reflog-not-email)
- [Non-Goals](#non-goals)
- [Phase 1 — Identity-Agnostic Ranking Vector](#phase-1--identity-agnostic-ranking-vector)
- [Phase 2 — Explain-Rank Diagnostic](#phase-2--explain-rank-diagnostic)
- [Open Questions](#open-questions)

## Problem

`rank_recent_activity` (the default headline Focus 5) ranks on `my_last_commit_ts`
= `git log -1 --author=<git config user.email>`. The operator commits under
multiple author emails (`noel@neochro.me` for CLI; `…noelsaw1@users.noreply.github.com`
for GitHub-web PR merges), so recent local work authored under a *non-matching*
email is invisible — the repo **silently** drops off the roster.

Verified 2026-06-24: `sleuth-app` (local commits ~15h ago as `noel@neochro.me`)
lost to `EOS-daily-skill` (surfaced only via GitHub-web merge commits stamped with
the noreply identity); sleuth's matched recency was a 3-day-old merge. Full trace
in [GH-81](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/81).

## Decision (why reflog, not email)

Email is a proxy for identity, and git identity is intrinsically fragmented
(author vs committer, web-merge noreply, squash author-rewrite, co-authors, bots,
per-repo/per-machine config). An email **set** only defers the same silent failure
to the next identity (maintenance treadmill); unifying identity can't control
web-merge authorship. Evaluated under the SWE lens, both fail **Minimal**
(ongoing config) and **Diagnosable** (silent drift).

The durable vector is **"did MY local checkout commit recently"** — the HEAD
reflog, filtered to local commit operations. It is identity-agnostic (no list to
maintain, no silent drift on a new identity), foreign-push-resistant (a pull-only
repo has no local `commit:` reflog entry), and intuition-aligned (local hands-on
work outranks a browser PR merge). Author email is retained as a *displayed /
diagnostic* detail, never the gate. The change is reversible (pure ranking
function + an additive signal column; snapshot recomputed hourly; Dirty Five +
off-roster strip remain as safety nets).

## Non-Goals

- Only `rank_recent_activity` (the headline board) changes — `dirty_first`,
  `my_work`, `any_touch` semantics are untouched.
- Focus 5 stays **device-local** — no multi-device commit aggregation.
- The author-email signal is **kept** (display/diagnostic), not removed.
- No editor/IDE-introspection vector ("what's open in VS Code") — out of scope.

---

## Phase 1 — Identity-Agnostic Ranking Vector

> Rank the headline board on local-commit reflog recency instead of a single
> `--author` email match.

- [ ] `probe_repo_signals` captures `my_local_commit_ts`: parse `.git/logs/HEAD`
      (or `git reflog show --date=unix HEAD`), take the latest entry whose op is a
      **local commit** — message starts with `commit`, `commit (amend)`,
      `commit (initial)`, or `rebase` — **excluding** `pull` / `fetch` /
      `checkout` / `clone` / `reset`. Never raises (no reflog → `None`).
- [ ] `RepoSignals` gains `my_local_commit_ts: int | None`; the author-email
      `my_last_commit_ts` stays (now display/diagnostic only).
- [ ] DB: additive migration (`0004_*`) adding the `my_local_commit_ts` column to
      `focus5_repo_signals` (or recompute-on-read if the column is avoidable —
      decide in review). Old rows tolerate `NULL`.
- [ ] `rank_recent_activity` ranks on `my_local_commit_ts` (eligible iff not
      `None`); `rank_reason` reads from it. Other strategies unchanged.
- [ ] Tests: reflog parse table (commit / amend / rebase count; pull / fetch /
      checkout / clone / reset do **not**); eligibility (no local commit →
      excluded); the sleuth-style case (local commit under a non-`user.email`
      identity ranks above a web-merge-only repo).
- [ ] **Proof artifact:** before/after `summarize_focus5()` roster diff on the
      real device DB, saved to the issue.

### QA Checklist — Phase 1

- [ ] **DRY:** one reflog-recency helper; no second reflog parse elsewhere.
- [ ] **SOLID:** the vector is isolated in `probe_repo_signals` + the strategy
      pure-function; the route/collector/render layers are untouched.
- [ ] **Diagnosable:** an unreadable/absent reflog degrades to `None` (repo simply
      not eligible), logged — never an exception or a silent crash.
- [ ] **Blast:** additive column + pure-function swap = reversible; no destructive
      migration. Roster recomputes hourly; revert is a one-function change.
- [ ] **Proof:** every acceptance check has a test or the captured roster diff;
      `pytest tests/` green; `rebalance doctor` clean.
- [ ] **Single write path:** the new column is written only by the focus5 sync
      path (same writer as the other signals) — no second writer.
- [ ] **UTC:** `my_local_commit_ts` is a Unix epoch (UTC); display formats at the
      edge only.

---

## Phase 2 — Explain-Rank Diagnostic

> Make "why is repo X (not) in Focus 5?" self-service, so the next surprise is a
> one-line answer instead of `git log` forensics.

- [ ] A pure `explain_focus5_rank(db, repo)` (or an extension of `summarize_focus5`)
      that returns, for a repo: its `my_local_commit_ts` (relative), the current
      #5 cutoff, eligibility, and the reason it is on / off the roster.
- [ ] Surface it on one channel (decide in review): CLI `rebalance focus5 explain`,
      an MCP field, or the web off-roster strip showing each repo's recency vs the
      cutoff. Default lean: extend the off-roster strip reason (cheapest, already
      rendered).
- [ ] Tests: explain output for an on-roster repo, an off-roster eligible repo
      (below cutoff), and an ineligible repo (no local commit).

### QA Checklist — Phase 2

- [ ] **DRY:** explain reuses the Phase 1 recency + the same cutoff the ranker
      uses — no parallel "what's the cutoff" calculation.
- [ ] **SOLID:** explain is a read-only pure function over the cached signals; no
      new probe, no write.
- [ ] **Proof:** the diagnostic reproduces the original GH-81 finding (sleuth
      off-roster: "last local commit 3d ago < #5 cutoff 16h") in a test.
- [ ] **Diagnosable (meta):** this *is* the Diagnosable win — confirm it answers
      the exact question that required manual forensics in GH-81.

---

## Open Questions

1. **Storage:** add a `my_local_commit_ts` column (migration `0004`) vs. compute
   reflog recency on read each render? Lean: column (consistent with the other
   cached signals; one write path), but confirm the probe cost is acceptable.
2. **Reflog op set:** include `rebase` / `merge`-that-creates-a-commit, or
   restrict to `commit*` only? Lean: `commit*` + `rebase`; exclude fast-forward
   merges (foreign).
3. **Explain surface (Phase 2):** off-roster strip reason vs CLI vs MCP — pick one
   for v1.
4. **Hybrid escape hatch:** keep an *optional* email-match union for operators who
   want web-merge-only repos to rank? Default OFF; only if requested.
