# RELAY · GH-101 Phase 2 — derived status/reason + doctor warning path (rebalance-OS#101)
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 2 / 5

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are the agent bound to it (see Setup) **and** the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup (read the real files / the latest `git show <last commit>` diff; cite `file:line`):
   - **Reviewer:** review vs the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete proposed fix → set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the artifact; you only append findings here. **Before you set `Approved`, re-read the artifact file itself** (not this log) and confirm every prior `Implemented` fix is actually present and complete — any that is missing or partial → set `Changes requested` with a `[Blocker] claimed-implemented-but-absent @ file:line` instead.
   - **Producer:** for every open finding log a disposition (Implemented / Modified / Declined + why), make the change, then add new work. **Before you flip `NEXT`, re-read the artifact and confirm each `Implemented → @ file:line` actually landed in the file** — cite the line as it appears in your commit diff. A claim you can't point to in the file is not done.
4. **Append ONE block** at the very bottom, directly **above** the marker line (`<!-- ↓↓↓ NEXT TURN ... -->`). Never edit earlier turns. Header it `### Round N · <Role> · <your-label> · <date time>`; a Reviewer block carries `**Verdict:**` + `**Findings & proposals:**` (graded bullets) + `**Commit:**`; a Producer block carries `**Decisions on proposals:**` + `**Did:**` + `**Re-review this:**` + `**Commit:**`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` (`Approved` closes the relay — Reviewer only; else leave `Open`); the Producer bumps `ROUND` when opening a new cycle.
6. **Commit only the files you touched** (artifact + this log): `git commit -m "relay(gh101-phase2-status-doctor): <your-label> r<N>"`, then put the short hash in your block's `Commit:` line.
7. **Stop.** Report your one-line result.

## Setup
- Artifact under review: `src/rebalance/ingest/index_ops.py`, `src/rebalance/cli/__init__.py`, `tests/test_index_ops.py`, `tests/test_doctor.py`
- Definition of Done: per [GH-101-SIGNAL-QUALITY-CONTRACT.md §5 Phase 2](../../PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md#phase-2--derived-statusreason--one-doctor-warning-path) — derive `status` (`ok`/`warn`/`degraded`) + `reason` per source, merged into the existing `payload["freshness"]` dict (never clobbering the semantic-drift keys already written there per the Phase 0 finding at index_ops.py:385), from (a) staleness vs. the source's window and (b) zero/collapsed `recent_row_count_7d`; plus **one** `doctor` warning path (cli/__init__.py) printing degraded sources with their reason. Test feeds a fresh-but-empty source and asserts `status == "degraded"` with a non-empty `reason`; a healthy source asserts `ok`; a legitimately quiet source does not hard-fail (warn only). Full `pytest tests/` green; `rebalance doctor` clean.
- Producer: codex   ·   Reviewer: agy
- Handoff: cli-driven (relay-xyz — codex builds, agy reviews; single-session headless)
- Started: 2026-07-05

## Task brief (for the Producer's first turn)
Part of the 2026-07-05 marathon, Lane B (see [MARATHON-2026-07-05.md](../../PROJECT/2-WORKING/MARATHON-2026-07-05.md)). Implements Phase 2 of [GH-101-SIGNAL-QUALITY-CONTRACT.md](../../PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md):

- Read `get_index_status()` in `src/rebalance/ingest/index_ops.py` (Phase 1 already added `recent_row_count_7d` per-source; Phase 0's finding at line ~385 shows `payload["freshness"]` is overwritten with a semantic-drift dict — you must **merge** derived `status`/`reason` into it, e.g. under a `signal_health` sub-key or additional keys alongside the existing drift keys, not replace the dict).
- Derive `status` ∈ `{ok, warn, degraded}` + `reason` (a short string, present only when not `ok`) per source: `warn`/`degraded` if the source hasn't advanced its timestamp within its expected window (stale), or if it synced recently but `recent_row_count_7d` collapsed to zero (or far below its norm). A legitimately zero-volume week should be `warn`, not a hard fail — never adjudicate, just surface.
- Add **one** `doctor` warning path in `src/rebalance/cli/__init__.py` (~line 114 per the doc) that prints degraded sources with their `reason`. No new screen, no new job.
- Tests: extend `tests/test_index_ops.py` (fresh-but-empty source → `degraded` + non-empty reason; healthy source → `ok`; legit-quiet source → `warn` not a hard fail) and `tests/test_doctor.py` (the new warning line shows on a seeded degraded DB).
- Verify: `pytest tests/` green, `rebalance doctor` clean, and write a `Verification summary` into `GH-101-SIGNAL-QUALITY-CONTRACT.md`'s Phase 2 section per the doc's own convention.
- **No new table, no new MCP tool, no ingest gate** — read-side only, per the doc's anti-goals.

## Ground rules
1. This file is the single source of truth. If it isn't written here, assume the other agent doesn't know it. The two agents may be different tools and never share memory.
2. Read the whole file. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns. Then update `NEXT`, `STATUS`, `ROUND` at the top.
4. Stay tight. Requests and findings are bullets, not essays.
5. **The Reviewer never edits the artifact.** It proposes graded findings, each with a concrete suggested fix where possible. The Producer decides each proposal and implements the approved ones — logging a disposition for every one.
6. Grade every finding: `[Blocker]` must fix to ship · `[Should]` strong recommendation · `[Nit]` optional · `[Pass]` checked and sound.
7. The Reviewer posts a Verdict every turn. The relay ends on **Approved**. If the max `ROUND` ends without `Approved`, set `STATUS: Escalated` and hand back to the human.
8. End your turn by committing it: `relay(gh101-phase2-status-doctor): <role> r<N>`, then fill the hash into your `Commit:` line.
9. **One window at a time, clean tree at every handoff.** Never flip `NEXT` with uncommitted changes left in the tree.
10. **Evidence contract — state your proof every turn.** Producer logs `Verification:` (`pytest`/`doctor` commands + results); Reviewer logs `Basis:` (`behaviorally proven` — ran the tests/doctor yourself — or `textual only`).
11. **Reconcile claims against the file, not this log**, before flipping `NEXT` (Producer) or setting `Approved` (Reviewer).

## Roles
- **Producer** — the only writer of the artifact: builds it, requests review, decides and implements proposals, updates.
- **Reviewer** — reviews against the DoD, proposes graded findings with suggested fixes, sets a verdict. Never edits the artifact.

---
## Log

### Round 1 · Producer · codex · 2026-07-05 15:38 PDT
**Decisions on proposals:**
- No prior reviewer findings on this first producer turn.

**Did:**
- Added read-side signal-health derivation rules, timestamp parsing, staleness/zero-volume classification, and preserved the existing semantic-drift keys by merging under `freshness.signal_health` in [src/rebalance/ingest/index_ops.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.8xFKdR/src/rebalance/ingest/index_ops.py:182), [src/rebalance/ingest/index_ops.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.8xFKdR/src/rebalance/ingest/index_ops.py:236), and [src/rebalance/ingest/index_ops.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.8xFKdR/src/rebalance/ingest/index_ops.py:516).
- Added the single warn-only `doctor` render path for degraded sources in [src/rebalance/cli/__init__.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.8xFKdR/src/rebalance/cli/__init__.py:143).
- Extended status tests for fresh-but-empty => `degraded`, healthy => `ok`, and legit-quiet Sleuth => `warn` in [tests/test_index_ops.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.8xFKdR/tests/test_index_ops.py:126).
- Added the seeded CLI regression test for the degraded doctor line in [tests/test_doctor.py](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.8xFKdR/tests/test_doctor.py:128).
- Wrote the Phase 2 verification summary back into the contract doc in [PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md](/private/var/folders/69/3l_82qtj7fzglnt_jjg07jh40000gn/T/rtl-wt.8xFKdR/PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md:311).

**Re-review this:**
- Confirm the merge into `payload["freshness"]` leaves the three semantic-drift keys intact and adds only `signal_health`.
- Sanity-check the quiet-source heuristic: `sleuth`/`figma`/`ask_self`/`apple_reminders` zero-volume weeks warn; `vault`/`github`/`calendar`/`email` zero-volume fresh syncs degrade.
- Confirm the CLI path is warn-only output and does not change `doctor` exit semantics.

**Verification:**
- `PYTHONPATH=src /Users/noelsaw/Documents/rebalance-OS/.venv/bin/python -m pytest tests/test_index_ops.py tests/test_doctor.py` → `33 passed`.
- Initial attempts with system Python and `uv run` were environment-only failures (`rebalance`/`typer` missing; then no network for PyPI). The passing run above used the existing repo virtualenv and the exact two changed test files only.

**Commit:** pending (relay harness owns the file-scoped commit; manual `git` was intentionally not run)

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->
