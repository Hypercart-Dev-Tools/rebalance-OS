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
| **Codex relay review integrated (2026-06-24)** — plan hardened per 4 findings: no-reflog **fallback ladder** + `recency_basis`, **semantic op-set** + test matrix, **minimal explain pulled into Phase 1**, DB-persist rationale, sleuth/EOS **regression oracle** + reflog-unavailable fixtures. | **Implement Phase 1** — probe `my_local_commit_ts` + `recency_basis` (reflog → author-email → any-commit fallback), rank on it, minimal explain payload, migration `0004`, op-matrix + oracle tests. |

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

## Phase 1 — Identity-Agnostic Ranking Vector (+ minimal explain)

> Rank the headline board on local-commit recency from the HEAD reflog, with an
> explicit **fallback** when the reflog is unavailable, plus a **minimal
> ranking-basis payload** so QA can see *why* each repo ranks (no silent bias).
> _(Codex relay r1: §[Should]×3 + §[Nit] integrated — see relay thread.)_

- [ ] **Define the signal semantically** (not a brittle message allowlist):
      `my_local_commit_ts` = the most recent HEAD-reflog entry for an **operation
      that creates or rewrites a locally-checked-out commit reachable at HEAD**.
      *Accept:* `commit`, `commit (amend)`, `commit (initial)`, a `merge` that
      **creates** a local merge commit, `cherry-pick`, `revert`, `rebase` (incl.
      interactive). *Reject:* fast-forward `pull`/`merge` (foreign), `fetch`,
      `checkout`, `clone`, `reset`. Tolerate reflog-message variance across git
      versions — enumerate accept/reject op families in **one** place; an
      unrecognized op is treated **conservatively as reject** and logged.
- [ ] **Fallback contract when the reflog is unavailable:** if HEAD reflog is
      missing / disabled (`core.logAllRefUpdates=false`) / GC-expired / absent in
      an atypical clone or worktree, degrade in a **defined order** — `local_reflog`
      → `author_email` (`my_last_commit_ts`, the *old* behavior, so we never
      regress below today) → `any_commit` (`last_commit_ts`) → `none` (ineligible).
      The chosen basis is **recorded, never silent**.
- [ ] `probe_repo_signals` captures `my_local_commit_ts` + a `recency_basis` enum
      (`local_reflog` | `author_email` | `any_commit` | `none`). Never raises.
- [ ] `RepoSignals` gains `my_local_commit_ts: int | None` + `recency_basis`; the
      author-email `my_last_commit_ts` stays (display/diagnostic **and** fallback input).
- [ ] `rank_recent_activity` ranks on the resolved recency (eligible iff
      `recency_basis != none`); `rank_reason` reads from it. Other strategies untouched.
- [ ] **Minimal explain in Phase 1:** `summarize_focus5()` carries, per roster +
      off-roster repo, its resolved recency + `recency_basis` + the current #5
      cutoff — enough for QA to distinguish "fixed ranking" from "new silent bias."
      (Operator-facing UX is Phase 2.)
- [ ] DB: persist `my_local_commit_ts` + `recency_basis` in `focus5_repo_signals`
      via additive migration `0004_*` (NULL-tolerant). **Reason:** the other signals
      are already persisted by the probe (one write path); adding these alongside
      keeps a single writer and lets explain/debug read the basis without
      re-probing. (Compute-on-read is simpler but splits the write path — rejected.)
- [ ] **Tests — op matrix:** accept (`commit`, `amend`, `merge`-commit,
      `cherry-pick`, `revert`, interactive `rebase`) vs reject (ff-only `pull`,
      `fetch`, `checkout`, `clone`, `reset`); the **reflog-unavailable** fixture
      (`core.logAllRefUpdates=false`) exercising each fallback rung; and the
      **regression oracle**: `sleuth-app` (local commits under a non-`user.email`
      identity) ranks **above** `EOS-daily-skill` (web-merge-only).
- [ ] **Proof artifact:** before/after `summarize_focus5()` roster diff on the real
      device DB, saved to the issue.

### QA Checklist — Phase 1

