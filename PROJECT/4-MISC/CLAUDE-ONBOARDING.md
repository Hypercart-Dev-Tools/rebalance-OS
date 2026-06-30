Status: Reviewed light but used only for directionality
Next Steps: Future review but low priority
Implementation: Paused

The whole design follows from one rule, which is the inverse of the bug you're fixing: **grouping may rearrange repos but must never hide one, and every grouping decision must be legible and reversible.** The original sin wasn't manual registration — it was *silent* registration. Keep the silence out and almost everything else falls into place.

## Ranked onboarding approaches

**1. Ambient file + inline `#tag` annotation, DB-backed (recommended core).** The file works as a read-on-day-0 report; if the user wants to group, they add a normal Obsidian `#tag`. SQLite is the source of truth, the file is a regenerated *view* that also accepts input.
*Trade-off:* best balance for this user — one character of "syntax" they already know, survives vault moves/deletes, degrades cleanly. Cost is a small parse-merge step and a low risk of wrong auto-guesses (mitigated below).

**2. Dashboard-native inline reclassification.** Fix the grouping where you actually feel the pain — a "rename / split this group" control in the noisy-org view.
*Trade-off:* highest intent (you edit at the moment of confusion), but requires UI you may not have yet, and ignores the daily-Obsidian habit. Best as a *complement* to #1, not a replacement.

**3. Read-only system report, no annotation surface.** File is purely system-written; dashboards group by org, full stop.
*Trade-off:* maximally robust and zero-learning, but noisy orgs stay noisy forever and power users hit a hard ceiling. This is the guaranteed *fallback floor*, not the whole product.

**4. Interactive CLI first-run wizard** ("BinoidCBD looks like a client org — name it?").
*Trade-off:* captures high-intent answers fast, but it's a blocking setup ritual that violates zero-config, and a forgetful user who skips it gets no good second chance. Only acceptable as a *non-blocking* one-line suggestion, never a gate.

**5. Silent cross-signal auto-enrichment** (calendar text / vault mentions → auto-assign projects with no confirmation).
*Trade-off:* magical when right, but lower precision means silent *mis*categorization — which is the same trust-eroding failure mode you just removed, wearing a nicer coat. Demote to suggestions only.

## Recommended approach

Layer #1 as the core, #3 as the always-on floor, #5 reduced to suggestions, #2 added later when dashboard UI exists.

**Grouping precedence (all zero-config, all keep every repo visible):**
`explicit #tag` → `detected name-prefix cluster` → `GitHub org`.

- **Smarter-than-org signal (Q2):** shared name-prefix tokens within an org (`LTVera-Pandas`, `LTVera-API` → `LTVera`). It's free, extremely common for solo devs, and — critically — *explainable* ("grouped by shared `LTVera-` prefix"), so the user can trust and override it. Repo topics are a good secondary signal when present. Calendar/vault matching is good but lower-precision, so it produces *suggestions*, never silent defaults. Avoid opaque signals like co-commit clustering as a default — "why did it group these?" must always have a one-line answer.

- **Lowest-friction annotation (Q3):** a trailing `#tag` on the repo line. No new syntax, and it doubles as a real Obsidian tag, so the project becomes navigable in Obsidian's tag pane — the annotation creates value *inside Obsidian itself*, not just in rebalanceOS.

- **Editable, but DB is source of truth (Q4):** the file is bi-directional, yet durable state lives in SQLite. The system parses tags as *input*, stores them, and rewrites the file canonically as *output*.
  - *Read-only failure mode:* user tries to annotate anyway, gets clobbered, goes hunting for another config surface — enrichment ceiling and quiet frustration.
  - *Naive editable (file = truth) failure mode:* sync clobbers edits; vault move/delete loses all config; concurrent edit during write creates conflict files. Worst option.
  - *DB-backed editable failure mode (chosen):* mild and mitigable — parse ambiguity, or a user editing a system-owned field (commit count) and seeing it revert. Mitigate by clearly marking which parts are system-owned, atomic temp-file-then-rename writes, reading current disk state before each rewrite so open edits aren't lost, and skipping the write entirely (keeping DB) if the vault path is gone.

- **Surface (Q5):** Obsidian is right for *ambient, ignorable* enrichment because of the daily-scratchpad habit and the free tag-pane payoff. The dashboard is the right surface for *high-intent reclassification* (build later). The CLI should only ever emit a one-line, non-blocking suggestion — never prompt-and-wait.

## What the user sees on first run

CLI (non-blocking, scrolls past — nothing waits on input):
```
✓ Synced 18 repos across 3 orgs → all live on your dashboards now.
✓ Wrote GitHub Repos.md to your vault. Nothing to configure; open it only if you want to.
  tip: "Hypercart-Dev-Tools" has 12 repos — add a #tag to any line to split them up.
```

`GitHub Repos.md` on first open (Q1) — the header self-explains, the data delivers value before any action, and one live example teaches the only "syntax" passively:
```
# GitHub Repos
_Auto-generated by rebalanceOS · last sync 2026-05-31 09:14 · 18 repos, 3 orgs._
_You don't need to do anything — every repo below is already on your dashboards._
_To group or split a noisy org, add a #tag after any line. That's the whole system._
_Safe to edit: this file is rewritten each sync, but your #tags are always kept._

## BinoidCBD · 3 repos
  ### LTVera  (auto-detected from name — add a #tag to override)
  - LTVera-Pandas      — 47 commits this week
  - LTVera-API         — 12 commits this week
  - storefront-theme   — 3 commits this week

## Hypercart-Dev-Tools · 12 repos
  - invoice-gen    — 8 commits      ← add  #billing  to group these
  - billing-cron   — 5 commits
  - scraper-v2     — 4 commits
  - … 9 more
```
Provenance is always visible: an auto-detected group says so and invites override; a `#tag` group is the user's. Nothing is ever silently filed away.

## Implementation order (quick wins → harder)

1. **Day-0 floor (ship first):** sync → org grouping → write the read-only-quality report with the self-explaining header. This alone beats the old behavior because nothing hides.
2. **Quick win:** prefix-cluster auto-grouping with the "(auto-detected)" label. Pure inference, no user action, immediately tames noisy orgs.
3. **Core:** `#tag` parsing with SQLite as source of truth and the atomic safe-rewrite loop. This unlocks enrichment without a config ritual.
4. **Later / higher effort:** calendar + vault matches surfaced as *suggestions* in the file ("mentioned in 4 events titled 'LTVera standup' — tag as #LTVera?"), and eventually dashboard-native inline reclassification for the highest-intent moments.

The thing to protect at every step: a forgetful user who never opens the file still gets a complete, correct dashboard — configuration only ever *improves* the view, never *gates* it.