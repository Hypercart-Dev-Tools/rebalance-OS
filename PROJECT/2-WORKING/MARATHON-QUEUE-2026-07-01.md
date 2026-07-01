---
title: MARATHON-QUEUE — 2026-07-01 (path-disjoint build lanes)
status: Active
created: 2026-07-01
updated: 2026-07-01
owner: noel@neochro.me
branch: development
roadmap_exempt: true
goal: >
  Ready-to-run build lanes drawn from the validated ROADMAP queue (deterministic `pdda.sh run`
  all-green + AI judgment pass, 2026-07-01), following the wave-2 marathon that closed Lanes
  A/C/D/E/F/G from MARATHON-QUEUE-2026-06-30.md. roadmap_exempt: this is a coordination/test
  artifact, not a tracked project deliverable — each lane's real work is tracked by its own doc
  or GitHub issue.
---

# MARATHON-QUEUE — 2026-07-01

## Status

| What was just completed | What's next |
|---|---|
| **Both lanes RAN and closed 2026-07-01** (2 concurrent agents via `tick`, work-bounded concurrency ~51%, 0 parked-claim suspects, 0 cross-lane writes). **MARATHON-A** (Focus5Native Phase 0-R) — sandboxed re-spike PASSED: all 10 QA gates observed in a codesigned App-Sandbox `.app`; `Process`→git empirically blocked, in-process libgit2 returns the full typed fact set, bookmark round-trip verified; key finding = SwiftGit2 SPM is iOS-only so a macOS-sliced libgit2 is a Phase 2 cost (evidence: `macOS/Apps/Focus5Native/PHASE-0-R-FINDINGS.md`). **MARATHON-B** (Signal-quality contract) — GH #101 opened, doc promoted to `PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md`, ROADMAP pointer parked, Phase 0 spike run (freshness-derivation cites confirmed; one REFUTED: `payload["freshness"]` is overwritten by the semantic-drift dict at index_ops.py:385, folded into Phase 2). Coordinator applied A's cross-lane doc updates to `FOCUS-5-APP-STORE.md`. | Operator litmus sweep (below) — the remaining ROADMAP items need human GUI/TCC checks, not agent lanes. Both project docs now point to their next phase (App Store → Phase 1; Signal-quality → Phase 1). |

_Original queue-build note (pre-run):_ Re-validated the ROADMAP queue against live doc/code state; confirmed wave-2 closures and independently verified DoD #4/#6 are live in code (their `COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md` Phase 6 checkboxes remain stale `[ ]` — flagged below). Carried MARATHON-A forward (seeded wave 2, never run); added MARATHON-B (newly promotion-ready). Re-excluded the reference-design refresh and DoD #1/#8 (no bounded path set).

## Why only 2 lanes

