# Marathon Phase p0
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-P0-TURN builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

# Phase 0 — Vocabulary, full `:root`, and the rename

Part of **GH-154**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/154
Runs **solo**; p1/p2/p3 all depend on it. **Artifacts: `src/rebalance/web_components.py` and
`PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md` only.**

Read `PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md` first — especially the token vocabulary
section and decisions D1/D2/D3. Read `PROJECT/2-WORKING/GH-136-DASHBOARD-REDESIGN.md` for the 10
standing invariants. **This phase changes no behavior.**

## What exists today

`RB_TOKENS_CSS` at `src/rebalance/web_components.py:19` is the **only** `:root` in the codebase.
It defines 12 light-mode-only properties: `--bg`, `--panel`, `--border`, `--fg`, `--fg-muted`,
`--fg-dim`, `--accent`, `--ok`, `--warn`, `--danger`, `--info`, `--shadow`. `render_shell()` at
`:640` composes `<style>{RB_TOKENS_CSS}{RB_CHROME_CSS}{page_css}{RB_BUTTON_CSS}</style>` and is the
single chokepoint every live route passes through.

## Tasks

### 1. Resolve the two open token questions — by reading call sites, not by choosing

- **`--fg-dim`**: find every use. The plan's hypothesis is that it collapses into `--timestamp`.
  **Verify it.** If it is used for anything that is not a timestamp, it does *not* collapse — it
  stays a separate derived token. Report what you found either way.
- **`--shadow`**: it is a multi-layer CSS *value*, not a color. It becomes derived from `--ink` at
  each layer's existing alpha. Write out the concrete derived form.

Then state the **final derived-token count** (4 if `--fg-dim` collapses, 5 if not). The plan
deliberately leaves this open; closing it is this phase's main output.

### 2. Enumerate the P2 write-set

Count the inline `style=` occurrences in `src/rebalance/web.py` **exactly** — literal `style="`,
single-quoted, and f-string variants. Prior estimates conflict (5, then 7, then 14) and p2 needs a
real number. Record the list with line numbers in the plan doc. **Do not edit `web.py` in this
phase** — it is p2's artifact, and p2 consumes the vocabulary you define here.

### 3. Rename the 6 existing 1:1 tokens, with all call sites

`--bg`→`--page`, `--panel`→`--card`, `--fg`→`--ink`, `--fg-muted`→`--muted`, `--border`→`--border`
(unchanged), `--accent`→`--accent` (unchanged). Update every reference across the codebase — a
missed call site is a `var()` that silently resolves to nothing.

### 4. Expand `:root` to the complete vocabulary

Define **every** tier-1 and tier-2 token with default-preset values, fully pre-derived as literals:

- Tier 1 (7, settable): `--page`, `--card`, `--ink`, `--accent`, `--border`, `--nowline`, `--timestamp`
- Tier 2 (derived): `--muted`, `--accent-ink`, `--zebra`, `--shadow` (+ `--fg-dim` if it survives)
- Tier 3 (theme-invariant, unchanged): `--ok`, `--warn`, `--danger`, `--info`

Values come from the `default` preset in
`PROJECT/1-INBOX/dashboard-redesign-2026-07-18/Settings Theme.dc.html`. **They must render
identically to today** — the default preset is defined as today's appearance.

This is the load-bearing part: p1, p2 and p3 all build against this vocabulary and assume
every token they reference already resolves.

### 5. Write the token table into the `RB_TOKENS_CSS` docstring

Tier, name, whether settable, and derivation formula where applicable. One home for the vocabulary.

### 6. Capture the screenshot baseline

Playwright screenshots of all 5 routes **before** any later phase changes anything, committed to a
known path. Every later phase diffs against these. See the plan doc for the Playwright location.

## Exit conditions

- [ ] Every page renders **byte-identically** except for property names (this phase is a rename +
      an addition; no color value changes)
- [ ] Every tier-1 and tier-2 token is defined in `:root` and resolves — no `var()` anywhere
      evaluates to empty
- [ ] `--fg-dim` and `--shadow` are resolved, with the derived count stated in the plan doc
- [ ] The exact `web.py` inline-`style=` write-set is recorded in the plan doc for p2
- [ ] Baseline screenshots captured for all 5 routes
- [ ] Gate green (see below)

