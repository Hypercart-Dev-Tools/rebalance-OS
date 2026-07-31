# Marathon Phase p1-gh189
STATUS: Approved
NEXT: claude

<!-- marathon-drive: task=MARATHON-P1-GH189-TURN builder=claude reviewer=agy round-cap=5 -->

## Phase Brief

# Marathon preflight packet — gh-189-pulse-dashboard-residual-gaps

- Generated: 2026-07-30T20:10:33Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-189-PULSE-DASHBOARD-RESIDUAL-GAPS.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ a4d22c43e)
- Suggested branch: `marathon/gh-189-pulse-dashboard-residual-gaps-2026-07-30` (branch_ready=false — carve-out: risk=1/independent zone, proceed on the current branch without asking)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k "doctor or pulse_web" -q`

- Artifacts: src/rebalance/doctor.py,scripts/pulse_web.py
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 4721 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] Health banner shows an absolute-anchored timestamp (via `format_timestamp()`),
- [ ] Repo-pie labels show short repo names (org prefix stripped), matching the
- [ ] No new time module or new stripping rule introduced — reuse existing helpers.
- [ ] `pytest -k "doctor or pulse_web"` green.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `src/rebalance/doctor.py,scripts/pulse_web.py` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k "doctor or pulse_web" -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-189-pulse-dashboard-residual-gaps RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact src/rebalance/doctor.py,scripts/pulse_web.py \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k "doctor or pulse_web" -q' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above


## Debug mantra (auto-triggered — 1 prior attempt(s) on this phase did not reach Approved)

Before trying again, read /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/relay-automation/DEBUG-MANTRA.md and follow its four-step discipline: reproduce reliably, know the fail path, question the hypothesis, treat this round as a breadcrumb for the next one.
Last recorded reason (/Users/matthewtaylor/htdocs/rebalance-OS/phases/10days-2026-07-30--p1-gh189/ESCALATION.md): `pre-advance-failed`. Read it before re-guessing.

---

▶ TAKE YOUR TURN (claude — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/doctor.py,scripts/pulse_web.py
2. Append a build block to this relay file: `### Round N · Builder · claude` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick claim MARATHON-P1-GH189-TURN --agent claude --paths "phases/10days-2026-07-30--p1-gh189/RELAY.md,src/rebalance/doctor.py,scripts/pulse_web.py"
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick ping MARATHON-P1-GH189-TURN --agent claude
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P1-GH189-TURN --agent claude --to agy
4. Edit ONLY these paths: phases/10days-2026-07-30--p1-gh189/RELAY.md and src/rebalance/doctor.py,scripts/pulse_web.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

### Round 1 · Builder · claude

**Files touched:** `src/rebalance/doctor.py`

**What was done:**
- Added `timedelta` to the top-level `from datetime import` (line 18) — no new module, just extending the existing `datetime` import.
- In `_check_pulse_collectors()`, replaced the two bare-relative branches (`elif health.age_hours >= 24:` and `else:`) with absolute-anchored output that computes a derived UTC datetime from `age_hours`, passes it through `format_timestamp()` for the absolute anchor, then appends the decimal relative suffix (e.g. `"1.2d ago"`) as a label.

**Example output (30h stale device):**
Before: `"ALERT — last scan 1.2d ago"`
After:  `"ALERT — last scan 2026-07-29 2:30 PM · 1.2d ago"`

**Key decisions:**
- Kept the `f"{health.age_hours / 24:.1f}d ago"` decimal suffix so the existing test (`assertIn("1.2d ago", detail)`) continues to pass.
- The fix-probe pattern `age_hours / 24` is still present as the suffix expression — the acceptance criterion is "absolute-anchored via format_timestamp()", not "remove the decimal", and the test enforces the decimal stays.
- `pulse_web.py` not changed: `render_repo_pie()` already calls `_repo_short_name()` at line 1038 (org prefix already stripped), so no edit was needed there.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/doctor.py,scripts/pulse_web.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P1-GH189-TURN --agent agy --to claude
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick done MARATHON-P1-GH189-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/10days-2026-07-30--p1-gh189/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to claude —
   claude, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

---

### Round 1 · Reviewer · agy

**Verdict:** Approved

swept file: yes

**Review summary:**
- Verified `src/rebalance/doctor.py`: `_check_pulse_collectors()` now computes and formats an absolute-anchored timestamp using `format_timestamp(derived, tz=local_tz())` alongside the relative age label.
- Verified `scripts/pulse_web.py`: `render_repo_pie()` uses `_repo_short_name()` for repo pie chart labels (org prefix stripped).
- Re-used existing timestamp and string helpers (`format_timestamp`, `_repo_short_name`); no redundant time modules or regexes added.
- Performed a full file sweep of `src/rebalance/doctor.py` and `scripts/pulse_web.py`: 0 pre-existing defects found.
- All target unit tests (`pytest -k "doctor or pulse_web"`) pass cleanly (81 passed).

relay closed, no further turn needed