Everything else in the ROADMAP "In progress" ledger is either:
- **done and just needs a human GUI/TCC litmus** (cannot be automated or parallelized — see the operator sweep below), or
- **still open-ended with no verified bounded path** (DoD #1 "single write path per raw source" and DoD #8 "test/observability blind spots" — scoping these to a specific source/test file is real work itself; forcing a guess would violate the disjointness rule), or
- **collision risk with no own doc section yet** (Focus5 Float reference-design refresh — `P2-MACOS-FOCUS5-FLOAT.md` still has no section describing it; same exclusion reason wave 2 used).

## Lanes (verified paths — do NOT infer, `tick info <id>` is authoritative)

### MARATHON-A — Focus 5 App Store Phase 0-R sandboxed re-spike (priority 30)
- **Paths:** `macOS/Apps/Focus5Native/**`
- **Contract:** Wave-2 Lane B, never run (absent from `.tick/STATE.md` Done). Produce findings from a **real sandboxed** run (App Sandbox entitlement ON), actually spike the `SwiftGit2`/libgit2 path, and **observe** (not assert) that `Process` exec of system `git` is blocked. Source of truth: [FOCUS-5-APP-STORE.md](FOCUS-5-APP-STORE.md) → "Phase 0-R".
- **Acceptance:** sandboxed `swift build` succeeds and the Phase 0 QA checklist gates in the doc flip to `[x]` with captured evidence.

### MARATHON-B — Signal-quality contract: open issue, promote, run Phase 0 spike (priority 20)
- **Paths:** `PROJECT/1-INBOX/SIGNAL-QUALITY-CONTRACT.md` (rename to `PROJECT/2-WORKING/GH-<n>-SIGNAL-QUALITY-CONTRACT.md`), `ROADMAP.md` (one-line pointer append only)
- **Contract:** doc is "Proposed... Phase 0 spike scoped, not yet run." Open a GitHub issue (issue-first SOP), rename the doc `GH-<n>-SIGNAL-QUALITY-CONTRACT.md`, park a one-line pointer in `ROADMAP.md`, promote to `2-WORKING`, then run Phase 0 (1-2h spike verifying `index_status()`/`get_index_status()` freshness derivation at [index_ops.py:224](../../src/rebalance/ingest/index_ops.py#L224) and the 7-day-window primitive at [index_ops.py:273](../../src/rebalance/ingest/index_ops.py#L273)), and write findings back into the doc. Source of truth: [SIGNAL-QUALITY-CONTRACT.md](../1-INBOX/SIGNAL-QUALITY-CONTRACT.md).
- **Acceptance:** Phase 0 QA gate passes with captured findings written in-doc; `utils/pdda/pdda.sh roadmap-coverage` still clean after the ROADMAP append.

**Disjointness (tick's literal-prefix rule):** `macOS/Apps/Focus5Native/` (A) and `PROJECT/1-INBOX/SIGNAL-QUALITY-CONTRACT.md` + `ROADMAP.md` (B) share no path prefix. No two lanes can claim an overlapping path.

## Operator sweep (no build work left — human litmus only, not a lane)

Per the Apple Reminders TCC findings, no CLI agent can satisfy a LaunchServices-launched GUI litmus, so these are operator tasks:

- [ ] **Unified UI refresh** — QA-R remediation shipped (PR #100); operator litmus on the live dashboard, then archive. → [UNIFIED-REFRESH-RESTART.md](UNIFIED-REFRESH-RESTART.md)
- [ ] **Repo links "focus-if-open"** — both phases code-complete, agy-Approved (91 tests); operator browser/GUI litmus on both surfaces. → [VSCODE-OPEN-WORKSPACE.md](VSCODE-OPEN-WORKSPACE.md)
- [ ] **Focus 5 Float reminders drawer** — Apple + Obsidian sections shipped; operator TCC litmus pending on the Apple/EventKit side. → [FOCUS5-REMINDERS-PANEL.md](FOCUS5-REMINDERS-PANEL.md)
- [ ] **Focus 5 Float — Telemetry tab** — code-complete, build green; launch app → 📊 tab → confirm 3 demo rows, then archive. → [P2-FOCUS5-TELEMETRY-TAB.md](P2-FOCUS5-TELEMETRY-TAB.md)
- [ ] **Focus 5 Float — offline resilience** — both phases built, `swift build` green; cold-launch offline litmus, then archive. → [P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md](P3-FOCUS5-FLOAT-OFFLINE-RESILIENCE.md)
- [ ] **Focus 5 Float (P2-MACOS)** — drop the `.icns`, then move to `3-COMPLETED`. → [P2-MACOS-FOCUS5-FLOAT.md](P2-MACOS-FOCUS5-FLOAT.md)

## ROADMAP / doc drift found while building this queue

- `COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md` Phase 6 still shows DoD #4 and #6 as `[ ]` — verified both are actually shipped in code (`src/rebalance/cli/semantic.py:29-30` imports `_all_semantic_sources()`; `scripts/setup_gmail_oauth.py:37,68` and `scripts/setup_calendar_oauth.py:27,56` both call `resolve_oauth_token_path`). Only DoD #1 and #8 remain genuinely open. **Not fixed here** — flagging for a doc-hygiene pass, separate from this build queue.
- ROADMAP.md's top-line "What's next" lists VS Code focus-if-open and Unified refresh as if they were still build work; both are actually operator-litmus-only per their own project docs (see Operator sweep above). Same class of drift the 2026-06-27 queue flagged.

## Prerequisites

`tick` is not currently on PATH (`.tick/` holds only the wave-2 event log). Reinstall via the `/xyz` skill's self-extracting installer, then:

```bash
export PATH="$PWD/xyz-tick/bin:$PATH"
export TICK_REPO_ROOT="$PWD"
tick init
```

## Seed (coordinator — run once)

```bash
tick log task.created MARATHON-A --agent dispatcher --priority 30 \
  --paths "macOS/Apps/Focus5Native/**" \
  --note "App Store Phase 0-R: real sandboxed run, spike SwiftGit2/libgit2, observe Process-exec block. Carried over from wave 2, never run. See FOCUS-5-APP-STORE.md."
tick log task.created MARATHON-B --agent dispatcher --priority 20 \
  --paths "PROJECT/1-INBOX/SIGNAL-QUALITY-CONTRACT.md,ROADMAP.md" \
  --note "Signal-quality contract: open GH issue, rename+promote to 2-WORKING, park ROADMAP pointer, run Phase 0 spike, write findings back. See PROJECT/1-INBOX/SIGNAL-QUALITY-CONTRACT.md."
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