- [ ] **DRY:** one op-classification + recency-resolution helper; no second reflog
      parse, and one `recency_basis` ladder shared by ranking + explain.
- [ ] **SOLID:** the vector is isolated in `probe_repo_signals` + the strategy
      pure-function; route/collector/render layers untouched.
- [ ] **Diagnosable:** reflog-absent degrades through the fallback ladder with the
      basis **recorded** (not a silent `None`); each rung + unrecognized ops logged.
- [ ] **Blast:** additive columns + pure-function swap = reversible; no destructive
      migration. Roster recomputes hourly; revert is a one-function change.
- [ ] **Proof:** op-matrix + reflog-unavailable + sleuth/EOS-oracle tests all run
      green; before/after roster diff captured; `pytest tests/` green; `doctor` clean.
- [ ] **Single write path:** the new columns are written only by the focus5 sync
      probe (same writer as the other signals) — no second writer.
- [ ] **UTC:** `my_local_commit_ts` is a Unix epoch (UTC); display formats at the edge.

---

## Phase 2 — Operator-Facing Explain UX

> The machine-readable explain payload ships in Phase 1; Phase 2 is the **human
> surface** that makes "why is repo X (not) in Focus 5?" a one-line answer instead
> of `git log` forensics — including when a fallback basis was used.

- [ ] Surface the Phase-1 explain payload on **one** channel: extend the web
      off-roster strip reason (each repo's recency + `recency_basis` vs the #5
      cutoff), or CLI `rebalance focus5 explain <repo>`, or an MCP field. Default
      lean: off-roster strip (cheapest, already rendered).
- [ ] Make the **`recency_basis` visible** — a fallback (e.g. "ranked by author
      email because this clone's reflog is disabled") is shown, not silent.
- [ ] Tests: explain UX for on-roster, off-roster-eligible (below cutoff),
      ineligible (no local commit), and a **fallback-basis** repo.

### QA Checklist — Phase 2

- [ ] **DRY:** the UX reuses the Phase-1 payload (recency + basis + cutoff) — no
      parallel recomputation of "what's the cutoff."
- [ ] **SOLID:** read-only pure render over the cached signals; no new probe, no write.
- [ ] **Proof:** reproduces the original GH-81 finding in a test (sleuth off-roster:
      "last local commit 3d ago < #5 cutoff 16h") **and** shows a fallback basis.
- [ ] **Diagnosable (meta):** confirm it answers the exact question that required
      manual forensics in GH-81 — including the reflog-unavailable fallback case.

---

## Open Questions

1. ~~**Storage**~~ — **RESOLVED (Codex r1):** persist `my_local_commit_ts` +
   `recency_basis` in `focus5_repo_signals` (one write path, basis inspectable
   without re-probe). Compute-on-read rejected (splits the writer).
2. ~~**Reflog op set**~~ — **RESOLVED (Codex r1):** semantic definition
   ("creates/rewrites a local commit reachable at HEAD") + enumerated accept/reject
   families + a test matrix; unrecognized ops reject-and-log. (Was: a `commit*`
   message allowlist — too fragile / incomplete.)
3. ~~**Phase split**~~ — **RESOLVED (Codex r1):** minimal explain payload moves to
   Phase 1 (observability for the new vector); operator-facing UX stays Phase 2.
4. **Explain surface (Phase 2):** off-roster strip reason vs CLI vs MCP — still pick
   one for v1. Lean: off-roster strip.
5. **Hybrid escape hatch:** keep an *optional* email-match union for operators who
   want web-merge-only repos to rank? Default OFF; only if requested. _(Note: the
   `author_email` fallback rung already covers the reflog-disabled case.)_

## Review history

- **Codex relay r1 (2026-06-24)** — Verdict: Changes requested → all findings
  integrated above (no-reflog fallback contract; semantic op-set + test matrix;
  minimal explain pulled into Phase 1; DB-persist rationale stated; regression
  oracle + reflog-unavailable fixtures added to QA). Thread:
  [relay-system/2026-06-24/gh81-rank-vector.md](../../relay-system/2026-06-24/gh81-rank-vector.md).
