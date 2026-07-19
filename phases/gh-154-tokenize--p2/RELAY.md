# Marathon Phase p2
STATUS: Open
NEXT: agy

<!-- marathon-drive: task=MARATHON-P2-TURN builder=agy reviewer=codex round-cap=5 -->

## Phase Brief

# Phase 2 — Tokenize `web.py`

Part of **GH-154**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/154
Independent of p1 and p3 (no shared files); runs after p0. **Artifact: `src/rebalance/web.py` only.**

Depends on p0, which defined the full `:root` vocabulary and **enumerated this phase's exact
inline-`style=` write-set** — read that list in `PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md`
before starting. Prior estimates conflicted (5, 7, 14); p0's enumeration is authoritative.

## Write-set

~51 literals across:

| Target | Location |
|---|---|
| `_CSS` | `web.py:244-356` |
| focus-5 inline `<style>` | `:700-731` |
| `_SYSLOG_TOGGLE_CSS` | `:1473` |
| Inline `style=` attributes | per p0's enumerated list — includes `#5b5750` in the graph tooltip at `:1851-1853` |
| Cytoscape `_KIND_COLOR` | `:1597-1601`, `:1714-1719` |

## Mapping rules

- Every literal maps onto a **tier-1 or tier-2** token. A **collapse, not a find-and-replace** —
  many literals share one token.
- The tooltip `#5b5750` is plain drift: it is today's `--fg-muted`, so it becomes `var(--muted)`.
- **Tier-3 status colors** (`--ok`, `--warn`, `--danger`, `--info`) stay literal.
- A literal that resists the mapping is a **finding** — report it with a line number, do not invent
  a token. Adding a token here desyncs p1 and p3, which consume the same vocabulary.

### Cytoscape `_KIND_COLOR` — categorical, handle differently

These are **identity** colors: a node's kind, not a theme choice. Per the plan doc's decision, they
**keep their hues** — recoloring identity per theme would make the same node kind a different color
in every theme, which is worse than a fixed palette. What must become theme-derived is the
**contrast furniture** around them: label color, stroke, and legend text take `--ink` / `--card` so
the graph stays legible on a dark page.

`_KIND_COLOR` reaches the page through a JS style object and inline attributes, **not** a
stylesheet, so `var()` cannot reach it the way it reaches `_CSS`. Feed the resolved values in at
render time.

## Exit conditions

- [ ] `/sleuth-graph`, `/focus-5` and `/auth-log` render **visually unchanged** vs p0's baseline —
      screenshot diff **and looked at** (invariant #8)
- [ ] The graph legend and node labels are legible; the graph is not left as a light-mode island
- [ ] Zero color literals remain in `_CSS`, the focus-5 `<style>`, `_SYSLOG_TOGGLE_CSS`, or inline
      `style=`, except tier-3 colors, `_KIND_COLOR` hues, and anything justified in the progress log
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

## Invariants

- **#5** No `sys.path` / `importlib` workarounds. **#6** Never hand-edit `web/pulse.html`.
- **#1** Do not touch time formatting — it goes through `format_timestamp()`.
- **#8 Verify by rendering.** Screenshot and look; assertions have passed broken layouts here before.
- **Stay in your artifact.** `web_components.py` and `pulse_web.py` belong to p1 and p3, elsewhere
  in this marathon. In particular **do not edit `:root`** — if a token is missing, report it.

---

▶ TAKE YOUR TURN (agy — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/web.py
2. Append a build block to this relay file: `### Round N · Builder · agy` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/wt/theme-picker/.xyz/bin/tick
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick claim MARATHON-P2-TURN --agent agy --paths "phases/gh-154-tokenize--p2/RELAY.md,src/rebalance/web.py"
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick ping MARATHON-P2-TURN --agent agy
   - /Users/noelsaw/wt/theme-picker/.xyz/bin/tick release MARATHON-P2-TURN --agent agy --to codex
4. Edit ONLY these paths: phases/gh-154-tokenize--p2/RELAY.md and src/rebalance/web.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (codex — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/web.py.
1. Append a review block: `### Round N · Reviewer · codex` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick release MARATHON-P2-TURN --agent codex --to agy
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick done MARATHON-P2-TURN --agent codex
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/wt/theme-picker/.xyz/bin/tick
   Edit ONLY phases/gh-154-tokenize--p2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
