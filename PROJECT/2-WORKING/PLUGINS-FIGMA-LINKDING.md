# Plugins: Figma & Linkding — source-module roadmap

> **Status:** Active working doc (2026-06-07). The *what / why / when* — which
> sources go through the plugin architecture, and in what order.
> **Architecture spec (the *how*):** [P2-PLUGIN-SOURCE-MODULES.md](./P2-PLUGIN-SOURCE-MODULES.md)
> — the `SourceModule` contract, the phases, the Phase 0 spike findings.
> **Supersedes** the figma-landing plan in
> [3-DONE/2026-06-06-merge-sequence.md](../3-DONE/2026-06-06-merge-sequence.md)
> (now retired; its `development → main` promotion runbook still lives there).

## Decision (2026-06-07)

**Figma is the first real customer of the plugin (`SourceModule`) architecture —
not linkding.** Linkding is demoted to an *optional, later* proof of external
(out-of-tree) entry-point discovery, built only if/when third-party plugins are
actually wanted.

Corollaries:

- **Don't land PR #49 (figma) as-is.** Its hardcoded collector +
  `_normalize_sources` / backfill if-ladder edits are exactly what the plugin
  architecture removes — landing it the old way means refactoring figma twice.
  Its API client, comment parsing, `figma_comments` schema, and migration are the
  **reusable implementation** behind a figma `SourceModule`; only the *wiring*
  changes.
- **Leave existing connectors alone.** vault / github / email / code / focus5 /
  ask_self / calendar / sleuth keep working untouched. The plugin payoff is
  reached via the **strangler**: new providers (figma) flow through the
  registry-driven path while the existing sources stay on their current path
  until conversion is convenient — mechanical, parity-gated, behavior-preserving
  (only the call-site moves; the SQL stays in `db/semantic.py`).
- **Defer Phase 3 (external entry-point discovery) + linkding indefinitely.**
  It's the highest-complexity, lowest-immediate-value piece (executing code from
  installed packages), and a personal tool likely never needs third-party
  out-of-tree plugins.

## Why figma over linkding as the proof

| | Figma (#49 exists) | Linkding (hypothetical) |
|---|:---:|:---:|
| Delivers a wanted feature | ✅ | ❌ demo only (needs a linkding server to matter) |
| Proves the in-tree `SourceModule` contract | ✅ | ✅ |
| Proves external out-of-tree discovery | ❌ (in-tree) | ✅ (entry-point) |
| Reuses existing code | ✅ #49's client/parser/schema | ❌ build from scratch |

Same effort as building the linkding demo, but it ships a real source instead of
a throwaway. Linkding keeps its value *later* as the external-discovery proof —
just not now.

## Roadmap

1. **Phase 1 — registry-driven vectorize (strangler).** Add `semantic_docs` to
   the descriptor; derive `_normalize_sources`' legal set from the registry; add
   the iteration path for modules that declare `semantic_docs` **alongside** the
   existing if-ladder (don't delete it yet). Parity-gated. → exact edits in
   [P2 Phase 1](./P2-PLUGIN-SOURCE-MODULES.md#phase-1--vector-write-path-becomes-registry-driven).
2. **Figma `SourceModule`.** Implement figma as the first provider through the
   new path, reusing #49's `rebalance.ingest.figma` client + comment→`SemanticDoc`
   mapping + `figma_comments` schema. **Migration numbering:** figma's
   `figma_comments` table is a real base table → numbered migration; claim the
   **next free number at implementation time** (`0002`/`0003` are taken by #54, so
   it's `0004` today — re-check before writing).
3. **(Optional) Phase 2 — figma dashboard panel** via the `Panel` view-model, if
   a figma panel is wanted.
4. **(Deferred) Phase 3 + linkding** — external entry-point discovery and the
   linkding reference integration, only if third-party plugins become a goal.
5. **(Eventually) convert the existing vectorizing sources** (vault / github /
   email / code) from the if-ladder to providers, then delete the ladder — once
   figma has proven the path. No rush.

## Tradeoff & escape hatch

This couples figma's ship date to building Phase 1. Figma isn't urgent (it was
intentionally deferred in the merge sequence), so that's acceptable.

**Escape hatch:** if figma becomes urgent before Phase 1 is ready, land #49 the
old way — cherry-pick `81e06b8`, renumber its migration to the next free number,
and **union** the `_normalize_sources` edit (keep both `code` and `figma`) — per
the retired doc's §Step 3 / Risk 2. Then let the eventual Phase 1 sweep figma into
a provider. A minor double-touch, not a trap.

## Pointers

- **Architecture spec / phases / Phase 0 findings:**
  [P2-PLUGIN-SOURCE-MODULES.md](./P2-PLUGIN-SOURCE-MODULES.md)
- **#49 figma branch (reusable implementation):**
  `codex/add-data-collector-for-figma-api-comments` (commit `81e06b8`); PR #49
  (open, deferred).
- **Retired merge-sequence doc** (figma escape-hatch runbook + `development → main`
  promotion runbook):
  [3-DONE/2026-06-06-merge-sequence.md](../3-DONE/2026-06-06-merge-sequence.md)
- **Spike artifacts** (throwaway — delete once Phase 1 has its own tests):
  `experimental/plugin-spike/`, `fixtures/linkding/`

## Open items

- [ ] **PR #49 disposition:** keep open as the reference implementation, or close
      with a pointer to this doc? (Leaning: keep open, labeled "reference for the
      figma `SourceModule`.")
- [ ] **Figma panel?** Does figma warrant a dashboard panel (Phase 2), or is it
      vector-only at first?
- [ ] **`development → main` promotion** (separate track) — runbook in the retired
      doc; execute when ready.
