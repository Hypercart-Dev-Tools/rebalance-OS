# Marathon Phase gh146-p1-exit-semantics
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-GH146-P1-EXIT-SEMANTICS-TURN builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

---
title: "GH-146 P1 — daily_sync.sh fatal vs partial/transient exit semantics"
status: "Brief authored; phase not yet run"
created: 2026-07-18
updated: 2026-07-18
owner: noel
gh_issue: 146
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Make daily_sync.sh exit non-zero
  only on fatal failure, so a transient sub-source error stops fabricating a daily health warn.
---

# GH-146 P1 — `daily_sync.sh`: fatal vs partial/transient exit semantics

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-18; parent capture is `PROJECT/1-INBOX/GH-146-HEALTH-SIGNAL-ACCURACY.md` | Execute as marathon phase `gh146-p1-exit-semantics` (reviewer: codex). Blocks P2. |

## The defect

`scripts/daily_sync.sh` ends with:

```bash
sys.exit(1 if result.get("errors") else 0)
```

Any error from any sub-source during a ~49-minute multi-source refresh fails the entire job.
The 2026-07-18 run completed all its work and wrote a full log, then exited 1 because of:

```json
"errors": [{ "scope": "github", "error": "Rate limited fetching /user" }]
```

**7 of the last 10 runs ended `finished with errors`** for reasons of this shape. Downstream:
launchd records status 1 → `doctor` WARNs hourly → `health_issue_reporter` files/comments → an
operator investigates a system that is working.

## What to build

Classify errors before choosing the exit code. A run must exit non-zero **only** when the sync
genuinely failed to do its job — not when a subset of sources degraded in a self-healing way.

Suggested shape (adapt if the code suggests better):

- **Transient / partial** — rate limits, timeouts, a single source stale or unreachable, auth
  that will refresh. The run did its work; report degradation in the JSON (which already carries
  `errors` and per-source detail) and exit **0**.
- **Fatal** — the refresh could not run at all: DB unopenable, config missing, every source
  failed, an unhandled exception. Exit **1**.

Requirements:

- Preserve the existing JSON result shape. Downstream consumers (P2 builds on it) read it; do not
  rename or drop existing keys. If you add a field (e.g. an explicit severity or a
  `fatal`/`degraded` split), add it **alongside** what is there.
- The log's closing line must distinguish the three outcomes, not two — currently it is only
  `complete` vs `finished with errors`. A degraded-but-successful run needs its own marker so the
  logs stay readable and P2 can key on it.
- Do not silence errors. Everything currently reported must still be reported; only the **exit
  code** changes meaning.

## Acceptance criteria

- A run whose only errors are transient/partial exits **0** and says so in the log.
- A run with a fatal error still exits **1**.
- The GitHub-rate-limit case from 2026-07-18 exits 0.
- The JSON result remains backward-compatible.

## Tests (required — this is the write-set's second file)

Add `tests/test_daily_sync_exit.py`. `tests/` is explicitly in your artifact allowlist; a fix
without a test is not complete.

Cover at minimum:
- transient-only errors → exit 0
- fatal error → exit 1
- clean run → exit 0
- the exact 2026-07-18 payload (`{"scope": "github", "error": "Rate limited fetching /user"}`) → exit 0

The test must fail against the current `sys.exit(1 if result.get("errors") else 0)` and pass
after your change. State in your turn which assertion demonstrates that.

## Out of scope

- `doctor`'s reading of launchd status (that is P2 — do not edit `src/rebalance/doctor.py`)
- Device scoping (P3)
- The `email data` 31-day staleness — a real, separate defect
- Anything touching the data plane or the store

## Debug mantra (auto-triggered — 1 prior attempt(s) on this phase did not reach Approved)

Before trying again, read /Users/noelsaw/wt/sentinel-process-review/.xyz/relay-automation/DEBUG-MANTRA.md and follow its four-step discipline: reproduce reliably, know the fail path, question the hypothesis, treat this round as a breadcrumb for the next one.
---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): scripts/daily_sync.sh,tests/test_daily_sync_exit.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/wt/sentinel-process-review/.xyz/bin/tick
   - /Users/noelsaw/wt/sentinel-process-review/.xyz/bin/tick claim MARATHON-GH146-P1-EXIT-SEMANTICS-TURN --agent codex --paths "phases/gh-146-health-signal-accuracy--gh146-p1-exit-semantics/RELAY.md,scripts/daily_sync.sh,tests/test_daily_sync_exit.py"
   - /Users/noelsaw/wt/sentinel-process-review/.xyz/bin/tick ping MARATHON-GH146-P1-EXIT-SEMANTICS-TURN --agent codex
   - /Users/noelsaw/wt/sentinel-process-review/.xyz/bin/tick release MARATHON-GH146-P1-EXIT-SEMANTICS-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/gh-146-health-signal-accuracy--gh146-p1-exit-semantics/RELAY.md and scripts/daily_sync.sh,tests/test_daily_sync_exit.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: scripts/daily_sync.sh,tests/test_daily_sync_exit.py.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/wt/sentinel-process-review/.xyz/bin/tick release MARATHON-GH146-P1-EXIT-SEMANTICS-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/wt/sentinel-process-review/.xyz/bin/tick done MARATHON-GH146-P1-EXIT-SEMANTICS-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/wt/sentinel-process-review/.xyz/bin/tick
   Edit ONLY phases/gh-146-health-signal-accuracy--gh146-p1-exit-semantics/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 1 · Builder · codex

Implemented `scripts/daily_sync.sh` and added `tests/test_daily_sync_exit.py`.

- Added backward-compatible `sync_outcome` to the emitted JSON and classify the run as `complete`, `degraded`, or `fatal`. Migration failures and runs with no successful stage remain fatal; partial source errors exit 0 without dropping their existing `errors` entries.
- Added distinct closing log markers for complete, degraded, and fatal outcomes.
- Reproduced the prior fail path by inspecting the existing `sys.exit(1 if result.get("errors") else 0)`: it turned the GitHub rate-limit envelope into exit 1. Hypothesis confirmed: the wrapper had no partial-success classification. No prior `ESCALATION.md` exists for this phase.
- Verified only the focused test: `python3 -m pytest tests/test_daily_sync_exit.py -q` → `4 passed`. The `test_github_rate_limit_payload_exits_zero` assertion is the explicit regression proof; it would have received exit 1 under the previous unconditional-errors exit rule.
