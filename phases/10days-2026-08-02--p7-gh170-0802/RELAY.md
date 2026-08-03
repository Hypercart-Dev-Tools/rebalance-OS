# Marathon Phase p7-gh170-0802
STATUS: Open
NEXT: claude

<!-- marathon-drive: task=MARATHON-P7-GH170-0802-TURN builder=claude reviewer=agy round-cap=5 -->

## Phase Brief

# Marathon preflight packet — gh-170-worktree-test-isolation

- Generated: 2026-08-02T17:46:01Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-170-WORKTREE-TEST-ISOLATION.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ 5b992a281)
- Suggested branch: `marathon/gh-170-worktree-test-isolation-2026-08-02` (branch_ready=false — not cut yet; ask the operator before proceeding, per GUIDING-PRINCIPLES.md §8)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -q`

- Artifacts: conftest.py,tests/conftest.py,pyproject.toml
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=600` (sized to ≈ 234 LOC across 3 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] Running `pytest` from inside a linked worktree imports that worktree's own
- [ ] A regression test (or documented manual repro) proves the isolation: modify a
- [ ] No behavior change for the normal (non-worktree) case.
- [ ] `pytest tests/` green from both the main checkout and a scratch worktree.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `conftest.py,tests/conftest.py,pyproject.toml` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-170-worktree-test-isolation RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact conftest.py,tests/conftest.py,pyproject.toml \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -q' \
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
1. Implement the brief by creating/editing the artifact file(s): conftest.py,tests/conftest.py,pyproject.toml
2. Append a build block to this relay file: `### Round N · Builder · claude` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick claim MARATHON-P7-GH170-0802-TURN --agent claude --paths "phases/10days-2026-08-02--p7-gh170-0802/RELAY.md,conftest.py,tests/conftest.py,pyproject.toml"
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick ping MARATHON-P7-GH170-0802-TURN --agent claude
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P7-GH170-0802-TURN --agent claude --to agy
4. Edit ONLY these paths: phases/10days-2026-08-02--p7-gh170-0802/RELAY.md and conftest.py,tests/conftest.py,pyproject.toml. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

### Round 1 · Builder · claude

**Files touched:**
- `conftest.py` — NEW root-level conftest. Detects linked worktree by checking whether `.git` is a file (worktree) vs directory (main checkout). If a file is found, prepends `<worktree_root>/src` to `sys.path[0]` before any test collection begins, overriding the main checkout's editable-install `.pth` entry. Idempotent (skips if already at position 0). No-op in main checkout.
- `tests/conftest.py` — Added `from pathlib import Path` import. Added `_assert_worktree_path_isolation` session-scoped autouse fixture as a regression guard: detects if running in a worktree and asserts `sys.path[0]` is this worktree's `src/`. Fails with a descriptive message if the root conftest.py is ever removed or broken.
- `pyproject.toml` — Added `[tool.pytest.ini_options]` with `testpaths = ["tests"]` so pytest resolves rootdir consistently and loads root `conftest.py` from any invocation directory.

**Key decisions:**
- Detection method: `.git` file vs directory is the standard git worktree marker — reliable, no subprocess needed.
- Regression guard goes in `tests/conftest.py` as a session fixture (scope lock prohibits a new test file); autouse session fixture fires once and gives a clear failure message if the isolation breaks.
- Manual repro documented in root `conftest.py` docstring (git worktree add → patch a symbol → confirm cross-checkout divergence).
- Acceptance criteria status: worktree imports own src/ ✓; regression guard in place ✓; no behavior change for main checkout ✓ (.git dir check early-returns); `pytest tests/` should be green (harness runs gate).

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: conftest.py,tests/conftest.py,pyproject.toml. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P7-GH170-0802-TURN --agent agy --to claude
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick done MARATHON-P7-GH170-0802-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/10days-2026-08-02--p7-gh170-0802/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to claude —
   claude, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
