# RELAY · GH-81 Focus 5 ranking vector — Codex CODE QA review (Phases 1 & 2)
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Reviewer (Codex)
STATUS: Open
ROUND: 1 / 1

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it (see Setup) and the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup. This is **shipped CODE** (not a plan): read the real source AND its tests, run/trace the logic, and ground every finding in `file:line`. `Basis: code+test read`.
   - **Reviewer (Codex):** adversarially review the implementation against the Review Questions in Setup → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each citing `file:line` with a concrete proposed fix. Set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the code; append findings here only.
   - **Producer (Claude):** for every open finding log a disposition (Implemented / Modified / Declined + why), then re-verify (`pytest tests/`).
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns. Header it `### Round N · <Role> · <label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Basis:**` + `**Findings & proposals:**` (graded bullets) + `**Answers:**` + `**Commit:**`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` — `Approved` closes the relay (Reviewer only). This relay is `ROUND: 1 / 1`: if you would request changes rather than approve, set `STATUS: Escalated` and hand back to the human (no second round).
6. **Commit only the files you touched** (this log): `git commit -m "relay(gh81-qa): reviewer r1"`, then put the short hash in your block's `Commit:` line and `git commit --amend --no-edit`.
7. **Stop.** Tell the operator your one-line result.

## Setup
- Artifacts under review (the **shipped Phase 1 & 2 implementation**, all committed on `development`):
  - `src/rebalance/ingest/focus5_scan.py` — the GH-81 vector:
    - `_classify_reflog_op` + `_REFLOG_ACCEPT_OPS`/`_REFLOG_REJECT_OPS` (the reflog op classifier).
    - `_probe_head_reflog_commit` (reads HEAD reflog newest-first; returns `(ts, reflog_available)`).
    - `resolve_recency` (the `local_reflog → author_email → any_commit → none` ladder, with the `any_commit` rung **gated behind `reflog_available=False`**).
    - `probe_repo_signals` wiring; `RepoSignals` gains `my_local_commit_ts` + `recency_basis`.
    - `rank_recent_activity` (now ranks on `my_local_commit_ts`).
    - `explain_recency` + `basis_badge` + `_BASIS_NOTE`/`_BASIS_BADGE` (Phase 2 explain helpers).
    - `summarize_focus5` (off-roster SELECT + `summary.rank_cutoff_ts`).
  - `src/rebalance/ingest/db/migrations/0007_focus5_local_commit_recency.sql` — additive `my_local_commit_ts` + `recency_basis` columns.
  - `src/rebalance/web.py` — `_f5_warning_strip` (renders `explain_recency`) + `_f5_card` (renders `basis_badge`).
  - `tests/test_focus5_scan.py` + `tests/test_web_focus5.py` — op matrix, ladder, real-git fallback fixtures, sleuth/EOS oracle, explain/badge tests.
  - `tests/test_calendar_composite_pk_migration.py` — fixture changed to apply real migrations 0002–0004.
- Context: the headline Focus 5 silently dropped repos whose recent local commits used a non-matching author email. Phase 1 switched the vector to local-commit HEAD-reflog recency; Phase 2 added the operator explain UX. Real-device proof: 24 repos no longer silently dropped.
- **Review Questions (the Definition of Done for this review):**
  1. **`any_commit`-gating refinement (the deliberate deviation from the plan's literal ladder)** — `resolve_recency` only uses the `any_commit` rung when `reflog_available=False`; a *readable* reflog with no local-commit op resolves to `none`. Is this correct and safe? Does it ever (a) wrongly drop a repo I really worked in, or (b) wrongly surface a foreign clone? Trace `_probe_head_reflog_commit`'s `reflog_available` signal: is the "readable but empty / no-accept-entry" vs "unreadable/disabled" distinction sound across git versions (empty reflog exit codes, `core.logAllRefUpdates=false`, GC-expired, shallow/worktree)?
  2. **Reflog op classifier** — `_classify_reflog_op` keys on the *leading op keyword* of `%gs`. Is the accept/reject partition right (commit/amend/initial, cherry-pick, revert, any rebase sub-op, non-ff merge = accept; pull/fetch/clone/checkout/reset/branch/ff-merge = reject)? Any op mis-bucketed or any `%gs` phrasing that breaks the leading-keyword parse (e.g. `merge` detail detection, `rebase -i (pick)`, detached-HEAD, localized git)? Is "unrecognized → reject + log, keep scanning older entries" the right conservative default?
  3. **Correctness of ranking + eligibility** — `rank_recent_activity` ranks on `my_local_commit_ts` (eligible iff not None). Any regression vs the old `my_last_commit_ts` gate? NULL legacy rows after migration `0007` (pre-resync rerank-from-cache) — acceptable, or a silent-empty-roster risk?
  4. **Phase 2 explain correctness** — `explain_recency` / `basis_badge` / `rank_cutoff_ts`: is the cutoff math right (off-roster repo below the #5 cutoff)? Any HTML-escaping or contract-shape (`/focus-5.json`) concern from the added `summary.rank_cutoff_ts` + card fields?
  5. **Tests & QA gaps** — do the op-matrix / fallback-fixture / sleuth-EOS-oracle tests actually pin the behavior, or is there a gap (e.g. a real-git `any_commit` path, a `pull`-that-creates-a-merge-commit case, worktree `.git`-file repos)?
- Producer: Claude (Opus 4.8)   ·   Reviewer: Codex CLI
- Handoff: automated (relay-drive.sh + codex-turn.sh, `--target-root` = this repo)
- Started: 2026-06-24

## Ground rules
- Read the **real** source + tests — cite `file:line`. `Basis: code+test read`.
- Grade every finding (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`) with a concrete proposed fix.
- The reviewer does **not** edit the code — append findings to this file only.
- One round trip. If not Approvable, set `STATUS: Escalated` and hand back to the human.

## Log

### Round 1 · Producer · Claude (Opus 4.8) · 2026-06-24
**Did:** Implemented GH-81 Phases 1 & 2 — reflog op classifier + `resolve_recency` ladder (with the `any_commit` rung gated behind reflog-unavailable), `my_local_commit_ts`/`recency_basis` on `RepoSignals`, `rank_recent_activity` ranks on the new vector, migration `0007`, and the Phase 2 explain UX (`explain_recency` on the off-roster strip + `basis_badge` on roster cards). Full suite green (1109 passed), `doctor` clean. Real-device proof: 24 repos no longer silently dropped.
**For the reviewer (Codex):** Adversarially pressure-test the implementation against the five Review Questions — especially (1) the `any_commit`-gating refinement and (2) the reflog op classifier. Cite `file:line`. Verdict + Escalate if any `[Blocker]`/`[Should]` remain.
**Re-review this:** `src/rebalance/ingest/focus5_scan.py`, `src/rebalance/ingest/db/migrations/0007_focus5_local_commit_recency.sql`, `src/rebalance/web.py`, `tests/test_focus5_scan.py`, `tests/test_web_focus5.py`.
**Commit:** (seed)

<!-- ↓↓↓ NEXT TURN APPENDS BELOW THIS LINE — do not write above it ↓↓↓ -->