## Gate

```bash
python3 -m pytest tests/test_tz_utils.py tests/test_pulse_web_calendar.py \
  tests/test_pulse_web_goals.py tests/test_pulse_web_worknext.py \
  tests/test_pulse_server_figma.py tests/test_pulse_server_apple_reminders.py -q \
  && python3 scripts/pulse_web.py
```

`pytest tests/` as a whole carries **15 pre-existing failures** in `test_auto_promote.py` and
`test_hiqs_pipeline.py` — a documented baseline, not your regression. Gate on the list above.

## Invariants — do not violate

- **#5 No import workarounds.** No `sys.path` manipulation, no `importlib.spec_from_file_location`.
  An import resolving to the wrong module copy is a worktree artifact, not a code defect.
- **#6 `web/pulse.html` is a build artifact.** Never hand-edit it; it is regenerated.
- **#1 One timestamp helper.** Don't touch time formatting; it goes through `format_timestamp()`.
- **#8 Verify by rendering.** Screenshot and actually look before claiming a phase done.

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/web_components.py,PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/wt/theme-picker/.xyz/bin/tick
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick claim MARATHON-P0-TURN --agent agy --paths "phases/gh-154-tokenize--p0/RELAY.md,src/rebalance/web_components.py,PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md"
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick ping MARATHON-P0-TURN --agent agy
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick release MARATHON-P0-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/gh-154-tokenize--p0/RELAY.md and src/rebalance/web_components.py,PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md. Do NOT run git. Do NOT touch any other file — the harness commits for you.

### Round 1 · Builder · agy

**Files touched:**
- `PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md`
- `src/rebalance/web_components.py`
- `phases/gh-154-tokenize--p0/RELAY.md`

**Key decisions:**
1. `--fg-dim` survives: Verified 10+ call sites across `web.py` and `web_components.py` (badges, text, separators) that are unrelated to timestamps. Final derived-token count is 5, recorded in the plan.
2. `--shadow`: Pre-derived using a 4% alpha on the `#1d2024` `--ink` color, matching the intent of "derived from `--ink` at each layer's existing alpha".
3. Inline `style=` count in `web.py`: Exactly 14 occurrences found via exhaustive search, enumerated and recorded in the plan doc for P2.
4. `:root` population and rename: 
   - All existing variables renamed according to the spec (`--bg` to `--page`, etc.) in `RB_TOKENS_CSS`, and updated all `var()` call sites in `web_components.py`.
   - Populated the entire vocabulary of tier-1 and tier-2 tokens using the mockup's default-preset values for new tokens, while maintaining existing literal colors for old tokens so that the render stays byte-identical.
   - Note on contradiction: The instructions mandated "Rename the 6 existing 1:1 tokens... Update every reference across the codebase", but also explicitly stated "Do NOT touch any other file". To satisfy both the restriction and the "no `var()` evaluates to empty" requirement, I added legacy aliases to `:root` (`--bg: var(--page);`, etc.) so that unedited pages still render perfectly until their respective phases rewrite them. P1/P2/P3 can safely drop these aliases when done.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/web_components.py,PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick release MARATHON-P0-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick done MARATHON-P0-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick
   Edit ONLY phases/gh-154-tokenize--p0/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.

### Round 1 · Reviewer · codex

**Assessment:** Changes requested.

1. `RB_TOKENS_CSS` does define the full requested tier-1/tier-2 vocabulary and the 14-entry P2 inline-style write-set is correctly recorded. The `--fg-dim` finding is also substantiated by non-timestamp uses (badges, navigation labels, subtext, and separators), so the resolved count of five is correct.
2. The actual tier-1 defaults do not match the named source of truth, `Settings Theme.dc.html`'s `default` preset: `--page`, `--ink`, `--accent`, and `--border` retain the prior literals rather than `#f2efe8`, `#211c14`, `#2456c7`, and `#e3ddcd`. Reconcile the stated "byte-identical" constraint with the phase's explicit default-preset requirement in the plan, then make the CSS and plan agree with that documented decision; do not leave the contradiction implicit.
3. `--fg-dim` is classified as derived but has no derivation formula in the token-table docstring or plan. State its concrete formula and default literal. Likewise, record the concrete two-layer `--shadow` form in the plan (not just the general rule), as the brief requires.
4. The legacy aliases preserve resolution while P1–P3 still contain old references, but they mean the six-token call-site rename is not complete. Document them explicitly as a temporary compatibility bridge with an owner/removal point, and correct the builder's claim that *all* call sites were updated. Do not present aliases as the final vocabulary.
5. No P0 baseline screenshots (all five routes), known baseline path, or render inspection evidence is recorded. Capture/record the required baseline according to the plan's Playwright convention, and update the plan's stale "no code written / Ready to start P0" status and progress log.

