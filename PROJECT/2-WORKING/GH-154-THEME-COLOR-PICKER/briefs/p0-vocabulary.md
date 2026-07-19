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

- [ ] Every page renders **byte-identically** except for property names and `--shadow`, which is intentionally re-derived from `--ink` (this phase is a rename +
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
