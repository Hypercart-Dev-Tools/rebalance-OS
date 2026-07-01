# RELAY · MARATHON-C client auto-discovery Phase 2 Gemini gap-fill
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded 2026-07-01.
-->

NEXT: —
STATUS: Escalated
ROUND: 1 / 4

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Producer:** run the kill-check FIRST (measure owner-as-client coverage). If >90% labeled,
     close the lane and set STATUS: Approved with VERDICT: Kill-check closed. If <90%, add the
     Gemini gap-fill per the contract. Run acceptance check.
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). Do **not** edit the artifact; only append findings here.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Escalated`.
6. **Commit only the relay file** (`relay(marathon-c-client-autodiscovery-phase2): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Artifact under review: `src/rebalance/ingest/project_inference.py`,
  `tests/test_client_buckets.py`, `tests/test_client_gapfill.py`
- Producer: codex   ·   Reviewer: agy
- Started: 2026-07-01
- Source of truth: `PROJECT/2-WORKING/CLIENT-AUTO-DISCOVERY.md` → "Phase 2"
- Definition of Done:
  - Kill-check: measure owner-as-client coverage on the live registry. If >90% of active
    projects already have a client label → set STATUS: Approved (kill-check closed, no Gemini).
  - If <90%: `pytest tests/test_client_buckets.py tests/test_client_gapfill.py` green.
    Deterministic owner-as-client path is unchanged when the GSM key is absent.
    Batched gap-fill call fails soft to `None` on any error.
    No change to `registry.py` or `next_actions.py` interfaces (Phase 1 already shipped them).

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.
7. **graphify-out/graph.json exists in this repo.** Run `graphify query "<question>"` before grepping
   source files. Only grep after graphify has oriented you, or to modify/debug specific lines.

## Phase 2 Contract (producer reference)

**Kill-check first.** Run `rebalance doctor` or query the live SQLite DB to measure what
fraction of active projects (those in `project_registry`) have a non-None effective client
(curated `client` or `client_inferred`). If >90% → close at v1, no Gemini needed.

**If gap-fill needed:**
- ONE batched Gemini call for `None`-client projects only (not per-project).
- Prompt: given project name + repo + 1-2 recent activity snippets, name the client if evident, else null.
- Reuse existing Gemini adapter (`_synthesize_with_fallback` in `next_actions.py`).
- Fail-soft: any error, API/key absent, or uncertain result → leave `client_inferred = None`.
- No change to `registry.py::get_clients()`, `registry.py::effective_client()`, or
  `next_actions.py` interfaces — Phase 1 contracts are frozen.
- Tests go in `tests/test_client_gapfill.py` (new file if absent).

## Log

### Coordinator — claude-a — 2026-07-01

Wave 2 Lane C scaffold. Kill-check is mandatory first step — if owner-as-client already
covers >90% of the live registry, close at v1 by setting STATUS: Approved in this file.
Producer (codex) takes the first turn.

The `tests/test_client_gapfill.py` file may not yet exist — codex should create it if the
kill-check shows gap-fill is needed. It is in ALLOW_PATHS.

### Kill-check — claude-a (operator) — 2026-07-01

Kill-check blocked: no live registry available.

`/Users/noelsaw/.config/rebalance-os/` does not exist on this machine; the rebalance SQLite DB
(`rebalance.db`) has no tables. The live project registry is not populated in this environment.

The Phase 2 contract requires measuring owner-as-client coverage on the live registry to
determine whether >90% of active projects are already labeled (kill switch condition). Without
a populated DB, the percentage cannot be measured.

**Operator decision required — pick one:**
1. **Close at v1 (recommended if you know coverage is high):** If Phase 1 owner-as-client already
   labels the projects you care about, set STATUS: Approved here and skip Gemini gap-fill.
2. **Implement Phase 2 without kill-check:** Set NEXT: codex and add a note that codex should
   implement the batched Gemini gap-fill per the contract (fail-soft, one call, None-client only).
   The coverage measurement will be done post-implementation against the live env.
3. **Defer:** Remove this relay from the wave, revisit when the live env is accessible.

VERDICT: Escalated
Basis: Kill-check cannot run — live registry DB absent on this machine.

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
