---
title: "Client Auto-Discovery (piggyback on the project lifecycle)"
project: "Client Auto-Discovery"
codename: HiQS
owner: Noel
created: 2026-06-30
updated: 2026-06-30
status: "SKETCH (1-INBOX intake) — design only, no code. Lazy-by-default: clients are an attribute of a project, not a new entity. Reuses project_registry / inference / confirm / classifier / rank-prompt; adds ~50 lines across 3 existing files + 1 test. No new table, no new lifecycle, no new MCP tool in v1."
goal: "Auto-discover a CLIENT name per project and expose clients as discrete buckets the 'what to do next' synthesis can group/prioritize by — without building a parallel client entity or its own lifecycle."
current_phase: "Phase 0 — design accepted? then build v1 (deterministic) + v1.1 (Gemini gap-fill)"
endgame: "The ranked next-action list is client-aware: items roll up under their client, and a sparse/at-risk client surfaces even when its projects are individually quiet."
kill_switch: "Kill if owner-as-client (free, deterministic) already labels >90% of active projects correctly — then Gemini gap-fill is unjustified and clients stay a pure derived GROUP BY."
tags: [signal-quality, client-discovery, ponytail]
roadmap_exempt: false
---

# Client Auto-Discovery

> **Thesis:** A client is not a new bucket to build — it is one field on a project we
> already discover, confirm, and persist. The cheapest correct design stores an inferred
> `client` *inside the existing project row* and derives the "buckets" as a GROUP BY on
> read. Curated config `client` always wins. Nothing new gets a table or a lifecycle until
> a client must exist independently of any project.

---

## Why so lazy on purpose

The audit found projects are auto-discovered into a discrete `project_registry` bucket
before synthesis; clients are not discovered at all (config-only metadata). The instinct is
to mirror the project lifecycle with a parallel **client** lifecycle: `client_registry`
table, client inference module, `confirm_clients` MCP tool, vault client sections, client
classifier. That is a second copy of an entire subsystem for a value that is already a
**field on a project** (`config.py:1066` carries `client` on each priority rule today).

Ponytail ladder applied:

1. **Does a client entity need to exist at all?** Not in v1. A client is `project.client`.
   Buckets = `GROUP BY client over projects`. Derived, not stored.
2. **Stdlib?** `collections.defaultdict` does the grouping.
3. **Already-installed dependency?** The Gemini adapter
   (`_synthesize_with_fallback` in [next_actions.py](../../src/rebalance/ingest/next_actions.py))
   and the project inference pass already exist — reuse both.
4. **Deterministic free win first.** Most clients ARE the GitHub owner/org, which
   `project_inference.py` already parses (`anthropics/claude-code` → owner `anthropics`).
   Owner-as-client costs zero calls and needs no API key.

So Gemini is **gap-fill, not the engine**: it runs only for projects where the owner is a
personal account or the project is calendar-only (no repo owner to lean on).

---

## Design — three edits, one test, zero new files (v1)

### Storage: reuse `project_registry.custom_fields_json`

No schema change. Each inferred client lands at
`custom_fields["client_inferred"]` on the existing project row. The **effective client**
resolves curated-first:

```
effective_client(project) =
    custom_fields["client"]            # curated (config priority rule) — always wins
    or custom_fields["client_inferred"] # machine-owned, activity_inference_v1
    or None                             # → "(unassigned)" bucket
```

This mirrors the existing curated-wins contract exactly (`project_inference.py:58-70`):
inference owns only `client_inferred`, never overwrites a curated `client`.

`# ponytail: client lives on the project row, not a client_registry table. Promote to a`
`# real table only when a client must exist with its own status/priority independent of`
`# any project (a client with zero active projects). Migration is then additive + mechanical.`

### Edit 1 — discover (`project_inference.py`, inside the existing `sync_inferred_project_registry()` pass)

After seeds are built, set each machine-owned project's `client_inferred`:

- **v1 (deterministic, no key):** `client_inferred = normalized GitHub owner` for
  github-backed projects (already in hand from owner grouping). Calendar-only and
  personal-account projects get `None`.
- **v1.1 (Gemini gap-fill, opt-in):** ONE batched call for *only* the `None`-client
  projects: "Given these project names + repos + 1-2 recent activity snippets, name the
  client/customer if evident, else null." Reuse the existing adapter; deterministic
  fallback on any failure = leave `None` (never guess, never block the pipeline).

~30 lines. Skipped: per-project calls (batch one prompt), retry/caching machinery
(the inference pass already reruns on refresh).

### Edit 2 — bucket (`registry.py`, beside `get_projects()`)

One derived reader — the "discrete buckets":

```python
def get_clients(database_path: Path) -> dict[str, list[str]]:
    """Group project names by effective client. Derived view, not stored state."""
    buckets: dict[str, list[str]] = defaultdict(list)
    for p in get_projects(database_path):
        cf = p.get("custom_fields") or {}
        client = cf.get("client") or cf.get("client_inferred") or "(unassigned)"
        buckets[client].append(p["name"])
    return dict(buckets)
```

~12 lines. Skipped: a `client_registry` table, a client dataclass, client status/priority —
none exist as a need yet.

### Edit 3 — synthesize (`next_actions.py`, `build_rank_prompt()`)

Add the effective client to each project line already in the prompt (~2 lines), so the
ranked "what to do next" can group by and reason about client. Optionally pass
`get_clients()` as a compact roster block so the synthesis can flag an at-risk client whose
projects are individually quiet — the actual decision-quality payoff.

### Test — one self-check (`tests/test_client_buckets.py`)

Asserts: curated `client` beats `client_inferred`; group-by produces correct buckets;
null-client projects land in `(unassigned)`. No fixtures, no framework beyond pytest.

---

## What this deliberately does NOT build (and when to add it)

| Skipped | Add when |
|---|---|
| `client_registry` table | a client must persist independently of its projects (zero-project client, client-level status/priority) |
| `confirm_clients` MCP tool | operators need to curate clients separately from projects — until then, confirming the project (existing `confirm_projects`) confirms its inferred client, and config `client` is the override |
| Client classifier / aliases | a single client name needs many spelling variants matched across signals |
| Vault client sections | the dashboard needs a client-grouped view distinct from the project view |
| Per-project Gemini calls | one batched gap-fill call measurably mislabels |

Every row above is an **additive** later step over `custom_fields.client_inferred` — none
requires reworking v1. That is the "don't paint into a corner" guarantee: v1's storage key
is forward-compatible with a future table (the table's first migration just lifts the key).

---

## Anti-goals

- Not a CRM or client database. One field per project + a derived group-by.
- Not a second inference subsystem. One write inside the pass that already runs.
- Not blocking the pipeline on Gemini. Deterministic owner-as-client is the spine;
  Gemini fills gaps and fails soft to `None`.

---

## Phased delivery

- **Phase 0 — accept design.** Confirm clients-as-project-attribute (not a new entity) is
  the intended v1. _Kill check:_ if owner-as-client already covers >90% of active projects,
  stop at v1 and skip Gemini entirely.
- **Phase 1 — v1 deterministic.** Edits 1 (owner-as-client) + 2 + 3 + test. No API key
  needed; `get_clients()` returns real buckets; rank prompt is client-aware.
- **Phase 2 — v1.1 Gemini gap-fill.** Batched call for `None`-client projects only.
  Verified live in the keyed env (sandbox has no GSM key).

## Verification (per ROUTER §7)

`rebalance doctor` clean + `pytest tests/` green (incl. the new self-check) before any
success claim. Doc-hygiene: `utils/pdda/pdda.sh run` before moving this doc to `2-WORKING`.
