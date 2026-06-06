# Open-PR Merge Sequence Plan — 2026-06-06

**Author:** Claude Code (analysis) — for Codex review
**Repo:** `Hypercart-Dev-Tools/rebalance-OS`
**Goal:** Land all three open PRs into `development` in an order that minimizes
conflict churn and guarantees every feature, migration, and doc lands intact.

> **Reviewer ask (Codex):** Please sanity-check the conflict matrix, the
> migration-collision reasoning, and the recommended order. Flag anything that
> would cause a feature, table, or migration to silently drop. All claims below
> are reproducible with the commands in the Appendix.

> **Rev 2 (2026-06-06) — Codex review incorporated.** Verified all findings
> against an authoritative sequential merge (`commit-tree` chain, not pairwise):
> (1) expanded the `semantic_index.py` must-union resolution — both PRs edit the
> same `_normalize_sources` lines; (2) fixed the backup ref-naming bug;
> (3) added an existing-v1-DB upgrade check for #55's baseline-schema edit;
> (4) corrected step-2/step-3 conflict sets (config.py is **not** a step-3
> conflict). Added a concrete **cherry-pick path for #49** (it's a single commit).

---

## ✅ Decision — 2026-06-06: land #55 + #54 today, defer #49

**Scope today:** merge **#55** then **#54** into `development`. **#49 (figma) is
deferred**, and the `development → main` promotion is deferred.

