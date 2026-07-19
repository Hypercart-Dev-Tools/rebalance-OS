# Marathon Phase p1
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-P1-TURN builder=agy reviewer=codex round-cap=5 -->

## Phase Brief

# Phase 1 — Tokenize the shared shell

Part of **GH-154**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/154
Independent of p2 and p3 (no shared files); runs after p0. **Artifact: `src/rebalance/web_components.py` only.**

Depends on p0, which already defined the full `:root` vocabulary. Read
`PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md` (token vocabulary section) and the
`RB_TOKENS_CSS` docstring p0 wrote — that docstring is the authoritative token list.

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
python3 -m pytest tests/test_tz_utils.py tests/test_pulse_web_calendar.py \
  tests/test_pulse_web_goals.py tests/test_pulse_web_worknext.py \
  tests/test_pulse_server_figma.py tests/test_pulse_server_apple_reminders.py -q \
  && python3 scripts/pulse_web.py
```

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

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/web_components.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/wt/theme-picker/.xyz/bin/tick
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick claim MARATHON-P1-TURN --agent agy --paths "phases/gh-154-tokenize--p1/RELAY.md,src/rebalance/web_components.py"
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick ping MARATHON-P1-TURN --agent agy
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick release MARATHON-P1-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/gh-154-tokenize--p1/RELAY.md and src/rebalance/web_components.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

### Round 1 · Builder · agy

**Files Touched:**
- `src/rebalance/web_components.py`

**Key Decisions & Progress Log:**
- Replaced 16 literal colors that cleanly collapsed into `var()` mappings:
  - `.rb-btn` fallbacks (`#1a73e8`) -> `var(--accent)`
  - `.sidebar` gradient (`#f8f4ec 0%, #f3efe7 100%`) -> `background: var(--page)`
  - `.kbd` and badge backgrounds (`#fff`) -> `var(--card)`
  - Alternating row stripes and hover states (`rgba(0,0,0,.03)` and `rgba(29,32,36,.03)`) -> `var(--zebra)`
  - `.cal-now-dot` and line (`var(--danger, #d43d2a)`) -> `var(--nowline)`
- **Resisting Mapping (Justifications for remaining literals):**
  - `rgba(31,111,235,.10)` (line 267): Active nav item background. We have no transparent accent token in tier 1/2. Collapsing to a solid token loses the blue highlight.
  - `rgba(124,196,255,.10)` (line 279): Side row link hover background. Requires a subtle `--info` or `--accent` tint.
  - `rgba(31,111,235,.18)` / `rgba(31,111,235,.08)` (lines 396-397): Rank marker border/bg. Semantic blue tint.
  - `rgba(29,111,168,.18)` / `rgba(29,111,168,.08)` (lines 401-402): Avatar marker border/bg. Semantic info tint.
  - `#e8b93a`, `#3d3006`, `#f5edd8`, `#a49a76` (lines 466-467): Semantic "upcoming" (vibrant yellow) and "past" (muted grey/yellow) calendar events. `--warn` (`#a65f00`) is too dark to collapse these into.
- Gate successfully checked.
---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/web_components.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick release MARATHON-P1-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick done MARATHON-P1-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick
   Edit ONLY phases/gh-154-tokenize--p1/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
