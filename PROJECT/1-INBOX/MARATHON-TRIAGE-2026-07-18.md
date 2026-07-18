# Marathon Triage — 2026-07-18 (collector health bundle)

**Requested bundle:** #140, #141, #127, #138, #139
**Branch:** `marathon/2026-07-18-collectors` (cut from `development` @ `961da06`)
**Verdict:** **0 of 5 are preflight-ready today.** Three are good candidates once contracts exist; two should not be queued at all.

---

## 1. Classification (skill step 2)

Every issue was checked against live GitHub state and against the in-repo capture set.

| Issue | State | Capture doc | Bucket | Action |
|---|---|---|---|---|
| #127 | OPEN | **none** | NEEDS-CONTRACT | author doc + contract → promote → preflight |
| #138 | OPEN | **none** | NEEDS-CONTRACT | author doc + contract → promote → preflight |
| #139 | OPEN | **none** | NEEDS-CONTRACT | author doc + contract → promote → preflight |
| #140 | OPEN | **none** | **NOT-A-WORK-ITEM** | investigation already answered — close, open fix issue |
| #141 | OPEN | **none** | **NEEDS-CONTRACT (blocked)** | root cause unknown — diagnose before contracting |

`ls PROJECT/1-INBOX/ PROJECT/2-WORKING/ | grep -E '^GH-(127|138|139|140|141)'` returns nothing. The inbox holds docs for GH-102/104/106/124/125/128/129/135/136 only.

**Consequence:** `swarm-preflight.sh --gh-issue N` would exit **3 (contract missing/invalid)** for all five. There is nothing to preflight yet. The issues were filed straight to GitHub today without going through `/idea`, so they never got an execution surface of record.

---

## 2. The two that should not be queued

### #140 — already answered, queueing it would re-run a finished investigation

Filed as an explicit *investigation*, and Codex delivered the attribution: one `github-sync` run costs **~2,292 requests** — `60 repos × 7` + `423 issues × 1` + `241 PRs × 6` + discovery — at **18 scheduled runs/day**. The question the issue asked is answered.

**Proposed:** close #140 as investigation-complete, and open a *fix* issue carrying the actionable remainder:
- reduce the per-PR 6× fan-out (detail, issue comments, reviews, review comments, commits, check-runs)
- reconsider `github-sync` cadence (18×/day) and the dashboard's `PULSE_AUTO_MIN=10` full-refresh
- land the `GitHubClient._request()` run-id counter Codex recommended

That fix issue *is* a strong marathon candidate. #140 as written is not.

### #141 — undiagnosed; a fix contract would be fiction

The email collector reports fresh while landing 0 rows in 7d. Three candidate causes remain live: fetching-and-discarding, fetching-nothing, or failing-silently. They have **different fixes and different write-sets**, so any `artifacts` list authored now would be a placeholder contract — exactly what the skill's step 4 says to flag.

**Proposed:** a single 20-minute diagnosis (check the Gmail OAuth token first) *before* contracting. This is not swarm work — it is one person or one agent reading one auth path. Once the cause is known, #141 becomes contractable and probably small.

---

## 3. The three real candidates

All three are well-specified with explicit acceptance criteria. Write-sets verified against the tree:

| Issue | Subject | Primary write-set | Size |
|---|---|---|---|
| **#127** | registry-driven health predicate (content quality) | `src/rebalance/health.py` (207 ln), collector registry, `tests/` | M–L |
| **#138** | doctor check: policy-table job not loaded | `src/rebalance/doctor.py` (986 ln), `SCHEDULER.md` parsing, `tests/` | M |
| **#139** | stable dedup key for health issues | `scripts/health_issue_reporter.py`, `tests/test_health_issue_reporter.py` | S–M |

### Collision analysis — REVISED after verifying the tree

The first pass of this section inferred the write-sets from file names and got them wrong. Verified against the code, **`src/rebalance/doctor.py` is a shared write-target for all three lanes**:

