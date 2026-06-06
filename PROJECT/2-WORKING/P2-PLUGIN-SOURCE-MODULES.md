# P2 Plugin Source Modules

> **Status:** Open plan — written 2026-06-06 on branch
> `claude/plugin-architecture-activity-stream`.
> **Builds on:** [P1-MODULE-REGISTRY.md](./P1-MODULE-REGISTRY.md) (decision **B′** —
> extend the runtime `index_ops` collector registry, descriptor-first) and
> [P2-SEMANTIC-INDEX.md](../1-INBOX/P2-SEMANTIC-INDEX.md) (the unified
> `semantic_documents` table already shipped).
> **What it adds:** B′ wires a new source into *refresh / status / doctor /
> brief / querier*. It deliberately stops at two planes this plan completes —
> the **vector write-path** and the **dashboard feed** — then proves the whole
> seam end-to-end with one external plugin: a self-hosted **linkding**
> bookmark server.

## TOC

- [Current State — what is pluggable, what is not](#current-state--what-is-pluggable-what-is-not)
- [Goals](#goals)
- [Architecture Direction](#architecture-direction)
- [The Contracts](#the-contracts)
- [Reference Integration: linkding](#reference-integration-linkding)
- [Phase 0 Technical Spike](#phase-0-technical-spike)
- [Phase 1 — Vector write-path becomes registry-driven](#phase-1--vector-write-path-becomes-registry-driven)
- [Phase 2 — Dashboard feed contract](#phase-2--dashboard-feed-contract)
- [Phase 3 — Discovery + registry-driven preconditions](#phase-3--discovery--registry-driven-preconditions)
- [Phase 4 — linkding reference integration (the proof)](#phase-4--linkding-reference-integration-the-proof)
- [Phase 5 — (Optional) Embedder seam](#phase-5--optional-embedder-seam)
- [Contracts and Ownership](#contracts-and-ownership)
- [Risks and Guardrails](#risks-and-guardrails)
- [Observability and Tests](#observability-and-tests)
- [Success Criteria](#success-criteria)
- [Open Questions](#open-questions)

## Current State — what is pluggable, what is not

The data plane has **one good registry and two hardcoded if-ladders** hanging off it.

| Plane | Where | Pluggable? |
|---|---|---|
| **Ingest** | `index_ops.COLLECTORS` + `register_collector` (`index_ops.py:64`) | ✅ Adding a source is one `register_collector(...)` call. |
| **Preconditions** | hardcoded ladder in `refresh_index` (`index_ops.py:924` — only `vault_path` / `github_token`) | ❌ A new source can't declare its own secret. |
| **Vectorize** | `_normalize_sources` (`semantic_index.py:66`, hardwired `{vault,github,calendar,sleuth,email}`) + the `if "vault"… / if "github"… / if "email"…` ladder in `backfill_semantic_documents` (`semantic_index.py:344`), each calling a bespoke `sync_*_documents` with hand-written SQL in `db/semantic.py` | ❌ Registering a collector does **not** vectorize its data. Four edits required — contradicts P2-SEMANTIC-INDEX goal "onboarding a new source = write rows into `semantic_documents`." |
| **Display** | `scripts/dashboard.py` hardcoded `fetch_*` fns; `scripts/pulse_web.py` `import`s those symbols directly | ❌ Tracked as an open violation: `DASHBOARD.md:24` #8 "adding a new ingest source requires touching the display layer" (also #4 duplicated `fetch_org_activity`, #5 two `dashboard.py`). No panel/feed contract, no JSON view-model. |
| **Embedder** | `embedder.py:21` hardwires MLX + `Qwen3-Embedding-0.6B`; `EMBEDDING_DIM=1024` baked into the vec0 DDL | ❌ Mac-only, one model, one dim, single global meta contract. (`embed_texts` is injectable — a usable seam.) |
| **Boundary / discovery** | built-ins registered at import (`index_ops.py:1008`); no entry-point discovery | ❌ A third-party module must be imported into the process to register. |

**The reframe that drives the phasing.** Today the dashboard's *activity* view is built from **structured SQL aggregation** over raw tables (`github_activity`, `calendar_events`, `email_messages`); the **vector index** powers `ask()` / semantic search only (`P1-SIGNAL.md:308` "embeddings should not participate in the scoring path"). So "vectorized activity stream → web dashboard" is two disjoint pipelines that don't meet. linkding is the first source designed to exercise **both** cleanly — a structured *panel* (counts / recent / unread) **and** a *vector* contribution (title+description+notes, genuinely embeddable) — which is exactly why it's the right proof.

## Goals

- [ ] One **`SourceModule`** descriptor (an extension of `Collector`) is the single place a source is declared — ingest, vectorize, render, config, health.
- [ ] Registering a module auto-wires it into refresh, semantic backfill/embed, and the dashboard — **zero edits** to dispatch, `_normalize_sources`, the backfill if-ladder, dashboard `fetch_*`, or `pulse_web` imports.
- [ ] Sources are **discovered** via Python entry points (`group="rebalance.sources"`), so a plugin can ship as its own package.
- [ ] One typed **view-model** (`Panel` / `PanelRow`) feeds the TUI and the web mirror — and is the JSON contract the Lovable mirror (`P2-LOVABLE-APP.md`) is waiting on.
- [ ] Preconditions/secrets are **declared on the module**, not hardcoded in `refresh_index`.
- [ ] **linkding** lands as an external module with no core edits — the executable definition of "done."

Non-goals (this pass): a scaffolder/codegen (B′ explicitly rejects it); a network/RPC boundary (modules stay in-process Python); replacing the embedder (Phase 5, gated).

## Architecture Direction

Extend the descriptor B′ already grows, into the two planes B′ omits, then make the registry discoverable.

```
                         register_source(SourceModule)  ◀── entry_points("rebalance.sources")
                                      │
        ┌──────────────┬─────────────┼───────────────┬────────────────┐
        ▼              ▼             ▼                ▼                ▼
   refresh()     semantic_docs()  panels()      requires/secrets   health_check()
   (ingest)      (vectorize)      (display)     (preconditions)    (doctor/onboard)
        │              │             │
        ▼              ▼             ▼
  source tables  semantic_documents  Panel view-model ──▶ TUI render
  (canonical)    → semantic_embeddings                └─▶ web/pulse.html render
                 (single-writer:                       └─▶ JSON push (Lovable, later)
                  semantic_index.py)
```

Three principles, all already endorsed elsewhere in the repo:

1. **Extend, don't rebuild** (B′). New descriptor fields are optional callables; a refresh-only collector stays a one-liner.
2. **Single writer per contract** (AGENTS.md). `semantic_index.py` stays the only writer of the semantic schema; modules *yield* `SemanticDoc`s, they never touch tables. A new `display/feed.py` owns the view-model; renderers consume it, never query sources.
3. **Derived, not canonical.** Source tables keep their domain columns. The vector index and the panel feed are both derived projections.

## The Contracts

Concrete shapes (final names settle in Phase 1). All new fields default to `None` so the existing six collectors keep working untouched.

```python
# index_ops.py — extends the existing Collector
@dataclass(frozen=True)
class SourceModule:
    name: str                                  # scope key, lowercase, unique
    refresh: Callable[..., dict]               # (db_path, **opts) -> summary   [exists today]

    # --- vector plane (Phase 1) ---
    semantic_docs: Callable[[Conn], Iterable["SemanticDoc"]] | None = None

    # --- display plane (Phase 2) ---
    panels: Callable[[Conn, "PanelCtx"], list["Panel"]] | None = None

    # --- preconditions / health (Phase 3, dovetails with B′) ---
    secrets: tuple[str, ...] = ()              # config keys this source needs
    requires: tuple[str, ...] = ()             # resolver names; checked generically
    health_check: Callable[[Conn], "Check"] | None = None   # B′ field
    included_in_all: bool = True


@dataclass
class SemanticDoc:                              # what a source yields; index owns hash/upsert/embed
    source_pk: str                             # stable, source-derived (see P2-SEMANTIC-INDEX mapping)
    doc_kind: str                              # 'bookmark' | 'chunk' | 'item_body' | ...
    title: str
    body: str                                  # the embeddable text
    metadata: dict                             # source-specific extras (url, tags, state)
    created_at: str
    updated_at: str
    # source_type is the module name; source_table is declared once on the module.


@dataclass
class PanelRow:                                # render-agnostic; no Rich, no HTML
    title: str
    subtitle: str = ""
    timestamp: str | None = None
    badges: tuple[str, ...] = ()               # e.g. agent tag, state, "unread"
    url: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class Panel:
    key: str                                   # stable id, e.g. "linkding.recent"
    title: str                                 # "Bookmarks"
    layout: str = "list"                       # "list" | "counts" | "timeline"
    rows: list[PanelRow] = field(default_factory=list)
```

- **Vectorize becomes iteration.** `backfill_semantic_documents` iterates `COLLECTORS` for modules with a `semantic_docs` callable and feeds each yielded `SemanticDoc` through the existing `upsert_document` + reconcile + `embed_pending` path. `_normalize_sources` derives its legal set from the registry. The three `sync_*_documents` functions become `semantic_docs` providers on their own collectors.
- **Display becomes iteration.** The TUI and `pulse_web` call `module.panels(conn, ctx)` for every registered module and render `Panel` → Rich table / HTML / (later) JSON. The duplicated `fetch_*` logic collapses into each module.
- **Discovery.** At registry init, load built-ins (as today) then
  `importlib.metadata.entry_points(group="rebalance.sources")`, calling each to obtain a `SourceModule` and `register_source` it. Built-ins win on name collision unless `replace=True`.

## Reference Integration: linkding

[linkding](https://github.com/sissbruecker/linkding) is a self-hosted bookmark manager with a token-auth REST API — a clean external source that exercises every contract above.

**API (read path).**
- Base URL: the user's instance (e.g. `https://links.example.com`).
- Auth: header `Authorization: Token <token>`.
- `GET /api/bookmarks/?limit=100&offset=N` → `{count, next, previous, results:[…]}` (paginate to `next is None`; `per_page=100` per AGENTS.md anti-patterns).
- Delta: filter/sort by `date_modified`; persist a high-water mark, request only newer on subsequent runs.
- Bookmark fields used: `id, url, title, description, notes, website_title, website_description, tag_names[], is_archived, unread, date_added, date_modified`.

**Config** (single pattern, `temp/rbos.config`, mirrors `get/set_github_token`):
`get_linkding_config()` / `set_linkding_config(base_url, token)` →
keys `linkding_base_url`, `linkding_token`. Token is a secret — masked in logs, never committed.

**Storage** — one canonical table (domain columns stay here):
```sql
CREATE TABLE linkding_bookmarks (
    id            TEXT PRIMARY KEY,     -- linkding bookmark id
    url           TEXT NOT NULL,
    title         TEXT,
    description   TEXT,
    notes         TEXT,
    tag_names     TEXT,                 -- json array
    is_archived   INTEGER NOT NULL DEFAULT 0,
    unread        INTEGER NOT NULL DEFAULT 0,
    date_added    TEXT,
    date_modified TEXT,
    synced_at     TEXT NOT NULL
);
```

**`semantic_docs` mapping** (no change to `semantic_documents` schema):

| field | value |
|---|---|
| `source_type` | `"linkding"` (module name) |
| `source_table` | `"linkding_bookmarks"` |
| `source_pk` | bookmark `id` (TEXT) |
| `doc_kind` | `"bookmark"` |
| `title` | `title or website_title or url` |
| `body` | `title + "\n" + description + "\n" + notes` (skip if empty) |
| `metadata` | `{url, tag_names, is_archived, unread, date_added}` |
| `created_at` / `updated_at` | `date_added` / `date_modified` |

**`panels`** — two render-agnostic panels:
- `linkding.recent` (layout `list`): newest N bookmarks → `PanelRow(title, subtitle=domain, timestamp=date_added, badges=tag_names + ["unread"?], url)`.
- `linkding.counts` (layout `counts`): total / unread / archived / added-this-week.

**Module assembly** (the whole integration, no core edits):
```python
SourceModule(
    name="linkding",
    refresh=linkding_refresh,            # paginate API → upsert linkding_bookmarks → backfill+embed
    semantic_docs=linkding_semantic_docs,
    panels=linkding_panels,
    secrets=("linkding_base_url", "linkding_token"),
    requires=("linkding_credentials",),
    health_check=linkding_health,        # creds present? base_url reachable? table fresh?
)
# exposed via entry point  rebalance.sources = { linkding = "rebalance_linkding:module" }
```

## Phase 0 Technical Spike

Timebox **1–2h**. Prove the three seams independently before building any of them. Read-only / throwaway.

- [ ] **Discovery:** register a dummy `SourceModule` via a local entry point; confirm the registry loads it and `refresh_index(scope=["dummy"])` dispatches to it. (Proves the plugin boundary.)
- [ ] **linkding API:** with a real token, paginate `GET /api/bookmarks/`; capture one page to `fixtures/linkding/bookmarks_page.json`; confirm field shape + `next` pagination + `Authorization: Token` auth.
- [ ] **Vector round-trip:** hand-map 5 fixture bookmarks → `SemanticDoc` → `upsert_document` → `embed_pending` against the **existing 1024-dim model**; run `semantic_index.query("…")` and confirm bookmark hits rank. (Proves linkding needs **no** embedder change → Phase 5 stays optional.)
- [ ] Findings block appended here: API quirks (self-signed TLS? rate limits?), pagination cap, embed timing.

**Gate:** if any seam fails (e.g. entry-point discovery is fighting the MCP launch model, or linkding text is too short to embed usefully), stop and re-scope before Phase 1.

## Phase 1 — Vector write-path becomes registry-driven

Kills impediment #1. Highest-risk phase (mirrors P2-SEMANTIC-INDEX's own warning about consolidating embed paths) — gate hard on parity.

- [ ] Add `semantic_docs` to the descriptor; add the `SemanticDoc` dataclass.
- [ ] Convert `sync_vault_documents` / `sync_github_documents` / `sync_email_documents` into `semantic_docs` providers attached to the vault/github/email collectors. Keep the SQL in `db/semantic.py` (single owner) — only the call site moves.
- [ ] Rewrite `backfill_semantic_documents` to iterate `COLLECTORS` for modules declaring `semantic_docs`; drive `_normalize_sources` from the registry (drop the hardwired set).
- [ ] Strangler: keep the old if-ladder behind a flag until parity passes, then delete.

**Gate (from P2-SEMANTIC-INDEX acceptance):** (1) row-count parity per source; (2) identity parity — hashed set of `(source_pk, content_hash)` tuples matches old vs new; (3) ≥80% top-k(10) overlap on the fixed query set. Re-embed touches only changed rows (`embedded_at` unchanged on a no-op re-run).

## Phase 2 — Dashboard feed contract

Kills impediment #2; flips `DASHBOARD.md` #4/#5/#8 to clear; produces the JSON shape Lovable needs.

- [ ] Add `Panel` / `PanelRow` view-model in a new `src/rebalance/display/feed.py` (single owner).
- [ ] Add `panels` to the descriptor; move each source's `fetch_*` logic into its module's `panels` provider (de-dupe `fetch_org_activity`, collapse the two `dashboard.py`s — DASHBOARD.md #4/#5).
- [ ] Refactor `scripts/dashboard.py` to render `Panel → Rich`; refactor `scripts/pulse_web.py` to render `Panel → HTML` (drop the direct `from dashboard import fetch_*`). Both iterate the registry.
- [ ] Add a `feed_json()` helper (serialize `list[Panel]`) — the contract `P2-LOVABLE-APP.md` Phase 2 push consumes.

**Gate:** TUI + `web/pulse.html` render the current six sources with parity (snapshot the rendered rows before/after). `DASHBOARD.md` #8 verified clear: adding a source touches no display file.

## Phase 3 — Discovery + registry-driven preconditions

Kills impediment #5 and the precondition half of #3.

- [ ] Entry-point loader (`group="rebalance.sources"`) at registry init; built-ins win on collision unless `replace=True`.
- [ ] Replace the hardcoded precondition ladder in `refresh_index` (`index_ops.py:924`) with generic resolution over each module's `requires` / `secrets`; missing creds surface as the existing structured error envelope.
- [ ] Dovetail with B′ Phase 2: each module's `health_check` is reachable via the `health_check()` MCP tool, and `onboarding_status` reflects a discovered source's `secrets` — so a freshly-installed plugin's setup hint reaches MCP-first agents (the exact gap B′ was triggered by).

**Gate:** an out-of-tree package exposing a `rebalance.sources` entry point appears in `index_status()`, `refresh_index`, `doctor`, and onboarding with no core edits.

## Phase 4 — linkding reference integration (the proof)

The end-to-end demonstration. If this needs **any** edit to dispatch / `_normalize_sources` / backfill / `fetch_*` / `pulse_web` imports, the architecture has failed and we fix the contract, not linkding.

- [ ] `contrib/rebalance_linkding/` (in-repo, but wired via entry point to exercise the external path): `client.py` (paginated REST, token auth, TLS-verify config, 429 backoff, `per_page=100`), `refresh`, `semantic_docs`, `panels`, `health_check`, `config` getters in `config.py`, `linkding_bookmarks` schema via an `ensure_*` migration.
- [ ] Mock harness `fixtures/linkding/`: happy path, pagination (multi-page `next`), `401`, `403`, `429`, `504`, malformed JSON (AGENTS.md testing rules). `MOCK_MODE=true` toggles the client.
- [ ] Integration test: clean DB → `refresh_index(scope=["linkding"])` → assert `linkding_bookmarks` populated, `semantic_documents` has `source_type='linkding'` rows embedded, `semantic_query("…")` returns a bookmark, and `feed_json()` contains a `linkding.recent` panel.
- [ ] Docs fan-out per B′ Phase 5 / ARCHITECTURE.md "Adding a New Source": one Signal-Sources row, CHANGELOG entry (MINOR — new feature), no 4X4/README unless user-facing is declared.

**Gate:** the integration test passes and `git diff` for the linkding feature touches **only** `contrib/rebalance_linkding/`, `config.py` (two getters), `fixtures/`, tests, and docs — nothing in the core dispatch/semantic/display modules.

## Phase 5 — (Optional) Embedder seam

Gated on evidence; linkding does **not** require it (Phase 0 proves the default model fits).

- [ ] `Embedder` protocol (`name`, `dim`, `embed(texts) -> vectors`); make `semantic_embedding_meta` per-source-capable; unfreeze the vec0 `float[1024]` DDL so a source can declare its own dim.
- [ ] Only build when a real source needs a different model (P2-SEMANTIC-INDEX open question #2). Until then this stays a documented seam, not code.

## Contracts and Ownership

- **`index_ops.py`** — owns `SourceModule`, the registry, discovery, precondition resolution.
- **`semantic_index.py`** — remains the *single writer* of the semantic schema. Sources yield `SemanticDoc`s; they never touch `semantic_documents` / `semantic_embeddings`. SQL stays in `db/semantic.py`.
- **`display/feed.py`** (new) — owns `Panel` / `PanelRow` / `feed_json`. Renderers (`scripts/dashboard.py`, `scripts/pulse_web.py`) consume the view-model only.
- **`config.py`** — owns all config getters/setters (linkding included).
- **Contract versioning:** `SourceModule` is a public contract once external plugins exist — changes are semver-tracked and announced (AGENTS.md "broadcast breaking changes").

## Risks and Guardrails

- **Semantic refactor is the biggest piece** (P2-SEMANTIC-INDEX flagged embed-path consolidation as ~a day on its own). Strangler + the three parity gates; don't delete the if-ladder until green.
- **Display refactor changes output.** Snapshot-parity the rendered TUI/HTML before deleting `fetch_*`.
- **Entry-point discovery = executing code from installed packages.** Trust boundary: only load the declared group; document that installing a `rebalance.sources` plugin is equivalent to trusting that package. No auto-install.
- **Self-hosted linkding realities:** self-signed TLS (verify-toggle config, never silent `verify=False`), pagination caps, rate limits (backoff), large libraries (bounded queries, `per_page=100`).
- **Scope spread** (P1-SIGNAL's central warning). linkding is the *only* new source in this plan. Resist adding a second until the seam is proven.
- **Reversibility.** Every phase is independently shippable; new descriptor fields are optional, so stopping after any phase leaves a working system.

## Observability and Tests

Per AGENTS.md "from day one":
- Structured logging with context (module name, scope, counts) on every refresh/embed/render path; mask the linkding token.
- Mock harness **before** hitting the linkding API; fixtures versioned in `fixtures/linkding/`.
- `health_check` for linkding (creds present, base_url reachable, table freshness) surfaced via the `health_check()` MCP tool.
- Counters/timing on ingest, embed, and panel build; the freshness signal already tracks `last_embed_at`.
- The Phase 4 integration test (clean DB → ingest → vectorize → query → panel) is the smoke test that proves the happy path.

## Success Criteria

- [ ] Adding a source = implement one `SourceModule` + register one entry point. **Zero edits** to refresh dispatch, `_normalize_sources`, the backfill if-ladder, dashboard `fetch_*`, or `pulse_web` imports (verified by the Phase 4 `git diff`).
- [ ] linkding bookmarks flow **ingest → vector → semantic query → TUI + web panel** from the descriptor alone.
- [ ] `DASHBOARD.md` #4, #5, #8 flip to clear.
- [ ] One view-model (`Panel`) feeds TUI + web, and `feed_json()` is ready for the Lovable push.
- [ ] A discovered (out-of-tree) plugin appears in `index_status`, `refresh_index`, `doctor`, and onboarding with no core edits.
- [ ] No semantic-recall regression: identity parity + ≥80% top-k overlap at the Phase 1 cutover.

## Open Questions

- [ ] **In-repo `contrib/` vs separate pip package** for linkding? Recommendation: in-repo `contrib/` as the canonical example, but wired through the entry-point path so it still proves external discovery.
- [ ] **Do `panels` belong on `SourceModule` or a separate render-module class?** B′ open question #3 raised `source` vs `render` module classes. Leaning: keep `panels` optional on the one descriptor (a source renders itself); reserve a separate render class only for pure consumers (e.g. a cross-source summary panel).
- [ ] **Activity vs vector on the dashboard.** linkding makes a source contribute both a structured panel and vector docs. Should the dashboard ever surface *vector* results directly (semantic "related bookmarks"), or do vectors stay search-only? This is the unresolved half of the reframe; decide after linkding ships both planes.
- [ ] **Per-source embedders** (Phase 5) — defer until a source needs a different model/dim (P2-SEMANTIC-INDEX open question #2).
- [ ] **`SourceModule` contract versioning** once third-party plugins exist — semver + a compatibility note in ARCHITECTURE.md.
