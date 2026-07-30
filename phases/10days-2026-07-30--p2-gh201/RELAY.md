# Marathon Phase p2-gh201
STATUS: Approved
NEXT: claude

<!-- marathon-drive: task=MARATHON-P2-GH201-TURN builder=claude reviewer=agy round-cap=5 -->

## Phase Brief

# Marathon preflight packet — gh-201-database-path-fallback

- Generated: 2026-07-30T20:10:34Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-201-DATABASE-PATH-FALLBACK.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ a4d22c43e)
- Suggested branch: `marathon/gh-201-database-path-fallback-2026-07-30` (branch_ready=false — carve-out: risk=1/independent zone, proceed on the current branch without asking)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k "paths or resolve_database" -q`

- Artifacts: src/rebalance/paths.py,tests/test_paths.py
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 475 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] An explicit `--database` path that does not exist raises a clear error instead
- [ ] Callers that legitimately want fallback-to-canonical (if any) keep working —
- [ ] `pytest -k "paths or database"` green.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `src/rebalance/paths.py,tests/test_paths.py` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k "paths or resolve_database" -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-201-database-path-fallback RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact src/rebalance/paths.py,tests/test_paths.py \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k "paths or resolve_database" -q' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above


---

▶ TAKE YOUR TURN (claude — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/paths.py,tests/test_paths.py
2. Append a build block to this relay file: `### Round N · Builder · claude` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick claim MARATHON-P2-GH201-TURN --agent claude --paths "phases/10days-2026-07-30--p2-gh201/RELAY.md,src/rebalance/paths.py,tests/test_paths.py"
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick ping MARATHON-P2-GH201-TURN --agent claude
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P2-GH201-TURN --agent claude --to agy
4. Edit ONLY these paths: phases/10days-2026-07-30--p2-gh201/RELAY.md and src/rebalance/paths.py,tests/test_paths.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/paths.py,tests/test_paths.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P2-GH201-TURN --agent agy --to claude
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick done MARATHON-P2-GH201-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/10days-2026-07-30--p2-gh201/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to claude —
   claude, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

---

### Round 1 · Builder · claude

**Files touched:** `src/rebalance/paths.py`, `tests/test_paths.py`

**What changed:**

`resolve_database_path()` previously treated `explicit` as candidate #1 in the shared ordered list, letting the loop fall through to canonical/env/config/walk-up layers when the explicit path didn't exist. Fixed by short-circuiting at the top of the function: if `explicit` is non-None and the resolved path does not exist, raise `DatabaseNotFoundError` immediately with only that candidate — no fallback, no silent success.

Created `tests/test_paths.py` (new file per GH-201 contract):
- `TestExplicitPath` — four tests: nonexistent explicit raises immediately; regression guard that a present canonical DB is NOT returned when explicit is wrong; existing explicit returned directly; explicit ignores env var.
- `TestFallbackChain` — five tests covering env var priority, canonical, user config, walk-up, and the all-absent raises path.
- `TestDatabaseNotFoundError` — three tests: candidates stored on the exception, message lists paths/sources, is-a FileNotFoundError.

All 12 tests pass (`pytest tests/test_paths.py` with worktree src on PYTHONPATH).

**Key decisions:**
- Raise immediately with a single-candidate list (only `--database flag`) rather than appending to the broader chain, so the error message is focused on what the operator actually typed.
- If explicit IS found, return it directly (skipping all other layers) — this was already the implicit intent and is now explicit.
- Acceptance criterion "callers that legitimately want fallback-to-canonical keep working" is satisfied because the only change in behaviour is when `explicit` is non-None; the entire fallback chain is unchanged when `explicit` is None.

---

### Round 1 · Reviewer · agy

**Verdict:** Approved

swept file: yes

**Review Summary:**
- Verified implementation of explicit `--database` non-existent path behavior in `src/rebalance/paths.py`: `resolve_database_path()` short-circuits when `explicit` is provided, raising `DatabaseNotFoundError` immediately if the file does not exist, without falling back to lower priority layers.
- Verified fallback chain remains intact when `explicit` is `None`.
- Reviewed all test cases in `tests/test_paths.py`: all 12 tests pass cleanly (`.venv/bin/python -m pytest tests/test_paths.py`).
- Conducted full-file sweep of `src/rebalance/paths.py` and `tests/test_paths.py` (swept file: yes); no pre-existing defects found.

relay closed, no further turn needed

