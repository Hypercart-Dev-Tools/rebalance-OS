---
title: "HiQS — clean-room rebuild of the rebalance-OS signal pipeline"
codename: HiQS
owner: Noel
gh_issue: TBA
source: "TBA"
status: "Active (2-WORKING) — plan rev 5, promoted 2026-08-03. No code written; Phase 0 (skeleton) is next."
created: 2026-08-03
updated: 2026-08-03
doc_type: project
branch: development
goal: >
  Rebuild the rebalance-OS work-signal pipeline from scratch as HiQS: plugin-native sources
  ingesting into one local SQLite, one hybrid (FTS5 + vector) search behind one seam, exactly
  one attested ranking read by every surface (MCP, CLI, one web page), and observability from
  the first commit. Target is a <= 3,000 LOC core with 4 top-level dependencies, living in this
  repo at HiQS/ and running alongside the incumbent until it covers the daily use.
non_goals: >
  No migration from the existing rebalance-OS database — HiQS starts on a fresh DB and the old
  system keeps running untouched. No local synthesis layer, no LLM in the ranking path, no write
  operations of any kind in v1 (read-only everywhere). No rename or refactor of existing
  rebalance-OS packages, modules, tables, or CLI. Not a fork of the incumbent's code: HiQS/
  imports nothing from it (clean room by construction).
related:
  - PROJECT/2-WORKING/GH-125-HIQS-PIPELINE.md
  - PROJECT/2-WORKING/GH-198-LOCAL-QWEN-EMBEDDING-PROOF.md
  - PROJECT/2-WORKING/REPO-HEALTH-AXES.md
context_tags: [hiqs, rebuild, search, embeddings, plugins, observability, clean-room]
effort: 5
complexity: 4
risk: 3
phases: 7
spin_out_target: "https://github.com/HiQS-Suite/HiQS"
---

# HiQS — Clean-Room Project Plan

> High Quality Signals. A ground-up rebuild of the rebalance-OS pipeline.
> This document is standalone and supersedes all prior planning for the rebuild.
> Plan rev 5. Versioning starts at 0.1.0.

## Status

