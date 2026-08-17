---
title: "GH-154 P1 — tokenize the shared shell"
status: "Complete — merged to development 2026-07-19 via PR #163"
created: 2026-07-18
updated: 2026-07-22
owner: Noel
gh_issue: 154
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Move the shared shell's colour
  literals in `web_components.py` onto the P0 token vocabulary, so `render_shell()` — the
  single chokepoint covering all four live routes — is themeable without touching callers.
---

# Phase 1 — Tokenize the shared shell

Part of **GH-154**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/154
Independent of p2 and p3 (no shared files); runs after p0. **Artifact: `src/rebalance/web_components.py` only.**

Depends on p0, which already defined the full `:root` vocabulary. Read
`PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md` (token vocabulary section) and the
`RB_TOKENS_CSS` docstring p0 wrote — that docstring is the authoritative token list.

## Status

| What was just completed | What's next |
|---|---|
| Phase built, verified, and **shipped to `development` 2026-07-19 via PR #163** (`feat/theme-picker`, tip `613f77b`). | Nothing phase-local — this phase is done and merged. Runs after p0; disjoint from p2 and p3 (no shared files). |

## The task

Rewrite the **36 color literals** in `RB_CHROME_CSS`, `RB_BUTTON_CSS`, and the shared row primitive
to `var()` references. Pure substitution — no new tokens, no `:root` changes, no layout changes.

`:root` is **not** yours to edit in this phase. p0 finished it; if you find yourself needing a token
that does not exist, that is a finding to report, not a token to add — adding one here races p2 and
p3, which consume the same vocabulary.

## Mapping rules

- Every literal maps onto a **tier-1 or tier-2** token. This is a **collapse, not a find-and-replace**:
  several distinct literals will map to the same token, because the picker exposes 7 colors while the
  stylesheets hold ~190 literals.
- A literal that **resists** the mapping is the valuable finding. Do not force it and do not invent a
  token — leave it, and report it with its line number and what it is used for.
- **Tier-3 status colors** (`--ok`, `--warn`, `--danger`, `--info`) stay as they are. They carry
  meaning independent of taste and are deliberately not themeable.
- Any literal that survives must be **justified in the plan doc's progress log**, not left silently.

## Exit conditions

- [ ] `/focus-5`, `/whats-next`, `/auth-log`, `/sleuth-graph` render **visually unchanged** —
      verified by Playwright screenshot diff against p0's baseline, and **looked at** (invariant #8)
- [ ] Zero color literals remain in `RB_CHROME_CSS`, `RB_BUTTON_CSS`, or the row primitive, except
      tier-3 status colors and anything explicitly justified in the progress log
- [ ] No `var()` resolves to empty on any route
- [ ] Gate green

## Gate

```bash
PYTHONPATH=src python3 -m pytest tests/test_tz_utils.py tests/test_pulse_web_calendar.py \
  tests/test_pulse_web_goals.py tests/test_pulse_web_worknext.py \
  tests/test_pulse_server_figma.py tests/test_pulse_server_apple_reminders.py -q \
  && python3 scripts/pulse_web.py
```

> **Running this as a marathon `--pre-advance-cmd`:** prefix it with `env` —
> `env PYTHONPATH=src python3 -m pytest ...`. The driver resolves the command's first token on
> PATH, so a bare `PYTHONPATH=src ...` prefix fails with "command 'PYTHONPATH=src' is not on PATH".

`pytest tests/` carries 15 pre-existing failures in `test_auto_promote.py` /
`test_hiqs_pipeline.py` — documented baseline, not your regression.

## Invariants

- **#3 One shared row.** Lists render through the shared row primitive with its zebra striping.
  You are tokenizing it, not forking it — do not add per-module row CSS.
- **#4 Narrow containers stack.** Do not touch the container query or `grid-template-columns`;
  a nowrap timestamp once starved the body column to literally `0px`.
- **#5** No `sys.path` / `importlib` workarounds. **#6** Never hand-edit `web/pulse.html`.
- **#8 Verify by rendering.** Tests and DOM assertions both passed a visibly broken layout once.
  Screenshot it and look.
- **Stay in your artifact.** `web.py` and `pulse_web.py` belong to p2 and p3, running in the same marathon.
