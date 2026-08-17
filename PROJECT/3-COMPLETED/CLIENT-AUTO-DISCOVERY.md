---
title: "Client Auto-Discovery (piggyback on the project lifecycle)"
project: "Client Auto-Discovery"
codename: HiQS
owner: Noel
created: 2026-06-30
updated: 2026-07-01
status: "Closed at v1 — Phase 2 kill-check fired (2026-07-01). Owner-as-client covers 100% of the live registry (15/15 active projects), so the Gemini gap-fill path is code-complete but currently dormant (zero None-client rows to fill). Lazy-by-default: clients are an attribute of a project, not a new entity. No new table, no new lifecycle, no new MCP tool."
goal: "Auto-discover a CLIENT name per project and expose clients as discrete buckets the 'what to do next' synthesis can group/prioritize by — without building a parallel client entity or its own lifecycle."
current_phase: "Phase 2 closed by kill-check (2026-07-01). All phases complete; ready for archive to 3-COMPLETED."
endgame: "The ranked next-action list is client-aware: items roll up under their client, and a sparse/at-risk client surfaces even when its projects are individually quiet."
kill_switch: "Kill if owner-as-client (free, deterministic) already labels >90% of active projects correctly — then Gemini gap-fill is unjustified and clients stay a pure derived GROUP BY."
tags: [signal-quality, client-discovery, ponytail]
effort: 2
complexity: 2
risk: 1
phases: 3
roadmap_exempt: false
---

## Status

| What was just completed | What's next |
|---|---|
| **Phase 2 kill-check closed at v1 (2026-07-01, PR #100).** Gemini gap-fill (`_infer_client` owner-as-client spine, `_build_client_gapfill_prompt`, `_gapfill_missing_clients`, batched-call fail-soft-to-`None`) was built code-complete in MARATHON-C-WAVE2 (2026-06-30) and shipped with `tests/test_client_buckets.py` + `tests/test_client_gapfill.py` (9 tests). The kill-check then measured owner-as-client coverage against the live repo-local registry: **15/15 active projects (100%) already labeled** — zero calendar-only/personal-account rows needing a Gemini fill. Kill switch fired (≥90% threshold); the gap-fill path stays in the codebase, dormant, ready to activate the moment a `None`-client row appears. `registry.py`/`next_actions.py` interfaces untouched. → `relay-system/2026-07-01/marathon-c-client-autodiscovery-phase2.md` | **None queued.** All phases complete. Move this doc to `3-COMPLETED`; re-open only if live coverage drops below 90% (e.g. a calendar-only or personal-account project is added). |

## Table of contents

- [Phase 0 — accept design](#phased-delivery) _(complete)_
- [Phase 1 — v1 deterministic](#phased-delivery) _(complete)_
- [Phase 2 — v1.1 Gemini gap-fill](#phased-delivery) _(closed by kill-check)_

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
  - **QA gate:** design accepted; doc carries triage ratings + status table; promoted to `2-WORKING`. ✅ (2026-06-30)
- **Phase 1 — v1 deterministic.** Edits 1 (owner-as-client) + 2 + 3 + test. No API key
  needed; `get_clients()` returns real buckets; rank prompt is client-aware.
  - **QA gate:** `tests/test_client_buckets.py` green (curated `client` beats `client_inferred`;
    group-by buckets correct; null-client → `(unassigned)`); full `pytest tests/` green;
    `rebalance doctor` clean. No new file beyond the one test; storage is `custom_fields.client_inferred` only. ✅ (2026-06-30 — suite 1222 green, doctor clean, PDDA 0 errors)
- **Phase 2 — v1.1 Gemini gap-fill.** Batched call for `None`-client projects only.
  Built code-complete (2026-06-30, MARATHON-C-WAVE2); kill-check closed 2026-07-01.
  - **QA gate:** `tests/test_client_buckets.py` + `tests/test_client_gapfill.py` green (9 tests,
    unit-level: batched-prompt shape, fail-soft-to-`None` on invalid JSON / non-Gemini fallback /
    missing key); deterministic owner-as-client path unchanged when the key is absent. ✅ (2026-07-01)
  - **Kill-check (superseded the "verified live" bullet):** measured owner-as-client coverage on
    the live repo-local registry — **15/15 active projects (100%) ≥ 90% threshold** → kill switch
    fired. Zero `None`-client rows exist to gap-fill, so "labels ≥1 previously-`None` project in
    the live keyed env" is **not applicable** — there was nothing left for Gemini to label. The
    gap-fill code ships dormant, covered by mocked unit tests only; it has not been exercised
    against a live Gemini call. Re-open if live coverage ever drops below 90%.
    → `relay-system/2026-07-01/marathon-c-client-autodiscovery-phase2.md` (VERDICT: Approved).

## Verification (per ROUTER §7)

`rebalance doctor` clean + `pytest tests/` green (incl. the new self-check) before any
success claim. Doc-hygiene: `utils/pdda/pdda.sh run` before moving this doc to `2-WORKING`.
