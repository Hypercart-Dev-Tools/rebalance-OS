---
title: ROADMAP.md → Dashboard Signal (cross-repo "what's next" collector)
status: Draft
created: 2026-06-30
updated: 2026-06-30
branch: development
goal: >
  Study and brainstorm turning the PDDA ROADMAP.md "What's next" ledger — which exists across
  many repos on this device — into a first-class rebalance/HiQS signal source, so the dashboard
  plane can answer "what should I work on next" using the project state agents already maintain.
  This is an INBOX brainstorm/plan, not yet active work; no ROADMAP.md pointer is required until
  it is promoted to 2-WORKING.
---

# ROADMAP.md → Dashboard Signal

## Status

| What was just completed | What's next |
|---|---|
| Reviewed the PDDA doc contract (`pdda/ROUTER.md`, `AGENTS.md`, `GUIDING-PRINCIPLES.md`, `ROADMAP.md` frontmatter); surveyed the device (17+ PDDA-style `ROADMAP.md` files under `GH Repos` alone) and verified **Spotlight is disabled** so `mdfind` is not usable here. Confirmed the **dedicated PDDA registry shipped 2026-06-30**: `~/git-pulse-sync/pdda/registry-<device>.tsv` (`repo · last_install_utc · mode · source_commit · startup_docs`), lists only PDDA-installed repos, cross-device, ships a name→path recipe — rollout partial (1 of 3 devices). Rewrote the plan around a **registry-seeds-read** discovery model. | Operator confirms discovery model + scan scope. If green-lit, open a GitHub issue, capture as `GH-<n>-*.md`, promote to `2-WORKING`, and build Phase 1 as a `register_collector(...)` source. |

---

## 1. The call

The PDDA `ROADMAP.md` ledger is the single highest-quality "what to work on next" signal we already
produce — and we produce one per repo, kept honest by deterministic checks, with a machine-readable
`What's next` column. rebalance/HiQS is in the business of aggregating high-quality signals into a
"what next" dashboard plane. **These two systems should connect.** The cleanest seam is a new
rebalance collector that scans this device for `ROADMAP.md` files with valid PDDA frontmatter and
projects their `What's next` rows into the dashboard as a ranked work-signal.

**The bet:** project state that agents already maintain (because PDDA forces it) is a *cheaper and
more trustworthy* "next action" signal than re-deriving priorities from raw GitHub/Gmail/calendar
activity. If true, this is near-free signal of unusually high quality. If false, it adds a noisy
source that double-counts work already visible elsewhere.

**Reversibility: Easy.** A collector is additive (one `register_collector(...)` call + its own
table per the `COLLECTORS` spine). It can be added behind `observe`-style gating and removed without
touching the dispatch chain or other sources.

---

## 2. Why this fits (two systems, one seam)

**PDDA side** — every repo that has adopted PDDA keeps a `ROADMAP.md` that is, by contract:
- a *pointer ledger* (not a plan body), with YAML frontmatter (`title, status, created, updated,
  branch, goal`) and a near-top `## Status` table whose columns are exactly
  `What was just completed | What's next`;
- kept current and drift-checked by `utils/pdda/pdda.sh` (`frontmatter`, `roadmap`,
  `roadmap-coverage`, `stale`);
