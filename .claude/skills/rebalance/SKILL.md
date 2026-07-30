---
name: rebalance
description: >
  Morning "what am I working on" brief that fuses the Rebalance/HiQS LIVE work SIGNAL
  (the ranked "what's next" verdict from calendar + GitHub + Sleuth + vault) with a
  deterministic, device-wide scan of RECENT GIT ACTIVITY across every repo on this machine.
  Git activity is the whole picture — current branches, ahead/behind vs trunk, dirty state,
  recent commits — and worktrees are ONE facet of it, not the whole thing. Classifies each
  branch/worktree as active-today / warm / merged / stale and reconciles that against the
  ranked signal into a single synthesized brief. Read-only: it never mutates git. Trigger on
  "live signal", "/rebalance live signal", "what am I working on", "morning brief",
  "active git / worktrees across all repos", "where is my code right now".
---

# Rebalance — Live Signal + Active Git

Answer one question deterministically every morning: **"What am I actually working on right
now?"** — by fusing two independent sources and reconciling them:

1. **The live work signal** — Rebalance/HiQS's ranked "what's next" verdict (calendar,
   GitHub, Sleuth, vault, email), i.e. what the day *says* you should do.
2. **Device-wide recent git activity** — what your repos *show* you are actually building:
   branch tips, divergence from trunk, dirty trees, recent commits. **Worktrees are a subset
   of this, not the point** — a repo with a single branch and fresh commits is just as much
   "active git" as one with five linked worktrees.

The value is in the reconciliation: the signal is often meeting/client-heavy while your
hands-on-keyboard code lives in a different repo entirely. Surface both, and where they
diverge, say so.

## Guardrails (read first)

- **Read-only. This skill never mutates git.** The collector runs only `find`, `git
  rev-parse/log/status/rev-list/worktree list`. No `rm`, `mv`, `prune`, `gc`, `branch -D`,
  or `--force` — ever, in the script or in follow-up commands you run for this skill.
- If synthesis leads you to *offer* cleanup (e.g. pruning merged worktrees), that is a
  **separate, explicitly-confirmed action** governed by `WORKTREE-SAFETY.md` at the repo
  root: use `git worktree remove` / `prune` / `repair`, never hand-`rm`, and never default
  to `--force` to silence a refusal (dirty worktrees refuse for a reason — the dirt may be
  real WIP, not throwaway). Confirm the dirty files are disposable before removing.
- The collector parses `git worktree list --porcelain` (stable API), never the
  human-readable table — matching `WORKTREE-SAFETY.md` §5/§12.

## Procedure (deterministic)

### Step 1 — Read the live work signal (cheap, cached)

Call `mcp__rebalance__get_next_actions` (MCP tool). It returns the persisted ranked verdict
the dashboard shows — no recompute, no model load. Capture: the ranked list (title / person /
source / evidence / why), `computed_at`, and `model_used`.

- If it errors or returns an empty ranking, fall back to
  `mcp__rebalance__ask(query="what should I work on next", skip_synthesis=true)` and read the
  `hiqs` key (same persisted ranking).
- Note the freshness: if `computed_at` is stale (hours old / yesterday), say so in the brief —
  don't present a stale ranking as this-minute truth.

### Step 2 — Collect device-wide git activity (deterministic, read-only)

Run the bundled collector (invoke with `bash`; it needs no execute bit and is CWD-independent
because it scans absolute roots):

```bash
bash "<skill_dir>/collect.sh"
```

Where `<skill_dir>` is this SKILL.md's directory. Optional knobs (defaults are the standard):

- `LSAG_WINDOW_DAYS=7` — "recent" horizon for commits and warm/active classification.
- `LSAG_DIRTY_GRACE_DAYS=30` — uncommitted changes only count as activity if the repo was
  also touched within this window (stray dirt in an abandoned clone is noise, not work).
- Positional args override the scan roots (default: `~/Documents`, `~/Local Sites`,
  `~/Valet-Sites`, `~/wt`, `~/bin`, `~/…/05 - Local Installs`, `~/.claude`).

The collector emits a structured report. Per active repo group (deduped by shared
`git-common-dir`, so each worktree set appears once) it prints, **for every worktree**:

```
## REPO <primary worktree path>
common_dir=… worktrees=<n>
  pdda=yes inbox=<n> working=<n>                       # OPTIONAL — only for PDDA repos
    working_doc=<basename> mtime=<YYYY-MM-DD HH:MM>     #   newest ≤3 active-effort docs
  - WORKTREE <path>
    kind=primary|linked branch=… fresh=<TAG> base=<trunk> behind=<n> ahead=<n> dirty=<n> age_days=<n>
    last_commit=<hash date subject>
    recent_commits(<=Nd): …
```

**Freshness tags** (deterministic, from age + divergence-vs-trunk):

