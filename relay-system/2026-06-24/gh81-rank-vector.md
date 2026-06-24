# RELAY · GH-81 Focus 5 ranking vector — Codex plan review
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
3. **Do your role's work** on the artifact named in Setup. This is a **planning document** (not code): read the real plan doc AND the referenced source it changes, and ground every finding in `file:line`. `Basis: code+doc read`.
   - **Reviewer (Codex):** adversarially review the plan against the Review Questions in Setup → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each citing `§section` or `file:line` with a concrete proposed fix. Set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the plan; append findings here only.
   - **Producer (Claude):** for every open finding log a disposition (Implemented / Modified / Declined + why) in the plan doc, then re-verify.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns. Header it `### Round N · <Role> · <label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Basis:**` + `**Findings & proposals:**` (graded bullets) + `**Answers:**` + `**Commit:**`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` — `Approved` closes the relay (Reviewer only). This relay is `ROUND: 1 / 1`: if you would request changes rather than approve, set `STATUS: Escalated` and hand back to the human (no second round).
6. **Commit only the files you touched** (this log): `git commit -m "relay(gh81): reviewer r1"`, then put the short hash in your block's `Commit:` line and `git commit --amend --no-edit`.
7. **Stop.** Tell the operator your one-line result.

## Setup
- Artifact under review: **the plan doc** [PROJECT/1-INBOX/GH-81-FOCUS5-RANK-VECTOR.md](../../PROJECT/1-INBOX/GH-81-FOCUS5-RANK-VECTOR.md) (GitHub issue #81).
- Code it changes (read for grounding):
  - `src/rebalance/ingest/focus5_scan.py` — `rank_recent_activity` (ranks on `my_last_commit_ts`), `_recency`, `probe_repo_signals` (captures signals incl. `my_last_commit_ts` via `git log -1 --author=<git config user.email>`, and `head_reflog_ts`), `RepoSignals`, `summarize_focus5`, `rank_repos`.
  - `src/rebalance/ingest/db/migrations/` — focus5 schema (`0003_focus5_roster.sql`); Phase 1 proposes an additive `0004` column `my_local_commit_ts`.
- Context: the headline Focus 5 silently dropped a repo (`sleuth-app`) whose recent local commits used a different author email than the device's `git config user.email`; a web-merge-only repo (`EOS-daily-skill`) ranked instead. The plan switches the ranking vector from single-email authorship → **local-commit HEAD-reflog recency** (identity-agnostic), + an explain-rank diagnostic. Two phases.
- **Review Questions (the Definition of Done for this review):**
  1. **Vector durability** — is local-commit reflog recency genuinely the most durable/maintainable vector, vs. an email-set or unify-identity? Failure modes we missed? (reflog expiry/gc, `git config core.logAllRefUpdates=false` disabling HEAD reflog, shallow clones, worktrees, squash/rebase reflog message variance across git versions, bare/server checkouts.)
  2. **Reflog op-set** — is `commit`/`commit (amend)`/`commit (initial)`/`rebase` the right inclusion set, excluding `pull`/`fetch`/`checkout`/`clone`/`reset`? Any op mis-bucketed (e.g. `merge` that creates a local merge commit = my work vs fast-forward = foreign; `cherry-pick`; `revert`)?
  3. **2-phase split** — right granularity, or should explain-rank fold into Phase 1 / split further?
  4. **DB migration** — additive `0004` column vs compute-on-read (Open Question 1). Which is more durable given the hourly recompute + the existing signal-cache pattern?
  5. **Acceptance criteria & QA gaps** — anything missing to call this safely done (proof oracle quality, backward-compat of old NULL rows, behavior when reflog is unavailable)?
- Producer: Claude (Opus 4.8)   ·   Reviewer: Codex CLI
- Handoff: automated (relay-drive.sh + codex-turn.sh)
- Started: 2026-06-24

## Ground rules
- Read the **real** plan doc + the cited `focus5_scan.py` functions — cite `§section` or `file:line`. `Basis: code+doc read`.
- Grade every finding (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`) with a concrete proposed fix.
- The reviewer does **not** edit the plan — append findings to this file only.
- One round trip. If not Approvable, set `STATUS: Escalated` and hand back to the human.

## Log

### Round 1 · Producer · Claude (Opus 4.8) · 2026-06-24
**Did:** Drafted GH-81 — switch `rank_recent_activity` from single-email authorship (`my_last_commit_ts`) to identity-agnostic local-commit HEAD-reflog recency, + an explain-rank diagnostic. Two phases; SWE-lens rationale in the plan; ROADMAP Deferred pointer added; PDDA doc gates green.
**For the reviewer (Codex):** Adversarially pressure-test the plan against the five Review Questions above — especially (1) vector durability / missed failure modes and (2) the reflog op-set correctness. Cite `file:line` in `focus5_scan.py` and `§section` in the plan. Verdict + Escalate if any `[Blocker]`/`[Should]` remain.
**Re-review this:** [PROJECT/1-INBOX/GH-81-FOCUS5-RANK-VECTOR.md](../../PROJECT/1-INBOX/GH-81-FOCUS5-RANK-VECTOR.md) + `src/rebalance/ingest/focus5_scan.py`.
**Commit:** (seed)

<!-- ↓↓↓ NEXT TURN APPENDS BELOW THIS LINE — do not write above it ↓↓↓ -->