| What was just completed | What's next |
|---|---|
| Plan rev 5 authored and promoted to `2-WORKING` 2026-08-03, with the rev-4 eval gate rewritten to be falsifiable (n raised to 60–75, paired disagreement set made the primary artifact, ground-truth protocol written, query set frozen, FTS-only baseline promoted to a decision, split-decision rule, cost axis, floor + truncation gates). Codebase location settled: HiQS ships **inside this repo at `HiQS/`**, not as a separate repository, so the plan doc and the code it governs live under one `git log`. PDDA compliance sections added (frontmatter, this table, table of contents, per-phase QA gates, §16 boundary note). The standalone anti-patterns ledger was **verified against `CHANGELOG.md` and folded in** — six-cluster failure-mode taxonomy at the head of the Lessons section, seven incidents L1–L15 missed added as **L16–L22**, and two new plugin rules (§5.7 explicit network timeout, §5.8 watermark advances only on a completed fetch); source archived to `PROJECT/4-MISC/HiQS-ANTI-PATTERNS.md`. **The four tenets were then audited against the plan itself and two failed**: ATTESTED had no `author` field and RANKED had no obligation model and no detector — so `author`/`owed_by`/`due` landed on `Doc`/`Candidate`, `activity_at` split from `updated_at` (L20), `source_age_s`/`source_status` landed on `RankedAction`, §7.1 added a frozen ranking-judgment set with three gates, §2's non-negotiable was widened from *retrieval*-quality to all quality claims, and **§18 records the dogfooding audit in both directions**. An **agy relay review (r1, Changes requested)** then found 3 Blockers + 2 Shoulds, all accepted and applied: `Doc` was missing `source` (a pre-rev-5 mismatch with §9); §7.1's obligation gate was self-justifying — its failure could be discharged by rewording the tenet, so it now **blocks**, with restatement demoted to a consequence of an explicit override; and **"never auto-delete" was silently corrupting the corpus** — chunk-by-heading plus no pruning means a renamed heading orphans its old `docs`/`docs_vec` rows forever, so rule 2 is now within-unit reconciliation, never across units and never on a failed fetch. Three unfalsifiable gate items got numbers. Cross-model review (Qwen) added the coverage boundary: the four tenets cover **neither** cluster D (resource) **nor** E (scope accretion), so **§18.3** names four counterpart invariants (PORTABLE/BOUNDED/LOUD/SMALL) and **L23** records the incumbent reintroducing an already-fixed defect because the lesson was prose. **r2 found 1 Blocker + 3 Shoulds + 1 Nit, all applied**: r1's own gate fix had propagated to §7.1 but not to the Phase 3 checklist (the exact drift class this plan warns about); §7.1's gates were all relative, so an absolute **floor of 3/5 top-5 overlap** was added; `docs_vec` reads must filter `WHERE model = <active>` or mixed 384/1024-dim vectors crash the cosine; **`hiqs auth <source>` added as a 6th subcommand** (~40 LOC, recorded not absorbed) because an unattended launchd job cannot complete a browser OAuth flow; and a **2-chunk-per-document cap** after RRF stops one long note flooding the top-10. Relay closed at r2 (`VERDICT: PARKED` — all findings fixed; the reviewer never issued `Approved`, so none is claimed). **Then the operator confirmed the spin-out**: `HiQS/` is a **staging home**, extracted to [`HiQS-Suite/HiQS`](https://github.com/HiQS-Suite/HiQS) (public, empty, created 2026-08-03) once stable, with rebalance-OS archived within weeks — added as **§19 + a real Phase 6**, which surfaced the **public-repo disclosure gate**: the frozen eval sets are built from a private vault and explicitly include client names, and were specced to be committed into what becomes a public repo. **No code written.** | **Operator checkpoint A — author `eval_queries.json` yourself.** Phases 0 and 1 are **built and green** (107 passed, 1 xfailed; 1,499 LOC core). M2 shipped the eval *runner*; it cannot produce the answer key, and an agent-authored one invalidates Decision 8 by construction. Write it from memory per §6.3, grep only to resolve, drop what you cannot locate, freeze it and record the SHA. Then score MiniLM vs Qwen3 and read the disagreement set query by query. **The vector-leg gate can delete torch from the plan** and reshape M4/M5, so do not fire M3 first. Still open: the GitHub issue belongs on [`HiQS-Suite/HiQS`](https://github.com/HiQS-Suite/HiQS), not here (§19.3). |

## Table of contents

| Phase | Section | Ships | QA gate |
|---|---|---|---|
| — | [§1–§11 Plan](#1-mission) | Mission, decisions, architecture, plugin spec, search, seams, observability, schema, surfaces, budget | n/a (context, not a phase) |
| **0** | [Phase 0 — Skeleton](#phase-0--skeleton) | repo subtree, `db.py`, `config.py`, `plugins.py`, `events.py`, empty CLI | [QA gate — Phase 0](#qa-gate--phase-0) |
| **1** | [Phase 1 — Vault, hybrid search, and the measurement that closes Decision 8](#phase-1--vault-hybrid-search-and-the-measurement-that-closes-decision-8) | `vault.py`, `docs_index.py`, `search.py`, frozen eval set | [QA gate — Phase 1](#qa-gate--phase-1) *(spike phase — findings written back to §17)* |
| **2** | [Phase 2 — GitHub](#phase-2--github) | `github.py` + candidates provider | [QA gate — Phase 2](#qa-gate--phase-2) |
| **3** | [Phase 3 — Calendar, ask, MCP](#phase-3--calendar-ask-mcp) | `calendar.py`, `ask.py`, MCP server, `Ranker` | [QA gate — Phase 3](#qa-gate--phase-3) |
| **4** | [Phase 4 — Surfaces and ops](#phase-4--surfaces-and-ops) | `web.py`, one launchd job, keyring hardening | [QA gate — Phase 4](#qa-gate--phase-4) |
| **5** | [Phase 5 — On demand only](#phase-5--on-demand-only) | extra plugins, LLM seams, sentinel, writes | [QA gate — Phase 5](#qa-gate--phase-5) |
| **6** | [Phase 6 — Extraction](#phase-6--extraction-to-hiqs-suitehiqs) | spin-out to `HiQS-Suite/HiQS`; plan doc travels; incumbent archived | [QA gate — Phase 6](#qa-gate--phase-6) |
| — | [Standing hygiene](#standing-hygiene) | cross-phase invariants | continuous |
| — | [§7.1 Ranking quality](#71-ranking-quality--the-second-detector) | the frozen judgment set + 3 gates behind the RANKED tenet | checked in the Phase 3 gate |
| — | [§16 PDDA compliance](#16-pdda-compliance-and-the-governance-boundary) | how this doc and `HiQS/` relate to repo governance | n/a |
| — | [§17 Phase findings (memory injection)](#17-phase-findings-memory-injection) | durable spike/discovery findings | filled per phase |
| — | [§18 Tenets & self/meta compliance](#18-hiqs-tenets--selfmeta-compliance--dogfooding) | the four tenets audited against both product and process, **plus the four failure classes they cannot see** ([§18.3](#183-the-four-tenets-are-not-the-whole-safety-surface)) | re-run at §13 cutover |
| — | [§19 Extraction & the archive](#19-extraction-to-hiqs-suitehiqs-and-the-rebalance-os-archive) | `HiQS/` is a staging home; spin-out to `HiQS-Suite/HiQS`, the **public-repo disclosure gate**, where governance goes when this repo is archived | Phase 6 |

**Why "HiQS":** in rebalance-OS, HiQS was the name of the unified work-signal
pipeline — one bundle across all sources, one ranked verdict, every action
attested with source/evidence/why (GH-125). It was the one subsystem where the
architecture got *right*. The rebuild takes the name because it takes that
invariant as the foundation: **one combined signal, attested, read by every surface.**

**What changed in rev 4** (full rationale in §15):

- Embedding **mechanism** locked to `sentence-transformers` with the torch
  backend; `backend="onnx"` recorded as the documented upgrade rung. Hand-rolled
  ONNX is explicitly rejected — it re-creates the L8 failure surface.
- Embedding **model tier** unlocked and made measurable. MiniLM ships as the
  default; Qwen3-Embedding-0.6B is a named challenger; the Phase 1 retrieval
  eval decides, not an estimate.
- `docs_vec` primary key made composite `(doc_id, model)` so two models can be
  scored head-to-head without migration machinery.
- Retrieval **quality** added to `status` alongside retrieval **mode** — L4's
  count-vs-meaning lesson applied one layer up.
- `Reranker` added to the reserved seam list.
- §14 deletion-ledger contradiction fixed (torch was listed as deleted while
  §§2/3/6/11 shipped it).

**What changed in rev 5** — rev 4's eval gate was specific enough to look
rigorous and loose enough to let a bad decision through. Fixed:

- **Sample size raised to 60–75.** At n=30 with binary relevance, rev 4's
  "≥5 points recall@10" threshold was 1.5 queries — a precise-looking rule its
  own eval set could not resolve.
- **The paired disagreement set is now the primary artifact**, thresholds
  secondary. At this scale, ten queries you can read beat a percentage point
  that can't clear noise.
- **Ground-truth construction protocol written** (§6.3). Building the answer key
  by running searches bakes the incumbent's bias into it and lets a model win
  by construction.
- **Query set frozen before scoring** — committed, SHA recorded in the
  `eval.completed` event. Queries added after seeing scores turn an eval into a
  justification.
- **FTS-only baseline promoted from a number to a decision.** If hybrid doesn't
  beat lexical-only by a stated margin, the vector leg has not earned torch.
- **Split-decision rule replaces rev 4's OR**, which shipped the challenger on a
  recall win even against an MRR loss.
- **Cost axis added:** embed time, index size, and peak RSS recorded per model.
- **Absolute floor gate added:** below recall@10 0.60, the problem is chunking or
  the query set, not the model, and Phase 1 does not exit.
- **Chunk-truncation precondition added:** `all-MiniLM-L6-v2` truncates at 256
  word-pieces, which silently decapitates long chunk-by-heading bodies.

---

## 1. Mission

Your work lives in N places that never talk to each other. HiQS ingests them
into one local SQLite, then lets any MCP host (Claude, ChatGPT, Cursor…) and
one local web page answer questions about your own work and tell you what to
do next — without sending private data to a cloud service.

That is the entire product. Everything in this plan serves it; everything
that doesn't is deleted in §14 with a written re-add trigger.

## 2. Non-negotiables → the mechanism that carries each

| Non-negotiable | Mechanism | Where |
|---|---|---|
| Least code possible | ≤ 3,000 LOC core, 4 top-level deps, stdlib everything else, one implementation per seam | §11 budget |
| Observability from the start | append-only `events` table + `log_event()` + `status()`; every sync, error, and eval run lands as a structured, queryable row | §8 |
| AI-native architecture | MCP-first surface; all payloads structured + attested; `Synthesizer`/`Ranker`/`Reranker`/`Sentinel` seams; the events table is the read surface for any future observer LLM (4B/12B sentinel plugs in as registration, not surgery) | §7 |
| Plugin/extension-native | built-in sources **are** plugins; entry-point discovery; written contract; pinned by a contract test | §5 |
| Flexible + semantic search | hybrid FTS5 (keyword) + `sentence-transformers` vectors (semantic), RRF-fused behind one `search()` | §6 |
| No unmeasured quality claims | every quality assertion — **retrieval and ranking alike** — traces to a run of a frozen eval set, recorded in `events`; thresholds are sized to be resolvable at the n that will evaluate them | §6.3, §7.1, §12 |
| The four tenets are claims, so they are measured | ATTESTED, RANKED, FRESH, STRUCTURED each map to a field, a gate, and a detector — never to prose. A tenet the product cannot meet is a bug or a false claim, never a slogan left standing | §18 |

## 3. Decisions

Decisions are split by whether they rest on judgment (locked) or on a number
we can obtain (measured). A locked decision changes only with a written
rationale in the CHANGELOG. A measured decision changes when the number changes.

### 3.1 Locked

1. **Embedding mechanism: `sentence-transformers`, torch backend, official
   model repos.** The library owns tokenization, mean-pooling,
   attention-mask weighting, and L2 normalization. Hand-rolled
   `onnxruntime` + `tokenizers` assembly is **rejected**: wrong pooling or a
   missing unit-norm yields fast, valid-looking, quietly degraded vectors and
   nothing throws — a fresh copy of L8 (0.32.0, embeddings extra absent,
   vector search silently inert for weeks). Saving ~150 MB of disk and ~2 s per
   refresh does not buy that risk.

   Documented upgrade rung, same seam, one kwarg, library keeps the math:

   ```python
   # v1 default
   model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
   # later, if torch install weight or cold start becomes a felt pain:
   model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", backend="onnx")
   ```

   `# ponytail: assumes ≤10k docs and delta-only embedding (~500 docs/refresh,`
   `# ~2–5 s torch CPU). Revisit if corpus >100k or embed time shows up in`
   `# SyncReport.meta timings.`

   Honest cost, stated: torch is ~200 MB of wheels and the 4 top-level deps
   expand to roughly ten installed packages. The plan accepts this; §14 names
   the exit.

2. **No local synthesis layer.** `ask()` returns structured attested context;
   the host agent synthesizes. A local 4B/12B plugs in later through the
   `Synthesizer` seam if ever wanted — nothing in core changes.

3. **v1 sources:** Obsidian vault, GitHub, Google Calendar — shipped as the
   first three plugins.

4. **Surfaces:** MCP (4 tools) + CLI (4 core subcommands + `serve` + `auth`) +
   one baseline web page showing the next-actions ranking.

   `auth` was added 2026-08-03 in review, and the reason is a real operational
   hole rather than a nice-to-have: Calendar uses OAuth, tokens expire, and the
   only runner is an unattended 2-hourly launchd job that **cannot open a
   browser**. Without an interactive re-authorization path the specced failure
   mode is a source that goes `error` with no operator action available except
   reading the plan and improvising one. `hiqs auth <source>` is that path —
   interactive, operator-invoked, writes to keyring. Honest budget note, per the
   SMALL invariant (§18.3): this is a **6th subcommand and ~40 LOC** the plan did
   not have, recorded here rather than absorbed quietly.

5. **Ranking:** deterministic, attested, ~40 LOC. No LLM in the ranking path.
   An LLM ranker is just another `Ranker` behind the same signature later.

6. **Read-only everywhere in v1.** No calendar writes, no reminder completion,
   no vault write-back. Write ops re-enter one at a time through the plugin
   `write()` seam (§14 triggers).

7. **Fresh DB, no migration.** Old rebalance-OS runs untouched alongside
   until HiQS covers the daily use. Clean room by construction.

   One correction now that the incumbent's archive is planned (§19.4):
   **archiving the repo does not uninstall the software.** The local install
   keeps running, its jobs keep firing, its DB keeps filling. What ends is the
   ability to *fix* it — so the fallback becomes unmaintained, not absent.

### 3.2 Measured — decided by the Phase 1 eval, not by estimate

8. **Embedding model tier.** Default is `all-MiniLM-L6-v2` (~90 MB, 384-dim).
   Named challenger is `Qwen3-Embedding-0.6B` (1024-dim, Matryoshka-truncatable).
   Both load through the identical `SentenceTransformer(...).encode()` call, so
   this is a one-string change, not an architecture change.

   Why this is not settled by assertion: MiniLM-class models hold up well on
   short symmetric similarity and degrade most on **asymmetric** retrieval —
   short query against a long note — plus private jargon (`git-pulse`,
   `Luggage`, `Cross Country`, client names) and *ranking order* rather than
   top-50 membership. "What did I decide about X" is the asymmetric case, and
   §13 makes it the definition of done. Aggregate model-comparison numbers fold
   in classification and STS tasks that HiQS never performs, so they are the
   wrong prior for this corpus.

   Selection rule, written and frozen in advance so the result can't be
   rationalized (rev 5 — supersedes rev 4's OR-rule, see §15):

   - **Precondition.** The §6.3 floor and truncation gates pass, and
     `eval_queries.json` is committed and frozen.
   - **Primary signal: the paired disagreement set.** Both models run the same
     frozen queries. Every query where the two disagree on the top hit is listed
     and read by the operator. At n≈70 this is typically 8–15 queries, and
     reading them is more informative than any single aggregate.
   - **Primary metric: recall@10.** Incumbent (MiniLM) ships unless Qwen3 leads
     by ≥8 points — roughly 6 queries at n=70, outside plausible noise.
   - **Tiebreak: MRR@10**, used only when recall@10 falls inside the ±8-point
     band. Qwen3 takes a tiebreak win at ≥0.05 MRR@10.
   - **Split decisions go to the incumbent.** If one metric favours Qwen3 and the
     other favours MiniLM, MiniLM ships and the disagreement set is recorded as
     the reason. A split is evidence of no clear win, not licence to pick.
   - **Ties go to the incumbent.** MiniLM is cheaper on every cost axis; parity
     is not a reason to pay more.
   - **Cost is recorded, not traded away silently.** `embed_ms` for a full
     re-embed, index size in MB, and peak RSS are captured per model in the same
     event. A quality win that costs >4× embed time is escalated to the operator
     as an explicit call rather than resolved by the rule.
   - The winner, the loser's scores, the disagreement set, the cost figures, the
     query-set SHA, and the date are recorded in `SPEC.md` and the CHANGELOG.
     Decision 8 then reads "measured," not "estimated."
   - Whichever model loses moves to §14 with a regression trigger.

   Deletion this earns either way: MLX, the Apple-Silicon lock, the GH-172
   memory guard, single-instance locks, and platform-gated extras are gone.
   Cross-platform semantic search is a property of `sentence-transformers`,
   not of the model tier — the two were never a package deal.

## 4. Architecture

```
plugins (vault, github, calendar — future: email, slack, figma, yours)
   │  fetch → normalize → upsert (each plugin owns its raw tables)
   ▼
SQLite: raw tables ──▶ docs + FTS5 + vec BLOBs    ◀── one projection stage
                       events (append-only telemetry)
   │
   ├── search(q)    FTS5 + cosine, RRF-fused  [+ optional Reranker]
   ├── ask(q)       attested context bundle + one ranked verdict [+ optional Synthesizer]
   ▼
Surfaces: MCP (4 tools) · CLI · one web page (next-actions + health)
```

The two-hub model from rebalance-OS is kept because it prevented a god-object:

- **Orchestration spine (fan-out):** `refresh()` walks the plugin registry. The one write entry point.
- **Persistence base (fan-in):** one thin `db_connection()` factory. Zero logic. Read freely, change rarely.

The AI-native bet in one line: **HiQS emits machine-readable, attested
telemetry; any LLM — host agent today, a local sentinel later — consumes the
same structured feed.** Nothing talks to an LLM except through a declared seam.

## 5. Plugin spec (the clean contract)

A plugin is one module exposing one object. Built-in sources register exactly
the way third-party plugins will — core has no privileged sources.

```python
# hiqs/plugins.py — the ENTIRE plugin surface
@dataclass(frozen=True)
class Source:
    name: str            # unique, [a-z0-9_]+
    fetch: Callable[[Conn, Config], SyncReport]                              # idempotent
    docs: Callable[[Conn], Iterable[Doc]] | None = None                      # → search index
    candidates: Callable[[Conn, Config], Iterable[Candidate]] | None = None  # → next-actions

@dataclass(frozen=True)
class SyncReport:   # structured by contract → feeds events table automatically
    counts: dict[str, int]                    # inserted / updated / unchanged / skipped / rejected
    errors: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)  # e.g. api_calls, window, peak_rss_mb, embed_ms
    units_ok: tuple[str, ...] = ()            # units THIS run genuinely fetched — the prune warrant

@dataclass(frozen=True)
class Doc:        # one search-index row
    source: str; id: str; title: str; body: str
    url: str = ""; ts: str = ""; project: str = ""; author: str = ""
    unit: str = ""        # which unit this chunk belongs to; "" = the doc IS its own unit

@dataclass(frozen=True)
class Candidate:  # one next-action candidate — attested, never bare
    title: str; source: str; evidence: str; why: str; ts: str
    url: str = ""; author: str = ""
    owed_by: str = ""     # who the work sits with, if the source knows ("" = unknown)
    due: str = ""         # ISO-8601 date the source states, if any ("" = none)
```

**`author` is a field, not prose (added 2026-08-03).** The ATTESTED tenet names
four receipts — source, author, time, link — and three of them were structural
here while the fourth was only expressible inside the free-text `evidence`
string. A receipt that lives in prose cannot be queried, validated, or asserted
non-empty; that is L4's count-vs-meaning failure arriving in the attestation
layer. `author` is `""` when the source genuinely doesn't know (a vault note is
yours), never a guess, and never a value invented to fill the column.

**`owed_by` and `due` are the minimum obligation fields**, and they exist for a
reason worth stating: the RANKED tenet claims signals are ordered by *what your
team owes*, and a schema with no representation of obligation cannot order by it
— it can only order by recency wearing obligation's name. Both default to `""`
and both are honest about ignorance: a source that cannot supply them leaves
them empty, and `status` reports the coverage rather than the ranker imputing a
value. See [§7.1](#71-ranking-quality--the-second-detector).

Adding these at Phase 0 is deliberate. Decision 7 ships no migration machinery
(and L17 is what migration numbering does when it goes wrong), so a column added
after Phase 2 costs a re-ingest or the exact machinery §11 budgeted away. This is
the same move `docs_vec`'s composite `(doc_id, model)` PK makes in §9 — pay a
schema decision early so a later question needs no migration step.

Discovery via `pyproject` entry points (stdlib `importlib.metadata`, ~10 lines):

```toml
[project.entry-points."hiqs.sources"]
vault = "hiqs.sources.vault:SOURCE"
```

**The rules (all of them):**

1. A plugin writes only its own raw tables, created in its own `fetch`
   (`CREATE TABLE IF NOT EXISTS`). Only the core projection writes `docs`;
   only core writes `events`. (One writer per table — rebalance-OS's single
   most important invariant, kept.)
2. `fetch` is idempotent and incremental. Three sanctioned patterns:
   hash/ID delta (vault, artifacts), window refetch + upsert (GitHub activity,
   calendar), full refetch + column-diff (reminder-style sources).
   Never auto-delete **across** units; **reconcile within** one.

   The unqualified "never auto-delete" was a real bug, not a style choice
   (found in review 2026-08-03). Vault notes chunk by heading (§6.1), so
   renaming, splitting, or deleting a heading emits a *new* chunk id and leaves
   the old `docs` and `docs_vec` rows in place forever. Those orphans keep
   matching FTS5 and cosine queries and keep surfacing in rankings — retrieval
   quality corrupting slowly, from content that no longer exists, with every
   gate green. Phase 1's eval would not catch it: a frozen query set scored
   against a fresh index has no orphans yet. That is cluster A in its purest
   form — a *successful* sync that quietly degrades the corpus.

   The rule that replaces it, precisely:

   - **Within a unit that was fetched successfully** — one vault file, one
     GitHub item, one calendar event — the projection reconciles: rows keyed to
     that unit which are absent from the freshly-derived set are deleted, in the
     same transaction that writes the new ones. Chunk ids are still scoped
     (`<source>:<unit>:<heading-hash>`) for legibility, but **`Doc.unit` is what
     the projection reads** — membership is a field, never parsed back out of an
     id. Splitting an id on `:` looked equivalent and is not: a vault path may
     itself contain a colon, and every source picks its own id grammar, so the
     parse silently returns the wrong unit and reconciliation then prunes the
     wrong rows. `unit` is `""` only when the doc genuinely *is* its own unit.
   - **The prune warrant is `SyncReport.units_ok`** (added 2026-08-03, after the
     build stalled on its absence). `fetch` returns the units it genuinely
     fetched this run; the projection reconciles **only** those and leaves every
     other unit untouched. This is the field that makes the rest of rule 2
     implementable, and without it the rule is not merely hard but impossible:
     `docs` is a separate later call taking only a connection, so it cannot know
     what `fetch` attempted, and "no chunks emitted" is identically the shape of
     *fetched fine, now empty* and *could not be read*. Attestation is the only
     thing that separates them.

     Two consequences that are not optional:

     - **A source that attests nothing prunes nothing.** `units_ok` defaults to
       `()`, so an un-migrated or third-party source degrades to insert/update
       and keeps its stale rows. The alternative default — absence of an
       attestation authorising deletion — is the GH-169 RC5 scar re-armed and
       pointed at every source at once. Stale is recoverable; deleted is not.
     - **Attestation is per-run and in-process.** The report goes straight from
       `fetch` into the projection in the same walk. It is never persisted and
       re-read, because a stored attestation outlives the run that earned it and
       becomes a licence to delete on the strength of an earlier success. This
       is why raw tracking tables (`vault_files`) cannot serve: they are
       cumulative state with no run identity.
   - **Never across units, and never on a failed or partial fetch.** A unit that
     errored is not reconciled at all — it keeps its existing rows. This is the
     other half of L15 and it is the half that matters: a source returning
     nothing transiently must never be able to empty the corpus. The incumbent
     has the scar (`sync_direct_commit_documents()` destroys-then-rebuilds, so a
     partial failure shortens the corpus while every upstream measure still
     reads healthy — GH-169 RC5).
   - **A deletion is a successful fetch, not a missing one.** A unit whose source
     proves it is gone — a vault path absent from a walk that itself completed
     without error — belongs in `units_ok`, emits zero docs, and therefore
     reconciles to zero. That is how deleting a note removes it from search.
     `fetch` must resolve the vanished unit at the raw layer too; leaving a
     tracked-but-absent row for `docs` to trip over takes down the whole source
     and freezes every other unit's rows as collateral. The distinction rides
     entirely on the walk's own success: absence proven by a clean enumeration
     is a deletion, absence during an errored one is unknown, and unknown never
     prunes.
   - `SyncReport.counts` carries `pruned` alongside inserted/updated/unchanged/
     rejected, so reconciliation is visible rather than inferred. A run that
     prunes an implausible share of a source is a `warn` event, not a silent
     success (cluster A again — the failure mode of a delete path is deleting
     too much, quietly).
3. Secrets go through `config.secret(name)`: keyring → `0600` file outside the
   repo → env. Plugins never hardcode paths or tokens.
4. No scheduling, threads, or network listeners inside plugins. One refresh
   walk and one web server are the only runners.
5. A plugin that raises does not abort the run — its error lands in `events`
   and `SyncReport.errors`; the walk continues.
6. Adding a source touches zero core files: one module + one entry-point line.
   Pinned by a contract test: a fake plugin reaches `docs`, `status`, and the
   ranking with no core edit.
7. **Every network call carries an explicit timeout.** No `urlopen` without one.
   A stalled request must fail its own source, not hold the SQLite writer while
   every other job piles up behind it (Lesson L18). The 30 s `busy_timeout` in
   §9 is the second half of the same fix, not a substitute for the first.
8. **A watermark advances only after the fetch it describes completed.** A
   cursor, `last-run`, or high-water mark moved on a failed or partial scan
   makes the skipped window permanently invisible to every later run — the
   failure repairs itself out of existence (Lesson L19). On error the watermark
   stays put and the error lands in `events`; the next run re-covers the window,
   which the upsert-only rule (2) makes free.

**Reserved future seam (zero code now):** `RepairProvider` — reads `events`,
proposes actions from a bounded named menu, destructive actions require
operator confirmation. This is the sentinel hook; see §7 and Lesson L10.

## 6. Search — hybrid, behind one seam

### 6.1 The path

```python
search(query, limit=10):
    fts  = FTS5 BM25, top 50                       # stdlib, exact/keyword leg
    vec  = numpy cosine over doc vectors, top 50   # WHERE model = <active>  ← see below
    hits = RRF-fuse(fts, vec, k=60)                # ~15 lines
    hits = cap_per_document(hits, max_chunks=2)    # diversity, before the slice
    return (RERANKER or identity)(query, hits)[:limit]
```

Two details in that path are load-bearing, both found in review 2026-08-03:

- **The vector leg MUST filter `WHERE model = <active>`.** `docs_vec`'s composite
  PK exists so a 384-dim and a 1024-dim model can coexist (§9) — which means an
  unfiltered `SELECT` loads BLOBs of two different widths into one array and the
  cosine dot-product raises on shape mismatch. The feature that makes the Phase 1
  comparison free is the same feature that breaks a naive read, so the filter is
  part of the contract, not an optimization.
- **Cap chunks per source document before slicing to `limit`.** Chunking by
  heading means one long note can match on five headings and occupy the entire
  top-10 in *both* legs, so RRF fuses two lists that agree on the same document
  and starves every other note. `max_chunks=2` per `rel_path`, applied after the
  fuse and before the slice. This is measurable rather than assumed: it should
  raise recall of *distinct* documents on the §6.3 eval, and if it doesn't, the
  cap is wrong and the number moves with a recorded measurement.

- Vectors stored as BLOBs in `docs_vec(doc_id, model, dim, vec)`, primary key
  `(doc_id, model)` — see §9. Brute-force numpy cosine.
  `# ponytail: ~10k docs ≈ 15 MB, <10 ms; revisit with ANN only past ~100k docs.`
- Embedding is delta-only (hash-keyed) during `refresh`; the model name is part
  of the key, so swapping models re-embeds lazily and **both models' vectors can
  coexist** — that is what makes the §6.3 comparison free of migration machinery.
- Chunking: vault notes chunk by heading, with chunk ids scoped to their file
  (`vault:<rel_path>:<heading-hash>`) so plugin rule 2's within-unit
  reconciliation can find every chunk a file currently owns. A renamed or
  deleted heading's row is pruned in the same transaction that writes the new
  one; a file whose read failed is not reconciled at all.
  `# ponytail: a single heading with a very long body produces one oversized`
  `# chunk; add a character cap if the eval shows long-note recall lagging.`

### 6.2 Degrade rungs — visible, never silent

| Rung | When | How it's known |
|---|---|---|
| Hybrid (default) | normal | `status.search.mode == "hybrid"` |
| FTS5-only | config flag, or embedding model unavailable | `status.search.mode == "fts_only"`, plus a `search.degraded` event row |
| `unknown` | probe unreadable | `status.search.mode == "unknown"` — never rendered as healthy |

This is Lesson L8's structural fix. There are no hidden fallback chains: a
degraded mode is a state you can query, not something you discover weeks later.

### 6.3 Retrieval eval — the quality detector

L4's lesson was that freshness checked row *counts*, not row *meaning*, and a
source starved for three weeks behind a green light. Reporting search *mode*
without search *quality* is that same mistake one layer up: a mediocre model
returns plausible rankings, reports `hybrid`, and renders green forever.

The eval set is the detector. It only works if it is built in an order that
can't flatter the incumbent, so the protocol is part of the spec.

**Composition — `tests/eval_queries.json`**

- 60–75 queries drawn from the real vault, each with one or more known-good
  `doc_id`s. Rev 4 said 30; at that size an 8-point recall difference is ~2.5
  queries and no threshold is resolvable.
- ≥50% asymmetric (short question → long note) — that is the §13
  done-criterion and the shape where model tiers actually diverge.
- ≥10 private-jargon queries (`git-pulse`, `Luggage`, `Cross Country`, client
  and project names) — the case where lexical usually beats semantic.
- ≥10 exact-phrase queries so the FTS leg is genuinely exercised.
- A handful of known-hard queries where you expect *both* legs to struggle. An
  eval where everything passes measures nothing.

**Amended 2026-08-03 — the operator does not author an answer key.** The protocol
below originally required resolving every query to known-good `doc_id`s up front.
The operator's objection killed it, and it is correct: *"If I knew the answers I
wouldn't be building the system."* Requiring a pre-authored answer key is only
tractable for questions you can already answer, which selects precisely the
queries that do not need the system — a biased set, expensively produced.

The deeper error was metric choice, not effort. Checkpoint A decides **which of
two models is better**, a *relative* question, yet the gate was written on
`recall@10`, an *absolute* metric that cannot be computed without ground truth.
§6.3 already named the **paired disagreement set** as the primary signal, and
that needs no answer key at all. The gate now rests on it.

**What the operator actually does — recognition, not recall**

1. Write the queries. **No answers.** Real questions, in the words you would
   really use, before touching the index. Seed set captured from the operator
   2026-08-03 and kept as literal fixtures, because they are evidence of real
   query shape (see §6.4):
   - *"What did I work on yesterday from 9 AM to 11 AM?"*
   - *"What did we decide on with XYZ to phase out the Bash scripts on which GH
     issue?"*
   - *"What tasks did I work on the Binoid repo project?"*
2. Both models run every query. The runner emits the disagreement set.
3. For each disagreeing query the operator sees **both result sets, unlabelled**,
   and picks better / worse / tie. Blind, so brand preference cannot leak in.
4. **The winner is decided on pairwise preference**, not recall. Judging asks only
   that you *recognise* a better answer when two are side by side — a categorically
   easier task than *recalling* one from memory, and the only one honestly
   available here.
5. **Ground truth accumulates as a by-product.** Whenever a result set contains
   something the operator recognises as genuinely right, that `doc_id` is recorded.
   Over a few rounds this grows into a real answer key that was *earned* rather
   than pre-declared — and from that point `recall@10` becomes computable and can
   return as a tracked metric. It is not a precondition for the Checkpoint A
   decision.

**What this costs, stated honestly.** No absolute recall figure at Checkpoint A.
Nothing in the model decision depends on one: every rule in §6.3's decision
procedure is a comparison between two models. Any claim needing an absolute number
reports `unknown` until the accumulated key supports it — which is the §8 rule
applied to this document's own gate.

**Anti-flattery rules that still bind.** These were the point of the original
protocol and survive unchanged:
- Queries are written **before** seeing any output, and frozen.
- A query is never edited after its scores are visible. Additions start a new
  frozen version and require re-running every model.
- Judging is **blind to which model produced which set**.
- A `doc_id` recorded in step 5 is recorded because the operator recognised it as
  correct, never because it ranked first.

Then, as before:

4. Commit and **freeze** the file. Its SHA is recorded in every
   `eval.completed` event. Queries added after scores are visible turn an eval
   into a justification, so additions start a new frozen version and require
   re-running every model.
5. **Split public from private from the start** (§19.2). The committed file
   carries opaque ids, `doc_id`s, and shape tags; the natural-language query
   text and note titles live in a gitignored local sidecar. This set is drawn
   from a private vault and explicitly includes client and project names, and
   `HiQS/` is extracted to a **public** repo at Phase 6 — retrofitting the split
   after that push does not un-publish anything. Freezing still covers both
   files; the recorded SHA spans them.

**Runner — `tests/eval_retrieval.py`**

- Offline, no network, fixture DB. Reports **recall@10** and **MRR@10** per leg
  (FTS-only, vector-only, fused) per model.
- Emits the **paired disagreement set**: every query where two models return a
  different top hit, with both hits named. This is the artifact a human reads.
- Captures cost per model: `embed_ms` for a full re-embed, index MB, peak RSS.
- Writes an `eval.completed` event with `{model, recall_at_10, mrr_at_10,
  n_queries, queryset_sha, embed_ms, index_mb, peak_rss_mb, git_sha}`.

**Gates that fire regardless of which model wins**

| Gate | Rule | If it fails |
|---|---|---|
| Floor | winner's fused recall@10 ≥ 0.60 | Phase 1 does not exit. Below this the fault is chunking or the query set; swapping models is treating a symptom |
| Vector-leg justification | fused recall@10 beats FTS-only by ≥10 points | the vector leg has not earned torch, 200 MB, and the embedding path — it moves to §14 and v1 ships FTS-only |
| Truncation | ≥95% of chunks fit the shipped model's context (256 word-pieces for MiniLM) | add a chunk cap to `vault.py` and re-run before scoring anything |

The vector-leg gate is the one most likely to be skipped and the one that most
changes the plan. §14's torch row depends on it: without a stated margin,
"FTS5 demonstrably misses queries users care about" is a vibe, not a trigger.

`status` surfaces the most recent result (§8). If none exists, quality is
`unknown` — never assumed good.

Cost is contained: this lives in the test budget, not the ≤3,000 LOC core.

### 6.4 Query shapes the seed questions expose (added 2026-08-03)

Asking the operator for real questions instead of an answer key paid for itself
immediately: all three seed questions need retrieval capabilities the plan did not
have. They are recorded here because **an eval that cannot express these shapes
would score the system on the wrong thing**, and Checkpoint A would then measure a
model against queries nobody asks.

Each is stated as a shape, a gap, and where it lands. None is a v1 blocker except
where marked.

**Q3 — project affinity. `"What tasks did I work on the Binoid repo project?"`**

The gap, in the operator's words: *"repo queries need affinity repos (same
client/related projects) so a broad question can cast a wider net if an operator
does not ask a precise question."* §9's `projects(name, aliases_json, repos_json)`
maps one project to its own repos and aliases. It has no notion of **sibling**
projects, so a deliberately broad question returns a thin, precise answer — which
reads as "not much happened" when the truth is "you asked narrowly."

This is a **recall** failure that presents as a **content** failure, which puts it
in cluster B: the measurement (few results) is trusted as the thing measured (few
tasks). That is why it is specified now rather than after scoring.

*Mechanism — take the incumbent's idea, not its code.* `project_inference.py`
already derives affinity from GitHub owner and name tokens
(`_build_repo_aliases`, `_owner_brand_aliases`, `_owner_group_key`) and it works.
It is also 981 LOC of accreted heuristics, and `_owner_group_key` only fires for
owners whose name ends in `team|cbd` — a **client vertical hardcoded into a
regex**, which is both a portability failure and exactly the kind of string §19.2
must keep out of a public repo. HiQS reimplements the idea in the clean room:

- **Same GitHub organisation is the primary affinity edge**, and it is free — the
  owner is already on every `github_items` row. No inference, no heuristic.
- **Name-token overlap is the secondary edge**, over a generic-token stoplist.
- **Issue-title matching is the third**, per the operator's suggestion: a query
  term appearing in issue titles across sibling repos widens the net.
- **Affinity widens, it never narrows.** A precise query must return exactly what
  it returns today; affinity only adds siblings *below* the direct hits, and every
  added row is labelled with the edge that pulled it in. An affinity edge is a
  claim, so it carries its receipt like any other (ATTESTED).
- **No client names in code.** Grouping is derived from data at runtime, never
  from a literal in a regex. Pinned by a test that greps the module for the
  operator's known client and project names and fails on a hit — the §19.2 gate
  applied at the source rather than at extraction.

*Lands in:* a new column or side table alongside `projects` (§9), consumed by
`search()` as a post-fusion widening step. **Phase 2**, with GitHub — it needs
`github_items.repo` populated, and specifying it before then is speculative.

**Q1 — time-window retrieval. `"What did I work on yesterday from 9 AM to 11 AM?"`**

Not a topical search at all. It is *"return everything from any source whose event
time falls in this window, ordered by time"* — a different access path from
BM25+cosine, and one no amount of retrieval quality delivers.

The data exists: `activity_at`, `Doc.ts`, `calendar_events.start/end`,
`Candidate.ts`. There is no path that reads them as a **range across sources**.
FTS5 and cosine both rank by similarity, and "yesterday 9–11am" has no similarity
signal — the words do not appear in the answer.

*Consequence for the eval:* a time-window query cannot be scored by recall@10
against a topical index, so **these are tagged as a separate shape and excluded
from the model comparison**. Scoring a retrieval model on a query no retrieval
model can answer would penalise both equally and add noise to a decision that is
already close. They still belong in the query set as a capability gap the eval
*reports* rather than *scores*.

*Lands in:* §7's `ask()` seam as a time-range branch, **Phase 3**, once calendar
is in and there is more than one clock to reconcile.

**Q2 — cross-source linking. `"What did we decide on with XYZ to phase out the
Bash scripts on which GH issue?"`**

Two joined asks: find a decision (which lives in a note), then name the artifact
carrying it (which lives in GitHub). Retrieval can surface the note. Nothing today
carries the edge *note → issue*.

Partly a chunking question and partly an extraction one. The honest v1 answer is
that HiQS returns the note **and** any GitHub item whose number or URL appears in
that note's text — a literal reference match, not entity extraction. That is a
small, deterministic win and it is most of the value; inferring an unstated link
is not v1 work.

*Lands in:* the projection, **Phase 2**. A reference is a link, so it is a receipt,
so it is a field — not something re-derived at query time (D5 in
`HiQS/GUIDING-PRINCIPLES.md`).

**What all three have in common.** Each is a *retrieval-path* gap, not a ranking
gap. The plan's quality machinery — §6.3, §7.1 — measures how well the system
orders what it found. None of it detects a question the system cannot reach an
answer to at all. §6.3's gates therefore report **coverage by query shape**
alongside recall, so a shape scoring zero is visible as a missing capability rather
than averaged away as a weak model.

## 7. AI-native seams (one signature, one implementation today)

```python
Synthesizer = Callable[[question: str, context: dict], str] | None
#   None (default) → host agent synthesizes from raw attested context
#   later: local 4B/12B via any runtime — ask() doesn't know or care

Ranker = Callable[[list[Candidate]], list[RankedAction]]
#   v1: deterministic score, attested. Terms, in order of weight:
#     obligation  — owed_by set, and due date proximity if the source states one
#     activity    — recency of activity_at (the event that happened, NOT updated_at, L20)
#     source      — per-source weight
#   later: LLM ranker is another Ranker; cache table only if it becomes slow

@dataclass(frozen=True)
class RankedAction:   # what a surface renders — carries its own freshness
    rank: int; title: str; source: str; evidence: str; why: str
    ts: str; url: str = ""; author: str = ""; owed_by: str = ""; due: str = ""
    source_age_s: int = -1        # age of that source's last SUCCESSFUL sync
    source_status: str = "unknown"  # ok | warn | error | unknown, from events

Reranker = Callable[[str, list[Doc]], list[Doc]] | None
#   v1: None. Reserved for a cross-encoder over the fused top-50.
#   Re-ranking only — no re-indexing, fully reversible, but it reintroduces
#   model weight, which is a real argument against it. Trigger in §14.

Embedder = Callable[[list[str]], list[list[float]]]
#   v1: sentence-transformers (torch backend); model tier per Decision 8.
#   Swap = one string + lazy re-embed; backend swap = one kwarg.

Sentinel (reserved, not built) = observer over the events table that proposes
   repairs from a bounded menu; destructive actions gated on operator confirm.
```

`ask()` return shape — LLM-food by design, every fact carries receipts:

```json
{
  "question": "...",
  "context": {
    "vault":    [{"id": "...", "title": "...", "snippet": "...", "url": "...", "ts": "..."}],
    "github":   [],
    "calendar": []
  },
  "ranking": [
    {"rank": 1, "title": "...", "source": "github",
     "author": "alice", "owed_by": "you", "due": "2026-08-07",
     "evidence": "PR #42 review requested from you, 3d, last commit 2026-08-01",
     "why": "unblocks milestone due Fri", "url": "...",
     "ts": "2026-08-01T14:02:00Z",
     "source_age_s": 1840, "source_status": "ok"}
  ],
  "synthesis": null
}
```

**Every ranked item carries its own source's freshness.** `source_age_s` and
`source_status` ride on the item, not just on the `status` payload, because the
FRESH tenet fails in a specific way otherwise: a source that has not synced in
three weeks can still put a three-week-old item at rank 1, correctly stamped
with its own `ts`, looking exactly as current as a live one. That is the 0.57.0
email shape — the item is honest and the ranking is not. A surface can now
render "rank 1, but this source last synced 19 days ago" without asking a second
question, and `-1` / `unknown` mean *not established*, never *fine*.

### 7.1 Ranking quality — the second detector

§2 lists "no unmeasured quality claims" as a non-negotiable. Until 2026-08-03 its
mechanism column read *"every **retrieval**-quality assertion traces to a run of
the frozen eval set"* — scoped to the one thing that already had a detector.
Meanwhile RANKED claims signals are ordered by *what your team actually owes*,
and §13's done-criterion checked only that a ranking was **present**, not that it
was **right**. A quality claim with no measurement behind it is the exact defect
§6.3 was written to prevent, one layer up, and the plan was making it.

So ranking gets a detector too. It is deliberately cheaper than §6.3's — ranking
truth is an operator judgment where retrieval truth is a `doc_id` — but it obeys
the same three rules that make §6.3 hard to flatter:

**`tests/eval_ranking.json` — the frozen judgment set**

*Preconditions, in order, before any ranking is scored — the same ordered block
§6.3 uses, for the same reason: an answer key built after seeing the output
measures the output's persuasiveness, not the ranking.*

1. Capture 20–30 **dated daily snapshots**: the candidate set exactly as it
   stood on a real morning, stored verbatim.
2. For each snapshot the operator writes their own top-5 **before** looking at
   what HiQS ranked, and before any scoring run exists. A snapshot whose
   judgment was recorded after seeing HiQS's order is dropped, not corrected.
3. Judgments are **pairwise where possible** ("A was owed before B"), not
   absolute scores. At this n an operator can rank a pair reliably and cannot
   assign a calibrated 1–10.
4. **Commit and freeze** the file. Its SHA is recorded in every
   `rank.evaluated` event, and no run may score against an uncommitted set.
   Snapshots added after any score is visible start a new frozen version and
   require re-scoring every ranker.
5. **Public/private split, same as §6.3 step 5** (§19.2). These snapshots are
   verbatim working days — real PR titles, real meeting summaries, real people —
   and the repo goes public at Phase 6. Committed file carries opaque ids and the
   operator's pairwise judgments; the candidate text lives in a gitignored
   sidecar. The runner reports a loud `unknown` when the sidecar is absent rather
   than silently scoring a subset.

n≈25 is small, and the plan says so rather than implying otherwise: it can
resolve a whole-item difference in top-5 overlap and cannot resolve a few
percentage points. The gates below are therefore written in **items**, not
percentages, wherever the metric permits — the rev-5 lesson that a threshold
smaller than its own instrument's resolution launders judgment as evidence.

**Metrics — deliberately few**

| Metric | What it catches |
|---|---|
| **top-5 overlap** with the operator's set | the headline: does the list contain what was owed |
| **pairwise inversion rate** | ordering, independent of membership |
| **obligation coverage** — % of ranked items with `owed_by` or `due` populated | whether the ranking *could* be obligation-ordered, or is recency in a costume |
| **staleness leakage** — % of top-5 whose `source_status != "ok"` | the FRESH failure above, measured rather than assumed |

**Gates**

| Gate | Rule | If it fails |
|---|---|---|
| **Floor** | top-5 overlap **≥3/5 on average** across snapshots | Phase 3 does not exit. Below this the fault is the *candidate set or the obligation fields*, not the ranker's weights — the same diagnosis §6.3's floor makes about chunking, one layer over. Tuning the ranker against a starved candidate pool is treating a symptom |
| Beats recency | top-5 overlap beats a recency-only baseline by ≥1 item on average | the obligation terms are not earning their complexity — cut them and ship recency, honestly labelled |
| Obligation coverage | ≥50% of top-5 items carry `owed_by` or `due` | **Phase 3 does not exit.** Fix the source projections and re-score |
| Staleness leakage | 0 items in the top-5 from a source whose `source_status` is `error` | fix the ranker's freshness read before anything else |

The floor exists because "beats recency by ≥1 item" is a *relative* gate and a
relative gate alone can pass on a bad absolute: if recency scores 1/5, a ranker
at 2/5 clears it while getting 60% of your mornings wrong (added 2026-08-03 —
§6.3 had this floor from the start and §7.1 shipped without it). 3/5 is a stated
number rather than a judgment word, and like the Phase 2 refresh ceiling it is
tunable **once real figures exist** — moving it is a CHANGELOG line with the
measurement that justified it, never a quiet edit when a run comes in under.

**These block; they are not resolvable by editing the claim** (corrected
2026-08-03 — an earlier draft offered "fix the projections **or** restate the
tenet," which let a failing gate be passed by rewording what it measured. A gate
whose failure you can discharge by changing its own definition is not a gate;
that is precisely the unfalsifiability rev 5 removed from §6.3, reintroduced one
section later).

The tenet restatement is a **consequence, not an alternative.** If the operator
elects to ship anyway over a failed obligation-coverage gate, that override is
explicit and costs both of the following, together: the RANKED tenet is reworded
to "ordered by recency and source weight" everywhere it appears — README, web
page, MCP tool description — and the override is recorded in the CHANGELOG with
the failing numbers. Shipping the claim unmeasured remains unavailable in every
branch; §2's non-negotiable does not have an exception.

`status.ranking.quality` surfaces the most recent result alongside
`status.search.quality`. Never measured reports `unknown`, not a default.

Cost is contained: this lives in the test budget, not the ≤3,000 LOC core.

**Drift-proof invariant (the HiQS namesake):** exactly one ranking exists.
It is written by `refresh`, read by `ask`, MCP, and the web page. No surface
computes its own ranking — so two surfaces are structurally incapable of
disagreeing (Lesson L1).

## 8. Observability — from the first commit

```sql
CREATE TABLE events(
  ts TEXT, kind TEXT, source TEXT,
  status TEXT CHECK(status IN ('ok','warn','error','unknown')),
  payload_json TEXT);   -- append-only; one writer: log_event()
```

- Every plugin `fetch` emits `sync.completed` / `sync.failed` with its
  `SyncReport` (counts, errors, peak RSS, embed timings) — telemetry is a
  contract side-effect, not an afterthought.
- Every eval run emits `eval.completed` with its metrics (§6.3).
- `status()` = per-source freshness + row counts + last error tail + search
  mode + search quality, derived from `events` + tables. Backs CLI
  `status --json`, the MCP `status` tool, and the web health strip. One
  function, three consumers.

```json
"search": {
  "mode": "hybrid",
  "model": "all-MiniLM-L6-v2",
  "quality": {"recall_at_10": 0.83, "mrr_at_10": 0.71,
              "n_queries": 34, "measured_at": "2026-08-01T09:12:00Z"}
}
```

- `unknown` is a first-class state: an unreadable probe reports `unknown`,
  never a false healthy (Lessons L4, L6). Quality that has never been measured
  reports `unknown`, not a default.
- Per-run peak RSS recorded in `SyncReport.meta` (Lesson L7 — attribute the
  job that ate the machine in one query, without a forensic stack).

This table is the sentinel substrate: a future observer LLM reads structured,
attested history — nothing else needs to change for it to exist.

## 9. Schema — 9 tables total (rebalance-OS ships ~35)

```
vault_files       path, content_hash, mtime
github_activity   login, repo, day, counts_json
github_items      repo, type, number, title, body, state, url,
                  author, assignee, updated_at, activity_at
calendar_events   id, summary, start, end, project, organizer, attendees_json
docs              source, id, title, body, url, ts, project, author  + FTS5 index
docs_vec          doc_id, model, dim, vec BLOB                 PK (doc_id, model)
projects          name, aliases_json, repos_json               (config projection)
project_affinity  project_a, project_b, edge, weight           PK (project_a, project_b, edge)
events            ts, kind, source, status, payload_json       ← observability spine
```

**`project_affinity` — sibling projects, added 2026-08-03 (Phase 2).** Nine tables
now, not eight; the budget line moves rather than the table being squeezed into
`projects`, because this is a *many-to-many* relation and `repos_json` is a list on
one row. §6.4 has the reasoning; the schema note is that `edge` records **why** two
projects are siblings — `same_org`, `name_token`, `issue_title` — so an affinity
hit arrives with its receipt and a bad edge class can be disabled without a
re-derivation. Symmetric pairs are stored once, canonicalised `project_a <
project_b`. `weight` orders the widening, never the direct hits.

**`updated_at` is stored but never ranked on (added 2026-08-03).** L20 is
explicit that `updated_at` is bumped by label, assignee, and edit activity that
indicates no real movement, so a ranker reading it would violate the plan's own
lesson on day one. `github_items` therefore carries **two** timestamps with
different jobs:

- `updated_at` — the source's own field. Kept because it is the correct **sync**
  watermark (it is exactly what "has anything about this row changed?" means).
- `activity_at` — the timestamp of the last event that actually *happened*
  (a commit, a comment, a review, a state change). This is the only one the
  ranker's recency term may read, and it is what `Candidate.ts` projects from.

Using the wrong one is a silent-quality bug of precisely the shape §6.2 exists
to make impossible, so the projection is pinned by a test: a row whose only
change is a label edit must not move in the ranking.

```sql
CREATE TABLE docs_vec(
  doc_id TEXT NOT NULL,
  model  TEXT NOT NULL,          -- e.g. 'all-MiniLM-L6-v2'
  dim    INTEGER NOT NULL,       -- 384 | 1024 — models of different width coexist
  vec    BLOB NOT NULL,
  PRIMARY KEY (doc_id, model));
```

The composite key is load-bearing, not cosmetic. With `doc_id` alone as PK you
get lazy model swap but only one live model; with `(doc_id, model)` you can hold
two models' vectors simultaneously and score them head-to-head (§6.3) with no
migration step. `dim` is stored so a 384-dim and a 1024-dim model can occupy the
table at the same time without the reader guessing.

Timestamps stored UTC ISO-8601; day boundaries pinned to device-local tz at
query time. Connection: WAL, foreign keys, 30 s `busy_timeout`.

## 10. Surfaces

- **MCP (product surface, standard JSON-RPC):** `refresh` · `status` ·
  `search` · `ask`. All structured JSON, all attested.
- **CLI:** `hiqs refresh | status | search | ask` (+ `hiqs serve`, `hiqs auth`).
  `status --json` for scripts and agents. `hiqs auth <source>` is the only
  interactive command — it exists because the scheduled runner cannot complete a
  browser OAuth flow, and `status` names it in the remediation text when a
  source reports `auth_expired`.
- **Web baseline:** `hiqs serve` → one localhost page on 127.0.0.1:8790:
  next-actions ranking with receipts at top, per-source health strip, last-sync
  line, search mode + last measured quality. Server-rendered, meta-refresh,
  zero JS. A `/refresh` link triggers a sync and redirects back — that's the
  entire interactive layer.
- **Scheduling:** one launchd/cron job → `hiqs refresh` every 2 h.

One server, one port, one page. The old dual-server route-drift class of bug
(L10) cannot exist when there is no second server.

## 11. File tree, LOC budget, dependencies

**Where the code lives (settled 2026-08-03):** HiQS is built **inside this repo** at
`HiQS/` — a **staging home, not a permanent one.** It is extracted to
`HiQS-Suite/HiQS` once stable and proven ([§19](#19-extraction-to-hiqs-suitehiqs-and-the-rebalance-os-archive),
Phase 6). Building here first buys one `git log`, one PR flow, and one CHANGELOG
cadence during the build; the clean-room property is preserved by an import rule
rather than a repo boundary, and that rule is also what makes the later
extraction a **move rather than a port**:

- `HiQS/` has its **own `pyproject.toml`** and is installed as its own package (editable install
  from that directory). It is not a subpackage of the incumbent and does not appear in the
  incumbent's `pyproject.toml`.
- **`HiQS/**` imports nothing from the incumbent tree, and the incumbent imports nothing from
  `HiQS/**`.** That one rule is the whole clean room; it is pinned by a test in Phase 0 so
  "clean room" is a check, not a promise.
- The **database never lives in the repo** — it stays at the canonical app-data path (§13). Only
  source, tests, and fixtures live under `HiQS/`.
- **Nothing HiQS needs may live above `HiQS/`.** No shared `conftest.py`, no
  root CI step it depends on, no `scripts/` helper, no config outside the
  subtree. Self-containment is what makes `git subtree split` sufficient; a
  single upward dependency turns Phase 6 into a rewrite with a deadline.
- `HiQS/`'s own five docs (§11 below) are product docs for the eventual standalone extraction;
  the repo-root governance docs still govern this plan. See [§16](#16-pdda-compliance-and-the-governance-boundary).

```
HiQS/                 ← repo-relative root; the only tree HiQS writes
  pyproject.toml      own package, entry-point group `hiqs.sources`
  README.md · ARCHITECTURE.md · SPEC.md · CHANGELOG.md · AGENTS.md
  hiqs/
    __main__.py       CLI: refresh|status|search|ask|serve|auth         ~180
    db.py             connection, schema, upsert helper                 ~130
    config.py         one JSON config + secrets (keyring → 0600 file)   ~130
    plugins.py        Source contract + entry-point discovery + walk    ~100
    events.py         log_event() + status aggregator                   ~90
    sources/
      vault.py        walk .md, hash delta, chunk by heading            ~150
      github.py       activity scan + artifact sync (stdlib urllib)     ~250
      calendar.py     OAuth read, window upsert                         ~180
    docs_index.py     raw → docs projection + embed (delta, lazy model) ~130
    affinity.py       sibling-project edges (same_org|name_token|       ~80
                      issue_title); widens search, never narrows (§6.4)
    search.py         FTS5 + numpy cosine + RRF + Reranker hook         ~95
    ask.py            context gather + attestation + Ranker             ~180
    web.py            ONE page, stdlib http.server, zero JS             ~150
    mcp_server.py     4 tools, thin wrappers                            ~120
  tests/              one file per module, network stubbed,
                      plugin contract test                              ~700
                      test_clean_room.py (import-boundary pin)          ~20
                      eval_retrieval.py + eval_queries.json             ~80
                                                     core ≈ 1,780–1,980
```

**Deps (4 top-level):** `mcp` · `sentence-transformers` · `google-auth-oauthlib`
· `keyring`.

Stated plainly so nobody is surprised at install time: `sentence-transformers`
brings torch, transformers, tokenizers, huggingface-hub, safetensors, numpy, and
scipy — roughly ten installed packages and ~200 MB of wheels. Four is the count
of things this project chose; it is not the count of things pip downloads. §14
names the exit if that weight ever becomes a felt cost.

Stdlib over libs everywhere else: argparse over typer, urllib over requests,
`http.server` over FastAPI, FTS5 + BLOBs over sqlite-vec.

**Docs (5 files, no governance machinery), all under `HiQS/`:** README ·
ARCHITECTURE (1 page) · SPEC.md (plugin contract + the measured Decision 8 result,
machine-readable) · CHANGELOG (semver, dated) · AGENTS.md (short conventions).
These are HiQS's *product* docs and are scoped to `HiQS/`; the repo-root governance
docs are not replaced by them ([§16](#16-pdda-compliance-and-the-governance-boundary)).

## 12. Phases — each shippable, each with an exit check

Every phase carries a **QA gate** in the implementation checklist below — an
observable, binary acceptance list that must pass before the next phase starts.
The exit checks here are the one-line summary; the gates are the contract.

| Phase | Ships | Exit check | QA gate |
|---|---|---|---|
| **0 — Skeleton** | `HiQS/` subtree, `db.py`, `config.py`, `plugins.py`, `events.py`, empty CLI | `hiqs status` on empty DB returns structured JSON; a fake event lands in `events` | [gate](#qa-gate--phase-0) |
| **1 — Vault + hybrid search + eval** | `vault.py`, `docs_index.py`, `search.py`, eval set | see the Phase 1 gate below — this is the phase that closes Decision 8 | [gate](#qa-gate--phase-1) |
| **2 — GitHub plugin** | `github.py` + candidates provider | GitHub candidates appear attested in a dry ranking; contract test passes with the fake source | [gate](#qa-gate--phase-2) |
| **3 — Calendar + ask + MCP** | `calendar.py`, `ask.py`, MCP server, Ranker | morning briefing in Claude: meetings + commits + notes in one shot, all receipts present | [gate](#qa-gate--phase-3) |
| **4 — Surfaces + ops** | `web.py`, one launchd job, keyring hardening | web page shows the same ranking MCP returns; a week unattended, `events` explains any miss | [gate](#qa-gate--phase-4) |
| **5 — On demand only** | email/slack/figma plugins · Synthesizer/Ranker/Reranker LLMs · sentinel · writes | each lands through its seam, each has a trigger in §14 | [gate](#qa-gate--phase-5) |
| **6 — Extraction** | `HiQS/` → `HiQS-Suite/HiQS`; plan doc travels; rebalance-OS archived | the new repo stands alone: clone, install, test, run — with no reference back, and nothing private in the history | [gate](#qa-gate--phase-6) |

**Phase 1 gate.** Ordered — the preconditions exist so that scoring can't be
contaminated by work done after seeing results.

*Preconditions, before any model is scored:*

- [ ] Hybrid search live — **smoke check, not a quality gate**: a paraphrased question returns a non-empty result set through the vector leg, and an exact phrase returns one through the FTS leg. This proves both legs are wired; it says nothing about how well they rank, and it is never cited as evidence of quality. The frozen eval below is the only thing that decides that
- [ ] Chunk-length histogram run; ≥95% of chunks fit 256 word-pieces, or a chunk cap is added to `vault.py`
- [ ] `tests/eval_queries.json` holds 60–75 real vault queries with known-good `doc_id`s
- [ ] ≥50% asymmetric; ≥10 private-jargon; ≥10 exact-phrase; several known-hard
- [ ] Every ground truth resolved by filename or grep — **none** by running `search()`
- [ ] Query set committed and frozen; SHA recorded

*Scoring:*

- [ ] `eval_retrieval.py` reports recall@10 and MRR@10 per leg (FTS-only, vector-only, fused), offline
- [ ] MiniLM scored; `eval.completed` event written with metrics, cost figures, and queryset SHA
- [ ] Qwen3-Embedding-0.6B scored identically, both vector sets coexisting via the composite PK
- [ ] Paired disagreement set generated and read by the operator

*Gates:*

- [ ] Floor: winner's fused recall@10 ≥ 0.60 — otherwise investigate chunking, do not exit Phase 1
- [ ] Vector-leg justification: fused beats FTS-only by ≥10 points recall@10
- [ ] If the vector leg fails its gate: v1 ships FTS-only, torch moves to §14, and Decision 8 is closed as moot

*Recording:*

- [ ] Winner chosen by the §3.2 rule (recall@10 primary, MRR@10 tiebreak, splits and ties to the incumbent)
- [ ] Winner, loser scores, disagreement set, cost figures, queryset SHA, and date written to `SPEC.md` + CHANGELOG
- [ ] Decision 8 restated as measured; losing model moved to §14 with a regression trigger
- [ ] `status.search.quality` returns the recorded metrics, not `unknown`

## 13. Cutover and definition of done (v1)

- Code at `HiQS/` in this repo; **data never in the repo.** Fresh DB at
  the canonical app-data path (`~/Library/Application Support/hiqs/hiqs.db`
  macOS / `$XDG_DATA_HOME/hiqs/hiqs.db` Linux — never inside a TCC-protected
  folder, Lesson L11). Own config at `~/.config/hiqs/config.json`. Living in the
  repo is a *source* decision only; it does not relax L11 or put a DB, a token, or
  a vault path under version control.
- rebalance-OS keeps running untouched; both systems read the same upstream
  sources with separate credentials stores. No migration, nothing to break.
- **The incumbent's archive is a deadline on this criterion, not on the code.**
  Reaching "done" before the archive means none of it matters; missing it means
  choosing between an unmaintained fallback and an unfinished replacement
  (§19.4). The mitigation is phase order — Phases 0–3 deliver the daily use;
  Phase 4's surfaces and Phase 5's extras are the deferrable part. Cut from the
  back, never from the eval gates.
- **Done =** one morning where you never open rebalance-OS: the web page shows
  your day's ranking with receipts, Claude answers "what did I decide about X"
  from the local corpus via MCP, and `status` is green — with `search.quality`
  showing a real measured number, not `unknown`, and everything else explained
  by the events table if anything isn't.

## 14. Deletion ledger and re-add triggers

Everything below is deleted in v1. Each row names what brings it back and the
seam that makes re-adding cheap — this is how nothing gets painted into a corner.

Note on what is *not* here: torch ships in v1 (Decision 1). The FTS5-only path
is a **degrade rung**, documented in §6.2, not a deletion. Rev 3 listed torch as
deleted while §§2/3/6/11 shipped it; that contradiction is resolved here.

| Deleted | Re-add trigger | Seam |
|---|---|---|
| Torch-free runtime (`backend="onnx"`) | torch install weight, cold-start latency, or a platform where torch wheels fail | `Embedder` — one kwarg, library keeps the pooling math |
| Hand-rolled `onnxruntime` + `tokenizers` | an embedding path outside Python where no library can own the model math | copy the pooling formula from `sentence-transformers` source; never derive it |
| The model tier that loses Phase 1 | shipped model drops ≥5 points recall@10 on a re-run of the frozen query set, or the corpus shifts materially (much longer notes, a new domain, a new source with different text shape) | `Embedder` — one string + lazy re-embed; both vector sets can coexist |
| The vector leg entirely, if it fails its §6.3 gate | FTS-only was within 10 points of fused, so torch is unearned; re-add when a later eval run shows fused ≥10 points ahead | `search()` — the vector leg is one function; `docs_vec` stays in the schema |
| Cross-encoder reranker | recall@10 ≥ 0.75 while MRR@10 < 0.55 — i.e. the right documents are being retrieved but ordered badly, which is the only condition a reranker fixes | `Reranker` seam — re-ranking only, no re-indexing, but it reintroduces model weight |
| ANN index | corpus past ~100k docs, or cosine scan shows up in timings | `search()` vector leg is one function |
| Local synthesis (Qwen/Gemini) | host-less use becomes common | `Synthesizer` seam |
| LLM ranking | deterministic list measurably worse | `Ranker` seam |
| 10-job launchd fleet | stale data between 2 h refreshes | one job today; stagger pattern documented if a fleet returns |
| Pulse (markdown push, web mirror, warning-watch) | you actually open the pulse page | read side is one SQL query |
| Focus 5 app, CLIO, stickies, triage, 3-Eyes, RepairFSM, Zapier, team calendars | individually, when missed | each was always a leaf reader; repair returns as `RepairProvider` |
| Onboarding machinery (preflight/lifecycle/`/welcome`) | multi-device onboarding becomes frequent | `status` already reports what's missing; wizard wraps it |
| Project registry lifecycle (discovery/inference/provenance) | registry grows past ~20 projects | `projects` config list read through one `get_projects()` |
| All write ops (calendar create, reminder complete, vault write-back) | explicit write need, one at a time | plugin `write()` seam; v1 is read-only so the one-writer invariant is trivially held |
| PDDA, audit_modules, roadmap ledger | drift actually recurs | the contract test + ARCHITECTURE-as-code replace prose governance |

## 15. Decision log — why rev 4 differs from rev 3

Rev 3 bundled two independent choices into one locked decision: *which library
runs the model* and *which model runs*. Rev 4 separates them, because they have
different evidence types.

**On mechanism, rev 3 was right and stays.** The case for hand-rolled ONNX was
~150 MB and ~2 s per refresh. The case against is that pooling, mask-weighting,
and normalization done wrong produce plausible, valid-looking, quietly wrong
vectors — the exact silent-degradation class that cost this project weeks at
0.32.0 and again at 0.49.0. Cosine ranking over non-unit-norm vectors degrades
without raising. That trade is not close. `backend="onnx"` reaches the same
destination later with the library still owning the math, so nothing is lost by
waiting.

**On model tier, rev 3 locked an estimate.** "Roughly 80–90% of Qwen3 quality on
this corpus" was never measured on this corpus. Aggregate model-comparison
figures average over classification and STS tasks HiQS doesn't perform; on
retrieval specifically, and on asymmetric retrieval especially, the gap is wider
and lands squarely on the query shape §13 calls done.

The decisive point is that rev 3's own mechanism choice makes the model question
cheap. `backend="onnx"` works through the same `encode()` for any model with an
export — so cross-platform, torch-free-later, and the higher quality tier were
never mutually exclusive. Rev 3 traded away model quality to buy a
cross-platform property it was getting from the library anyway.

**On measurement, rev 3 had the instinct and not the power.** Its Phase 1 exit
check — "a paraphrased question finds the right note" — is an eval with n=1.
Rev 4 keeps that check and adds 29 more queries. It also fixes the schema detail
that made comparison awkward: `docs_vec` keyed on `doc_id` alone permits one live
model, and rev 3 already promised lazy per-model re-embedding, so the composite
key was implied but not written.

**The standard this document holds itself to.** Fifteen lessons, each traced to
a version number and an incident. Against that, one unmeasured estimate deciding
the core retrieval path was the weakest joint in an otherwise evidence-built
plan. Rev 4 does not assert MiniLM is wrong — it may well win. It asserts the
number should exist before the decision is called locked.

### Rev 5 — the eval gate was unfalsifiable

Rev 4 replaced an unmeasured estimate with a measurement whose criteria couldn't
settle the question. Six specific failures, each fixed above:

**The threshold was smaller than the noise.** "≥5 points recall@10" at n=30 is
1.5 queries. A rule that reads as precise while being unresolvable by its own
instrument is worse than an obvious guess, because it launders judgment as
evidence. Fixed by raising n to 60–75, widening the margin to 8 points, and
demoting aggregates beneath the paired disagreement set — at this scale, reading
ten queries where the models differ beats a delta that can't clear noise.

**Ground truth could have been built from search output.** This is the failure
that would have silently invalidated the whole exercise: mark what the current
index returns as "correct," and the current model wins by construction, with
numbers to prove it. The §6.3 protocol now requires queries authored from memory
and resolved by grep. It is the same class as L5 — generated output fed back
into its own input — arriving in the measurement layer instead of the data layer.

**Nothing froze the query set.** Without a commit and a recorded SHA, queries can
be added after scores are visible, and an eval becomes a justification.

**The FTS-only baseline was computed but decided nothing.** §14's torch row said
"FTS5 demonstrably misses queries users care about" — a vibe, not a trigger. It
now has a margin: fused must beat FTS-only by ≥10 points recall@10 or the vector
leg has not earned torch. This is the gate most likely to be skipped and the one
that most changes the plan, because it can delete a dependency rather than pick
between two models.

**The OR-rule shipped the challenger on a split.** Rev 4's "≥5 recall **or**
≥0.05 MRR" hands the win to Qwen3 on a recall lead even against an MRR loss —
precisely the rationalization gap the rule existed to close. Splits and ties now
go to the incumbent, which is also the cheaper model.

**Cost wasn't in the decision at all.** A 10× parameter model winning by 6 points
while costing 4× embed time is a real tradeoff, not an automatic upgrade. Cost
figures are now recorded in the same event and a >4× embed-time win escalates to
the operator rather than being resolved silently by a threshold.

Two gates were also missing outright: an absolute floor (below recall@10 0.60 the
fault is chunking, not model tier) and a truncation precondition (MiniLM's 256
word-piece limit silently decapitates long chunk-by-heading bodies, which would
have been misread as a model-quality result).

## 16. PDDA compliance and the governance boundary

This plan is a `PROJECT/2-WORKING` doc in the rebalance-OS repo, so it is governed
by [`PROJECT/PDDA.md`](../PDDA.md) — frontmatter, the exact two-column `## Status`
table, a table of contents listing every phase, a QA gate after every phase,
spike findings written back into the doc, repo-relative paths only, and a
`ROADMAP.md` pointer. All of those are present above.

**This governance is time-limited, and the end state is written down** rather
than left to be improvised: rebalance-OS is archived within weeks, so at Phase 6
the plan doc travels to `HiQS-Suite/HiQS` and sheds PDDA at that boundary — which
is §14's deletion ledger taking effect, not a contradiction of it. PDDA governs
the *work*; the work ends when the product ships. See
[§19.3](#193-where-governance-goes-when-the-repo-is-archived) for the full
disposition, including where the tracking issue is filed and what happens to the
cross-repo links.

**The boundary, stated plainly, because §14 looks like it contradicts this.**
§14's deletion ledger retires "PDDA, audit_modules, roadmap ledger" — that is a
statement about **what HiQS the product builds**, not about how this plan is
governed. The two are different scopes and both hold:

| Scope | Governed by | Meaning |
|---|---|---|
| This plan doc (`PROJECT/2-WORKING/HIQS-PROJECT.md`) | repo-root PDDA — frontmatter, status table, QA gates, ROADMAP pointer | how the *work* is tracked |
| `HiQS/**` source and its five product docs | HiQS's own conventions (`HiQS/AGENTS.md`), plus the contract test | how the *product* documents itself |

So: HiQS does not ship PDDA machinery, an `audit_modules` equivalent, or a roadmap
ledger of its own — that is §14, unchanged. The plan that builds HiQS is still a
tracked doc in a PDDA repo, because that is where the work happens. §14 deletes
governance *from the product*; it does not exempt the project from the repo it
lives in.

Concrete consequences while HiQS is under construction:

- **CHANGELOG split.** `HiQS/CHANGELOG.md` is the product's semver log (§11).
  The repo-root `CHANGELOG.md` remains the PDDA end-of-iteration record — an
  iteration that lands HiQS code gets an entry in both, and neither is a copy of
  the other. Root records *what changed and how it was verified*; `HiQS/` records
  *what shipped at which version*.
- **Roadmap pointer.** This doc is registered in `ROADMAP.md` under *In progress*
  as a one-line pointer. Phase state lives here, never there — when the roadmap
  entry needs more than a line plus a link, the detail belongs in this doc.
- **Issue-first SOP.** `gh_issue: TBA` today. The GitHub issue is opened before
  Phase 0 code lands; the number is then written into the frontmatter and the
  ROADMAP entry. This is the one open compliance item.
- **Status table currency.** The `## Status` table is updated at the end of every
  phase, not at the end of the project. It is the front door for a cold agent and
  a stale one is worse than an absent one.
- **Before this doc moves to `PROJECT/3-COMPLETED`,** a
  `## Lessons Learned (For Future Agents)` section is appended — the quirks and
  gotchas of building HiQS, in the same spirit as the Lessons section below
  captures rebalance-OS's.
- **Verification.** `utils/pdda/pdda.sh run` is the check; its deterministic
  findings are not overridden by prose in this doc.

## 17. Phase findings (memory injection)

Durable findings from any discovery or spike phase land here, in this doc, before
that phase's QA gate can pass. This is the canonical place for what was *learned*
— `SPEC.md` and the CHANGELOG record what was *decided*.

Each entry answers three questions: **what was investigated**, **what was found**
(concrete mechanics, with `file:line` pointers where the finding lives in code),
and **what it changes** about the phases that follow.

### Phase 1 — retrieval eval (Decision 8)

*Not yet run. This section is filled before the Phase 1 QA gate can pass.*

- **What was investigated:** which embedding model tier — `all-MiniLM-L6-v2` vs
  `Qwen3-Embedding-0.6B` — retrieves better on *this* vault, and whether the
  vector leg earns torch at all against an FTS-only baseline.
- **What was found:** *(pending)* winner, loser's scores per leg, the paired
  disagreement set with the operator's read of it, cost figures (embed time,
  index MB, peak RSS), the frozen query-set SHA, and the date.
- **What it changes:** *(pending)* whether §14's torch row fires, whether a chunk
  cap lands in `vault.py`, and which model Phases 2–5 build on.

## 18. HiQS tenets & self/meta compliance — dogfooding

HiQS sells four tenets. They are claims, so §2 requires them to be measured, and
that applies in **both directions**: to the product HiQS ships, and to the plan
and process that build it. If the method that produces HiQS cannot satisfy the
tenets, the product will not spontaneously do so either — and this section
exists because that is not hypothetical. Two of the four failed in the same
direction on both sides, and the plan-side failure is *why* the product-side one
went unnoticed until 2026-08-03.

### 18.1 The scorecard, both directions

| Tenet | The product (as specced) | The plan & process | Verdict |
|---|---|---|---|
| **01 ATTESTED** — source, author, time, link | `Candidate`/`Doc` carry source, ts, url, plus `evidence` + `why`; **`author` added 2026-08-03** after it was found missing (§5) | **incident** attribution is strong — every lesson L1–L22 cites a version and an incident, and every quality claim must cite an `eval.completed`/`rank.evaluated` row or be marked an estimate. **Decision** attribution is not: no rev, no locked decision, and no §14 row records *who* decided it or on what date, beyond a single `owner:` in frontmatter | **aligned, after a fix, and partial on the process side.** Both sides had the same hole in the same place — the *who* — and the product's has been closed while the process's has not |
| **02 RANKED** — ordered by what your team owes | `owed_by` + `due` fields and the §7.1 detector, **both added 2026-08-03**; before that, recency wearing obligation's name | phases are dependency-ordered and §14 is an explicit "not now"; across `PROJECT/2-WORKING` the roadmap is a **list, not an order** | **the weak tenet on both sides.** Product now measured; process still unranked |
| **03 FRESH** — stale signals decay | 2 h refresh, per-source freshness in `status`, `unknown` first-class, and **`source_age_s` on every ranked item** (added 2026-08-03) | `pdda.sh stale` flags docs past 4 days; the Status table's left column is the last verified state change; `updated:` validated | **aligned.** Shared blind spot: a fresh timestamp over stale content — the product answers with `activity_at` vs `updated_at`, the process with an LLM rubric |
| **04 STRUCTURED** — clean to read, ready to feed agents | MCP-first, typed JSON everywhere, `status --json`, `events` as the machine feed, zero-JS page | machine-readable frontmatter, exact status-table headers as a contract, JSONL findings with a stable `check` id | **aligned and strongest.** `PROJECT/PDDA-ACTIVITY.jsonl` is an events table for docs — the same architecture, applied to the work |

### 18.2 What the audit actually found

The finding worth keeping is not "two tenets were unmet." It is **why they were
unmet, and that the reason was the same reason twice.**

Neither the product nor the process had a representation of **who** or of
**obligation** — and the *who* gap needs stating precisely, because the two
sides fail it differently (sharpened 2026-08-03 after review flagged §18.1 and
this paragraph disagreeing):

- **Product:** no `author` field at all. Now fixed (§5).
- **Process:** *incident* attribution is thorough — every lesson names a version
  and an event. *Decision* attribution is absent: nothing records who chose
  MiniLM as the default, who set the ≥8-point margin, or who wrote a §14 row,
  beyond one `owner:` covering the whole document. So the process attests to
  **what happened** and not to **who concluded what** — a partial failure, not
  the total one the product had.

**Obligation** is the gap both sides fail outright: no assignee, due date, or
blocked-by in the product; no cross-doc order over the working set in the
process. So these are not independent bugs that happened to co-occur — a working
method with no obligation model produced a plan with no obligation model, and
the omission was invisible from inside because nothing in the method would have
flagged it.

The mechanism of the miss is also on record. §2's non-negotiable read *"every
**retrieval**-quality assertion traces to a run of the frozen eval set."* The
guarantee had been scoped to the one subsystem that already had a detector,
while RANKED — the tenet the product is named for — made a quality claim with no
measurement behind it and §13's done-criterion checked only that a ranking was
*present*. That is L4's count-vs-meaning error, committed by a plan whose §6.3
exists specifically to prevent it. Rev 5 caught it in the eval gate; this section
is the same class of defect found one layer further out.

**One caveat on this whole exercise, stated so it isn't over-claimed.** The four
tenets were *extracted from* these incidents — ATTESTED and RANKED were
articulated at 0.56.1/0.57.0 precisely because two surfaces disagreed and the
email rows were empty. They are scar tissue codified, so "would the tenets have
caught the scars?" is partly circular and is not the useful question. The useful
question is the one §18.3 answers: are they **structural now**, or still prose?
The incumbent already demonstrated which one matters — see L23, where a known,
already-fixed defect was reintroduced by a new module because the lesson lived
in a changelog rather than in a test.

### 18.3 The four tenets are not the whole safety surface

A scorecard with exactly four rows invites the reading that passing all four
means the system is sound. It does not, and the plan's own taxonomy proves it:
clusters **D (environment/resource assumptions)** and **E (scope accretion)**
map to *no tenet at all*, and part of **A (silent no-ops)** escapes too, because
the tenets govern the quality of *signals* and these are failures of
*operations* — a silent success is not a bad signal, it is no signal.

| Uncovered class | Why no tenet sees it | The incidents | Counterpart invariant |
|---|---|---|---|
| **Portability** | a path or shell assumption produces no signal to attest, rank, or date | hardcoded home dirs (0.29.0) · TCC `~/Documents` launchd exit 128 (0.18.2) · Bash 3.2 (0.63.0) — **L11, L21** | **PORTABLE** — canonical app-data paths only, templates rendered per-machine, no shell in the runtime path, no absolute user path in `HiQS/**`. Gate: Phase 4 |
| **Resource discipline** | a job that eats the machine emits perfectly well-formed telemetry right up to the OOM | no HTTP timeout + no `busy_timeout` lock cascade (0.25.0) · 46 GB jobs reporting 30 MB (0.68.0) — **L7, L18** | **BOUNDED** — explicit timeout on every network call (rule 7), 30 s `busy_timeout`, peak RSS per run, and the stated ≤100 calls / ≤500 MB refresh ceiling. Gate: Phase 2 |
| **Silent no-ops** | the operation *succeeded*; there is no unhealthy state to report | config whitelist dropping keys (0.26.0) · duplicate migration skipped (0.32.0) · **and the orphaned-chunk bug found in review 2026-08-03** — **L16, L17** | **LOUD** — a no-op that was meant to be an op is an event. Unknown config keys reported in `status`; `pruned` counted in `SyncReport`; an implausible prune share warns. Gate: Phase 0 + Phase 2 |
| **Scope accretion** | a bloated system can be fully attested, ranked, fresh, and structured | 10-job launchd fleet (L12) · +519 net LOC against a ≤0 criterion (0.57.0) · governance sweeps eating releases (L14) | **SMALL** — ≤3,000 LOC core and 4 top-level deps as a measured budget, §14 triggers stated as numbers, one launchd job. Gate: Phase 5 |

The orphaned-chunk defect is the useful confirmation here, because it was found
**after** §18 was written and lands squarely in the one class the tenets cannot
see: `refresh()` returns success, `status` reports `ok`, the counts are honest,
every payload is typed — and the corpus rots. Four tenets, all green, one silent
failure. That is what a coverage boundary is for.

One correction to a tempting reading: FRESH is sometimes said to miss the 119
empty email rows because "the rows existed, so by count the source looked
fresh." That was true of freshness *as the incumbent implemented it*, and it is
the reason L4 exists — but it is not true of FRESH as specced here. Records that
cannot attest are rejected at the write boundary, `SyncReport.counts`
distinguishes stored from rejected, and §7.1 measures staleness leakage into the
top-5. The tenet was upgraded from count to meaning; the uncovered classes above
are the ones that remain genuinely outside it.

### 18.4 The standing rule

**A tenet is a field, a gate, and a detector — never a slogan.** Concretely:

- Every tenet maps to at least one **structural field** (ATTESTED → `author`;
  RANKED → `owed_by`/`due`; FRESH → `source_age_s`/`activity_at`; STRUCTURED →
  the typed payloads themselves). Prose does not count; a receipt reachable only
  by parsing free text fails.
- Every tenet maps to a **QA gate** in a phase (§12), so it is checked before the
  phase closes rather than asserted at launch.
- Every tenet that makes a *quality* claim maps to a **detector** with a frozen
  answer key: §6.3 for retrieval, §7.1 for ranking.
- **A tenet the product cannot meet is a bug or a false claim.** §7.1's
  obligation-coverage gate is written so its failure branch changes the tenet's
  wording, not just the backlog — if HiQS cannot order by obligation, the honest
  claim is "ordered by recency and source weight," and it stays that way until a
  measurement says otherwise.
- **The same rule binds the four counterpart invariants** (§18.3). PORTABLE,
  BOUNDED, LOUD, and SMALL are not a second manifesto — each names a gate in a
  phase, and each is checked there. A plan that made only the tenets executable
  would still ship the four failure classes they cannot see.
- **This audit re-runs.** The tenets *and* the counterpart invariants are
  re-checked against the shipped system at the §13 cutover and any time a
  tenet's wording changes. A dogfooding section written once and never re-run is
  itself a stale signal.

### 18.5 Open self-compliance gap

**The process is still not RANKED.** `PROJECT/2-WORKING` holds ~45 active docs
with no obligation order over them: PDDA's triage ratings
(`effort`/`complexity`/`risk`/`phases`) give an *ease* signal and a risk gate,
but nothing encodes what is owed, to whom, or by when — the same absence the
product just fixed. This is recorded rather than fixed here because it belongs
to the repo's governance layer, not to HiQS's build, and inventing a parallel
mechanism inside this plan would be the §14 governance-machinery trap. Named so
it is a known gap rather than an unexamined one.

## 19. Extraction to `HiQS-Suite/HiQS`, and the rebalance-OS archive

**`HiQS/` is a staging home, not a permanent one** (confirmed by the operator
2026-08-03). Once the code is stable and proven over several days of real use, it
is extracted to **`https://github.com/HiQS-Suite/HiQS`** — which exists today,
**public**, empty, created 2026-08-03. Separately, **rebalance-OS is archived
within weeks**, no firm date.

Both facts are load-bearing and neither is a footnote, so they get a phase
([Phase 6](#phase-6--extraction-to-hiqs-suitehiqs)) rather than an intention.
A planned migration that is not a phase is a migration improvised at 11pm.

### 19.1 What the two facts change

| Fact | Consequence for this plan |
|---|---|
| Code spins out to its own repo | The clean-room import test (Phase 0) stops being a purity property and becomes the **extraction precondition**. If `HiQS/**` imports nothing from the incumbent, extraction is `git subtree split` — a move. If it imports anything, extraction is a port, and a port is a rewrite with a deadline |
| Target repo is **public** | Everything under `HiQS/` becomes world-readable at extraction. §19.2 is the consequence, and it is the one most likely to be discovered after the push rather than before |
| rebalance-OS is archived | This doc's governance home disappears (§16), its `ROADMAP.md` pointer freezes, and the root `CHANGELOG.md` stops being the end-of-iteration record. §19.3 |
| Archive has no firm date | The incumbent stops being a *maintained* fallback on an unknown date. §19.4 |

### 19.2 The public-repo disclosure gate — the non-obvious one

The plan mandates committing two artifacts built **from the operator's private
vault and real working days**:

- `tests/eval_queries.json` (§6.3) — 60–75 real vault queries, explicitly
  including **"≥10 private-jargon queries (`git-pulse`, `Luggage`,
  `Cross Country`, client and project names)"**, each resolved to a real
  `doc_id`. Committed and frozen by design.
- `tests/eval_ranking.json` (§7.1) — 20–30 **verbatim daily candidate sets**:
  real PR titles, real meeting summaries, real obligations, real people.

Both are load-bearing (frozen answer keys are the whole anti-gaming mechanism)
and both are, as specced, a client-data disclosure the moment the repo goes
public. Nothing in §6.3 or §7.1 noticed, because they were written for a private
tree.

**Rule:** the frozen sets are **real but not public**. Concretely —

- The committed files carry **stable opaque ids and the operator's judgments**,
  never the source text. A query becomes `{"id": "q-041", "doc_id": "...",
  "shape": "asymmetric|jargon|exact-phrase|hard"}`; the natural-language query
  and the note title live in a local sidecar that is **gitignored and never
  extracted**.
- The eval runner reads the sidecar when present and **skips with a loud
  `unknown`** when it isn't — never silently scoring a subset, which would be a
  cluster-A failure in the measurement layer.
- The SHA recorded in `eval.completed` / `rank.evaluated` covers **both** files,
  so freezing still means what §6.3 says it means.
- A pre-extraction scan for vault paths, client names, tokens, and absolute home
  directories is a **blocking** Phase 6 gate item, run against the full history
  that `subtree split` will carry — not just the tip. History is the part people
  forget, and it is the part that cannot be fixed with a follow-up commit.

This gate is why Phase 6 exists as a phase. It is discovered by *tracing the
path*, exactly like the OAuth hole r2 found — and like that one, it is invisible
if you only read the sections separately.

### 19.3 Where governance goes when the repo is archived

§16 says this plan is governed by rebalance-OS's PDDA while HiQS is built here.
That is now explicitly **time-limited**, and the end state is written down rather
than left to be improvised when the archive happens:

- **The plan doc travels with the code.** At Phase 6 it moves to
  `HiQS-Suite/HiQS` as `docs/PLAN.md` (or is retired into `CHANGELOG.md` if the
  build is complete), and it **sheds PDDA at that boundary** — which is not a
  contradiction, it is §14's deletion ledger finally taking effect. PDDA governed
  the *work*; the work ends when the product ships.
- **The archived copy stays valid as provenance.** An archived repo is
  read-only, not deleted. `PROJECT/2-WORKING/HIQS-PROJECT.md` remains the record
  of how HiQS was designed, and the new repo's `docs/PLAN.md` opens with a link
  back to it.
- **Before the archive**, this doc moves to `PROJECT/3-COMPLETED/` with the
  `## Lessons Learned (For Future Agents)` section §16 already requires. A doc
  frozen in `2-WORKING` by an archive is a stale signal with no one left to
  flag it.
- **Cross-repo links rot.** `related:` points at `GH-125-HIQS-PIPELINE.md` and
  others in this repo. At extraction they become citations ("see rebalance-OS
  `PROJECT/…`"), not links, since a relative path across a repo boundary is a
  dead link that looks live.
- **The GitHub issue goes to `HiQS-Suite/HiQS`, not here.** An archived repo's
  issues are frozen, so filing HiQS's tracking issue against a repo that is about
  to be archived buries it. PDDA already permits this: a foreign-repo issue is
  disambiguated by the `source:` URL, which is why that field exists.

### 19.4 The archive is a deadline, and the honest read of it

Decision 7 says the incumbent "runs untouched alongside until HiQS covers the
daily use." That stays true with one correction: **archiving a repo does not
uninstall the software.** The local rebalance-OS keeps running, its launchd jobs
keep firing, its DB keeps filling. What ends is the ability to *fix* it.

So the risk is not "the fallback disappears," it is "the fallback becomes
unmaintained on an unknown date." Stated plainly because it is the one thing in
this plan that a schedule can break:

- If HiQS reaches §13's done-criterion before the archive, nothing here matters.
- If it doesn't, and the incumbent breaks after the archive, the operator is
  choosing between an unmaintained system and an unfinished one. Unarchiving is
  trivial, which is why this is Costly and not a one-way door — `risk: 3` is
  unchanged and this is why.
- **The mitigation is phase order, not heroics.** Phases 0–3 deliver the
  MCP/`ask` path, which is the daily use. Phase 4's surfaces and Phase 5's
  extras are genuinely deferrable. If the archive date firms up and is tight,
  cut scope from the back — that is what §14's deletion ledger is for, and it is
  a better answer than compressing the eval gates, which are the only thing
  standing between this plan and the incumbent's 68 versions of scar tissue.

---

# Lessons Learned from Rebalance

The old system's CHANGELOG is a 68-version scar record. Every lesson below is
a real incident, cited; each one is encoded structurally in this plan, not as
a promise.

## The taxonomy — six clusters, one meta-pattern

The lessons below are grouped by *subsystem* (architecture, data quality,
observability, …) because that is where the fix lands. Grouped instead by
*failure mode*, the same incidents collapse into six clusters — and the clusters
are not equal. Folded in from the standalone anti-patterns ledger, whose version
citations were re-verified against `CHANGELOG.md` on 2026-08-03.

| Cluster | What it is | Incidents | HiQS's structural answer |
|---|---|---|---|
| **A. Silent failure / silent degradation** | the system fails and reports itself healthy | empty rows accepted at the write boundary (0.57.0) · embeddings extra never installed (0.32.0) · retired Gemini model forcing fallback (0.49.0) · TCC paths failing every machine (0.18.2) · config whitelist dropping keys (0.26.0) · duplicate migration number skipped (0.32.0) | reject-at-write-boundary (§5.2) · `unknown` as a first-class state (§8) · no hidden fallback chains, degrade rungs are queryable (§6.2) · `sentence-transformers` owns the model math (§3.1) |
| **B. Trusting the wrong signal as truth** | the measurement, not the thing measured | health-check misreads, 6 of 6 (0.60.0, 0.67.0) · green tile over an unreadable fleet (0.67.0) · RSS as a memory ruler (0.68.0) · a doc's `status:` field over git (0.67.1→0.67.2) · `updated_at` as progress (0.28.3) | health derived from `events`, never from exit-code archaeology (§8) · peak RSS per run in `SyncReport.meta` · search *quality* measured, not just mode (§6.3) |
| **C. Drift from duplication** | two implementations of one fact | two synthesis surfaces (0.56.1) · `pulse_server.py` re-declaring `web.py` routes (0.50.1) · per-source dispatch in the ranker (0.56.1) · five UTC formatters (0.59.0) · five home-dirs baked into plists (0.29.0) | exactly one ranking, written by `refresh`, read by everyone (§7) · one server, one port, one page (§10) · registry walk, never a dispatch chain (§5.6) |
| **D. Environment / resource assumptions** | the machine is not what the code assumed | no memory guard until the machine died (0.68.0) · no HTTP timeout + no `busy_timeout` (0.25.0) · reasoning model eating its own budget (0.49.1) · Bash 3.2 (0.63.0) | explicit timeouts + 30 s `busy_timeout` (§5.7, §9) · no LLM in the ranking path (§3.1.5) · no shell in the runtime path (§10) |
| **E. Scope and complexity accretion** | the machinery becomes the project | net-LOC criterion missed, +519 (0.57.0) · PDDA hygiene sweeps eating releases (0.67.1) · `audit_modules` · a 10-job launchd fleet | ≤3,000 LOC core with a named budget (§11) · §14 deletion ledger with numeric re-add triggers · one launchd job (§10) |
| **F. Self-reference / feedback loops** | output re-enters as input | generated `What To Do Next.md` ranking itself (0.49.1) · `last-run` advancing on a failed scan (0.18.2) | v1 writes nothing back (§3.1.6) · watermarks advance only on completed fetches (§5.8) |

**A is the meta-pattern.** Nearly every severe incident — the empty email table,
the inert embeddings, the retired model, the 46 GB jobs, the green-but-unknown
fleet — is one bug in different clothes: *a degraded or broken state that
reported itself as healthy.* The durable fix is structural, not per-case, and it
is why §8 exists before any source does: reject unusable records at the write
boundary, make `unknown` distinct from `ok`, assert row *quality* not row
*count*, and never let one surface compute its own truth.

**One cluster is still live in the incumbent as of 2026-08-03, and that matters
here.** C's two-server row is not history: `scripts/pulse_server.py` (FastAPI,
:8767) and `src/rebalance/web.py` both declare `/focus-5`, `/focus-5.json`,
`/focus-5/note`, `/focus-5/goals`, and `/whats-next`, and `pulse_server.py`
still carries a *"must stay in sync"* comment on a path it shares with
`pulse_web.py`. Every other row above has a shipped fix in the incumbent (the
dispatch chain became a `candidates=` registry walk; the self-ranking loop is
guarded by `_is_generated_next_actions_file`; the UTC formatters consolidated
into `tz_utils.py`). §10's one-server rule is therefore the one lesson HiQS
adopts from a defect that is still open, not from one already closed.

## Architecture

**L1 — Two synthesis surfaces drifted, and the product's core claim was only
two-thirds true.** The broad-synthesis path saw no Slack reminders, email, or
design comments; the ranked what's-next engine saw no email or design comments.
Two surfaces shared no code, so nothing prevented drift (0.56.1, GH-125).
→ *HiQS:* exactly one ranking, written by refresh, read by everyone. Surfaces
that re-rank inline are structurally impossible (§7 invariant).

**L2 — The per-source dispatch chain was a standing violation.** The ranker
hand-dispatched per source; every new signal meant editing it (until 0.57.0
replaced it with a registry walk, pinned by a fake-source test).
→ *HiQS:* plugin-native from day one; the contract test ships in Phase 0 (§5.6).

**L3 — The consolidation bet.** Four overlapping signal efforts stalled for the
same reason: nothing combined the signals, so no single one could prove its
value (0.56.1). → *HiQS:* combining *is* the product; sources ship as plugins
into one bundle, never as parallel pipelines.

## Data quality

**L4 — Silent coercion at a write boundary starved a source for three weeks.**
Email push-ingest defaulted missing fields to empty strings; 119 of 124 stored
rows had no sender, subject, or timestamp. Nothing reported unhealthy because
freshness checked row *counts*, not row *meaning* (0.57.0).
→ *HiQS:* records rejected at the write boundary when they can't attest;
`SyncReport.counts` distinguishes stored from rejected; `status` derives health
from both. **Applied one layer up (§6.3):** reporting search *mode* without
search *quality* is the same count-vs-meaning error, so `status` carries a
measured recall/MRR figure or reports `unknown`.

**L5 — Generated output fed back into its own input.** The generated
"What To Do Next.md" was ingested as a recent vault edit and ranked into its
own list (0.49.1). → *HiQS:* v1 writes nothing into the vault; if write-back
returns via the `write()` seam, generated files are excluded from ingest by
construction.

**L16 — A config whitelist silently dropped every key it didn't know.**
`get_pulse_config()` returned an explicit-keys dict, so an unrecognized key
vanished without a word and the first iteration of a new filter simply no-op'd
(0.26.0). → *HiQS:* one JSON config read whole. A key the code doesn't consume
is reported in `status`, not discarded — a setting that appears to be honoured
and isn't is cluster A wearing a config file.

**L17 — A duplicate migration number would have been silently skipped.** A
second `0002` on an already-stamped DB is a no-op, and the table it created
would never exist (0.32.0, caught during review and renumbered). → *HiQS:* no
migration framework in v1 at all — fresh DB, `CREATE TABLE IF NOT EXISTS`, and
the composite `(doc_id, model)` PK exists precisely so a model swap needs no
migration (§9). If versioned migrations ever arrive, uniqueness of the number is
a test, not a convention.

**L19 — A watermark advanced on a failed scan, and the gap repaired itself out
of existence.** `last-run` moved even when the scan errored, so commits authored
during the broken window became invisible to every later run (0.18.2). → *HiQS:*
plugin rule 8 — the watermark advances only after the fetch it describes
completed; on error it stays put and the error lands in `events`. Upsert-only
(rule 2) makes re-covering the window free.

**L20 — `updated_at` is not a progress signal.** It is bumped by label,
assignee, and edit activity that indicates nothing about real movement; the
triage spike deliberately used last-comment dates instead (0.28.3). Noted at
design time rather than paid for — the one item here that is a trap avoided, not
a scar. → *HiQS:* a `Candidate.ts` is the timestamp of the event that actually
happened, and `evidence` names it, so a stale item cannot masquerade as fresh.

## Observability

**L6 — Months of "the collectors are unstable" were health-check misreads.**
6 of 6 investigated findings were misreads; zero were real collector defects:
exit-1 from one sub-source failed a whole successful sync; stale `launchctl`
status asserted as current health; device-bound checks warned on machines they
didn't describe (0.60.0, GH-146). Later, a running daemon reported FAILING
because health read the prior exit code instead of the live PID, and a
sandboxed probe returned empty → "not-loaded" → a false all-clear rendered as
green in the UI (0.67.0).
→ *HiQS:* `unknown` is a first-class status; probes fail closed; health is
derived from the events table (what actually happened), never from process
exit-code archaeology (§8).

**L7 — The job that ate the machine reported 30 MB.** The watchdog measured
resident RAM, which excludes compressed/swapped pages; two jobs grew to ~46 GB
while reporting ~30 MB, and the machine OOM'd (0.68.0). The earlier GH-172
embedding incident was hard to attribute because only the process name was
recorded. → *HiQS:* peak RSS is recorded per run in `SyncReport.meta` so
attribution is one query (§8). Note the honest correction to rev 3: a smaller
model reduces but does not eliminate this class — torch batch encoding has its
own memory profile — so per-run RSS recording is the real mitigation, and the
model tier is not.

## ML / synthesis

**L8 — Silent degradation, twice.** A retired Gemini model 404'd and every
synthesis silently fell back to local Qwen, surfacing as placeholder titles
(0.49.0). Separately, the embeddings extra was simply never installed, so
vector search was silently inert and degraded to lexical-only (0.32.0).
→ *HiQS:* no hidden fallback chains; `status` reports the live search mode and
synthesis mode explicitly (§6.2). A degraded mode is a visible state, never a
silent one. **This lesson is also why hand-rolled ONNX is rejected** (§3.1):
wrong pooling or a missing L2 norm is the same silent, plausible-looking
degradation arriving through the model math instead of through a missing install.

**L9 — Reasoning models eat their own budget.** A thinking model spent ~1,962
of 2,048 tokens on hidden reasoning and emitted 2 of 15 ranked items (0.49.1).
→ *HiQS:* no LLM in the ranking path at all in v1; if a Ranker LLM returns via
the seam, token-budget control is part of that seam's contract.

## Operations

**L10 — Two servers, two route tables, drift that bit twice.** `pulse_server.py`
hand-re-declared a subset of `web.py`'s routes; routes added to one were
invisible on the other, and the KeepAlive daemon kept serving a stale route
table until kickstarted. Separately, a client assumed one port was the only
backend and needed dual-port probing (ARCHITECTURE drift gotcha; 0.50.1).
→ *HiQS:* one server, one port, one page (§10).

**L11 — Hardcoded paths and protected folders fail silently at 3 am.** One
developer's home directory was baked into five plists (0.29.0); the sync repo
living in TCC-protected `~/Documents` made launchd jobs fail with exit 128 on
every machine, invisibly, until someone checked (0.18.2).
→ *HiQS:* canonical app-data paths only; templates render per-machine; no
absolute user paths; DB never inside a TCC-protected folder (§13).

**L12 — A fleet of jobs becomes its own project.** Ten launchd jobs required a
policy table, conformance tests, per-job installers, collision de-confliction
(GH-175), lock-contention retries (GH-131), and ordering dependencies between
Gemini summary jobs. → *HiQS:* one job. The stagger lessons are documented in
the deletion ledger for the day a second job appears (§14).

**L13 — Repair must be bounded.** RepairFSM's durable lessons: deterministic
repair first; the LLM picks from a bounded named menu, never free-form
execution; `reset_hard` was excluded because it discarded the work and reported
false success; destructive actions require explicit operator authorization
(0.31.5). → *HiQS:* reserved as the `RepairProvider` contract, unchanged in
spirit, zero code until a sentinel exists (§5, §7).

**L18 — One stalled HTTP request took down every scheduled job.** With no
timeout on `urlopen` and no `busy_timeout` on SQLite, a request that hung after
sleep/wake held the writer, and `database is locked` cascaded through the daily
sync, every hourly vault sync, and the TUI refresh until the holder was killed
by hand (0.25.0). → *HiQS:* both halves are structural — plugin rule 7 requires
an explicit timeout on every network call, and §9 pins `busy_timeout` to 30 s on
the one connection factory. A stalled source fails itself and nothing else
(plugin rule 5).

**L21 — The runtime assumed a shell it didn't have.** An empty-array expansion
under `set -u` broke every normal run on macOS's stock Bash 3.2 (0.63.0). →
*HiQS:* no shell in the runtime path at all. One launchd job invokes a Python
entry point directly; there is no wrapper script to be incompatible with.

## Process

**L14 — Documentation governance became its own workload.** Multiple releases
went to PDDA hygiene sweeps, status-field corrections that had to be corrected
again, and audit machinery checking that docs mention code (0.67.1–0.67.2).
→ *HiQS:* five docs total; the plugin contract is code, not prose; the
contract test replaces the audit.

**L15 — The sync patterns were right the first time.** Hash/ID delta, window
refetch + upsert, full refetch + column-diff; upsert-only, never auto-delete —
these survived 68 versions intact (ARCHITECTURE sync model).
→ *HiQS:* kept verbatim as the three sanctioned plugin patterns (§5.2). Same
for one-writer-per-table, attested candidates (source/evidence/why), and the
two-hub fan-out/fan-in model — the best ideas in the old codebase are load-bearing
in the new one.

**L23 — A shipped fix was re-introduced by a new module, because the lesson was
prose.** `doctor._check_launchd` read `launchctl list`'s status column and
ignored the live PID, so a running daemon reported FAILING; that was diagnosed
and fixed under GH-146. Months later the new 3-Eyes health module **reproduced
the identical misread** (0.67.0) — the principle was known, the fix had shipped,
and nothing stopped a second implementation from re-committing it. This is the
lesson that governs all the others: a principle that lives in a changelog
protects exactly one code path, the one that was edited.
→ *HiQS:* every lesson that produces a fix is pinned at the **seam**, not in the
module. The plugin contract test is the model — it asserts a property of *any*
source, so a source written next year inherits it without anyone remembering to.
Concretely: one writer per table, attestation non-empty, watermark-on-success,
within-unit-only reconciliation, and timeout-on-every-call are all properties the
contract test checks against a fake plugin, so a seventh source cannot
reintroduce them. A lesson with no seam-level test is documentation, and §18.4's
"field, gate, detector" rule exists because of this incident.

**L22 — A doc's own status field is not evidence.** A correction pass replaced
one wrong claim with a second wrong claim because it read prose for the "was it
merged?" half instead of asking git (0.67.1 → 0.67.2). → *HiQS:* the same rule
applied to the system's own claims about itself. `status` is derived from
`events` and table state, never from a constant or a hand-maintained field, and
every retrieval-quality number traces to an `eval.completed` row carrying the
query-set SHA that produced it (§6.3, §8). A claim with no row behind it reports
`unknown`.

---

# Implementation checklist

## Phase 0 — Skeleton

- [ ] `HiQS/` subtree scaffolded at the repo root, own `pyproject.toml`, entry-point group `hiqs.sources`
- [ ] `db.py` — `db_connection()` factory, WAL, FKs, 30 s busy_timeout, schema create
- [ ] `docs_vec` created with composite PK `(doc_id, model)` and a `dim` column
- [ ] **Tenet-bearing columns created now, not later** — `docs.author`; `github_items.author/assignee/activity_at`; `calendar_events.organizer/attendees_json`. Decision 7 ships no migration machinery, so a column added after Phase 2 costs a re-ingest (§5, §9)
- [ ] `events.py` — `log_event()` as the sole writer; `status()` aggregator stub
- [ ] `config.py` — one JSON config, `secret()` resolution chain keyring → 0600 file → env
- [ ] `plugins.py` — `Source`/`SyncReport`/`Doc`/`Candidate` dataclasses + entry-point walk
- [ ] Contract test: a fake plugin reaches `docs`, `status`, and ranking with zero core edits
- [ ] **The contract test is the lesson-seam (L23)** — it asserts the invariants against *any* source, not the shipped three: one writer per table, attestation non-empty, watermark advances only on success, reconciliation within a unit only, explicit timeout on every network call. A future source inherits them without anyone remembering to
- [ ] Clean-room test: `HiQS/**` imports nothing from the incumbent tree and vice versa
- [ ] Exit: `hiqs status` on an empty DB returns structured JSON; a fake event lands in `events`

### QA gate — Phase 0

Binary and observable; all must pass before Phase 1 starts.

- [ ] **Structural.** `pip install -e HiQS/` succeeds from a clean venv; `hiqs --help` lists `refresh`, `status`, `search`, `ask`, `serve`.
- [ ] **Clean room (DRY, and the property that makes this a rebuild).** `tests/test_clean_room.py` fails if any module under `HiQS/**` imports the incumbent package, or the reverse. Enforced by a test, not by review.
- [ ] **One writer per table.** Exactly one function writes `events` (`log_event()`) and exactly one writes `docs` (the projection); grep-pinned in the test suite.
- [ ] **Observability (SOLID / dependency direction).** A fake `sync.completed` event round-trips: `log_event()` → `events` row → `status()` reads it back. Failing to write the event fails the test — telemetry is a contract side-effect, not optional.
- [ ] **Plugin substitutability.** The fake source registers via entry point only; **zero** files under `HiQS/hiqs/` change to admit it. Any core edit needed to make the fake work is a Phase 0 failure, not a Phase 0 workaround.
- [ ] **Degrade honesty.** `status` on an empty DB reports `unknown` for search mode and quality — never a default that reads healthy (L4/L6/L8).
- [ ] **No hardcoded paths.** No absolute user path anywhere in `HiQS/**`; the DB path resolves from the app-data helper (L11).
- [ ] **Deploy check:** none — Phase 0 is local-only, no scheduled job, no server, no remote environment.

## Phase 1 — Vault, hybrid search, and the measurement that closes Decision 8

> **Spike phase (memory injection).** Phase 1 exists to *learn* which retrieval
> configuration is right — its output is evidence, not just code. Its findings must
> be written back into [§17](#17-phase-findings-memory-injection) of this doc before
> the gate can pass; `SPEC.md` and the CHANGELOG record the decision, and §17 records
> what was learned. A result that lives only in an `eval.completed` event and an agent's
> context is exactly the drift this contract exists to prevent.

- [ ] `vault.py` — walk `.md`, hash delta, chunk by heading
- [ ] `docs_index.py` — raw → `docs` projection, delta-only embedding keyed by content hash
- [ ] `search.py` — FTS5 BM25 leg, numpy cosine leg (**filtered `WHERE model = <active>`** — mixed widths in one array raise), RRF fuse (k=60), per-document cap of 2 chunks before the slice, `Reranker` hook wired to `None`
- [ ] `status.search.mode` reports `hybrid` / `fts_only` / `unknown`; a degrade writes a `search.degraded` event
- [ ] Histogram chunk lengths in word-pieces; add a chunk cap to `vault.py` if >5% exceed 256
- [ ] Author 60–75 eval queries from memory and intent, before consulting the index
- [ ] Resolve every ground truth by filename or `grep`; drop any query you can't independently locate
- [ ] Verify the mix: ≥50% asymmetric, ≥10 private-jargon, ≥10 exact-phrase, several known-hard
- [ ] Commit and freeze `tests/eval_queries.json`; record its SHA
- [ ] `tests/eval_retrieval.py` — offline, fixture DB, recall@10 + MRR@10 per leg, plus disagreement set and cost capture
- [ ] Score `all-MiniLM-L6-v2`; write an `eval.completed` event with metrics, costs, and queryset SHA
- [ ] Score `Qwen3-Embedding-0.6B` through the same `encode()`; both vector sets coexist via composite PK
- [ ] Read the paired disagreement set query by query — this is the primary evidence, not the aggregate
- [ ] Check the floor gate: winner's fused recall@10 ≥ 0.60, else stop and investigate chunking
- [ ] Check the vector-leg gate: fused beats FTS-only by ≥10 points recall@10
- [ ] If the vector leg fails, ship FTS-only, move torch to §14, close Decision 8 as moot
- [ ] Otherwise apply the §3.2 rule: recall@10 primary (≥8 pts), MRR@10 tiebreak, splits and ties to MiniLM
- [ ] Escalate to the operator if the winner costs >4× embed time
- [ ] Record winner, loser scores, disagreement set, costs, queryset SHA, and date in `SPEC.md` and CHANGELOG
- [ ] Mark Decision 8 measured; move the losing model to §14 with a regression trigger
- [ ] Verify `status.search.quality` returns real numbers rather than `unknown`
- [ ] **Write the findings back into [§17](#17-phase-findings-memory-injection)** — what was measured, what it changed, what it kills

### QA gate — Phase 1

- [ ] **Preconditions honoured in order.** The §12 Phase 1 gate's precondition block passed *before* any model was scored — chunk histogram run, query set authored from memory, ground truth resolved by filename/grep only, file committed and its SHA recorded. An out-of-order run invalidates the result even if every number looks fine.
- [ ] **Floor gate.** Winner's fused recall@10 ≥ 0.60, else Phase 1 does not exit and the investigation goes to chunking or the query set, not the model.
- [ ] **Vector-leg justification.** Fused beats FTS-only by ≥10 points recall@10, or the vector leg (and torch) moves to §14 and v1 ships FTS-only. This gate is allowed to *delete a dependency* — it is not a formality.
- [ ] **Truncation.** ≥95% of chunks fit the shipped model's context, or a chunk cap landed in `vault.py` and everything was re-scored after it.
- [ ] **Reproducibility (DRY of evidence).** `eval_retrieval.py` is offline, fixture-backed, and re-runnable; a second run on the same DB and query set reproduces the same recall/MRR figures. A number nobody can reproduce is not a measurement.
- [ ] **Both models resident, no crash.** With MiniLM (384) and Qwen3 (1024) vectors coexisting in `docs_vec`, a search returns correct results for each — proving the `WHERE model` filter holds. The head-to-head comparison is the whole point of the composite PK, so the read path must survive it (§6.1).
- [ ] **Chunk diversity.** A query matching several headings of one long note returns at most 2 chunks from it in the top-10; other relevant notes are not starved (§6.1).
- [ ] **Observability.** Every scored run left an `eval.completed` row carrying `{model, recall_at_10, mrr_at_10, n_queries, queryset_sha, embed_ms, index_mb, peak_rss_mb, git_sha}`; `status.search.quality` reads from that row, not from a constant.
- [ ] **Degrade honesty.** Forcing the model unavailable makes `status.search.mode` report `fts_only` **and** writes a `search.degraded` event. Verified by test, not by inspection — this is L8's structural fix.
- [ ] **Memory injection (spike requirement).** §17 carries the winner, the loser's scores, the disagreement set with the operator's read of it, the cost figures, and what the result changes about Phases 2–5. An unwritten "we'll know after the eval" left dangling is itself a gate failure.
- [ ] **Deploy check:** none — the eval is offline and fixture-backed by design; no remote environment, no network, no scheduled job.

## Phase 2 — GitHub

- [ ] `github.py` — activity scan + artifact sync over stdlib `urllib`
- [ ] Window refetch + upsert pattern; never auto-delete
- [ ] `candidates()` provider emitting attested `Candidate` rows (source/evidence/why)
- [ ] Project `author`, `assignee`, and `activity_at` — the last event that *happened*, never `updated_at` (L20)
- [ ] Map `assignee` / requested-reviewer → `Candidate.owed_by`; milestone or stated deadline → `due`; leave `""` when unknown, never guess
- [ ] Peak RSS and API call counts recorded in `SyncReport.meta`
- [ ] **`project_affinity` populated (§6.4, §9).** Sibling edges derived at runtime from data: `same_org` from the owner already on every row, `name_token` over a generic stoplist, `issue_title` from query-term hits across sibling repos. Each row records its `edge`.
- [ ] **Affinity widens, never narrows.** Siblings are appended *below* direct hits and labelled with the edge that pulled them in; a precise query returns byte-identical results to affinity-off. Pinned by a test.
- [ ] **No client or project literal in code.** A test greps the affinity module for the operator's known client and project names and fails on a hit — §19.2's disclosure gate enforced at the source, not at extraction. (The incumbent's `_owner_group_key` hardcodes a client vertical in a regex; that is the defect being avoided, not copied.)
- [ ] **Reference linking (§6.4, Q2).** The projection records GitHub numbers/URLs literally present in a note's text as an edge — a receipt in a field, not a query-time re-derivation (D5). Literal matches only; inferring an unstated link is not v1.
- [ ] Exit: GitHub candidates appear attested in a dry ranking; contract test still green

### QA gate — Phase 2

- [ ] **A broad query beats a narrow one on coverage (§6.4, Q3).** The operator's seed question — *"What tasks did I work on the Binoid repo project?"* — returns work from sibling repos in the same org, not only the exactly-named one. Recorded as a coverage figure, because a recall failure here presents as "not much happened" and is trusted as content (cluster B).
- [ ] **Zero core edits.** Adding GitHub touched only `sources/github.py` and one entry-point line. Any file changed under `HiQS/hiqs/*.py` to make GitHub work is a plugin-contract defect (L2), fixed in the contract rather than absorbed here.
- [ ] **Attestation is total.** Every emitted `Candidate` carries a non-empty `source`, `evidence`, and `why`. A bare candidate fails the test — receipts are the product, not decoration.
- [ ] **Idempotence.** Two consecutive `refresh` runs over an unchanged window produce zero inserts and zero updates; `SyncReport.counts` distinguishes inserted / updated / unchanged / skipped / rejected. Never auto-delete (L15).
- [ ] **Isolation on failure.** With the network stubbed to raise, the GitHub source's error lands in `events` and `SyncReport.errors`, and the rest of the walk still completes (plugin rule 5).
- [ ] **Quality, not count (L4).** Rows that cannot attest are *rejected* at the write boundary and counted as rejected — a run that stores 100 contentless shells must not report healthy.
- [ ] **Efficiency, with numbers.** `api_calls` and `peak_rss_mb` recorded in `SyncReport.meta`, and a full refresh stays inside a stated budget: **≤100 API calls** and **≤500 MB peak RSS** per run. Exceeding either is a `warn` event naming the figure, not a silent pass. (The plan's own standing-hygiene rule forbids a trigger stated as a judgment word — "an operator-visible budget" was exactly that, corrected 2026-08-03. Tune the two numbers once real figures exist; changing them is a CHANGELOG line, not a shrug.)
- [ ] **Secrets.** The token resolves only through `config.secret()`; no token, path, or username is hardcoded, and none appears in an `events` payload.
- [ ] **Deploy check:** none yet — still local. Network access is real, so the test suite stubs it; no scheduled job is installed until Phase 4.

## Phase 3 — Calendar, ask, MCP

- [ ] `calendar.py` — OAuth read-only, window upsert
- [ ] `hiqs auth <source>` — the interactive re-authorization path a launchd job cannot perform; writes to keyring, and `status` names it in the remediation text on `auth_expired`
- [ ] `ask.py` — context gather + attestation + deterministic `Ranker` (~40 LOC)
- [ ] `mcp_server.py` — `refresh` · `status` · `search` · `ask`, thin wrappers
- [ ] `RankedAction` carries `author`, `owed_by`, `due`, `source_age_s`, `source_status`
- [ ] Ranker's recency term reads `activity_at` only; pinned by a test that a label-only edit does not move a row (L20)
- [ ] Author 20–30 dated snapshots into `tests/eval_ranking.json`, operator top-5 recorded **before** seeing HiQS's output
- [ ] Commit and freeze the judgment set; record its SHA
- [ ] `tests/eval_ranking.py` — top-5 overlap, pairwise inversion rate, obligation coverage, staleness leakage; writes a `rank.evaluated` event
- [ ] Check the three §7.1 gates; if obligation coverage fails, either fix the projections or restate the RANKED tenet — do not leave the claim standing
- [ ] Verify the single-ranking invariant: MCP and `ask` read the ranking written by `refresh`
- [ ] Verify `status.ranking.quality` returns real numbers rather than `unknown`
- [ ] Exit: a morning briefing in Claude returns meetings + commits + notes with every receipt present

### QA gate — Phase 3

- [ ] **RANKED is measured, not asserted (§7.1).** The frozen judgment set is committed and scored, and all four gates pass: floor (top-5 overlap ≥3/5 average), beats-recency (≥1 item over a recency-only baseline), obligation coverage (≥50%), staleness leakage (zero top-5 items from an `error` source). **A failed gate blocks Phase 3 exit until the projections are fixed and it is re-scored.** The only other way past it is an explicit operator override, which costs the tenet reword everywhere the claim appears *plus* a CHANGELOG entry carrying the failing numbers — an override is not a way to close the gate, it is a recorded decision to ship over it. Shipping the claim unmeasured is unavailable in every branch (§2).
- [ ] **Recency means activity, not metadata (L20).** A test asserts that a row whose only change is a label or assignee edit does not move in the ranking. `updated_at` is a sync watermark; `activity_at` is the ranking input, and confusing them is a silent-quality bug.
- [ ] **Freshness rides on the item (FRESH).** Every `RankedAction` carries `source_age_s` and `source_status`; a stale source's item cannot render as current. Unmeasured is `-1` / `unknown`, never a default that reads healthy.
- [ ] **ATTESTED is total, all four receipts.** Every ranked item carries source, **author**, time, and link — as fields. A receipt reachable only by parsing `evidence` prose fails this gate; `""` is permitted only where the source genuinely cannot know, and is never a guess.
- [ ] **The namesake invariant, proved (L1).** Exactly one ranking exists. A test asserts `ask()`, the MCP `ask` tool, and the persisted ranking are byte-identical for the same DB state; no surface computes its own. This is the single most important check in the plan — the old system's core claim was two-thirds true because nothing enforced it.
- [ ] **Thin wrappers (SOLID).** `mcp_server.py` contains no ranking, scoring, or filtering logic — only marshalling. A behavioural difference between CLI and MCP for the same query is a defect.
- [ ] **Determinism.** The `Ranker` is pure and repeatable: same candidates in, same order out, no clock- or network-dependent tiebreak, no LLM anywhere in the path (L9).
- [ ] **Read-only, enforced.** The calendar client is scoped read-only; a test asserts no write method is reachable from `HiQS/**` (Decision 6).
- [ ] **Attestation survives the seam.** Every item in the `ask()` `ranking` array carries `evidence`, `why`, and a resolvable `url`; `synthesis` is `null`, not an empty string, so a host can tell "no synthesizer" from "synthesizer returned nothing".
- [ ] **Observability, checkable by a test.** A failed OAuth refresh produces a `sync.failed` event whose payload carries a **non-empty `error_type`** (a stable, enumerable token — `auth_expired`, `network`, `rate_limit`, `parse`) **and a non-empty `message`**, and leaves `status` reporting `error` for that source. "A readable reason" was unfalsifiable prose (corrected 2026-08-03); two non-empty fields with a closed vocabulary can be asserted. Never a silent empty result rendered as green (L6, L8).
- [ ] **Deploy check:** **yes, partly** — the MCP server must be registered in a real MCP host (Claude) and the morning-briefing exit check run there, not just in tests. OAuth is a real external credential flow; verify on the actual device, and confirm the token lands in keyring rather than the repo.

## Phase 4 — Surfaces and ops

- [ ] `web.py` — one page, `http.server`, zero JS, meta-refresh, `/refresh` redirect
- [ ] Health strip shows per-source freshness, search mode, and last measured search quality
- [ ] One launchd/cron job → `hiqs refresh` every 2 h; no fleet
- [ ] Canonical app-data DB path; confirm it is outside any TCC-protected folder
- [ ] Keyring hardening; verify no absolute user paths anywhere in the repo
- [ ] Exit: web page and MCP return the identical ranking; one week unattended with `events` explaining any miss

### QA gate — Phase 4

- [ ] **One server, one port, one page (L10).** Exactly one route table exists in the codebase; a grep for a second `http.server` handler returns nothing. The web page renders the persisted ranking — it does not re-rank.
- [ ] **Surface parity.** The web page and the MCP `ask` tool return the same ordered ranking for the same DB state, asserted by a test, not by looking at both.
- [ ] **Unattended honesty.** After a week of 2-hourly runs, every gap in the data is explained by an `events` row. A miss with no event is an observability defect, not an operations anecdote (L6).
- [ ] **Every failure has an operator action.** Expire the calendar token deliberately, then confirm: the run reports `auth_expired`, `status` names `hiqs auth calendar` as the remedy, and running it restores the source. A failure whose only remedy is improvisation is not specced — an unattended runner that cannot open a browser needs an interactive path to exist before it is needed, not after (Decision 4).
- [ ] **Path portability (L11).** Zero absolute user paths in `HiQS/**` or in the installed job; the plist/crontab is rendered per-machine from a template. The DB path is verified to sit outside any TCC-protected folder on the actual device.
- [ ] **Coexistence with the running incumbent (blocking).** HiQS is built and run on the same machine that already runs rebalance-OS — **7 live launchd jobs**, including `vault-sync` and `github-sync`, both of which embed. HiQS embeds every 2 h. **This is GH-172 exactly**: three concurrent embedding runs stacked to ~90 GB on a 68.7 GB machine and the kernel panicked. That fix was a `flock` + memory ceiling applied at the *incumbent's* library leaves, and a separate HiQS process knows nothing about it — two systems each correctly guarding themselves is not a guard. Required: HiQS's embed path takes the **same machine-scoped lock** (read the incumbent's path, do not invent a parallel one), keeps its own memory ceiling regardless, offsets its schedule, and the installer **probes and refuses** on a bound port (`:8790` vs the incumbent's `:8767`) or an already-loaded `com.hiqs.*` label.
- [ ] **Job hygiene (L12).** Exactly one scheduled job. If a second is ever proposed, it goes through §14 with a stated trigger — the fleet is the failure mode, not the solution.
- [ ] **Secrets at rest.** Keyring is confirmed *live* (write, then read back in a fresh process) rather than assumed — a keyring write that silently no-ops and still prints success is a known real failure mode in this repo's history.
- [ ] **Local-only exposure.** The server binds `127.0.0.1` and refuses a non-loopback origin; verified by an actual request from a second host failing.
- [ ] **Deploy check:** **yes** — this phase installs a real scheduled job and a long-running local server on the operator's device. Nothing here is provable in CI; the exit check is explicitly a week of real unattended runtime.

## Phase 5 — On demand only

Nothing in Phase 5 is built speculatively. Each item lands only when its §14
re-add trigger has actually fired, and each lands through an existing seam.

- [ ] Additional source plugins (email, slack, figma, …) — one module + one entry-point line each
- [ ] `Synthesizer` / `Ranker` / `Reranker` implementations, if their triggers fire
- [ ] Sentinel / `RepairProvider` over the `events` table
- [ ] Write operations, re-entering one at a time through the plugin `write()` seam

### QA gate — Phase 5

- [ ] **Trigger first.** The §14 row's stated number or observable event is cited *before* work starts. "It would be nice" is not a trigger; a judgment word instead of a number is a §14 defect to fix, not a licence to build.
- [ ] **Through the seam, not around it.** The addition changes no core file. If it cannot be expressed through `Source`, `Synthesizer`, `Ranker`, `Reranker`, or `write()`, the seam is wrong and gets fixed — the feature does not get a bypass.
- [ ] **Budget honesty.** The LOC and dependency effect is measured and recorded. Crossing ≤3,000 LOC core or 4 top-level deps is an explicit operator decision written into the CHANGELOG, never a drift discovered later.
- [ ] **Write ops are gated.** Any write path is one source at a time, keeps one-writer-per-table, and — for destructive actions — requires explicit operator confirmation from a bounded named menu (L13). No free-form execution.
- [ ] **No generated-output feedback (L5).** Anything HiQS writes back is excluded from its own ingest by construction, not by a filename convention someone has to remember.
- [ ] **Deploy check:** per item — a write op or a sentinel touches the operator's real data and must be verified live under confirmation prompts before it runs unattended.

## Phase 6 — Extraction to `HiQS-Suite/HiQS`

Runs when the code is stable and proven over several days of real use (§19).
Not gated on Phase 5, which is on-demand-only and may never run.

- [ ] Confirm the clean-room test is green — this is the precondition that makes extraction a move rather than a port
- [ ] Confirm `HiQS/` is self-contained: no shared `conftest.py`, no root-level CI step, no `scripts/` helper, no config outside the subtree. Anything HiQS needs that lives above it must move in **first**, as its own commit
- [ ] Rewrite `tests/eval_queries.json` and `tests/eval_ranking.json` to opaque-id form; move the natural-language text and note titles to a gitignored local sidecar (§19.2)
- [ ] Confirm the eval runners read the sidecar when present and report a loud `unknown` when absent — never a silently-scored subset
- [ ] Scan the **full history** `subtree split` will carry for vault paths, client names, tokens, and absolute home directories — not just the tip
- [ ] `git subtree split --prefix=HiQS -b hiqs-extract` and push to `HiQS-Suite/HiQS`, preserving commit history for those paths
- [ ] Move this plan doc to the new repo as `docs/PLAN.md`, shedding PDDA at the boundary (§14 taking effect); open it with a link back to the archived original
- [ ] Convert `related:` cross-repo links to citations — a relative path across a repo boundary is a dead link that looks live
- [ ] File/transfer the tracking issue to `HiQS-Suite/HiQS`; the archived repo's issues freeze
- [ ] Move `PROJECT/2-WORKING/HIQS-PROJECT.md` → `PROJECT/3-COMPLETED/` with `## Lessons Learned (For Future Agents)` appended, **before** the archive
- [ ] Update `ROADMAP.md` to point at the new repo rather than the working doc
- [ ] **Decommission the incumbent's scheduled jobs — operator action, and only here.** After §13's
      done-criterion is met, unload the 7 `com.rebalance-os.*` launchd jobs so two systems stop
      contending for the same machine, API budget, and embedding memory. This belongs at cutover
      and nowhere earlier: the incumbent is the **fallback** until HiQS is proven (Decision 7), and
      disabling it sooner removes the safety net before the replacement has earned its place —
      exactly backwards, and worse now that the archive makes the fallback unmaintained (§19.4).
      Never performed by a build turn: unloading 7 jobs on the operator's machine is a destructive,
      hard-to-reverse act that must not happen unattended. Keep the plists; unload is reversible,
      deletion is not.

### QA gate — Phase 6

- [ ] **It stands alone, proven by doing it.** Clone `HiQS-Suite/HiQS` to a fresh directory on a machine that has never held rebalance-OS: `pip install -e .`, run the suite, run `hiqs status`. All three succeed with no reference back. A "should work" here is worth nothing — the failure mode of an extraction is a dependency nobody noticed, and the only detector is a clean clone.
- [ ] **Nothing private in the history (blocking).** The scan above is clean across every commit `subtree split` carried, not just the tip. History is the part that cannot be fixed with a follow-up commit — and this repo's own L11 is what a leaked absolute path costs.
- [ ] **The frozen sets are still frozen.** Post-extraction, `eval_retrieval.py` and `eval_ranking.py` reproduce the same figures from the opaque ids plus the local sidecar. If the anonymization changed a score, the anonymization is wrong; a frozen answer key that moves is not frozen.
- [ ] **History preserved.** `git log` in the new repo shows the real commit history for `HiQS/**`, not one squashed import. The provenance is the point — this plan's whole method is traceability.
- [ ] **No orphaned pointer.** `ROADMAP.md` and this doc's `3-COMPLETED` copy both point at the new repo; the new repo points back at the archived original. Neither side is a dead end.
- [ ] **Deploy check:** **yes** — the launchd job and config path move with the operator's install. Confirm the scheduled job still fires against the extracted package before the incumbent is archived, not after.

## Standing hygiene

- [ ] Re-run the retrieval eval whenever the embedding model, chunking strategy, or fusion constant changes
- [ ] Any new quality claim in any doc cites an `eval.completed` event or is marked an estimate
- [ ] Every `# ponytail:` assumption carries a named revisit threshold
- [ ] Every §14 re-add trigger states a number or an observable event — never a judgment word like "poor" or "demonstrably"
- [ ] Adding eval queries starts a new frozen query-set version and requires re-scoring every model; never append to a set that has already been scored
- [ ] Any decision threshold is checked against the sample size that will evaluate it — a margin smaller than a few queries is not a threshold
- [ ] Deletion-ledger rows stay consistent with what v1 actually ships — a row claiming something is deleted while another section ships it is a rev-4-class bug
- [ ] Every lesson that produced a fix is pinned at the seam by the contract test, not only in the module that broke — a lesson with no seam-level test is documentation (L23)
- [ ] The four counterpart invariants (PORTABLE, BOUNDED, LOUD, SMALL) are re-checked alongside the four tenets; passing all four tenets is not evidence the system is sound (§18.3)
- [ ] A gate's failure branch never permits discharging it by redefining what it measures — that is the unfalsifiability rev 5 removed from §6.3 (§7.1, corrected 2026-08-03)

---

*Plan owner: the operator. **Phases 0 and 1 are built, reviewed and green** —
1,499 LOC core, 107 tests passing, via marathons M1 and M2 (2026-08-03).*

*Next step: **operator checkpoint A**, amended — write the queries, judge the
paired disagreement set blind, and let the answer key accumulate from what you
recognise (§6.3, amended 2026-08-03). The vector-leg gate there can remove torch
from the plan and reshape Phases 3–4, so M3 does not fire before it. §6.4 records
three retrieval-path gaps the operator's own seed questions exposed — project
affinity, time-window retrieval, and cross-source reference linking — two of which
land in Phase 2 and must be specified before it is built.*

*Still open: the GitHub issue belongs on
[`HiQS-Suite/HiQS`](https://github.com/HiQS-Suite/HiQS) (issue-first SOP; not this
repo — it is being archived).*
