---
gh_issue: 193
title: "GH-193 implementation plan — optional PDDA lifecycle signal for the rebalance skill"
status: "PLAN — concrete implementation spec for /relay-xyz (Codex) review before build."
created: 2026-07-22
doc_type: tooling
roadmap_exempt: true
---

# GH-193 — Implementation plan (review target)

Concrete spec for the optional PDDA lifecycle signal in `.claude/skills/rebalance/`. Parent
capture + why/triage: [GH-193-REBALANCE-PDDA-LIFECYCLE-SIGNAL.md](GH-193-REBALANCE-PDDA-LIFECYCLE-SIGNAL.md).
This doc is the artifact under `/relay-xyz` review; it carries the actual diffs so Codex critiques
real code, not intent.

## Design invariants (non-negotiable)

1. **Additive & optional.** Non-PDDA repos emit **exactly** today's output — the PDDA block is only
   printed when a PDDA marker exists, so absence == no change (strict byte-for-byte for non-PDDA repos).
2. **Structural facts only in the collector.** No prose parsing. **No execution of `pdda.sh` or any
   repo-owned script.** Filesystem probes only (`test -f`, `ls`, `stat`).
3. **PDDA never feeds the git freshness tag.** `fresh_tag()` inputs are unchanged; the PDDA block is
   emitted on a separate line and consumed only by the (advisory) synthesis layer.
4. **Determinism caveat, stated honestly.** Report *shape* stays deterministic. `mtime` values are
   wall-clock filesystem metadata (a checkout can bump them without content change) — hence PDDA is
   explicitly an *advisory, allowed-stale* signal, quarantined in its own `pdda_*` fields.
5. Preserve GH-190 guards: macOS bash 3.2 (no `declare -A`), no temp files, CWD-independent.

## Collector patch (`collect.sh`)

### (a) new helper, beside `fresh_tag()` (after line 95)

```bash
# mtime as a stable ISO string; BSD stat (macOS) first, GNU stat fallback. Advisory only.
pdda_mtime() {
  stat -f '%Sm' -t '%Y-%m-%d %H:%M' "$1" 2>/dev/null \
    || { stat -c '%y' "$1" 2>/dev/null | cut -d. -f1; }
}
```

### (b) per-repo PDDA block, emitted once after the `common_dir=` header (after line 136)

`$primary` is already the primary-worktree root (repo root), where `ROUTER.md` / `PROJECT/` live.

```bash
  # --- optional PDDA lifecycle annotation (structural only; advisory; never
  #     alters a freshness tag; emitted ONLY when a PDDA marker exists, so
  #     non-PDDA repos are byte-for-byte unchanged). Reads the filesystem only;
  #     it NEVER runs pdda.sh or any repo-owned script. ---
  if [ -f "$primary/ROUTER.md" ] || [ -f "$primary/PROJECT/PDDA.md" ]; then
    inbox_n=$(ls "$primary"/PROJECT/1-INBOX/GH-*.md 2>/dev/null | grep -c .)
    working_n=$(ls "$primary"/PROJECT/2-WORKING/*.md 2>/dev/null | grep -c .)
    echo "  pdda=yes inbox=$inbox_n working=$working_n"
    # newest up-to-3 active-effort docs: basename + mtime, no prose parsing.
    ls -t "$primary"/PROJECT/2-WORKING/*.md 2>/dev/null | head -3 | while read -r wd; do
      echo "    working_doc=$(basename "$wd") mtime=$(pdda_mtime "$wd")"
    done
  fi
```

### Emitted shape (PDDA repo)

```
## REPO /Users/noelsaw/Documents/rebalance-OS
common_dir=… worktrees=6
  pdda=yes inbox=7 working=5
    working_doc=GH-169-COMMIT-HISTORY-COVERAGE.md mtime=2026-07-21 22:08
    working_doc=GH-136-DASHBOARD-REDESIGN.md mtime=2026-07-21 22:08
    working_doc=GH-164-COGNEE-INTEGRATION-PLAN.md mtime=2026-07-19 16:56
  - WORKTREE …            # unchanged git block follows
```

**Open choice for review:** emit block only when `pdda=yes` (chosen, for strict additivity) vs.
always emit `pdda=no` for parse uniformity. Leaning additive.

