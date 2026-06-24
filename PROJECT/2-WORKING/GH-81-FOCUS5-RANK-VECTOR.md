---
gh_issue: 81
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/81
title: "Focus 5 — identity-agnostic ranking vector (local-commit recency)"
status: complete
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
| **Phases 1 & 2 SHIPPED + Codex r2 QA passed (2026-06-24) — GH-81 complete.** P1: reflog vector + `resolve_recency` ladder; migration `0007`; 24 repos no longer silently dropped. P2: explain UX (`explain_recency` strip + `basis_badge`). **Codex r2 (code review): `any_commit` gate confirmed `[Pass]`; 2 `[Should]` + 1 `[Nit]` fixed** — migration `0008` backfills legacy NULL recency (hide/rerank can't blank the board), `rank_cutoff_ts`/explain gated to the Focus 5 view (no Dirty-Five mislabel), + a linked-worktree fixture. Full suite green (**1112 passed**), `doctor` clean. | **Done** — ready to move to `3-COMPLETED`. |

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

- [x] **Define the signal semantically** (not a brittle message allowlist):
      `_classify_reflog_op` keys on the **leading op keyword** of each HEAD-reflog
      subject. *Accept:* `commit`/`commit (amend)`/`commit (initial)`, `cherry-pick`,
      `revert`, any `rebase` sub-op, and a **non-ff `merge`** (a real local merge
      commit). *Reject:* `pull`, `fetch`, `clone`, `checkout`, `reset`, `branch`,
      and a `merge … : Fast-forward`. Enumerated in **one** place
      (`_REFLOG_ACCEPT_OPS`/`_REFLOG_REJECT_OPS`); an unrecognized op → `None` →
      caller treats as reject **and logs** (`unknown_reflog_ops` stat).
- [x] **Fallback contract when the reflog is unavailable:** `resolve_recency`
      degrades `local_reflog` → `author_email` (old behavior, never regress below
      today) → `any_commit` → `none`. **Refinement (GH-81 impl):** the `any_commit`
      rung is gated behind `reflog_available=False`. A *readable* reflog with no
      local-commit op is a **definitive** "I never committed here" → `none`, so a
      foreign-only clone with a normal (enabled) reflog can never fall through to a
      foreign author's commit time and resurface the very bug this fixes. `any_commit`
      only fires when the reflog is genuinely off/missing. Basis is **recorded**.
- [x] `probe_repo_signals` captures `my_local_commit_ts` + `recency_basis`
      (`local_reflog`|`author_email`|`any_commit`|`none`) via `_probe_head_reflog_commit`
      + `resolve_recency`. Never raises (degrades through the ladder).
- [x] `RepoSignals` gains `my_local_commit_ts: int | None` + `recency_basis: str`;
      author-email `my_last_commit_ts` stays (display/diagnostic **and** fallback input).
- [x] `rank_recent_activity` ranks on `my_local_commit_ts` (eligible iff it's not
      `None` ⇔ `recency_basis != "none"`); `rank_reason` reads from it. Other
      strategies (`dirty_first`/`my_work`/`any_touch`) untouched.
- [x] **Minimal explain in Phase 1:** cards carry `recency_basis` + `my_local_commit_ts`
      (via `s.*`); off-roster rows now SELECT them too; `summary.rank_cutoff_ts` =
      the #5 repo's resolved recency (the board's threshold). Operator UX = Phase 2.
- [x] DB: persisted `my_local_commit_ts` + `recency_basis` via additive migration
      **`0007_focus5_local_commit_recency.sql`** (NULL-tolerant `ADD COLUMN` ×2).
      **Plan said `0004` — already taken (figma); `0005`/`0006` too — next free is
      `0007`.** Single writer (the focus5 probe), same as the other signals.
- [x] **Tests — op matrix:** `ReflogOpClassificationTests` (accept/reject/unknown),
      `ResolveRecencyTests` (all 4 rungs + the foreign-clone guard),
      `ReflogVectorProbeTests` (real-git: reflog basis, foreign-authored local
      commit eligible, `core.logAllRefUpdates=false` → author_email & any_commit
      rungs, empty repo → none), and `Focus5RankOracleTests` (pure + **real-git**
      sleuth-vs-EOS: local work outranks a fetch/checkout-only web-merge analog).
- [x] **Proof artifact:** captured on the real device DB (88 repos) — **24 repos the
      old email gate would silently drop are now eligible via reflog; 51 repos'
      ranking input changed** (largest local-vs-email gap +2145h). Basis spread:
      53 `local_reflog` / 27 `none` / 6 `author_email` / 2 `any_commit`. _The raw
      per-repo dump includes client repo names, so only the name-free aggregate was
      posted to [GH-81](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/81#issuecomment-4792867024)._

### QA Checklist — Phase 1

- [x] **DRY:** one classifier (`_classify_reflog_op`) + one ladder (`resolve_recency`),
      both consumed by probe; ranking + explain read the stored result, no second parse.
- [x] **SOLID:** vector isolated in `_probe_head_reflog_commit`/`resolve_recency` +
      the `rank_recent_activity` pure function; route/collector/render layers untouched.
- [x] **Diagnosable:** reflog-absent degrades through the ladder with the basis
      **recorded** (never a silent `None`); unrecognized ops logged + counted.
- [x] **Blast:** additive columns + pure-function swap = reversible; no destructive
      migration. Roster recomputes hourly; revert is a one-function change.
- [x] **Proof:** op-matrix + reflog-unavailable + sleuth/EOS-oracle tests green;
      before/after roster captured; `pytest tests/` **1098 passed**; `doctor` clean.
- [x] **Single write path:** the new columns are written only by the focus5 probe
      (`_SIGNAL_COLUMNS`), same writer as the other signals — no second writer.
- [x] **UTC:** `my_local_commit_ts` is a Unix epoch (committer `%ct`, UTC); display
      formats at the edge.

---

## Phase 2 — Operator-Facing Explain UX

> The machine-readable explain payload ships in Phase 1; Phase 2 is the **human
> surface** that makes "why is repo X (not) in Focus 5?" a one-line answer instead
> of `git log` forensics — including when a fallback basis was used.

- [x] Surfaced on the **off-roster strip** (the default lean — cheapest, already
      rendered): `_f5_warning_strip` now appends `explain_recency(...)` per repo —
      "your local commit Nd ago · below the #5 cutoff (Xh ago)" — reusing the
      Phase-1 `summary.rank_cutoff_ts`. (CLI/MCP surfaces deferred; one channel ships.)
- [x] **`recency_basis` made visible** — a fallback rung is shown, not silent:
      `explain_recency` appends "ranked by author email — this clone's HEAD reflog
      is disabled" / "ranked by latest commit — …" on the strip, and `basis_badge`
      puts a compact "(via author email)" / "(via latest commit)" badge on a
      **rostered** card so a degraded basis is visible on the board too.
- [x] Tests: `ExplainRecencyTests` (on-roster local_reflog, off-roster-below-cutoff,
      ineligible `none`, both fallback bases, no-cutoff case) + `BasisBadgeTests`,
      plus web-render tests (`test_off_roster_strip_explains_recency_vs_cutoff`,
      `…_shows_fallback_basis`, `…_card_shows_fallback_basis_badge`, `…_no_badge_on_normal`).

### QA Checklist — Phase 2

- [x] **DRY:** the UX reads `summary.rank_cutoff_ts` + the per-repo basis/recency
      from the Phase-1 payload; the basis→phrase vocabulary lives in **one** place
      (`_BASIS_NOTE`/`_BASIS_BADGE` in `focus5_scan.py`). No cutoff recomputation.
- [x] **SOLID:** `explain_recency`/`basis_badge` are pure functions over the cached
      payload; the web layer only renders. No new probe, no write.
- [x] **Proof:** `test_off_roster_strip_explains_recency_vs_cutoff` reproduces the
      GH-81 finding verbatim ("your local commit 3d ago · below the #5 cutoff
      (16h ago)") **and** `…_shows_fallback_basis` shows a fallback basis.
- [x] **Diagnosable (meta):** the strip answers "why isn't this repo in Focus 5?"
      inline (recency vs cutoff) and names the fallback basis when one was used —
      the exact question that needed `git log` forensics in GH-81.

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
4. ~~**Explain surface (Phase 2)**~~ — **RESOLVED (Phase 2 impl):** shipped on the
   **off-roster strip** (`explain_recency`) + a rostered-card fallback badge
   (`basis_badge`). CLI/MCP surfaces deferred — one channel was enough for v1.
5. **Hybrid escape hatch:** keep an *optional* email-match union for operators who
   want web-merge-only repos to rank? Default OFF; only if requested. _(Note: the
   `author_email` fallback rung already covers the reflog-disabled case.)_

## Review history

- **Codex relay r1 (2026-06-24)** — Verdict: Changes requested → all findings
  integrated above (no-reflog fallback contract; semantic op-set + test matrix;
  minimal explain pulled into Phase 1; DB-persist rationale stated; regression
  oracle + reflog-unavailable fixtures added to QA). Thread:
  [relay-system/2026-06-24/gh81-rank-vector.md](../../relay-system/2026-06-24/gh81-rank-vector.md).
- **Phase 1 implementation (2026-06-24)** — shipped in `focus5_scan.py` +
  migration `0007` + `test_focus5_scan.py`. Two deviations from the plan, both
  recorded above:
  1. **Migration number `0007`, not `0004`** — `0004`–`0006` already exist; the
     runner takes the next free integer.
  2. **`any_commit` rung gated behind `reflog_available=False`** — a literal
     `local_reflog → author_email → any_commit → none` ladder reintroduced the
     vendor-clone bug: a repo whose *enabled* reflog simply shows no local commit
     would fall through to a foreign author's commit time and become eligible. The
     impl resolves `none` for a readable-but-no-local-commit reflog, and only uses
     `any_commit` when the reflog is genuinely unavailable. All four basis values
     remain reachable; the core "foreign work can't masquerade as mine" invariant
     holds. (Worth a Codex r2 confirmation of this refinement.)
- **Phase 2 implementation (2026-06-24)** — operator explain UX shipped in
  `web.py` (off-roster strip + card badge) over two pure helpers in
  `focus5_scan.py` (`explain_recency`, `basis_badge`); no new probe/write. Tests:
  `ExplainRecencyTests` + `BasisBadgeTests` (pure) and 4 web-render assertions.
  Full suite **1109 passed**, `doctor` clean. GH-81 is feature-complete; remaining
  is the optional Codex r2 on the `any_commit`-gating refinement + filing the doc
  to `3-COMPLETED`.
- **Codex relay r2 (2026-06-24) — CODE QA, Verdict: Changes requested → all resolved.**
  Thread: [relay-system/2026-06-24/gh81-code-qa.md](../../relay-system/2026-06-24/gh81-code-qa.md).
  The `any_commit`-gating refinement was confirmed correct (`[Pass]`). Three findings,
  all Implemented:
  1. **[Should]** post-`0007` hide/rerank could blank the board (legacy NULL recency
     rows). → migration **`0008`** backfills NULL rows to the old author-email basis;
     `rerank_focus5_from_cache` runs migrations before reading, so the backfill always
     precedes a rerank. Regression test added.
  2. **[Should]** `rank_cutoff_ts` was mislabelled under Dirty Five (Focus-5 copy on a
     `dirty_first` cutoff). → cutoff + explain caption gated to the `recent_activity`
     view only. Test added.
  3. **[Nit]** no linked-worktree (`.git`-file) reflog fixture. → added.
  Result: `pytest tests/` **1112 passed**, `doctor` clean.
