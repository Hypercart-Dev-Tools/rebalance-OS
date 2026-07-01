---
title: MARATHON-QUEUE — XYZ harness test (path-disjoint build lanes)
status: Active
created: 2026-06-30
updated: 2026-06-30
owner: noel@neochro.me
branch: development
roadmap_exempt: true
goal: >
  A ready-to-run set of seven NON-OVERLAPPING, path-scoped build lanes for testing the XYZ /
  `tick` multi-agent harness on real work. Lanes are derived from the validated ROADMAP queue
  (deterministic PDDA + AI judgment pass, 2026-06-30) plus a same-day housekeeping/issue-triage
  pass (lanes D-G), and scoped to verified file paths so two agents can build concurrently
  without colliding. roadmap_exempt: this is a coordination/test artifact, not a tracked project
  deliverable — each lane's real work is tracked by its own doc or GitHub issue.
---

# MARATHON-QUEUE — XYZ harness test

## Status

| What was just completed | What's next |
|---|---|
| Validated the ROADMAP queue (deterministic `pdda.sh` checks all green; AI judgment pass found drift: watch-list guard done via PR #82, and items #1/#5/#6 are a phase ahead of their ROADMAP text). Defined 3 path-disjoint lanes against **verified** paths; confirmed literal-prefix disjointness. **Expanded to 7 lanes** after a same-day GitHub-issue + doc-hygiene triage surfaced 4 more small, bounded, verified-path fixes (D-G); confirmed disjoint against A/B/C and each other. Run has not started — `.tick/` holds only leftover state from the closed GH-81 relay, no `tick` binary installed yet. | Install `tick` via the `/xyz` skill (self-extracting), run the **Seed** block below, then launch 2 agents on the **Run loop**. Coordinator scores with `tick analyze`. |

## Why these lanes

**A/B/C** picked from the validated In-progress queue for **clean partitionability + an acceptance check** (the XYZ scope test). Excluded:
- **Watch-list coverage guard** — done (PR #82 merged); not work.
- **Focus5 reminders panel (#3)** and **VS Code focus-if-open (#4)** — code-complete, remaining step is an **operator TCC/GUI litmus** that cannot be automated or parallelized.
- **Focus5 reference-design refresh (#7)** — shares the `Focus5Float` write surface with other tracks (collision risk) and has no own doc yet.

**D-G** added same-day from a GitHub-issue + doc-hygiene triage pass: each is a small, mechanical, single-purpose fix with an already-verified file location and a concrete acceptance check — the same bar as A/B/C. Excluded from that same triage:
- **Collector audit DoD #1** (single write path per raw source) and **DoD #8** (test/observability blind spots) — both open-ended audits with no bounded path set yet; adding them now would mean inferring paths, which the disjointness rule below forbids.

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

### MARATHON-D — pdda.sh changelog check: recognize semver headings  (priority 8)
- **Paths:** `utils/pdda/pdda.sh`
- **Contract:** `check_changelog()`'s date regex (`pdda.sh:365`, `'^##[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2}'`) only matches a bare `## YYYY-MM-DD` heading. This repo's actual `CHANGELOG.md` uses semver-style `## [x.y.z] - YYYY-MM-DD`, so the check can't see the newest entries and false-warns on every `pdda.sh run`. Fix the regex to recognize both heading shapes. Source of truth: [GH-98](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/98).
- **Acceptance:** `utils/pdda/pdda.sh changelog` run against this repo's real `CHANGELOG.md` reports 0 warns.

### MARATHON-E — snap_calendar_edges MCP tool: validate `days`  (priority 6)
- **Paths:** `src/rebalance/mcp/tools/calendar.py`, `tests/test_calendar_snap.py`
- **Contract:** `snap_calendar_edges` (`calendar.py:141`) passes `days` straight to `snap_edges()` without validating the 1-7 range; the underlying `ValueError` is uncaught, so the MCP tool returns a raw exception instead of a friendly error dict. The CLI sibling (`calendar-snap-edges`) already validates correctly with `typer.BadParameter` — mirror that behavior in the MCP tool. Source of truth: [GH-9](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/9).
- **Acceptance:** `pytest tests/test_calendar_snap.py` green, including a new case for `days` outside 1-7 returning a structured error, not a raised exception.

### MARATHON-F — semantic-maintenance CLI: fix `--source all` drift  (priority 4)
- **Paths:** `src/rebalance/cli/semantic.py`
- **Contract:** `rebalance semantic-backfill --source all` / `semantic-embed --source all` still normalize to the legacy `["vault", "github"]` triad, while the live `semantic` stage covers `_all_semantic_sources()` = `['vault', 'github', 'email', 'code', 'figma']`. Make the CLI's `all` match the stage's `all`. Source of truth: [COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md](COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md) → "Phase 6" (DoD #4).
- **Acceptance:** a test asserts `--source all` expands to `_all_semantic_sources()`, not the hardcoded triad.

### MARATHON-G — OAuth setup scripts: use the shared token-path resolver  (priority 2)
- **Paths:** `scripts/setup_gmail_oauth.py`, `scripts/setup_calendar_oauth.py`
- **Contract:** both scripts still hardcode Google OAuth token paths instead of calling `resolve_oauth_token_path(service)` (already used by the runtime `calendar.py`/`gmail.py` paths per the audit's Phase 4). Route both setup scripts through the same resolver. Source of truth: [COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md](COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md) → "Phase 6" (DoD #6).
- **Acceptance:** neither script constructs a token path by hand; both call `resolve_oauth_token_path`; existing OAuth setup tests (if any) still green.

**Disjointness (tick's literal-prefix rule):** lane prefixes `scripts/` (A) · `macOS/Apps/Focus5Native/` (B) · `src/rebalance/ingest/project_inference.py` (C) · `utils/pdda/pdda.sh` (D) · `src/rebalance/mcp/tools/calendar.py` (E) · `src/rebalance/cli/semantic.py` (F) · `scripts/setup_gmail_oauth.py` + `scripts/setup_calendar_oauth.py` (G) never prefix one another — A's and G's `scripts/*` filenames are each distinct, full filenames with no shared prefix chain. Test globs `tests/test_unified_refresh_` (A), (none for B), `tests/test_client_` (C), (none for D), `tests/test_calendar_snap.py` (E) are mutually non-prefixing. No two lanes can claim an overlapping path.

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
tick log task.created MARATHON-D --agent dispatcher --priority 8 \
  --paths "utils/pdda/pdda.sh" \
  --note "pdda.sh changelog check doesn't recognize semver '## [x.y.z] - DATE' headings, false-warns every run. Fix the date regex at pdda.sh:365. See GH-98."
tick log task.created MARATHON-E --agent dispatcher --priority 6 \
  --paths "src/rebalance/mcp/tools/calendar.py,tests/test_calendar_snap.py" \
  --note "snap_calendar_edges MCP tool doesn't validate days (1-7) or catch the resulting ValueError. Mirror the CLI's existing typer.BadParameter validation. See GH-9."
tick log task.created MARATHON-F --agent dispatcher --priority 4 \
  --paths "src/rebalance/cli/semantic.py" \
  --note "semantic-backfill/-embed --source all still normalizes to the legacy [vault,github] triad instead of _all_semantic_sources(). See COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md Phase 6 DoD #4."
tick log task.created MARATHON-G --agent dispatcher --priority 2 \
  --paths "scripts/setup_gmail_oauth.py,scripts/setup_calendar_oauth.py" \
  --note "OAuth setup scripts hardcode token paths instead of calling resolve_oauth_token_path(service). See COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md Phase 6 DoD #6."
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