## Synthesis patch (`SKILL.md`)

**Step 2 (collector legend):** document the three new optional fields (`pdda=`, `inbox=`/`working=`,
`working_doc=…/mtime=…`) and state plainly they are advisory and never affect the freshness tag.

**Step 3 §2 "Where the code actually is":** add an optional annotation, only where `pdda=yes`:

- Match a `working_doc=` basename to a reported branch (`GH-169-*.md` ↔ `feat/gh-169-*`, case-insensitive
  on the `gh-NNN` token). On a match, append a one-line *declared-intent* note:
  `↳ PDDA: intent doc GH-169 touched 2026-07-21 22:08 (advisory)`.
- The model MAY open a matched doc to read its `status:` frontmatter / `## Status` table when it would
  sharpen the brief — presented as *declared intent, possibly stale*, never overriding a git fact.

**Step 3 §3 "Bottom line" — sharper cleanup calls:** for a `MERGED` worktree, cross-check whether its
matching doc still sits in `2-WORKING/` (paperwork open → mention before offering prune) vs. already in
`3-DONE/`/`3-COMPLETED/` (clean → safe to prune per WORKTREE-SAFETY.md).

**New guardrail line in SKILL.md:** "PDDA lifecycle data is an *advisory* third axis. It never changes
the ACTIVE/WARM/MERGED/SYNCED tag (git-only), and the collector never executes `pdda.sh` or any repo
script — it reads the filesystem. Treat `status:`/ROADMAP prose as declared intent that may be stale."

## Test / litmus (matches capture QA)

- Non-PDDA repo (e.g. `cognee`, `claudian`) block is unchanged — diff the collector output before/after.
- `grep -nE 'pdda\.sh|rm |mv |prune|gc |--force|-D ' collect.sh` → only comments/safe matches.
- `bash -n collect.sh` clean; live run annotates the 6 PDDA repos, freshness tags identical to pre-change.
- Stale case: a `working_doc` mtime newer than the branch's last commit is shown as advisory, tag untouched.

## Out of scope

- No `pdda.sh` invocation, no PDDA compliance reporting, no ROADMAP prose parsing in shell.
- No change to HiQS ranking or to `fresh_tag()` logic.

## Adjudication — Codex `/relay-xyz` review (2026-07-22)

Codex (via `consult.sh`, cross-repo read of the whole repo) returned **Changes requested**, all
findings `file:line`-cited. Adjudicated against GUIDING-PRINCIPLES.md / AGENTS.md — **all accepted**
(each independently verified; none conflicted with the principles — they strengthen the Attested/
honest signal bar and P9 verified-done):

- **[Blocker] GNU `stat -f` fallback corrupts output** → accepted. `pdda_mtime` now OS-selects
  (`case $(uname -s)`: BSD `-f` on Darwin, GNU `-c … | cut` elsewhere) instead of probe-and-fallback.
- **[Blocker] `ROUTER.md` marker too broad → breaks strict additivity** → accepted. Marker tightened
  to the PDDA-unique `PROJECT/PDDA.md` only. Verified live: all 6 active PDDA repos carry it (zero
  coverage lost); a decoy `ROUTER.md`-only repo now correctly emits nothing (smoke-tested).
- **[Should] `inbox=` counted only `GH-*.md`** → accepted; counts all `1-INBOX/*.md` (symmetric with
  `working=`, honest label).
- **[Should] Safety header claimed "only find + git"** → accepted; header now lists the read-only
  utilities and reaffirms no repo-script execution.
- **[Should] No executable smoke test** (AGENTS.md:148 mandates "smoke test before feature code") →
  accepted; added `test-pdda-annotation.sh` (marker present/absent, spaces, mtime format).
- **[Should] Determinism caveat under-owned mtime→selection/order** → accepted; the whole PDDA block
  is now explicitly excluded from the git determinism guarantee, in both the collector header and SKILL.md.
- **[Nit] Full-report diff unstable via `generated_epoch`** → accepted; litmus/smoke compares a single
  non-PDDA stanza, not the whole report.
- **5× [Pass]** (glob-empty→0, subshell-only, spaces-safe, placement, no-pdda.sh, no-assoc-arrays) —
  acknowledged; confirm the core design is sound.