| Tag | Meaning |
|-----|---------|
| `ACTIVE` | committed today (age_days ≤ 0) — hands-on-keyboard right now |
| `WARM`   | carries unmerged commits (`ahead > 0`), committed within the window — in-flight |
| `STALE`  | carries unmerged commits (`ahead > 0`), older than the window — parked/forgotten |
| `MERGED` | no unmerged commits (`ahead == 0`) **and** behind trunk — work has landed; cleanup candidate |
| `SYNCED` | no unmerged commits and level with trunk (`ahead == 0, behind == 0`) — nothing outstanding |

`ahead`/`behind` are measured against the **trunk** (`origin/HEAD` → development/main),
so `ahead` = unmerged commits this branch carries and `ahead==0` = nothing unmerged.
**WARM/STALE require `ahead > 0`** — a branch level with or merged into the trunk carries no
unmerged work and is therefore `SYNCED`/`MERGED`, never WARM/STALE. In the synthesis, group
`SYNCED` with the quiet/no-action repos (it is "in sync, nothing to do", not in-flight work).

**Optional PDDA annotation** (a THIRD, *advisory* axis — the repo's own declared intent). It is
emitted **only** for repos carrying `PROJECT/PDDA.md`, and is absent otherwise — so a non-PDDA
repo's output is byte-for-byte unchanged. Fields: `pdda=yes`, lifecycle counts `inbox=`/`working=`
(all `*.md` under `PROJECT/1-INBOX`/`2-WORKING`), and the newest ≤3 `2-WORKING/*.md` docs with
their `mtime`. Treat it as **look-for-but-don't-rely-on**: it is *filesystem* state, not git —
mtime order/membership can shift on a bare touch or checkout — so it **never** affects a freshness
tag and sits outside the determinism guarantee. Any `status:`/ROADMAP prose it leads you to is
*declared intent that may be stale*, and never overrides a git fact.

### Step 3 — Synthesize the brief (fixed structure)

Read the collector output and the signal, then produce **one** brief with these sections, in
order. Keep it tight; lead with the reconciliation, not raw dumps.

1. **What the signal says today** — a compact ranked table from Step 1 (top ~5 rows: what /
   when / source), plus the single most actionable *buildable* (non-meeting) item. Flag if
   the ranking is stale.
2. **Where the code actually is** — group Step 2 output by freshness, **🔥 ACTIVE → 🌤 WARM →
   🪪 STALE → 🪦 MERGED**. For each active/warm repo give one line: repo, branch, ahead-of-trunk,
   dirty, last-commit subject + time. Call out worktree topology where it exists (e.g. "3
   worktrees, one detached") but do **not** frame the whole section as "worktrees" — it's git
   activity, of which worktrees are a part. `MERGED` worktrees go in a short cleanup list; `SYNCED`
   repos are "in sync, nothing to do" — fold them into a one-line count, don't itemize.
   **Optional (only where `pdda=yes`):** you MAY append one *advisory* declared-intent line by
   matching a `working_doc=` basename to a reported branch on the `gh-NNN` token
   (`GH-169-*.md` ↔ `…gh-169…`), e.g. `↳ PDDA: intent doc GH-169 touched 2026-07-21 22:08
   (advisory)`. You may open a matched doc to read its `status:`/`## Status` as declared intent —
   labelled possibly-stale, never overriding the git freshness tag.
3. **Bottom line** — reconcile the two (three where `pdda=yes` adds declared intent): name the
   repo/branch you're truly working in right now (usually the freshest ACTIVE commit, which may
   differ from what the signal ranks first), then 1–3 concrete follow-ups (e.g. "gh-57 is
   relay-approved and 500 ahead — ripe to land"; "N rebalance-OS worktrees are merged — safe to
   prune per WORKTREE-SAFETY.md"). When offering to prune a `MERGED` worktree of a PDDA repo,
   cross-check its doc: a matching doc still in `PROJECT/2-WORKING/` = paperwork open (say so);
   one already in `3-DONE/`/`3-COMPLETED/` = clean to prune.

### Step 4 — Offer, don't act

End by offering the obvious next moves (dig into the live marathon, verify a relay-approved
branch is landable, safely prune merged worktrees). Do **not** perform any mutating or
outward-facing action without explicit confirmation, per the guardrails above.

## Notes

- Deterministic given tree state + window: same inputs → same **git** report shape and tags. The
  optional PDDA annotation is the one exception — it is advisory filesystem (mtime) state, so its
  values, order, and membership can move without a git/content change; it never feeds a tag.
- Read-only by construction: the collector runs only `find`, read-only `git`, and read-only file
  utilities (`ls`/`stat`/`grep`/`awk`/…). It **never** executes a repo-owned script such as
  `pdda.sh` — the PDDA annotation is pure filesystem probing.
- macOS-safe: the collector avoids `declare -A` (bash 3.2) and creates **no temp files**
  (sandbox-safe; the repo list lives in a shell variable). `pdda_mtime` is OS-selected (BSD vs GNU
  `stat`). A bundled `test-pdda-annotation.sh` smoke-tests the PDDA annotation (happy path +
  additivity + spaces + mtime format).
- Fast filtering: quiet single-worktree repos (old head, clean, or ancient-dirt) are skipped;
  multi-worktree groups are always reported because topology is itself signal.