- explicitly designed (per PDDA's `GUIDING-PRINCIPLES.md`) so a *cold agent* can answer "what was
  just done, what's next" in seconds. That is the same question the dashboard plane asks.

**rebalance/HiQS side** — the repo is an MCP server whose data-plane spine is the `COLLECTORS`
registry (`src/rebalance/ingest/index_ops.py`); a new source is added with one
`register_collector(...)` call, not edits to the dispatch chain. The product north star (per the
HiQS rebrand memory) is to judge every source by **signal + decision quality**. A `ROADMAP.md`
`What's next` row is about as high-signal as a "what next" input gets: it is a human/agent's own
stated next step, per project, already curated.

**The overlap to respect:** rebalance already tracks repos (`list_watched_repos`,
`WATCHLIST-COVERAGE-GUARD.md`) and already has signal-generation work in flight
(`PROJECT/2-WORKING/SIGNAL-GENERATION/`, `1-INBOX/P1-SIGNAL.md`, `1-INBOX/GEMINI-WHATS-NEXT-VAULT.md`).
This plan must slot in as one more *source* feeding that existing plane — not a competing
"what next" engine. See §8.

---

## 3. Key finding: the discovery engine, not Spotlight

The initial idea was a "system search job" detecting newly created/edited `ROADMAP.md` files —
implicitly Spotlight/`mdfind`. **Verified on this device today: Spotlight server is disabled**
(`mdutil -s /Users/noelsaw/Documents` → "Spotlight server is disabled"; `mdfind` for `ROADMAP.md`
returns 0). A raw `find` walk works fine and immediately surfaced 17 PDDA-style `ROADMAP.md` files
under `GH Repos` at depth 4. So the discovery mechanism is an open decision, not a given:

| Option | How it finds ROADMAPs | Pros | Cons |
|---|---|---|---|
| **A. Raw filesystem walk** (`find` / `os.walk` over configured roots, noise-pruned) | Walk a small set of dev roots, skip `node_modules`/`.venv`/`site-packages` | Works *today* (Spotlight off); no OS dependency; fully portable; we control scope | Polling, not event-driven; cost grows with tree size (mitigated by root list + mtime filter) |
| **B. PDDA registry (PRIMARY — shipped 2026-06-30)** | Read the per-device PDDA registry the pdda repo now drops into the git-pulse sync repo: `~/git-pulse-sync/pdda/registry-<device>.tsv`, columns `repo · last_install_utc · mode · source_commit · startup_docs` | **Exists today**; enumerates *only repos with PDDA installed* → a frontmatter-valid `ROADMAP.md` is essentially guaranteed (validity gate becomes a cheap confirm); carries `mode`/`source_commit`; ships the name→path resolution recipe in its own header; cross-device by design (one file per device) | Name-keyed, absolute paths omitted by design → still resolve name→path (recipe provided). **Rollout in progress**: only the `mbp-16-m1-pro` registry exists so far; other devices pending |
| **B′. git-pulse activity-log seed (supplement)** | Distinct `repo` column from `~/git-pulse-sync/pulse-<device>.md` (TSV `epoch · ts · repo · branch · sha · subject`) | Catches repos with recent activity that are **not yet PDDA-registered** (adoption nudge); also cross-device | Activity ≠ PDDA-adopted → must validity-gate each; noisier than B |
| **C. rebalance watched-repos list** | Reuse `list_watched_repos` + known repo paths | Curated, low-noise, already exists | Manual upkeep; misses new repos until watched; couples to watchlist semantics |
| **D. `fswatch`/FSEvents daemon** | OS file-event stream on the dev roots | True "newly created/edited" event-driven detection | New long-running dependency; overkill for a signal refreshed on the existing pulse cadence |

**Recommendation (updated — the dedicated PDDA registry shipped 2026-06-30):** **seed from the PDDA
registry (B) as primary, resolve name→path, read each repo's `ROADMAP.md` (A), confirm frontmatter.**
The registry only lists PDDA-installed repos, so a valid `ROADMAP.md` is essentially guaranteed — the
"walk + validity-gate" work shrinks to "resolve path + parse the known-good file." Mechanics: read
every `~/git-pulse-sync/pdda/registry-<device>.tsv`, union the `repo` column across devices, resolve
each name to a local path with the recipe shipped in the file header
(`find ~ -type d -name "<repo>" -exec test -d "{}/.git" \; -print`; cache the map), read its
`ROADMAP.md`, and detect "newly created/edited" via mtime / stored `content_hash` vs the last scan
(the pulse runs on a cadence, so polling suffices — no `fswatch` daemon (D) needed). Use the git-pulse
**activity log (B′)** as a supplementary seed to surface active-but-not-yet-PDDA repos as adoption
candidates, and a bounded blind walk (A alone) only as a last-resort fallback. Note the registry
rollout is partial today (only `mbp-16-m1-pro` present), so v1 should degrade gracefully when a
device's registry file is missing.

---

## 4. The frontmatter contract *is* the signal schema

The reason this is high-signal and low-effort: PDDA already defines and enforces the shape we need
to parse. A valid PDDA `ROADMAP.md` gives us, per repo, for free:

- **Identity & freshness** — `title`, `branch`, `created`, `updated` (frontmatter) + file mtime.
- **Lifecycle** — `status` (Active / …) tells us whether this repo is live work.
- **Intent** — `goal:` (one paragraph of why this repo matters right now).
- **The actual signal** — the `## Status` table's **`What's next`** cell: the curated next step.
- **Optional richer rows** — the `### In progress` / `### Queue` ledger bullets, each already a
  one-line pointer with a date and a link to a `PROJECT/**` doc.

**Validity gate = "correct front matter data" (the user's phrase), made precise:** a file counts as
a signal source only if it parses as YAML frontmatter containing at least `title` + `status` and has
a `## Status` table with the exact `What was just completed | What's next` columns. This is the same
contract `pdda.sh frontmatter` + `status-table` enforce — we can mirror that check, or (cleaner)
shell out to `pdda.sh` where it is installed and trust its verdict rather than re-implementing the
parser. Files that fail the gate are skipped (logged), never guessed at. **Note:** because the
primary seed (the PDDA registry) only lists PDDA-installed repos, registry-sourced ROADMAPs almost
always pass — the gate is a cheap confirmation there, and matters mainly for the supplementary
activity-log seed (B′) where PDDA adoption is not guaranteed.

---

## 5. Architecture sketch (rebalance side)

Follow the spine, don't fight it:

1. **`roadmap` collector** registered via `register_collector(...)` in the `COLLECTORS` registry.
   Inputs: a configured list of scan roots (+ optional PDDA-registry seed). Output: one normalized
   row per discovered+valid `ROADMAP.md`.
2. **Own table** (e.g. `roadmap_signals`), single-writer per the collector contract
   (`tests/test_collector_contracts.py` discipline). Suggested columns:
   `repo_path` (or normalized repo name), `title`, `status`, `branch`, `goal`, `whats_next`,
   `whats_completed`, `roadmap_updated`, `file_mtime`, `content_hash`, `scan_date`, `valid` (+ reason
   if not). `content_hash` is what makes "newly *edited*" detectable across scans.
3. **Dashboard projection** — the read side (`querier.py` / dashboard layer) surfaces a "Project next
   steps" panel: active repos ranked by a freshness/recency signal, each showing its one-line
   `What's next`. No display-layer changes to *add* the source (Row 8 of `DASHBOARD.md`: adding a
   source must not touch the display layer beyond the new panel that reads the new table).
4. **MCP exposure** — fold into the existing "what next" surface (`get_next_actions` /
   `publish_pulse`) rather than a new bespoke tool, so it composes with other signals.

**Ranking (first cut, deliberately dumb):** recency of `roadmap_updated`/mtime × `status == Active`.
Resist building a scoring model in Phase 1 — the raw `What's next` list, freshest first, is already
useful. Smarter ranking (cross-referencing GitHub activity, staleness, goal embeddings) is a later
phase and should reuse the existing signal-generation work, not reinvent it.

---

## 6. Open decisions (operator input wanted)

1. **Discovery mechanism** — confirm **registry-seeds-read**: union the per-device PDDA registries
   (`~/git-pulse-sync/pdda/registry-<device>.tsv`) for the candidate set, resolve name→path, read +
   confirm each `ROADMAP.md`, mtime/hash detects new/edited; git-pulse activity log (B′) as a
   supplementary adoption-nudge seed. (Recommended — the registry shipped 2026-06-30 and lists only
   PDDA repos.) Must degrade gracefully while the registry rollout is partial (1 of 3 devices today).
2. **Scan scope** — which roots? (`~/Documents/GH Repos`, `~/Documents/rebalance-OS`,
   `~/Valet-Sites`, `~/Local Sites`, …). A short config list beats walking `$HOME`.
3. **Validity strictness** — mirror the frontmatter check in Python, or shell out to an installed
   `pdda.sh` and trust its verdict? (Leaning: shell out where available, fall back to a minimal
   in-process parse — avoids drift with the PDDA contract.)
4. **Non-PDDA ROADMAPs** — skip silently, or surface as "candidate, needs PDDA frontmatter" (which
   doubles as a nudge to adopt PDDA)? The latter turns the dashboard into a PDDA-adoption signal too.
5. **Cross-device** — single-device (this box) for v1, or design the table for the git-pulse
   multi-device registry from day one (path-normalized repo identity, no absolute folder paths —
   matching the pdda repo's own multi-device approach)?

---

## 7. Risks & failure modes

- **Double-counting.** A repo's `What's next` may restate work already visible via GitHub/Gmail
  signals → dashboard noise. *Mitigation:* keep it a distinct, clearly-labeled panel; let ranking
  dedupe later, don't merge sources in v1.
- **Staleness masquerading as signal.** A `ROADMAP.md` that says "What's next: X" but hasn't been
  touched in weeks is low-value. *Mitigation:* surface `updated`/mtime prominently; `pdda.sh stale`
  semantics can flag it.
- **Schema drift.** If we re-implement frontmatter parsing it will drift from the PDDA contract.
  *Mitigation:* prefer delegating to `pdda.sh` (decision §6.3).
- **Walk cost / portability.** Spotlight-off was the lesson; don't re-introduce an OS-specific
  dependency. Raw walk + a bounded root list keeps it portable and cheap.
- **Privacy/scope creep.** Walking broad filesystem roots could ingest unrelated repos. *Mitigation:*
  explicit allow-list of roots, never `$HOME`-wide.

---

## 8. Relationship to existing work (do not duplicate)

This is a **source**, feeding the *existing* "what next" plane — not a new engine:
- `PROJECT/2-WORKING/SIGNAL-GENERATION/` and `1-INBOX/P1-SIGNAL.md` — the signal-generation
  effort this should plug into; reuse its ranking/plane, add a collector.
- `1-INBOX/GEMINI-WHATS-NEXT-VAULT.md` — closest sibling ("what's next" from the vault). Worth
  reading before building, to share the "what next" projection rather than fork it.
- `WATCHLIST-COVERAGE-GUARD.md` / `list_watched_repos` — the repo-enumeration this can borrow
  (Option C) and should stay consistent with.
- pdda repo's **multi-device PDDA status via git-pulse** item — **now shipped** as
  `~/git-pulse-sync/pdda/registry-<device>.tsv`; this is the primary seed (Option B) and the
  cross-device path (§6.5).

**Before promotion:** read `GEMINI-WHATS-NEXT-VAULT.md` and the SIGNAL-GENERATION doc to confirm the
shared projection point, so we add one collector to one plane, not a parallel one.

---

## 9. Phased plan (rough — firm up at promotion)

- **Phase 0 — Decide & locate the seam.** Lock §6 decisions. Read `GEMINI-WHATS-NEXT-VAULT.md` +
  `SIGNAL-GENERATION/` to find the exact projection point. Open a GitHub issue; capture as
  `GH-<n>-ROADMAP-SIGNAL.md`; park in `ROADMAP.md`; promote to `2-WORKING`.
- **Phase 1 — Collector + table (PDDA-registry seed → read).** `register_collector("roadmap", …)`,
  `roadmap_signals` table; seed candidates by unioning `~/git-pulse-sync/pdda/registry-<device>.tsv`
  across devices, resolve name→path (header recipe), read each `ROADMAP.md`, confirm frontmatter,
  mtime/hash-based "new/edited" detection. Degrade gracefully when a device registry is absent.
  Collector-contract tests (single-writer; no display-layer import).
- **Phase 2 — Dashboard panel.** "Project next steps" panel reading the new table; fold into
  `get_next_actions`/`publish_pulse`. Dumb recency×Active ranking.
- **Phase 3 — Full cross-device + adoption nudges.** Aggregate ROADMAP signals across *all* device
  registries once the rollout completes (all 3 devices present); fold in the git-pulse activity log
  (B′) to surface active-but-not-PDDA repos as adoption candidates; path-normalized repo identity.
- **Phase 4 (optional) — Smarter ranking.** Cross-reference GitHub activity/staleness/goal
  embeddings, reusing the existing signal-generation ranking rather than a new model.

Each phase: `rebalance doctor` + `pytest tests/` green, and `utils/pdda/pdda.sh run` clean for the
doc work, before reporting done.
