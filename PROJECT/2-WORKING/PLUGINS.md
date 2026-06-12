# Plugin Source Modules — plan & roster

> **Developer how-to lives in the root [PLUGINS.md](../../PLUGINS.md)** (the
> step-by-step for writing a `SourceModule`). This doc is the *roadmap/decisions*.
>
> **Status:** Active (2026-06-07). The single plan for the plugin (`SourceModule`)
> architecture and the sources onboarding through it. Consolidates the former
> `P2-PLUGIN-SOURCE-MODULES.md` (architecture spec — archived) and
> `PLUGINS-FIGMA-LINKDING.md` (decision).
> **Long-form architecture + full Phase 0 spike detail:** archived
> [3-DONE/P2-PLUGIN-SOURCE-MODULES.md](../3-DONE/P2-PLUGIN-SOURCE-MODULES.md).
> **Builds on:** P1-MODULE-REGISTRY.md (decision **B′** — extend the `index_ops`
> collector registry, descriptor-first).

## The idea

The data plane has **one good registry** (`index_ops.register_collector`) and
**hardcoded if-ladders** hanging off it for vectorize and display. Adding a source
is one `register_collector(...)` line to *ingest*, but it does **not** get
vectorized or shown without also editing `_normalize_sources`, the `backfill`
if-ladder, and the dashboard `fetch_*` fns. The plan extends the collector
descriptor into a `SourceModule` so that registering a module auto-wires
ingest + vectorize + display — **zero edits** to dispatch.

## Decision (2026-06-07): real sources first, demo last

1. **Figma is the first real customer** of the architecture (not linkding) — it
   ships a wanted feature *and* proves the seam, reusing #49's implementation.
2. **Apple Reminders is the second real source** — already designed as a
   collector with an optional semantic opt-in, so it slots straight into the
   `SourceModule` shape.
3. **Linkding is deferred** to an optional, later proof of *external*
   (out-of-tree) entry-point discovery — only if third-party plugins are ever
   wanted.
4. **Existing connectors stay untouched.** Strangler: new providers flow through
   the registry-driven path; vault/github/email/code/etc. stay on the current
   if-ladder until conversion is convenient (mechanical, parity-gated; only the
   call-site moves, SQL stays in `db/semantic.py`).

## Contracts (final names settle in Phase 1)

All new fields default to `None`/`()` so the existing collectors keep working.

```python
@dataclass(frozen=True)
class SourceModule:                                     # extends today's Collector
    name: str
    refresh: Callable[..., dict]                        # exists today
    semantic_docs: Callable[[Conn], Iterable[SemanticDoc]] | None = None  # vector plane
    panels: Callable[[Conn, PanelCtx], list[Panel]] | None = None         # display plane
    secrets: tuple[str, ...] = ()                       # config keys it needs
    requires: tuple[str, ...] = ()                      # resolver names (preconditions)
    health_check: Callable[[Conn], Check] | None = None
    included_in_all: bool = True

@dataclass
class SemanticDoc:        # a source yields these; the index owns hash/upsert/embed
    source_pk: str; doc_kind: str; title: str; body: str
    metadata: dict; created_at: str; updated_at: str

@dataclass
class Panel:              # render-agnostic view-model (feeds TUI + web + JSON)
    key: str; title: str; layout: str = "list"; rows: list[PanelRow] = ...
```

- **Vectorize becomes iteration:** `backfill_semantic_documents` iterates modules
  with a `semantic_docs` callable through the existing upsert+embed path;
  `_normalize_sources` derives its legal set from the registry.
- **Display becomes iteration:** TUI + `pulse_web` call `module.panels(...)` and
  render `Panel` → Rich / HTML / JSON. Collapses the duplicated `fetch_*`.
- **Discovery (deferred):** at registry init, load built-ins, then optionally
  `entry_points(group="rebalance.sources")` for out-of-tree packages.

## Phase 0 spike — done (the load-bearing findings)

Spike at `experimental/plugin-spike/` (vs current `development`: 11/12 here,
14/14 in-container; the 1 gap is only the un-`pip install`ed dummy plugin):

- **F1 — the semantic schema is already source-agnostic.** A brand-new
  `source_type` upserts → dedupes → embeds → KNN with **zero** edits to
  `upsert_document` / `db/semantic.py` / vec0. Phase 1 is *not* a semantic rewrite.
- **F2 — the only vector-plane blocker is orchestration.**
  `_normalize_sources(["linkding"])` raises `Unsupported source type` — that one
  allow-list (+ the backfill if-ladder it guards) is the entire gate.
