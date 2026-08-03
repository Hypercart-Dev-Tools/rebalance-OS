# Marathon Phase p10-gh186-0802
STATUS: Open
NEXT: claude

<!-- marathon-drive: task=MARATHON-P10-GH186-0802-TURN builder=claude reviewer=agy round-cap=5 -->

## Phase Brief

# Marathon preflight packet — gh-186-scheduler-eintr-crash

- Generated: 2026-08-02T17:46:05Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-186-SCHEDULER-EINTR-CRASH.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ 5b992a281)
- Suggested branch: `marathon/gh-186-scheduler-eintr-crash-2026-08-02` (branch_ready=false — not cut yet; ask the operator before proceeding, per GUIDING-PRINCIPLES.md §8)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k scheduler -q`

- Artifacts: scripts/github_sync.sh,scripts/lib/scheduler_common.sh
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=300` (sized to ≈ 125 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] A transient interpreter-bootstrap `EINTR` is retried (bounded, e.g. 1-2 retries)
- [ ] Retry is scoped to the actual interpreter-startup failure mode, not a blanket
- [ ] `rebalance doctor` / scheduler tests green.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `scripts/github_sync.sh,scripts/lib/scheduler_common.sh` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k scheduler -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-186-scheduler-eintr-crash RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact scripts/github_sync.sh,scripts/lib/scheduler_common.sh \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k scheduler -q' \
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
1. Implement the brief by creating/editing the artifact file(s): scripts/github_sync.sh,scripts/lib/scheduler_common.sh
2. Append a build block to this relay file: `### Round N · Builder · claude` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick claim MARATHON-P10-GH186-0802-TURN --agent claude --paths "phases/10days-2026-08-02--p10-gh186-0802/RELAY.md,scripts/github_sync.sh,scripts/lib/scheduler_common.sh"
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick ping MARATHON-P10-GH186-0802-TURN --agent claude
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P10-GH186-0802-TURN --agent claude --to agy
4. Edit ONLY these paths: phases/10days-2026-08-02--p10-gh186-0802/RELAY.md and scripts/github_sync.sh,scripts/lib/scheduler_common.sh. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: scripts/github_sync.sh,scripts/lib/scheduler_common.sh. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P10-GH186-0802-TURN --agent agy --to claude
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick done MARATHON-P10-GH186-0802-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/10days-2026-08-02--p10-gh186-0802/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to claude —
   claude, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

---

### Round 1 · Builder · claude

**Files touched:** `scripts/lib/scheduler_common.sh`, `scripts/github_sync.sh`

**What was done:**

Added `rb_run_python_with_retry` to `scripts/lib/scheduler_common.sh`. The function:
- Reads the Python script from stdin (heredoc) into a temp file.
- Runs `$PYTHON <script_file>`, appending stdout to `LOG_FILE` and capturing stderr separately.
- On non-zero exit, checks stderr for EINTR/Interrupted-system-call signals **combined** with a `<frozen` traceback frame (the `<frozen getpath>` / other frozen bootstrap modules) to scope the retry strictly to interpreter-startup failures.
- Retries up to 2 times (3 total attempts) on a confirmed bootstrap EINTR; logs each retry via `log`.
- Falls through to a normal non-zero return for any other failure — real application errors are never retried.

Updated `scripts/github_sync.sh`: replaced `"$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1` with `rb_run_python_with_retry <<'PY'` (I/O is now managed inside the helper).

**Key decisions:**
- Two-condition EINTR detection (`grep -qE "EINTR|Interrupted system call"` AND `grep -q "<frozen"`) ensures retry is scoped to bootstrap, not application-level interrupts.
- Max 2 retries keeps the job bounded; excessive retries would delay launchd's failure reporting.
- Temp file for the script (rather than shell variable) avoids bash's trailing-newline stripping on `$()` capture.
- `bash -n` syntax check passes on both files.

**Acceptance criteria status:**
- [x] Transient bootstrap EINTR is retried (up to 2 retries)
- [x] Retry scoped to bootstrap failure mode (`<frozen` + EINTR, not blanket retry)
- [ ] Scheduler tests green — to be confirmed by harness gate
