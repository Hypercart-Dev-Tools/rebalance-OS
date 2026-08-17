---
gh_issue: 93
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/93"
title: "MCP: probe raw source rows + read persisted 'what to do next' ranking"
status: "Completed (shipped 2026-06-30)"
created: 2026-06-30
updated: 2026-06-30
doc_type: feedback
---

## Outcome (2026-06-30)

Shipped both tools in `src/rebalance/mcp/tools/index.py` (no new file/infra) + listed in
`manifest.json`. `peek_source` is allowlist-guarded (7 verified source tables, `limit`
clamped 1..200, no free-form SQL); `get_next_actions` reads the persisted ranking via
`load_ranked_next_actions` + `get_ranked_meta` (no recompute, None-safe). 4 tests in
`tests/test_mcp_probe.py` drive them through the real FastMCP server. Suite **1226 green**,
`rebalance doctor` clean, PDDA gates 0 errors.

# GH-93 — MCP probe tools (raw rows + persisted ranking)

Two read-only MCP tools so a client (Claude Desktop) can probe **both** raw incoming
data and the synthesized headline — closing the two gaps in the existing `rebalance`
MCP surface. Ponytail: fold into the existing `index.py` tool module, no new infra.

## Asks (from the issue)

- `get_next_actions()` — wrap `load_ranked_next_actions(database_path)` (+ `get_ranked_meta`);
  reads the persisted ranking, no model recompute.
- `peek_source(source, limit=20)` — ONE allowlist-guarded tool. `source -> order column`
  is a fixed dict; the caller's `source` is validated against it (never interpolated as a
  raw table name) and `limit` is capped. Allowlist (verified live schema): `github_activity`,
  `github_commits`, `github_items`, `calendar_events`, `sleuth_reminders`, `email_messages`,
  `project_registry`.

## Out of scope

Generic SQL passthrough (security hole); per-source tools (one allowlist covers it);
filtering beyond "last N".

## Acceptance

Both tools registered + in `manifest.json` `tools[]`; `peek_source` rejects unknown source,
caps `limit`, returns rows for a known source; `get_next_actions` None-safe on a fresh DB;
`pytest tests/` green; `rebalance doctor` clean.
