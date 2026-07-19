---
title: Cognee integration for rebalance-OS (Phase 0 spike + phased implementation plan)
status: Active
created: 2026-07-19
updated: 2026-07-19
owner: GitHub Copilot
goal: >
  Evaluate and implement a low-blast-radius integration path that lets rebalance-OS ingest
  and query Cognee memory as an optional source while preserving existing orchestrator,
  semantic single-writer, and observability contracts.
gh_issue: 164
branch: gh-164-cognee-pdda-spike
effort: 3
complexity: 3
risk: 2
phases: 4
related:
  - PROJECT/PDDA.md
  - ARCHITECTURE.md
  - src/rebalance/ingest/index_ops.py
---

# GH-164 — Cognee Integration Plan

## Status

| What was just completed | What's next |
|---|---|
| Created a dedicated worktree/branch from `origin/development`, carried over local `.vscode/settings.json`, and completed Phase 0 technical spike: Cognee 1.4.0 installed in an isolated venv, session `remember`→`recall` executed successfully, and recall output projected into a temporary SQLite table at `temp/spikes/gh-164-cognee/spike_results.sqlite`. | Finalize Phase 1 implementation scope and acceptance gates, then implement `cognee` as an opt-in source collector wired through the existing orchestrator path. |

## Table of contents

- [Context](#context)
- [Discuss](#discuss)
- [Phase 0 — Technical spike (completed)](#phase-0--technical-spike-completed)
- [Phase 1 — Optional Cognee source collector (MVP)](#phase-1--optional-cognee-source-collector-mvp)
- [Phase 2 — Hybrid retrieval in ask/query path](#phase-2--hybrid-retrieval-in-askquery-path)
- [Phase 3 — Session bridge and MCP bridge options](#phase-3--session-bridge-and-mcp-bridge-options)
- [Risks and controls](#risks-and-controls)
- [Open questions](#open-questions)

## Context

GH-164 tracks integration possibilities between `rebalance-OS` and Cognee. The preferred rollout is staged:

1. Start with an opt-in source collector (`scope=["cognee"]`) and keep `all` behavior unchanged.
2. Preserve single-writer semantics for `semantic_documents` and `semantic_embeddings` by routing projection through the existing semantic stage.
3. Keep advanced bridge behavior (bi-directional memory writes, MCP-to-MCP) out of MVP.

## Discuss

- We will treat Cognee as an opt-in source first, not default-on, to avoid introducing new runtime/network dependencies into existing daily sync paths.
- Phase 0 should prove real executable viability (install/runtime) plus data-shape viability (a projection row can be captured) before implementation planning proceeds.
- Temporary spike artifacts remain under `temp/spikes/gh-164-cognee/` and are not production integration code.

## Phase 0 — Technical spike (completed)

### Objective

Validate that Cognee can run in this environment and produce retrievable memory that can be projected into SQLite rows.

### Actions executed

1. Verified local prerequisites in worktree:
   - `Python 3.14.6`
   - `Docker 29.3.1`
2. Created isolated environment:
   - `temp/spikes/gh-164-cognee/.venv`
3. Installed and imported Cognee:
   - `cognee==1.4.0`
4. Ran probe script:
   - `remember(..., session_id="gh164_spike")`
   - `recall(..., session_id="gh164_spike")`
   - persisted recall rows into `temp/spikes/gh-164-cognee/spike_results.sqlite` table `cognee_recall_probe`

### Findings written back

- Cognee runtime initializes successfully in this environment.
- With a dummy API key, graph embedding/indexing fails (expected `401`), but session-memory flow still completes and returns a recall result from `source='session'`.
- Projection shape is viable: at least one recall row inserted into SQLite (`count(*) = 1`) with timestamp, session id, query, and serialized result payload.
- Integration implication: MVP can start with pull/projection patterns without requiring immediate graph-mode dependency guarantees.

### QA checklist

- [x] Cognee install/import succeeds in isolated environment.
- [x] At least one `remember` call executes successfully.
- [x] At least one `recall` result is returned.
- [x] Recall result persisted into local SQLite probe table.
- [x] Findings recorded in this plan doc.

**Verification summary:**
- Runtime checks: pass (`python3`, `docker` present)
- Package install/import: pass (`cognee 1.4.0`)
- Session memory roundtrip: pass (`recall_count = 1`)
- SQLite projection probe: pass (`cognee_recall_probe` row count = 1)
- Known non-blocking warning: graph embedding retries failed with `401 invalid_api_key` under dummy key

## Phase 1 — Optional Cognee source collector (MVP)

### Scope

- Add `cognee` as explicit scope (opt-in; excluded from `all`).
- Implement source-owned collector write path to Cognee raw tables.
- Project Cognee rows via semantic stage only (no direct semantic writes from collector).
- Add source-level health and row-count observability.

### Deliverables

- New collector registration entry in orchestrator registry.
- New source table(s) for Cognee pull results.
- Config switches/env docs for enabling/disabling source.
- Tests for collector registration, ingest path, and projection handoff.

### QA checklist

- [ ] `refresh_index(scope=["cognee"])` executes successfully.
- [ ] `refresh_index(scope=["all"])` behavior unchanged when cognee is disabled.
- [ ] Semantic tables written only by semantic stage.
- [ ] Source observability emitted (rows, duration, status).
- [ ] Tests added and passing.

## Phase 2 — Hybrid retrieval in ask/query path

### Scope

- Add optional retrieval fan-in from Cognee recall + local semantic corpus.
- Attach provenance (`source: cognee` vs local sources).
- Keep feature behind config flag for gradual rollout.

### QA checklist

- [ ] Retrieval merge returns stable, deterministic shape.
- [ ] Provenance appears in returned evidence.
- [ ] Feature flag off preserves current behavior.
- [ ] Metrics include hit-rate and latency deltas.

## Phase 3 — Session bridge and MCP bridge options

### Scope

- Evaluate selective push of agent trace artifacts to Cognee session memory.
- Evaluate optional MCP-to-MCP bridge for teams already running Cognee service.
- Keep strict redaction and explicit opt-in boundaries.

### QA checklist

- [ ] Redaction path verified against credential-like strings.
- [ ] Session write path can be disabled globally.
- [ ] MCP bridge failure modes documented and non-fatal.
- [ ] Clear operator controls for tenancy and namespace boundaries.

## Risks and controls

- Risk: accidental expansion of `all` scope behavior.
  - Control: keep `cognee` explicit opt-in until measured stable.
- Risk: semantic table ownership drift.
  - Control: enforce single-writer path in tests.
- Risk: memory ingesting sensitive artifacts.
  - Control: redaction filters before any storage/projection.
- Risk: runtime dependency instability.
  - Control: feature flag + fail-soft source execution.

## Open questions

1. Should Cognee start as pull-only or include early write-back from rebalance sessions?
2. What tenancy boundary should map to Cognee namespaces (`project`, `repo`, `operator`)?
3. Should Cognee-backed evidence appear in pulse publishing by default or remain query-only initially?
4. Which provider config is canonical for production (OpenAI-compatible vs local provider path)?