**Why:** every *silent*-failure risk in this batch belongs to #49 — it owns the
migration `0002` collision (drop it and #54's `0002`/`0003` land clean) and the
`semantic_index.py` source-union trap (that's #49-vs-#55). Without #49, #55 is a
clean merge and #54 has a single easy `config.py` conflict — ~2 of 3 features,
near-zero risk, ~15 minutes. Figma comments are not needed urgently; #49 is a
self-contained single commit (`81e06b8`) that will rebase/re-cut more cleanly
against a stable `development` when it's actually wanted.

Sections below for **#49 (Step 3)** and **promotion** are retained but marked
**DEFERRED** — they are the runbook for if/when we pick figma back up.

One maintainability item to address regardless of #49: **#55 edits the frozen
baseline schema** instead of a numbered migration (Risk 3) — convert to a
migration as a fast-follow.

---

## TL;DR

Recommended merge order: **#55 → #54 → #49**

1. **#55** (Chat with your data) — merges clean today; merge first as the anchor.
2. **#54** (Focus 5) — one conflict, `config.py` (vs development); keep both blocks.
3. **#49** (Figma collector) — heaviest/stalest, a **single commit**; land last
   **and renumber its migration `0002_add_figma_comments.sql` →
   `0004_add_figma_comments.sql`.** Conflicts: `MEMORY.md`, `index_ops.py`,
   `semantic_index.py`. Because it's one commit, **cherry-pick/rebase onto the
   integrated `development` is the recommended mechanic** (see
   [Step 3](#step-3--land-49-codexadd-data-collector-for-figma-api-comments)).

Two highest-risk items, both **silent** (no error, no failed test):

- **Migration number collision** (#49 & #54 both ship `0002_*`). If not
  renumbered, the forward-only runner skips the loser → missing table.
- **`_normalize_sources` union** in `semantic_index.py`. #49 adds `"figma"`,
  #55 adds `"code"` to the *same lines*. A take-one-side merge drops a whole
  source from default/`all` coverage. Details in [Risks](#critical-risks).

---

## PR inventory

All three target `development` (not `main`). `development` is **63 commits
ahead of / 1 behind `main`**, i.e. it is the integration branch.

| PR | Title | Branch | vs `development` today | New collector | Migrations | Age |
|----|-------|--------|------------------------|---------------|------------|-----|
| **#55** | Chat with your data (FTS+RRF / native code corpus) | `feature/chat-with-data-phase1-hybrid` | ✅ MERGEABLE (clean) | `code` | none (edits `db/schema.py` directly) | 2026-06-06 |
| **#54** | Focus 5 Phase 1+2 (device-local repo collector + `/focus-5` web view) | `feature/focus5-phase1` | ⚠️ conflict: `config.py` only | `focus5`, `ask_self` | `0002_ask_self_indexes`, `0003_focus5_roster` | 2026-06-06 |
| **#49** | Add Figma comments collector | `codex/add-data-collector-for-figma-api-comments` | ⚠️ conflict: `MEMORY.md`, `index_ops.py` | `figma` | `0002_add_figma_comments` ← **collides** | 2026-06-02 |

### Functional independence (verified)

The three features do **not** depend on each other. Each PR only imports its own
new modules; none imports another PR's new module:

- #49 → `rebalance.ingest.figma`
- #54 → `rebalance.ingest.focus5_scan`, `rebalance.ingest.ask_self_scan`
- #55 → `rebalance.ingest.code_collector`, `rebalance.chat`

Each registers a distinct collector name in the central registry
(`src/rebalance/ingest/index_ops.py`) via `register_collector(...)`. So ordering
is purely about **conflict-resolution cost** and **migration numbering**, not
build-order correctness.

---

## Shared files / collision surface

| File | #49 | #54 | #55 | Notes |
|------|:---:|:---:|:---:|-------|
| `src/rebalance/ingest/index_ops.py` | ✎ | ✎ | ✎ | Collector registry — each adds one `register_collector(...)` line |
| `src/rebalance/mcp/tools/index.py` | ✎ | ✎ | ✎ | MCP tool registry — additions land in different regions, **auto-merge** in all trials |
| `src/rebalance/ingest/config.py` | ✎ | ✎ | — | #54 vs #49 config blocks overlap |
| `src/rebalance/ingest/semantic_index.py` | ✎ | — | ✎ | #49 figma backfill vs #55 code backfill |
| `src/rebalance/ingest/db/semantic.py` | ✎ | — | ✎ | auto-merges in trials |
| `db/migrations/000X_*.sql` | ✎ | ✎ | — | **`0002` number collision** (see Risks) |
| `MEMORY.md` | ✎ | ✎ | — | doc index, trivial |

### Conflict matrix — authoritative sequential merge

Pairwise `merge-tree` trials use each branch's own merge-base and are noisy, so
the numbers below come from a **real sequential chain** (`commit-tree` to carry
each merge forward) in the recommended order. This is the signal that matters:

| Step | Merge | Result | Conflicting files |
|------|-------|--------|-------------------|
| 1 | #55 into `development` | ✅ clean | — |
| 2 | #54 into (dev+#55) | ⚠️ | `config.py` |
| 3 | #49 into (dev+#55+#54) | ⚠️ | `MEMORY.md`, `index_ops.py`, `semantic_index.py` |

Corrections vs the first draft of this plan:

- **Step 2's `config.py` conflict is #54-vs-`development`, not #54-vs-#55.** #55
  does not touch `config.py` at all — `development` diverged from #54's
  merge-base. The operator resolves it either way; the cause just isn't #55.
- **Step 3 does *not* conflict in `config.py`.** The earlier draft listed it;
  the sequential merge proves #49's `config.py` changes auto-merge against the
  integrated base. Real step-3 set is the three files above.
- The new high-severity item is `semantic_index.py` at step 3 — see Risk 2.

---

## Critical risks

### 1. Migration `0002` collision (#49 vs #54) — silent data loss if unhandled

`development/src/rebalance/ingest/db/migrations/` currently has **only
`README.md`** (no numbered migrations). Then:

- **#49** adds `0002_add_figma_comments.sql`
- **#54** adds `0002_ask_self_indexes.sql` **and** `0003_focus5_roster.sql`

The forward-only runner (`db/migrate.py`) derives the applied **version from the
numeric prefix** (confirmed by `tests/test_db_migrations.py`: applying a
`0002_*` file makes `run_migrations` return `2`). If two files both claim
`0002`, the runner applies the first sorted one, sets `version = 2`, then sees
`version >= 2` for the second and **skips it with no error**. The losing
migration's table/indexes never get created.

**Mitigation:** the PR that lands **second** renumbers. With #49 last, that means
renaming **one** file: `0002_add_figma_comments.sql` → `0004_add_figma_comments.sql`.
(If #49 were merged before #54 instead, you'd have to renumber **both** of #54's
files — more churn. This is the main reason #49 goes last.)

`tests/test_db_migrations.py` uses a temp dir and discovers by glob+numeric sort,
so it does **not** hardcode the real filenames — the rename is safe for the test.

### 2. `semantic_index.py` — must **union**, not pick-a-side (#49 after #55) — silent coverage loss

This is the highest-severity *resolution* risk (vs the migration, which is a
*numbering* risk). #49 and #55 edit the **same lines** of `_normalize_sources`,
plus overlapping regions of `backfill_semantic_documents()` and `embed_pending()`.

Baseline (`development`):

```python
def _normalize_sources(source_types):
    if source_types is None:
        return ("vault", "github", "email")        # <-- both PRs edit this
    ...
        if item == "all":
            return ("vault", "github", "email")    # <-- and this
        if item not in {"vault", "github", "calendar", "sleuth", "email"}:  # <-- and this
            raise ValueError(...)
```

- **#55** turns the valid-set into `{..., "email", "code"}` (and adds `"code"` to
  the default/`all` tuples + a `sync_code_documents` branch in backfill + a
  `"code" in selected_sources` branch in embed).
- **#49** turns the same lines into `("vault","github","email","figma")` and
  `{..., "email", "figma"}` (and adds a figma sync branch in backfill/embed).

A naive resolver that takes one side yields, e.g., `("vault","github","email","code")`
— **`figma` is silently dropped** from default and `all` coverage and rejected by
the valid-set. No migration runs, no test necessarily fails; the figma collector
just never appears in a default semantic refresh/query. (Symmetric risk for
`code` if the other side wins.)

**Required resolution — keep BOTH in every spot:**

1. `_normalize_sources`: both `return` tuples become
   `("vault", "github", "email", "code", "figma")`; valid-set becomes
   `{"vault", "github", "calendar", "sleuth", "email", "code", "figma"}`.
2. `backfill_semantic_documents()`: keep **both** the `sync_code_documents` and
   the figma-sync branches.
3. `embed_pending()`: keep **both** source-set additions (`code` and `figma`).

Verify after resolution: `_normalize_sources(None)` and `_normalize_sources(["all"])`
each return a tuple containing **both** `"code"` and `"figma"`.

### 3. #55 edits the *frozen baseline* schema (not a migration) — validate the upgrade path

Per `db/schema.py` (~line 567): the `ensure_*_schema` functions "stay frozen at
the baseline … see db/migrations/README.md," and `BASELINE_SCHEMA_VERSION = 1`.
#55 nonetheless edits `ensure_semantic_schema()` to add the `semantic_documents_fts`
FTS5 table + AI/AD/AU triggers, rather than shipping a numbered migration. It is
written to be upgrade-safe (an `FTS_VERSION` guard that drop/rebuilds on change,
plus a one-time backfill for DBs that predate the FTS table), so it works — but
it deviates from the migrations-not-baseline contract.

Consequence for validation: a **fresh-DB** check is insufficient. The post-merge
check must also **upgrade an existing v1 DB** (one with rows in
`semantic_documents`) and assert the FTS table + triggers appear and the one-time
backfill populated them. See the post-merge step. (Open question for Codex:
should this instead be a real numbered migration?)

### 4. Collector registry (`index_ops.py`)

All three append a `register_collector(...)` call. These collide as adjacent
edits, but resolution is mechanical: **keep every registration**. Watch the
`included_in_all=False` flags (#54 sets them on `focus5`/`ask_self`) — preserve
them exactly.

### 5. Staleness of #49

#49 is from 2026-06-02 and also touches `ARCHITECTURE.md`, `CHANGELOG.md`,
`semantic.py`, `semantic_index.py`. It is a **single commit** (`81e06b8`), which
makes cherry-pick/rebase onto the integrated base clean — see Step 3.

---

## Recommended sequence

### Step 1 — Merge #55 (`feature/chat-with-data-phase1-hybrid`)

- Clean against `development` today; zero-friction anchor.
- No migration file → nothing to renumber.
- Merging it first keeps it clean. (If #54/#49 landed first, #55 would *gain* an
  `index_ops.py` conflict it doesn't currently have.)
- **After merge:** run the suite, confirm the `code` collector registers.

### Step 2 — Merge #54 (`feature/focus5-phase1`)

- Expected conflict: `config.py` only — and it's **#54 vs `development`** (#55
  doesn't touch `config.py`). Resolve by keeping both config blocks.
- No `index_ops.py` collision with #55 (different regions).
- Migrations `0002_ask_self_indexes` + `0003_focus5_roster` land cleanly (no
  numbered migrations exist yet).
- **After merge:** suite green; `focus5` + `ask_self` collectors register;
  `/focus-5` web view loads.

### Step 3 — Land #49 (`codex/add-data-collector-for-figma-api-comments`) — ⏸️ DEFERRED (2026-06-06)

> **Deferred per the decision above.** Do not run this step today. It is the
> runbook for if/when figma comments are picked back up. When you do, re-verify
> the conflict set against the then-current `development` (it will have moved).

**Mechanic: cherry-pick / rebase (recommended).** #49 is a single commit
(`81e06b8`). Replaying it onto the integrated `development` lets you resolve all
conflicts + apply the migration rename in one atomic step with linear history,
instead of a merge commit full of resolutions:

```bash
git switch development && git pull            # now contains #55 + #54
git cherry-pick 81e06b8                        # stops on the 3 conflicts below
git mv src/rebalance/ingest/db/migrations/0002_add_figma_comments.sql \
       src/rebalance/ingest/db/migrations/0004_add_figma_comments.sql   # mandatory, see Risk 1
# ...resolve the 3 files (below), then:
git cherry-pick --continue
```

> The cherry-pick changes the SHA, so GitHub won't auto-close PR #49. After
> pushing `development`, close #49 manually with a note: "landed via cherry-pick
> of 81e06b8 onto development, migration renamed to 0004." A plain merge of the
> PR branch works too and resolves the *same* conflicts — pick whichever your
> review process prefers; the cherry-pick is just cleaner history for a 1-commit PR.

**Conflicts to resolve (3 files — authoritative sequential set):**

  - `MEMORY.md` — doc index, trivial (keep both entries).
  - `index_ops.py` — add `register_collector("figma")` alongside the others.
  - `semantic_index.py` — **union, do not pick a side** (see Risk 2): both
    `_normalize_sources` tuples + valid-set must contain `code` *and* `figma`;
    keep both backfill branches and both `embed_pending` source-sets.
  - (`config.py` does **not** conflict at this step — corrected from draft 1.)

- **After merge:** see the post-merge validation below — fresh-DB migration check,
  existing-v1-DB upgrade check, `_normalize_sources` union assertion, full suite.

---

## Post-integration validation (on `development`, before promotion)

Run all of these once #49 is in. They target the two *silent* failure modes.

1. **Full suite** green on `development`.
2. **Migration — fresh DB:** create a new DB, run `run_migrations`, assert the
   final version matches the highest prefix (now `0004`) and that
   `figma_comments`, the ask_self indexes, and the focus5 roster table all exist.
3. **Migration — no duplicate prefixes:** assert no two files in `db/migrations/`
   share a numeric prefix (guards the `0002` class of bug from recurring).
4. **#55 baseline-schema upgrade (Risk 3):** start from an **existing v1 DB**
   that already has rows in `semantic_documents`, run the app's schema-ensure
   path, then assert `semantic_documents_fts` + its `_ai/_ad/_au` triggers exist
   and the one-time backfill populated the FTS table (`count(fts) == count(docs)`).
5. **Source union (Risk 2):** assert `_normalize_sources(None)` and
   `_normalize_sources(["all"])` each return a tuple containing **both** `"code"`
   and `"figma"`; assert both are accepted (not `ValueError`) by the valid-set.
6. **Collectors registered:** `figma`, `code`, `focus5`, `ask_self` all present in
   the registry, with `focus5`/`ask_self` still `included_in_all=False`.

---

## Post-merge — promote `development → main` (backup measure) — ⏸️ DEFERRED (2026-06-06)

> **Deferred per the decision above.** Not part of today's work. Retained as the
> runbook for a future `development → main` promotion. Also note the force-push
> rollback in (D) is a break-glass option only — on a shared `main`, prefer the
> revert-PR path.

After all three PRs land and the suite is green on `development`, promote it to
`main` as a single integration step. `development` is currently **63 commits
ahead of / 1 behind `main`**, so this is also the moment to capture a known-good
checkpoint of `main` *before* the big advance — the backup half of this plan.

### A. Capture a rollback point first (the "backup")

Use **distinct** names for the tag and the branch (a tag and branch sharing a
name make `git push origin <name>` ambiguous), and push **explicit refspecs**:

```bash
git fetch origin --quiet
# Immutable, annotated tag of main as it stands today
git tag -a backup/main-pre-merge-2026-06-06 origin/main \
  -m "main snapshot before development promotion 2026-06-06"
# Separate safety BRANCH with a different name
git branch backup-main-pre-merge-2026-06-06 origin/main
# Push each via its fully-qualified ref so neither is ambiguous
git push origin refs/tags/backup/main-pre-merge-2026-06-06
git push origin refs/heads/backup-main-pre-merge-2026-06-06
```

This guarantees a one-command rollback target regardless of what the promotion
merge does. Keep both until `main` has been validated in the wild.

### B. Reconcile the "1 behind"

`main` has **1 commit `development` does not** (the `1` in `1\t63`). Before
promoting, pull that commit into `development` so the promotion is a clean
fast-forward / no-surprise merge and nothing on `main` is lost:

```bash
git rev-list --left-right --oneline origin/main...origin/development | grep '^<'  # the main-only commit(s)
# merge main into development, resolve if needed, push development
```

Re-run the suite on `development` after this reconcile.

### C. Promote via a single integration PR (preferred over fast-forward)

```bash
gh pr create --base main --head development \
  --title "Integrate development → main (figma + focus5 + chat-with-data)" \
  --body "Promotes development after merging #55, #54, #49. Backup tag: backup/main-pre-merge-2026-06-06"
```

- A PR (not a raw fast-forward) gives CI a gate and a reviewable diff for the
  full 63-commit advance.
- Squash is **not** recommended here — preserve history so individual features
  remain bisectable on `main`. Use a merge commit.
- **After merge to main:** run migrations on a fresh DB from `main` and assert
  the final migration version + all three new tables/indexes
  (`figma_comments`, ask_self indexes, focus5 roster) exist. This is the real
  end-to-end check that the `0002→0004` renumber held.

### D. Rollback procedure (if main goes bad post-promotion)

```bash
# Hard reset main to the backup tag (requires permission to force-push main).
# Use the fully-qualified source ref to avoid tag/branch ambiguity.
git push origin refs/tags/backup/main-pre-merge-2026-06-06:refs/heads/main --force-with-lease
# …or, if force-push to main is disallowed, open a revert PR of the merge commit:
gh pr create --base main --head revert/development-promotion --title "Revert development→main promotion"
```

Prefer the revert-PR path on a protected `main`; keep `--force-with-lease` as the
break-glass option only.

> **Note on branch protection:** steps A–D assume the operator has push/tag
> rights and (for D) either force-push or revert-merge permission on `main`.
> Confirm before relying on the force-push rollback.

---

## Open questions for Codex

1. **Frozen-baseline (Risk 3):** should #55's FTS5 table/triggers be moved out of
   `ensure_semantic_schema()` into a real numbered migration to honor the
   schema.py frozen-baseline contract — or is the `FTS_VERSION`-guarded
   ensure-path acceptable as-is? This doesn't change merge order either way.
2. **Migration numbering:** `0004_add_figma_comments.sql` (figma last, one rename)
   confirmed acceptable in your review — flag if you'd rather figma keep `0002`
   and bump focus5/ask_self instead.

Resolved since draft 1 (kept here for the audit trail):

- ~~Hidden ordering constraint in `semantic_index.py`?~~ → It's a content
  collision in `_normalize_sources`/`backfill`/`embed`, resolved by **union**
  (Risk 2), not an ordering constraint.
- ~~Rebase #49 vs merge-commit?~~ → #49 is one commit; **cherry-pick/rebase**
  onto integrated `development` is the recommended mechanic (Step 3).

---

## Appendix — reproduce the analysis

```bash
# Open PRs
gh pr list --state open --json number,title,headRefName,baseRefName,mergeable

# development vs main divergence  (prints "1\t63")
git fetch origin --quiet
git rev-list --left-right --count origin/main...origin/development

# Migration files per branch
for b in development \
         codex/add-data-collector-for-figma-api-comments \
         feature/focus5-phase1 \
         feature/chat-with-data-phase1-hybrid; do
  echo "--- $b ---"
  git ls-tree -r --name-only origin/$b -- src/rebalance/ingest/db/migrations/
done

# Each PR merged into current development (in-memory)
for b in codex/add-data-collector-for-figma-api-comments \
         feature/focus5-phase1 \
         feature/chat-with-data-phase1-hybrid; do
  echo "=== $b ==="
  git merge-tree --write-tree origin/development origin/$b | grep CONFLICT || echo CLEAN
done

# Pairwise branch collisions (noisy — uses each pair's own merge-base)
git merge-tree --write-tree origin/codex/add-data-collector-for-figma-api-comments origin/feature/focus5-phase1 | grep CONFLICT
git merge-tree --write-tree origin/codex/add-data-collector-for-figma-api-comments origin/feature/chat-with-data-phase1-hybrid | grep CONFLICT
git merge-tree --write-tree origin/feature/focus5-phase1 origin/feature/chat-with-data-phase1-hybrid | grep CONFLICT

# AUTHORITATIVE sequential chain (#55 -> #54 -> #49) via commit-tree.
# Reports the real per-step conflict set used in the table above.
dev=$(git rev-parse origin/development)
pr55=$(git rev-parse origin/feature/chat-with-data-phase1-hybrid)
pr54=$(git rev-parse origin/feature/focus5-phase1)
pr49=$(git rev-parse origin/codex/add-data-collector-for-figma-api-comments)
T1=$(git merge-tree --write-tree $dev $pr55 | head -1)              # step 1 (clean)
C1=$(git commit-tree $T1 -p $dev -p $pr55 -m sim55)
echo "STEP2:"; git merge-tree --write-tree $C1 $pr54 | grep CONFLICT  # -> config.py
T2=$(git merge-tree --write-tree $C1 $pr54 | head -1)
C2=$(git commit-tree $T2 -p $C1 -p $pr54 -m sim54)
echo "STEP3:"; git merge-tree --write-tree $C2 $pr49 | grep CONFLICT  # -> MEMORY.md, index_ops.py, semantic_index.py

# The _normalize_sources collision (Risk 2): both PRs edit the same lines
git show origin/development:src/rebalance/ingest/semantic_index.py | sed -n '66,80p'
git diff $(git merge-base $dev $pr49) $pr49 -- src/rebalance/ingest/semantic_index.py | grep -E '"figma"'
git diff $(git merge-base $dev $pr55) $pr55 -- src/rebalance/ingest/semantic_index.py | grep -E '"code"'

# #49 is a single commit (cherry-pick feasibility)
git rev-list --count $(git merge-base $dev $pr49)..$pr49   # -> 1
```