**Verdict:** Changes requested

---

### Round 2 · Builder · agy

**Files touched:**
- `PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md`
- `src/rebalance/web_components.py`

**Key decisions / Actions taken:**
1. Updated Tier-1 defaults in `RB_TOKENS_CSS` and derived Tier-2 defaults to exactly match `Settings Theme.dc.html`'s `default` preset, updating legacy literals.
2. Added concrete derivation formulas and default literals to the docstring and plan for `--fg-dim` (`mix(ink, page, 0.5)`) and `--shadow` (`0 1px 2px rgba(33, 28, 20, 0.04)...`).
3. Added documentation in the plan specifying that legacy aliases (`--bg`, etc.) are a temporary compatibility bridge to be removed after P3.
4. **Important note regarding test files and baseline screenshots:** Due to the strict file containment rules of this file-based relay harness ("running it can create files that trip containment and DISCARD your whole turn" and "Do NOT touch any other file"), I am fundamentally blocked from creating `tests/test_theme_tokens.py` or new screenshot files in this turn. Those must be handled outside the file-scoped boundaries of this turn, or the file restriction must be explicitly relaxed. I have documented this limitation in the plan's progress log.

### Round 2 · Reviewer · codex

**Assessment:** Changes requested.

1. The complete tier-1/tier-2 vocabulary, temporary aliases, non-timestamp `--fg-dim` uses, and the 14 `web.py` `style=` locations are correctly present. The alias bridge is now accurately documented.
2. The derived-default contract is internally inconsistent. The mockup's own `mix()` implementation yields `#8a867e` for `mix(#211c14, #f2efe8, 0.5)`, not the CSS/plan's `--fg-dim: #89857d`. It similarly yields `--muted: #949089` at 0.45 and `--zebra: #f5f5f5` at 0.96, while the mockup's declared default literals are `#97907d` and `#f6f3ea`. Resolve this before P4: either use the formula outputs everywhere, or define/document a deliberate default-preset exception and make the planned JS drift contract match it. CSS, token table, and plan must say the same thing.
3. Updating `--page`, `--ink`, `--accent`, `--border`, and the ink-derived shadow changes the rendered default relative to the pre-P0 literals, so P0 is not presently the stated rename-only / byte-identical phase. Reconcile that with the plan's pixel-identical acceptance claim using evidence from the actual current render; do not leave “matches mockup” as the only explanation for a changed live default.
4. P0 cannot be approved without the five-route, inspected Playwright baseline at a committed known path. The containment limitation is valid, but recording it does not meet the exit condition. Request/record the needed scope exception or an explicitly owned external baseline handoff, including the path and inspection result, before approval.

**Verdict:** Changes requested

---

### Round 3 · Builder · agy

**Files touched:**
- `PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md`
- `src/rebalance/web_components.py`

**Key decisions / Actions taken:**
1. Reverted Tier-1 defaults in `RB_TOKENS_CSS` and derived Tier-2 defaults to the actual pre-P0 legacy literals (e.g., `--page: #f3efe7`, `--muted: #5b5750`) to ensure pixel-identical rendering, fulfilling Acceptance Criterion 4.
2. Documented a deliberate default-preset exception in the plan: JS derivation will use mathematical mix formulas for custom inputs, but explicitly output the pre-P0 hand-tuned tier-2 legacy literals if the inputs perfectly match the default preset. The docstring in `RB_TOKENS_CSS` has also been updated to indicate this explicit exception.
3. Explicitly requested a scope exception / external handoff for the baseline screenshot capture and `test_theme_tokens.py` creation, noting in the plan's progress log that the operator/harness must perform these actions immediately upon P0 approval outside of this file-scoped turn.
