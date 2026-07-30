# Marathon Phase p4-gh166
STATUS: Approved
NEXT: claude

<!-- marathon-drive: task=MARATHON-P4-GH166-TURN builder=claude reviewer=agy round-cap=5 -->

## Phase Brief

# Marathon preflight packet — gh-166-vault-ingest-lag

- Generated: 2026-07-30T20:10:37Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-166-VAULT-INGEST-LAG.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ a4d22c43e)
- Suggested branch: `marathon/gh-166-vault-ingest-lag-2026-07-30` (branch_ready=false — carve-out: risk=1/independent zone, proceed on the current branch without asking)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k "index_ops or vault_sync" -q`

- Artifacts: src/rebalance/ingest/index_ops.py,src/rebalance/health.py
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 2243 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [x] `index_status`/`doctor` surfaces vault ingest lag as a direct, degrading-health
- [x] Pending-embed rows stuck past a reasonable threshold are distinguished from an
- [x] `pytest -k "index_ops or vault or semantic_index"` green.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `src/rebalance/ingest/index_ops.py,src/rebalance/health.py` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k "index_ops or vault_sync" -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-166-vault-ingest-lag RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact src/rebalance/ingest/index_ops.py,src/rebalance/health.py \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k "index_ops or vault_sync" -q' \
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
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/ingest/index_ops.py,src/rebalance/health.py
2. Append a build block to this relay file: `### Round N · Builder · claude` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick claim MARATHON-P4-GH166-TURN --agent claude --paths "phases/10days-2026-07-30--p4-gh166/RELAY.md,src/rebalance/ingest/index_ops.py,src/rebalance/health.py"
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick ping MARATHON-P4-GH166-TURN --agent claude
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P4-GH166-TURN --agent claude --to agy
4. Edit ONLY these paths: phases/10days-2026-07-30--p4-gh166/RELAY.md and src/rebalance/ingest/index_ops.py,src/rebalance/health.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

### Round 1 · Builder · claude

**Files touched:** `src/rebalance/ingest/index_ops.py`, `src/rebalance/health.py`

**What was done:**

**GH-166 Fix 1 — Vault ingest lag surfaced as a degrading health signal:**

- Added `_safe_vault_ingest_lag(conn)` helper that queries `MAX((julianday('now') - julianday(last_modified)) * 24 * 60)` across `vault_files WHERE last_modified > ingested_at` — returns the age in minutes of the most out-of-date unsynced file, 0 when all files are current.
- Added `"ingest_lag_minutes"` field to the vault source payload in `get_index_status()`.
- Extended `_SIGNAL_HEALTH_RULES["vault"]` with `lag_key="ingest_lag_minutes"`, `lag_warn_minutes=120` (2 missed hourly cycles), `lag_degraded_minutes=240`.
- Extended `_derive_signal_health()` with a lag-check block after the content-predicate check: only overrides an `ok` verdict (a source already flagged by freshness/zero-rows keeps its existing verdict).

**GH-166 Fix 2 — Stuck pending-embed rows distinguished from in-flight tail:**

- Added module-level constant `_STUCK_EMBED_THRESHOLD_HOURS = 4`.
- Added `drift["semantic_documents_stuck_embed"]` in `get_index_status()`: count of `semantic_documents` rows where `(embedded_hash IS NULL OR embedded_hash != content_hash) AND julianday(updated_at) < julianday('now', '-4 hours')`. A row is stuck when updated_at is older than the threshold yet it hasn't been embedded — the embedder ran at least once since that update and didn't pick it up.
- Also records `drift["semantic_documents_stuck_embed_threshold_hours"]` so callers know the threshold used.

**`health.py` — signal_health surfaced in the doctor verdict:**

- Added `signal_health_as_checks(status)` (public): converts `freshness.signal_health` degraded/warn entries to `signal:<source>` Check objects (FAIL for degraded, WARN for warn).
- Modified `compute_health_status` to merge `signal_health_as_checks(status)` into the check list before running `ordered_problem_checks`, so vault ingest lag and similar metrics affect the health verdict without changes to doctor.py.

**Key decisions:**
- Lag threshold 120min (warn) / 240min (degraded): sized to the hourly ingest cadence — 2h means 2 missed cycles, 4h means clearly stuck.
- `signal:` prefix on check names distinguishes synthetic checks from doctor credential checks and lets them be demoted to notices via `notice_patterns`.
- Lag check only fires when existing verdict is `ok` — fresher, stronger signals (stale ingested_at, zero rows) are not superseded.

**Tests:** 26 `test_index_ops` + 2 `test_index_ops_migration_gate` pass; 15 `test_health` pass.

---

### Round 1 · Reviewer · agy

swept file: yes

**Assessment:**
All acceptance criteria are satisfied and cleanly implemented:
1. `_safe_vault_ingest_lag(conn)` calculates out-of-date file age in minutes, exposed as `ingest_lag_minutes` in `get_index_status()`. Evaluated against 120m (warn) and 240m (degraded) thresholds in `_derive_signal_health()`.
2. `signal_health_as_checks()` in `health.py` converts `signal_health` degradation/warn statuses into `signal:<source>` synthetic Check objects integrated into `compute_health_status()`, surfacing ingest lag to doctor/health verdicts without modifying `doctor.py`.
3. `drift["semantic_documents_stuck_embed"]` distinguishes pending rows stuck longer than `_STUCK_EMBED_THRESHOLD_HOURS` (4h) from normal in-flight tails.
4. Comprehensive file sweeps of both `src/rebalance/ingest/index_ops.py` (2089 lines) and `src/rebalance/health.py` (276 lines) revealed clean design with no pre-existing or introduced defects.
5. Verification via `pytest -k "index_ops or health"` passed cleanly (142 tests passed).

**Verdict:** Approved