- **F3 — the embedder is Apple-Silicon-bound.** `mlx_embeddings` can't import on
  Linux. Tests **must inject `embed_texts`**, never load mlx. (vec0 + FTS load
  fine on Linux — only the embedder is Mac-bound.)

## Roadmap

1. **Phase 1 — registry-driven vectorize (strangler).** Add `semantic_docs`;
   derive `_normalize_sources` from the registry; add the iteration path
   *alongside* the existing if-ladder (don't delete yet). Parity gates: row-count
   + identity parity + ≥80% top-k(10) overlap. Tests inject the embedder (F3).
2. **Figma `SourceModule`** — first provider (see roster).
3. **Apple Reminders `SourceModule`** — second provider, gated on the macOS TCC
   unblock (see roster).
4. **(Optional) Phase 2 — dashboard panels** via the `Panel` view-model.
5. **(Deferred) Phase 3 + linkding** — external discovery + the external proof.
6. **(Eventually) convert vault/github/email/code** off the if-ladder; delete it.

## Source roster

### 1. Figma — primary proof (real source, reuse #49)
- **Implementation:** PR #49, branch `codex/add-data-collector-for-figma-api-comments`
  (`81e06b8`, open/deferred) — API client (`rebalance.ingest.figma`), comment
  parsing, `figma_comments` schema. **Re-wire as a `SourceModule`; don't land
  #49 as-is** (avoids a double refactor). Vector `body` = comment text; optional
  `figma.recent` panel.
- **Escape hatch** (if figma must ship before Phase 1): land #49 the old way —
  cherry-pick, renumber its migration to the next free number, and **union** the
  `_normalize_sources` edit (keep both `code` and `figma`) — per the archived
  merge-sequence doc §Step 3 / Risk 2.

### 2. Apple Reminders — second real source (NEW)
- **Detailed spec:** [APPLE-REMINDERS.md](./APPLE-REMINDERS.md).
- **Shape:** live Apple Reminders SQLite → **read-only temp snapshot** →
  normalized rows → `apple_reminders` collector/table → optional semantic opt-in.
  Tool surface already designed: `refresh_index(scope=["apple_reminders"])`.
- **`SourceModule` fit:** `refresh` = snapshot + normalize; `semantic_docs` =
  reminder title + notes (opt-in, *after* field quality is proven); `panels` =
  due / overdue / recent; `requires` = macOS Full Disk Access.
- **Hard rules:** never write to the Apple Reminders store; not EventKit-primary;
  **distinct from Sleuth reminders** (`sleuth_reminders.py`) — this does not
  replace it.
- **Blocker:** Phase 0 blocked 2026-06-05 on macOS **TCC / Full Disk Access** (the
  agent runtime can't read the Reminders `Stores` dir). Unblock = grant the host
  runtime FDA or run the spike from a terminal that already has access. The vector
  opt-in stays **gated** until reminder fields prove clean (don't embed
  low-quality personal data prematurely).

### 3. Linkding — deferred external-discovery proof
- Self-hosted bookmark server (token-auth REST). Its value is proving *out-of-tree*
  entry-point discovery, not the feature itself — build only if third-party
  plugins become a goal. Fixtures already seeded (`fixtures/linkding/`).

## Risks & guardrails

- **Embedder Mac-lock (F3):** never import the embedder eagerly; inject in tests.
- **Semantic refactor:** strangler + parity gates; don't delete the if-ladder
  until green.
- **Apple Reminders privacy:** read-only snapshot only; semantic opt-in gated; TCC
  is a real precondition, surfaced via `health_check` (`requires`).
- **Entry-point discovery = executing installed-package code** (Phase 3): only
  load the declared group; installing a plugin == trusting it; no auto-install.
- **Scope spread:** figma + apple reminders are the only new sources in flight;
  resist a third until the seam is proven.

## Pointers & open items

- Architecture long-form / Phase 0 detail → [3-DONE/P2-PLUGIN-SOURCE-MODULES.md](../3-DONE/P2-PLUGIN-SOURCE-MODULES.md)
- Apple Reminders detail → [APPLE-REMINDERS.md](./APPLE-REMINDERS.md)
- Figma reusable impl → PR #49 / `rebalance.ingest.figma`
- `development → main` promotion (separate track) → [3-DONE/2026-06-06-merge-sequence.md](../3-DONE/2026-06-06-merge-sequence.md) §Post-merge
- Spike artifacts (delete after Phase 1 has its own tests) → `experimental/plugin-spike/`, `fixtures/linkding/`

- [ ] **PR #49 disposition:** keep open as the figma reference, or close with a pointer here?
- [ ] **Apple Reminders:** unblock macOS TCC → Phase 0 → collector → (opt-in) vector.
- [ ] **Panels (Phase 2):** figma / reminders panels, or vector-only first?