| Lane | Why it edits `doctor.py` | Evidence |
|---|---|---|
| #127 | the freshness check to extend **is in doctor**, not `health.py` | `doctor.py:330 _check_collector_freshness()` |
| #138 | adds the policy-table liveness check to doctor | doctor is the per-device health surface |
| #139 | root cause is a duplicate check emitter, and doctor owns the canonical one | `doctor.py:761` emits `pulse collector:` vs `health_issue_reporter.py:377` emits `pulse-collector:` |

`health.py` (207 ln) turned out **not** to be #127's write-target — `compute_health_status()` consumes check results; `_check_collector_freshness()` produces them, and lives in `doctor.py` (986 ln).

**Consequence: the three health lanes cannot run concurrently.** Any two of them would contend on one 986-line file. This materially reduces what a swarm buys on this bundle — see §4.

| Wave | Lanes | Rationale |
|---|---|---|
| **1** | **#139** ∥ **#144** | #139 first: collapsing the duplicate emitter stabilizes check names that #138 and #127 both build on. #144 is genuinely disjoint (`_http.py`, github sync) — the one safe parallel lane. |
| **2** | **#138** | doctor liveness check, on a stable name surface. |
| **3** | **#127** | freshness predicate in `doctor.py`; largest and most kernel-ish, lands last. |

Only **one** pair runs concurrently in the whole plan (#139 ∥ #144). Everything else serializes on `doctor.py`.

`#141` slots in wherever its diagnosis lands it.

---

## 4. Swarm feasibility (Codex + agy)

**Feasible, and it is the native execution model** — `swarm-preflight.sh` explicitly "assigns Codex/agy lanes" and emits a packet for `marathon-drive.sh`.

Verified present:

| Component | Path | Status |
|---|---|---|
| preflight planner | `.xyz/utils/swarm-preflight.sh` | ✅ |
| marathon planner | `.xyz/utils/marathon-plan.sh` | ✅ |
| marathon driver | `.xyz/relay-automation/marathon-drive.sh` | ✅ |
| Codex turn | `.xyz/relay-automation/codex-turn.sh` | ✅ |
| agy turn | `.xyz/relay-automation/agy-turn.sh` | ✅ |
| `tick` CLI | `.xyz/bin/tick` | ✅ present, **not on PATH** |
| `codex` CLI | `~/.local/bin/codex` | ✅ |
| `agy` CLI | `~/.local/bin/agy` | ✅ |

**Path caveat:** the marathon-triage skill documents `utils/swarm-preflight.sh` and `utils/marathon-plan.sh` at the repo root. In this repo they live only under the vendored `.xyz/` install. Every invocation must use the `.xyz/` prefix; the bare paths fail. The script self-detects the vendored layout internally (it resolves `ROOT` from `.xyz/utils` → grandparent), so only the *call site* needs the prefix.

**Lane assignment principle** (from the contract schema): `lanes.orchestrator_only` should hold anything kernel-ish or shared-ledger; `lanes.agy_safe` the independent zones. On this bundle, `scripts/health_issue_reporter.py` (#139) is the most obviously agy-safe — self-contained, well-tested, no kernel path. `#127`'s health-kernel edit is the strongest orchestrator-only candidate.

---

## 5. Needs a decision before any of this runs

1. **Close #140?** It is answered. Confirm, and confirm the follow-up fix issue should be opened.
2. **#139 design choice.** The issue offers two dedup approaches — a hidden body marker vs a registry-level stable id. A swarm will pick arbitrarily unless the contract states which. **Decide before contracting.**
3. **#141 diagnosis** — assign it, or accept that it stays out of this marathon.
4. **Authoring 3–5 capture docs is itself the first unit of work.** Each needs a preflight contract with a real `fix_probes` and `artifacts` set. This is the gating step for everything above.
5. **Backfill decision for #141** — whether the 7-day email gap gets recovered or written off.

---

## 6. What was NOT done

Per GUIDING-PRINCIPLES.md §8 and the skill's guardrails: no branch was auto-cut for any lane, no marathon fired, no doc promoted, no issue closed. This is a plan.

The working branch `marathon/2026-07-18-collectors` was cut **at the operator's explicit instruction** before triage ran — it is not a lane branch and carries no commits yet.
