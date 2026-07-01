---
title: "Signal-Quality Contract (observe-first source health)"
codename: HiQS
owner: Noel
status: "Proposed (1-INBOX — not yet active). Phase 0 spike scoped, not yet run. Supersedes the two SKETCH-* drafts."
created: 2026-06-30
updated: 2026-06-30
branch: development
doc_type: project
goal: >
  Detect silent signal degradation — "false freshness", silent empty sets, and volume
  collapse — at the point of USE (index_status / doctor / ask), without adding a blocking
  ingest gate. Make a degraded source legible to any querying agent instead of letting the
  pipeline present dead signal as healthy.
non_goals: >
  Not an ingest gate. Does not stop refresh_index, reject messy upstream rows, or add a new
  enforcement pipeline. Not a relevance-ranking engine. Not a new table or new MCP tool in v1.
supersedes:
  - PROJECT/1-INBOX/SKETCH-REBALANCE-SIGNAL-CONTRACT-00.md
  - PROJECT/1-INBOX/SKETCH-REBALANCE-SIGNAL-CONTRACT-DRAFT-01.md
related:
  - PROJECT/1-INBOX/PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md
  - PROJECT/1-INBOX/GEMINI-WHATS-NEXT-VAULT.md
  - PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md
  - PROJECT/2-WORKING/WATCHLIST-COVERAGE-GUARD.md
effort: 2
complexity: 2
risk: 1
phases: 4
roadmap_exempt: true
---

## Status

