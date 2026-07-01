---
title: MARATHON-QUEUE — XYZ harness test (path-disjoint build lanes)
status: Active
created: 2026-06-30
updated: 2026-06-30
owner: noel@neochro.me
branch: development
roadmap_exempt: true
goal: >
  A ready-to-run set of three NON-OVERLAPPING, path-scoped build lanes for testing the XYZ /
  `tick` multi-agent harness on real work. Lanes are derived from the validated ROADMAP queue
  (deterministic PDDA + AI judgment pass, 2026-06-30) and scoped to verified file paths so two
  agents can build concurrently without colliding. roadmap_exempt: this is a coordination/test
  artifact, not a tracked project deliverable — each lane's real work is tracked by its own doc.
---

# MARATHON-QUEUE — XYZ harness test

## Status

| What was just completed | What's next |
|---|---|
| Validated the ROADMAP queue (deterministic `pdda.sh` checks all green; AI judgment pass found drift: watch-list guard done via PR #82, and items #1/#5/#6 are a phase ahead of their ROADMAP text). Defined 3 path-disjoint lanes against **verified** paths; confirmed literal-prefix disjointness. | Install `tick` via the `/xyz` skill (self-extracting), run the **Seed** block below, then launch 2 agents on the **Run loop**. Coordinator scores with `tick analyze`. |

## Why these three lanes

Picked from the validated In-progress queue for **clean partitionability + an acceptance check** (the XYZ scope test). Excluded:
- **Watch-list coverage guard** — done (PR #82 merged); not work.
- **Focus5 reminders panel (#3)** and **VS Code focus-if-open (#4)** — code-complete, remaining step is an **operator TCC/GUI litmus** that cannot be automated or parallelized.
- **Focus5 reference-design refresh (#7)** — shares the `Focus5Float` write surface with other tracks (collision risk) and has no own doc yet.

## Lanes (verified paths — do NOT infer, `tick info <id>` is authoritative)

### MARATHON-A — unified-refresh v1 remediation  (priority 30)
- **Paths:** `scripts/pulse_web.py`, `scripts/apple_reminders_helper_app.swift`, `scripts/build_apple_reminders_helper_app.sh`, `tests/test_unified_refresh_remediation.py`
- **Contract:** `/api/refresh` must (1) surface helper failures instead of swallowing them into a `200 OK`, (2) restore the dropped SQLite DB read path, (3) gain automated coverage. Source of truth: [UNIFIED-REFRESH-RESTART.md](UNIFIED-REFRESH-RESTART.md) → "Phase QA-R".
- **Acceptance:** `pytest tests/test_unified_refresh_remediation.py` green + `rebalance doctor` clean.

### MARATHON-B — Focus 5 App Store Phase 0-R sandboxed re-spike  (priority 20)
- **Paths:** `macOS/Apps/Focus5Native/**`
- **Contract:** produce findings from a **real sandboxed** run (App Sandbox entitlement ON), actually spike the `SwiftGit2`/libgit2 path, and **observe** (not assert) that `Process` exec of system `git` is blocked. Source of truth: [FOCUS-5-APP-STORE.md](FOCUS-5-APP-STORE.md) → "Phase 0-R".
- **Acceptance:** sandboxed `swift build` succeeds and the Phase 0 QA checklist gates in the doc flip to `[x]` with captured evidence (local/operator step — no shared-tree collision).

### MARATHON-C — client auto-discovery Phase 2 Gemini gap-fill  (priority 10)
- **Paths:** `src/rebalance/ingest/project_inference.py`, `tests/test_client_buckets.py`, `tests/test_client_gapfill.py`
- **Contract:** **kill-check first** — measure owner-as-client coverage on the live registry; if >90% of active projects are already labeled, close at v1 and skip Gemini. Else add ONE batched Gemini call for `None`-client projects only, fail-soft to `None`. Do NOT change `registry.py`/`next_actions.py` interfaces (Phase 1 already shipped them). Source of truth: [CLIENT-AUTO-DISCOVERY.md](CLIENT-AUTO-DISCOVERY.md) → "Phase 2".
- **Acceptance:** `pytest tests/test_client_buckets.py tests/test_client_gapfill.py` green.

**Disjointness (tick's literal-prefix rule):** lane prefixes `scripts/` · `macOS/Apps/Focus5Native/` · `src/rebalance/ingest/project_inference.py` never prefix one another; test globs `tests/test_unified_refresh_`, (none for B), `tests/test_client_` are mutually non-prefixing. No two lanes can claim an overlapping path.

## Prerequisites

`tick` is not vendored in this repo (only the `.tick/` event dir from prior relay use exists). Install the runtime first:

```bash
# via the xyz skill's self-extracting installer (materializes ./xyz-tick/bin/tick)
#   then put it on PATH for this shell:
export PATH="$PWD/xyz-tick/bin:$PATH"
export TICK_REPO_ROOT="$PWD"      # so tick writes to THIS repo's .tick/
tick init
```

## Seed (coordinator — run once)

```bash
tick log task.created MARATHON-A --agent dispatcher --priority 30 \
  --paths "scripts/pulse_web.py,scripts/apple_reminders_helper_app.swift,scripts/build_apple_reminders_helper_app.sh,tests/test_unified_refresh_remediation.py" \
  --note "Unified refresh v1 QA-R: stop swallowing helper failures into 200, restore DB read path, add coverage. See UNIFIED-REFRESH-RESTART.md."
tick log task.created MARATHON-B --agent dispatcher --priority 20 \
  --paths "macOS/Apps/Focus5Native/**" \
  --note "App Store Phase 0-R: real sandboxed run, spike SwiftGit2/libgit2, observe Process-exec block. See FOCUS-5-APP-STORE.md."
tick log task.created MARATHON-C --agent dispatcher --priority 10 \
  --paths "src/rebalance/ingest/project_inference.py,tests/test_client_buckets.py,tests/test_client_gapfill.py" \
  --note "Client auto-discovery Phase 2: kill-check coverage first; else one batched Gemini gap-fill for None-client projects, fail-soft. See CLIENT-AUTO-DISCOVERY.md."
tick project   # render .tick/STATE.md
```

## Run loop (each agent, distinct --agent id e.g. claude-a / codex-b)

Recite the XYZ mantra first (verify-don't-assume; code-to-the-contract; stay in your lane).

```bash
A=claude-a                               # the other agent uses A=codex-b
tick take --agent "$A"                   # atomic claim of the next non-overlapping lane
tick info <TASK-ID>                      # AUTHORITATIVE paths — never infer
# ... work strictly inside the claimed paths; heartbeat periodically:
tick ping <TASK-ID> --agent "$A" --note "what I just did"
# ... run the lane's acceptance check, then:
tick done <TASK-ID> --agent "$A" --note "acceptance: <command> green"
# repeat tick take until: (no available task)
```

## Coordinator wrap-up / scoring

```bash
tick analyze --format human            # concurrent-claim %, parked-claim suspects
tick analyze --format md --write PROJECT/2-WORKING/MARATHON-QUEUE.md   # appends a report section
```

Reject in wrap-up: any finding without a `file:line` citation, or any edit outside a claimed lane (the XYZ contract). A run with parked-claim suspects is disqualified.
