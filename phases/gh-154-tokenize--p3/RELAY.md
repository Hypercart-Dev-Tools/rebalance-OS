# Marathon Phase p3
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-P3-TURN builder=agy reviewer=codex round-cap=7 -->

## Phase Brief

# Phase 3 — Tokenize `PAGE_CSS` and the canvas palettes

Part of **GH-154**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/154
Independent of p1 and p2 (no shared files); runs after p0. **Artifact: `scripts/pulse_web.py` only.**

The largest phase: **101 literals across ~690 lines**, plus 7 inline `style=` attributes, plus the
two Chart.js canvases. Depends on p0's `:root` vocabulary — read the `RB_TOKENS_CSS` docstring and
`PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md` first.

## Write-set

| Target | Location |
|---|---|
| `PAGE_CSS` | `pulse_web.py:1698-2388` — 101 literals |
| Inline `style=` attributes | 7 occurrences |
| `PIE_PALETTE` | defined `:1001`, consumed `:982` and `:1040` |

## Mapping rules

- Every literal maps onto a **tier-1 or tier-2** token. A **collapse, not a find-and-replace**.
- **Tier-3 status colors** (`--ok`, `--warn`, `--danger`, `--info`) stay literal.
- A literal that resists the mapping is a **finding** — report it with a line number. Do not invent
  a token; adding one here desyncs p1 and p2, and **`:root` is not your artifact**.

### The calendar module (from GH-137)

`.cal-*` carries the `#e8b93a` / `#f5edd8` event tones and the now-line. **The now-line becomes
`var(--nowline)`** — that is precisely why the mockup exposes it as a settable tier-1 color. Take
care here: this module was built the day before and its 3-column anatomy is fragile (invariant #4 —
a nowrap timestamp once starved the body column to `0px`). Change colors, not geometry.

### The Chart.js canvases — `var()` cannot reach them

`PIE_PALETTE` (`:1001`) is 12 hardcoded fills consumed at `:982` and `:1040`, feeding two canvases.
A canvas has no computed style to inherit, so CSS variables cannot reach it at all — these must be
fed resolved values at render time.

Per the plan doc's decision, the 12 fills are **categorical** (a repo's slice = identity, not taste)
and **keep their hues**. What becomes theme-derived is the contrast furniture: label color, border/
stroke between slices, and legend text take `--card` / `--ink`, so slices stay legible on a dark
page. A pie chart that stays light-mode while the page goes dark is the failure this prevents.

## Exit conditions

- [ ] `python3 scripts/pulse_web.py` regenerates cleanly
- [ ] A Playwright screenshot of `/` is **pixel-identical** to p0's baseline — and **looked at**
      (invariant #8)
- [ ] Both pie charts render with legible labels; neither is a light-mode island
- [ ] Zero color literals remain in `PAGE_CSS` or its inline `style=`, except tier-3 colors, the
      `PIE_PALETTE` hues, and anything justified in the progress log
- [ ] No `var()` resolves to empty
- [ ] Gate green

## Gate

```bash
python3 -m pytest tests/test_tz_utils.py tests/test_pulse_web_calendar.py \
  tests/test_pulse_web_goals.py tests/test_pulse_web_worknext.py \
  tests/test_pulse_server_figma.py tests/test_pulse_server_apple_reminders.py -q \
  && python3 scripts/pulse_web.py
```

`pytest tests/` carries 15 pre-existing failures in `test_auto_promote.py` /
`test_hiqs_pipeline.py` — documented baseline, not your regression.

## Invariants — read these, this phase touches the riskiest surface

- **#6 `web/pulse.html` is a build artifact.** You regenerate it via `python3 scripts/pulse_web.py`.
  **Never hand-edit it** — `install_pulse_web_scheduler.sh` silently overwrites direct edits.
- **#4 Narrow containers stack.** Do not touch `grid-template-columns`, the container query, or any
  layout geometry. Colors only.
- **#7 Geometry in constants.** If you find yourself editing hour heights or gutters, stop — that is
  out of scope for a tokenization phase.
- **#1** Do not touch time formatting. **#5** No `sys.path` / `importlib` workarounds.
- **#8 Verify by rendering.** This is the phase where a screenshot matters most: 101 substitutions
  in one file is exactly the change that passes every test while looking wrong.
- **Stay in your artifact.** `web_components.py` and `web.py` belong to p1 and p2, running in the same marathon.

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): scripts/pulse_web.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/wt/theme-picker/.xyz/bin/tick
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick claim MARATHON-P3-TURN --agent agy --paths "phases/gh-154-tokenize--p3/RELAY.md,scripts/pulse_web.py"
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick ping MARATHON-P3-TURN --agent agy
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick release MARATHON-P3-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/gh-154-tokenize--p3/RELAY.md and scripts/pulse_web.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: scripts/pulse_web.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick release MARATHON-P3-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick done MARATHON-P3-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick
   Edit ONLY phases/gh-154-tokenize--p3/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