| What was just completed | What's next |
|---|---|
| **Plan authored + grounded against live code (2026-06-30).** Merged the two `SKETCH-*` drafts into one phased plan and verified the central surfaces: `index_status()` → `get_index_status()` ([index_ops.py:224](../../src/rebalance/ingest/index_ops.py#L224)) already derives per-source freshness from each table's own timestamp via `_safe_max`; a `_safe_count_where` 7-day-window primitive **already exists** ([index_ops.py:273](../../src/rebalance/ingest/index_ops.py#L273)); `payload["freshness"]` is an empty dict ready to hold derived labels ([index_ops.py:236](../../src/rebalance/ingest/index_ops.py#L236)). **Correction to the sketch:** there is **no `sync_state` table** — freshness is already per-table, so the work is smaller and lower-risk than assumed. | **Open a GitHub issue** (issue-first SOP), rename this doc `GH-<n>-SIGNAL-QUALITY-CONTRACT.md`, park a one-line pointer in `ROADMAP.md`, promote to `2-WORKING`, then **run Phase 0** (1–2h spike) and write its findings back here before the Phase 0 QA gate can pass. |

---

## Table of contents

- [Phase 0 — Spike: validate the observe-first contract against the real schema](#phase-0--spike-validate-the-observe-first-contract-12h) _(scoped, not run)_
- [Phase 1 — `recent_row_count_7d` in `index_status`](#phase-1--recent_row_count_7d-in-index_status) _(blocked on Phase 0)_
- [Phase 2 — derived `status`/`reason` + one `doctor` warning path](#phase-2--derived-statusreason--one-doctor-warning-path) _(blocked on Phase 1)_
- [Phase 3 — optional: surface degradation at query time (`ask`)](#phase-3--optional-surface-degradation-at-query-time-ask) _(kill-gated on Phase 2)_

# Signal-Quality Contract

> **Thesis:** `rebalance` is an automated ingest pipeline, not a human workflow gate. The
> contract therefore lives at the point of **use** (`index_status`, `doctor`, `ask`), never at
> the point of **collection**. It **observes and downgrades trust**; it never blocks a sync or
> rejects an upstream row. What it detects is **signal degradation** — not schema violations,
> which the storage boundary already rejects.

---

## 1. Does the premise survive falsification?

**The case against building this:** adding quality ceremony to an automated pipeline risks
dropping real signal and breaking the sync loop in the name of "quality" — violating the very
"Fresh" pillar it claims to enforce. Structure is already enforced by the SQLite schemas; symmetry
with PDDA is not a reason to build.

**It survives — with one hard constraint: observe-first, never block-first.** The justification is
**silent failures of meaning**. The historical proof is the Focus 5 identity bug ([GH-81](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/81)):
the pipeline executed perfectly, the rows were structurally sound, the sync was marked fresh — yet
repos were silently dropped from the ranking and the system had **no way to detect it**. The pipeline
currently *asserts* quality; it does not *observe* it. That is the gap.

The contract must therefore:

- **not** stop `refresh_index()`, **not** reject messy upstream data, **not** add a blocking gate;
- **do** append health metadata that read-side tools can see, and **do** downgrade trust / surface
  warnings at query/use time.

---

## 2. What is actually true today (grounded, not asserted)

The two drafts assumed a `sync_state` table and described freshness as "asserted only." The live
code is **better than that**, which shrinks the work:

| Pillar | Real state today | Evidence (file:line) |
|---|---|---|
| **Structured** | Enforced at the storage boundary; malformed writes don't land. | source schemas / type affinities |
| **Fresh** | **Already derived per-table**, not from a missing `sync_state`. `get_index_status` computes a per-source last-timestamp via `_safe_max(conn, table, col)`. | [index_ops.py:244-302](../../src/rebalance/ingest/index_ops.py#L244-L302) |
| **Attested** | Asserted only — rows carry source IDs/URLs, but synthesis is not structurally required to cite them. | (out of scope for v1) |
| **Relevant** | Structurally weak — relevance is query-time; no signal when important rows were silently omitted. | (the GH-81 class) |

**Three findings that de-risk the build:**

1. **No `sync_state` table exists** (`grep` → 0 hits). Freshness is *already* per-source, so Phase 1
   does not need new freshness plumbing — only a second metric beside the existing counts.
2. **The 7-day-window primitive already exists**: `_safe_count_where(conn, table, predicate)` is used
   today for `apple_reminders` active-count ([index_ops.py:273](../../src/rebalance/ingest/index_ops.py#L273)).
   `recent_row_count_7d` is one call to it with a `timestamp > now-7d` predicate.
3. **`payload["freshness"]` is an initialized empty dict** ([index_ops.py:236](../../src/rebalance/ingest/index_ops.py#L236)) —
   the natural, DRY home for the derived `status`/`reason` labels, rather than a parallel structure.

There is also a ready-made **source → content-timestamp** map to reuse: `_PEEKABLE_SOURCES`
([index.py:193](../../src/rebalance/mcp/tools/index.py#L193)) already pins each source to the column
that means "when this row's data is about / arrived" (`calendar_events→start_time`,
`email_messages→received_at`, `github_activity→scanned_at`, …). Volume must be counted on the
**content** timestamp, not the **sync** timestamp — otherwise "synced 2 min ago, 0 useful rows"
looks healthy.

---

## 3. The sharpest gap: false freshness & silent degradation

The dangerous failure is not a loud crash — it is a source that looks healthy from the outside while
the useful signal has degraded or vanished. Three modes:

1. **Stopped / stuck** — collector stops updating; data is plainly stale. (Caught by the existing
   `last_*_at` timestamp.)
2. **Successful-but-empty / volume-collapse** — collector runs, returns `[]` or a sharply reduced set,
   exits clean, sync marked fresh. **(Not caught today.)**
3. **Structurally-valid-but-meaning-compromised** — rows still write, but the result no longer means
   what it did (the GH-81 class).

Concrete, each already plausible on this system:

- A GitHub PAT loses `repo` scope but keeps `public_repo`; `github_scan` succeeds, private work
  silently drops out → "fresh", 100% — but dead.
- Gmail/Calendar auth breaks into a clean empty list; `ask` confidently answers "nothing happened
  this week."
- `sleuth_reminders` stops syncing; `ask` answers from stale reminder state with full confidence.

**One metric cannot catch all three. Two can:** the existing timestamp catches *stopped*; a recent
row count catches *empty / collapsed*.

---

## 4. Minimal contract surface

Reuse the read-side primitives — **no new pipeline, no new table, no new MCP tool in v1.**

**Per-source derived shape (added to the existing `index_status` source dicts):**

- `recent_row_count_7d` — counted on the source's content timestamp (`_PEEKABLE_SOURCES` column).
- `status` — derived label `ok` | `warn` | `degraded`.
- `reason` — short string, present only when not `ok`.

**Derivation logic (interpret, don't over-fire):**

- `warn`/`degraded` if a source has not advanced its timestamp within its expected window (stale).
- `warn`/`degraded` if it synced recently but `recent_row_count_7d` collapsed to zero (or far below
  its own norm).
- Leave *legitimately* zero-volume cases (a real quiet week) for the host agent to interpret — the
  contract surfaces the anomaly, it does not adjudicate it.

This stays read-only and derivable from existing tables. No source-specific config in v1 unless
Phase 0 proves a source needs a custom window (e.g. calendar's "look back 7d AND forward").

---

## 5. Phased delivery

### Phase 0 — Spike: validate the observe-first contract (1–2h)

**This is a discovery phase — its findings MUST be written back into this doc before its QA gate can
pass (PDDA discovery contract).**

Goal: confirm the schema supports a useful observe-first contract with **zero new tables**, and lock
the per-source window/column choices.

Checklist:

- [ ] Read `get_index_status` end-to-end ([index_ops.py:224](../../src/rebalance/ingest/index_ops.py#L224)):
      confirm the per-source dict shape and whether anything already populates `payload["freshness"]`.
- [ ] Confirm `_safe_count_where` ([index_ops.py:273](../../src/rebalance/ingest/index_ops.py#L273))
      can express `WHERE <ts_col> > <now-7d>` cheaply for each core source (index present? full scan?).
- [ ] Pin the content-timestamp column per source against `_PEEKABLE_SOURCES`
      ([index.py:193](../../src/rebalance/mcp/tools/index.py#L193)); note where `vault` differs (its
      rows live in `vault_files`/`chunks`, not the peekable set).
- [ ] Decide which sources need a custom window vs. the default rolling 7-day count.
- [ ] Produce one concrete `recent_row_count_7d` + derived `status` example for `vault`, `github`,
      `calendar`, and `sleuth` from the live DB.

Exit criteria:

- `last_*_at` and `recent_row_count_7d` are computable cheaply for the core sources, **no new table**.
- The set of sources needing custom windows/columns is named (or confirmed empty).
- **If Phase 0 contradicts the no-new-table assumption, pause and escalate — do not start Phase 1.**

**QA gate:** findings (with `file:line`) written back into this doc; the four example outputs recorded
here; per-source window decisions recorded. `utils/pdda/pdda.sh run` clean for the doc edit.

### Phase 1 — `recent_row_count_7d` in `index_status`

- Add `recent_row_count_7d` to each source dict in `get_index_status`, via `_safe_count_where` on the
  content-timestamp column locked in Phase 0.
- **No ingest change. No gate. No new table.** Pure additive read field.
- Host agents can immediately read it ("you asked about this week but github shows 0 events — token
  scope?") even before `doctor` consumes it.

**QA gate:** new unit test asserts `recent_row_count_7d` is present and correct for ≥2 seeded sources
(incl. a zero-volume case); full `pytest tests/` green; `rebalance doctor` clean. No new file beyond
the test; `index_status` stays read-only.

### Phase 2 — derived `status`/`reason` + one `doctor` warning path

- Derive `status` (`ok`/`warn`/`degraded`) + `reason` per source into `payload["freshness"]` from
  (a) staleness vs. the source's window and (b) zero/collapsed `recent_row_count_7d`.
- Add **one** `doctor` warning path ([cli/__init__.py:114](../../src/rebalance/cli/__init__.py#L114))
  that prints the degraded sources with their `reason`. No new screen, no new job.

**QA gate:** test feeds a fresh-but-empty source and asserts `status == "degraded"` with a non-empty
`reason`, and a healthy source asserts `ok`; `doctor` shows the degraded line on the seeded DB; legit
quiet source does **not** hard-fail (warn only). Full suite green; `doctor` clean.

### Phase 3 — optional: surface degradation at query time (`ask`)

**Kill-gated:** only build if Phase 2's signal catches a *real* defect in live use (see Falsifiability).
If the `index_status`/`doctor` surface already changes behavior, this is unjustified — stop at Phase 2.

- When `ask()` answers from a source whose `status` is `degraded`, prepend a one-line visible warning
  ("⚠ calendar looks fresh but returned 0 rows this week — answer may be incomplete").

**QA gate:** test asserts the warning is prepended when a used source is `degraded` and absent when all
used sources are `ok`; synthesis output is otherwise unchanged; suite green.

---

## 6. Anti-goals

- **Not an ingest gate.** Never stops `refresh_index`, never rejects an upstream row, never blocks a
  sync. Observe-and-downgrade only.
- **Not a new subsystem.** No new table, no new MCP tool, no new pipeline in v1 — extend
  `index_status` + `doctor`, reuse `_safe_count_where` and `payload["freshness"]`.
- **Not a relevance engine.** v1 detects *freshness/volume* degradation. The GH-81 relevance class is
  the motivation, not the v1 deliverable — kept as a shared "signal health" surface, decided in §7.
- **Not an adjudicator of zero.** A legitimately quiet week must not hard-fail; the contract surfaces
  the anomaly for the host agent to interpret.

---

## 7. Falsifiability — this is only worth keeping if it catches real defects

The contract earns its place only if it flags defects the current system misses:

- **Plain staleness:** semantic backfill crashes mid-vault-refresh; `vault` stops updating → flag stale
  `last_*_at` before `ask` serves stale context as current.
- **False freshness:** PAT loses `repo` scope but keeps public; sync still "succeeds" → flag the
  recent-volume collapse instead of reporting fully healthy.
- **Silent empty set:** Gmail/Calendar auth breaks into a clean `[]` → surface "fresh but empty"
  instead of letting `ask` answer "nothing happened."

If, after Phase 2, none of these three is caught on the live DB, **stop** — the contract is not paying
for itself and Phase 3 is unjustified.

---

## 8. Open questions

- Should `ask()` prepend a visible degraded-source warning (Phase 3), or is the `index_status`/`doctor`
  surface enough? (Kill-gated above.)
- Should "expected volume" stay heuristic + agent-interpreted, or should some sources declare an
  explicit floor in config?
- Is a rolling `recent_row_count_7d` enough, or do some sources need bespoke windows (e.g.
  `calendar_30d_back_7d_forward`)? — **decided in Phase 0.**
- Should relevance degradation (GH-81 class) share this "signal health" surface, or stay separate? v1
  ships freshness/volume only; this question is deferred, not answered.

---

## 9. Relationship to existing work (don't duplicate)

This is a **read-side health contract**, distinct from the in-flight signal efforts — it should not
fork them:

- [ROADMAP-SIGNAL-SCAN.md](PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md) — adds a *new `roadmap` collector*
  (a source). This plan instead *grades the health of existing sources*. Complementary: a future
  `roadmap` source would get `recent_row_count_7d` for free.
- [GEMINI-WHATS-NEXT-VAULT.md](GEMINI-WHATS-NEXT-VAULT.md) / [SIGNAL-GENERATION/](../2-WORKING/SIGNAL-GENERATION/) —
  the *synthesis/ranking* plane. This contract feeds it trust metadata; it is not a second ranker.
- [WATCHLIST-COVERAGE-GUARD.md](../2-WORKING/WATCHLIST-COVERAGE-GUARD.md) — already guards *repo
  roster* drop-off via the focus5-snapshot pattern. Reuse its snapshot/anomaly idiom for volume
  collapse rather than inventing a new one.

---

## 10. Verification (per ROUTER §7)

`rebalance doctor` clean + `pytest tests/` green before any success claim on a code phase.
Doc-hygiene: `utils/pdda/pdda.sh run` clean before promoting this doc to `2-WORKING`.
