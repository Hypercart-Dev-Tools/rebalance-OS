---
title: "M4 p3 — mcp_server.py: four thin tools"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M4 p3 — mcp_server.py: four thin tools

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m4-p2` is approved. |

**Canonical spec:** `HIQS-PROJECT.md` §10 (MCP is the product surface), §7 (the payload), §11
(~120 LOC), Phase 3 gate.

## Build

`HiQS/hiqs/mcp_server.py` — standard JSON-RPC MCP exposing exactly four tools:
`refresh` · `status` · `search` · `ask`. All structured JSON, all attested.

**Thin wrappers, zero logic.** Marshalling only.

## Acceptance

- A test asserts the module contains no ranking, scoring, filtering, or ordering logic — it calls
  `ask.py` and returns what it gets.
- **Parity:** for the same DB state, the MCP `ask` tool and `ask()` return byte-identical rankings.
  A behavioural difference between CLI and MCP for one query is a defect, not a nuance.
- Tool descriptions state the RANKED tenet in whatever wording §7.1's gates currently justify —
  if the obligation-coverage gate has not passed, the description says "ordered by recency and
  source weight". The claim in the tool description is a claim like any other (§2).
- Errors surface as structured MCP errors, never a silent empty result.

## Do not

- Do not add a fifth tool. Decision 4 counts them; §18.3's SMALL invariant makes a fifth a recorded
  decision.
- Do not reimplement anything from `ask.py`, `search.py`, or `events.py`.
