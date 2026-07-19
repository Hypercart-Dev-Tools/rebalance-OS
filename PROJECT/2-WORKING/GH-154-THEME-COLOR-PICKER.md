---
title: Web app theme color picker — tokenize the UI CSS, then ship Settings → Color theme
status: "Planning — no code written. Worktree ~/wt/theme-picker on branch feat/theme-picker (from origin/development). QA relay R1 + a follow-up design consult both folded in; P6 cut, v1 is localStorage-only and ends at P5. Ready to start P0."
gh_issue: 154
owner: noelsaw1
created: 2026-07-18
updated: 2026-07-18
branch: feat/theme-picker
supersedes: []
synthesizes:
  - PROJECT/2-WORKING/GH-136-DASHBOARD-REDESIGN.md
  - PROJECT/1-INBOX/dashboard-redesign-2026-07-18/Settings Theme.dc.html
goal: >
  Ship an operator-facing theme color picker (4 presets + custom, 7 tunable colors, live
  preview) that applies across every Pulse web page. The picker is small; the enabling work
  is tokenizing ~190 hardcoded color literals across three Python-embedded stylesheets onto
  a single derived token vocabulary with exactly one derivation implementation.
---

# Theme color picker (GH-154)

## Contents
- [Answering the framing question](#answering-the-framing-question)
- [Current state](#current-state)
- [The token vocabulary](#the-token-vocabulary)
- [Design decisions](#design-decisions)
- [Phases](#phases)
- [Acceptance criteria](#acceptance-criteria)
- [Verification gate](#verification-gate)
- [Anti-goals](#anti-goals)
- [Risks](#risks)
- [Progress log](#progress-log)

## Answering the framing question

> *"We'll need to first tokenize the UI CSS on all the pages right?"*

Yes — but with one refinement that changes the shape of the work.

Tokenizing is necessary and it is the bulk of the effort. It is **not** sufficient, and it is
also not the hard part. The hard part is that a theme picker needs a *small* vocabulary — the
mockup exposes exactly **7** operator-tunable colors — while the stylesheets contain ~190
distinct literals. So this is not a mechanical `#f3efe7` → `var(--bg)` find-and-replace. It is a
**collapse**: every literal must be mapped onto one of ~20 semantic tokens, of which only 7 are
directly settable and the rest are *derived*. Literals that resist that mapping are the finding,
not an obstacle — each one is either a token the vocabulary is missing or a color that shouldn't
have been bespoke.

The second refinement: tokenizing every page is *not* enough to theme every page, because `/` is
not a page in the same sense as the others. See [Design decisions](#design-decisions) D2.

## Current state

Inventory taken 2026-07-18 against `origin/development`.

**All CSS in this repo is Python-embedded. Zero tracked `.css` files.**

| Surface | Lines | hex | rgb/rgba | `var()` refs | `:root` |
|---|---|---|---|---|---|
| `scripts/pulse_web.py` | 3241 | 42 | 59 | 157 | no |
| `src/rebalance/web.py` | 1879 | 37 | 14 | 68 | no |
| `src/rebalance/web_components.py` | 664 | 24 | 12 | 44 | **yes — the only one** |
| `scripts/pulse_server.py` | 596 | 0 | 0 | 0 | — |

Key locations:

- `web_components.py:19` — `RB_TOKENS_CSS = """:root {` — the single existing token source, **12 properties, light-mode only**: `--bg #f3efe7`, `--panel #ffffff`, `--border #e3ddd0`, `--fg #1d2024`, `--fg-muted #5b5750`, `--fg-dim #8a857c`, `--accent #1f6feb`, `--ok #2f7437`, `--warn #a65f00`, `--danger #c0392b`, `--info #1d6fa8`, `--shadow`.
- `web_components.py:640` — `render_shell()` composes `<style>{RB_TOKENS_CSS}{RB_CHROME_CSS}{page_css}{RB_BUTTON_CSS}</style>`. **This is the chokepoint.**
- `pulse_web.py:1698-2388` — `PAGE_CSS`, a ~690-line block.
- `pulse_web.py:2395` — `CSS = RB_TOKENS_CSS + RB_CHROME_CSS + PAGE_CSS`.
- `web.py:244-356` — `_CSS`; `web.py:700-731` — inline `<style>` in the focus-5 body; `web.py:1473` — `_SYSLOG_TOGGLE_CSS`.
- **12 inline `style="..."` attributes** (7 in `pulse_web.py`, 5 in `web.py`) that no stylesheet swap reaches.

Routes and their renderers:

| Route | Renderer | Live or static |
|---|---|---|
| `/` | `pulse_server.py:268` `FileResponse` of `web/pulse.html`, built by `pulse_web.py:2977 build_page()` | **static artifact** |
| `/focus-5` | `pulse_server.py:108` → `web.py:775 focus5_page()` | live |
| `/whats-next` | `pulse_server.py:194` → `web.py:1427 whatsnext_page()` | live |
| `/auth-log` | `pulse_server.py:98` → `web.py:1547 auth_log_page()` | live |
| `/sleuth-graph` | `pulse_server.py:199` → `web.py:1683` | live |

Persistence: **no settings table exists.** The convention is `src/rebalance/ingest/config.py` —
non-secret config in `temp/rbos.config` (gitignored JSON), path seam `CONFIG_PATH` (`config.py:28`)
with `REBALANCE_CONFIG` env override. Copy the `get_vault_path()` / `set_vault_path()` shape at
`config.py:377-392`. CLI surface would go in `src/rebalance/cli/config_cmds.py`.

There is **no `localStorage` usage anywhere in the codebase** today.

Prior art: `PROJECT/2-WORKING/FOCUS5-UI.html` already carries a 36-reference token vocabulary.
Mine it for names before inventing new ones.

Out of scope, noted so nobody "helpfully" includes them: `scripts/dashboard.py` (24 hex, but a
**Rich terminal TUI**, not CSS — it has its own theme and its own test at
`tests/test_dashboard_terminal_theme.py`), `experimental/freshness/spike.py`,
`experimental/release-board/spike.py`, `ARCHITECTURE/system-diagram.html`, `.swe-diagram/`.

## The token vocabulary

Three tiers. The picker only ever touches tier 1.

**Tier 1 — settable (7).** Exactly the mockup's `customFields`:

| Token | Mockup key | Label |
|---|---|---|
| `--page` | `page` | Page background |
| `--card` | `card` | Card background |
| `--ink` | `ink` | Text |
| `--accent` | `accent` | Accent |
| `--border` | `border` | Borders |
| `--nowline` | `nowline` | Calendar time line |
| `--timestamp` | `timestamp` | Date + time text |

**Tier 2 — derived, never settable.** The first three are the mockup's `themeOf()`; the fourth is
ours, because the existing `--shadow` is colored and so cannot stay literal:

- `--muted` = `mix(ink, page, 0.45)`
- `--accent-ink` = `#ffffff` if `isDark(accent)` else `#111111`
- `--zebra` = `mix(card, isDark(page) ? #ffffff : #000000, 0.96)`
- `--shadow` = the existing multi-layer value with each layer's color replaced by `--ink` at that
  layer's alpha. It is a full CSS value, not a color, so its derivation returns a string — the
  derivation returns a string rather than a color — the JS derivation layer must handle it as such.

`isDark(hex)` is the standard luminance test `0.299R + 0.587G + 0.114B < 128`.

**The count is resolved to 5 derived tokens.** `--fg-dim` does *not* collapse into
`--timestamp` because it is used for badges, subtext, nav section labels, and other non-time text.
It survives as a tier-2 derived token.

**Tier 3 — semantic status colors, theme-invariant for v1.** `--ok`, `--warn`, `--danger`, `--info`.
These carry meaning independent of taste; a custom theme that recolors "danger" is a footgun. They
stay literal in v1 and are explicitly *not* exposed. Revisit only if a dark preset makes them
unreadable — which the acceptance contrast check will catch if so.

**Reconciling with the 12 existing properties.** The current names are not the mockup's. The
mapping is 1:1 and should be done as a rename, not a parallel vocabulary:

`--bg`→`--page`, `--panel`→`--card`, `--fg`→`--ink`, `--fg-muted`→`--muted`, `--border`→`--border`,
`--accent`→`--accent`. `--fg-dim` and `--shadow` need a call: `--fg-dim` most likely collapses into
`--timestamp` (verify at its call sites — if it is used for anything that is not a timestamp, it
stays as a derived tier-2 token instead); `--shadow` becomes derived from `--ink` at low alpha.

**Rule: a tier-1 or tier-2 token is the only way a color reaches the page.** Any literal that
survives phase 3 must be justified in the doc, not left silently.

### Color that CSS variables cannot reach

The inventory above covers stylesheets. Three surfaces emit color *outside* them, so tokenizing
`PAGE_CSS` will not touch them — and the "5 routes × 5 themes" criterion is meaningless if they stay
frozen while everything around them changes.

| Surface | Where | Why `var()` can't reach it |
|---|---|---|
| **Chart.js pie fills** | `PIE_PALETTE` (`pulse_web.py:1001`), consumed at `:982` and `:1040` | 12 hardcoded fills passed as canvas paint values; a canvas has no computed style to inherit |
| **Cytoscape graph + legend** | `_KIND_COLOR` emitted inline (`web.py:1597-1601`, `:1714-1719`) | colors go into a JS style object and inline `style=` attributes, not a stylesheet |
| **Inline `style=` attributes** | `web.py` — 14 occurrences (literal, single-quote, f-string variants), incl. `#5b5750` in the graph tooltip at `:1851-1853` | inline styles are reachable by `var()`, but only once each is rewritten by hand |

Two of the three are *categorical* colors — a repo's slice, a node's kind. They encode identity, not
theme, which makes them closer to tier 3 than tier 1. The call for each is made in P0 and recorded
here, but the leaning is:

- **Pie + graph palettes stay categorical**, and get a derived *contrast* treatment rather than a
  derived hue: keep the 12 fills, but take label/stroke color from `--card` and `--ink` so slices
  stay legible on a dark page. Recoloring identity per theme would make the same repo a different
  color in every theme, which is worse than a fixed palette.
- **The tooltip literal is plain drift** — `#5b5750` is today's `--fg-muted`. It becomes `var(--muted)`.

The true inline `style=` write-set for P2 is exactly **14 occurrences** in `web.py` (lines 414, 431, 432, 501, 1717, 1718, 1724, 1731, 1732, 1735, 1737, 1740, 1851, 1852). This includes literal `style="`, single-quote, and f-string variants.

## Design decisions

**D1 — Where derivation lives: JavaScript, single implementation.**
The live preview re-derives on every color-input drag. A server round-trip per drag is not viable,
so derivation must exist in JS. Having it *also* in Python guarantees drift. Therefore: **JS owns
derivation**, and Python's `RB_TOKENS_CSS` ships only the *default preset*, fully pre-derived, as
literal values — a no-JS fallback that renders exactly today's appearance.

**The corollary: Python never derives, so Python must never be the thing that stores derived
values.** The persisted artifact is the **7 settable inputs, versioned** — not the derived output:

```json
{ "schema_version": 1, "derivation_version": 1, "preset": "custom", "inputs": { …7 colors… } }
```

Python serializes that record into the page; the single JS implementation derives from it before
paint. The boundary holds because Python is moving *data it was given*, never computing a color.

*Superseded design, kept because the reason matters:* an earlier revision persisted a
**fully-derived snapshot** — all 10 resolved tokens, computed by JS at Save time. It also honored
"Python never derives", but it was strictly worse, and the failure is instructive. Derived output
frozen at Save time cannot survive a change to the mix/luminance formula: every stored snapshot is
silently stale, the drift test can't catch it (it derives fresh fixtures from current JS), and
because the inputs were discarded there is **no way to regenerate** the user's intended theme. The
versioned-inputs record has the opposite property — a formula change re-derives correctly from what
was kept, and `derivation_version` makes the change detectable rather than silent. *(Found by the
GH-154 design consult, 2026-07-18.)*

The record is validated on read (all 7 inputs present, each a well-formed hex, `schema_version`
recognized) and rejected wholesale on failure — a partial record would render a half-themed page,
which is worse than falling back to the default preset.

The drift risk this creates is real and must be gated, not trusted — but the obvious test does not
gate it. Loading a page with *no* stored theme only reads Python's own defaults back and asserts
they equal themselves; JS derivation never runs. The test must therefore **seed `localStorage`
before navigation**:

1. Seed the default preset's 7 settable colors, load, and assert all resolved tokens from
   `getComputedStyle(document.documentElement)` equal the Python `RB_TOKENS_CSS` defaults. This is
   the actual drift gate: JS derives, Python's literals are the expected value.
2. Seed at least one **non-default** fixture whose expected outputs are computed independently (by
   hand, in the test, from the mix/luminance formulas — not by calling the implementation), so the
   test can fail if the derivation formula itself changes.

Playwright is already available (see [[reference-playwright-install]]) and invariant #8 already
requires rendering.

*Alternative rejected:* derivation in Python exposed via a `/settings/theme/preview` endpoint —
correct single-source, but a network round-trip on `input` events makes the live preview laggy, and
the mockup's value is that the preview is immediate.

**D2 — Theming is client-side, applied before paint.**
`/` is a static build artifact regenerated by `scripts/install_pulse_web_scheduler.sh`; invariant #6
says never edit it directly, and re-running `build_page()` on every theme change is absurd. So the
theme is applied by setting custom properties on `document.documentElement` from a **small inline
script in `<head>`, before first paint**, reading `localStorage`. Deferring this to a
`<script defer>` or `DOMContentLoaded` produces a flash of the default theme on every load — that
flash is a defect, not a cosmetic nit, and the acceptance criteria call it out.

This is the reason the whole feature is possible without touching the render pipeline.

**D3 — Persistence: `localStorage` only. v1 has no server-side theme storage.**
The versioned record from D1 lives in `localStorage` and nowhere else. There is no `config.py`
write-through, no `POST` endpoint, and no server-rendered custom theme.

This reverses an earlier revision of this doc, and the reason is worth stating plainly, because
"the durable record is obviously better" is the intuition that produced the mistake:

**Durable cross-browser theming cannot work for `/` without a rebuild, and `/` is the main page.**
`/` is served as a `FileResponse` of an already-built `web/pulse.html` (`pulse_server.py:268`),
regenerated by a **30-minute** scheduler (`install_pulse_web_scheduler.sh:27`). A config write does
not regenerate it. So "Save → clear `localStorage` → reload" would show the *old* theme on `/` for
up to half an hour. The sting is precise: with `localStorage` intact every route themes instantly
via the pre-paint script, so **the only scenario durable persistence exists to serve is the exact
scenario in which it fails.** It would have added a config schema, an endpoint, and a shared
serializer to buy a stale page.

The available fixes were rebuild-on-Save (a `build_page()` regeneration in the request path, racing
the scheduler and needing atomic-write care) or dropping it. For a single-operator local dashboard,
dropping it is correct — the cleared-browser case is rare, cheap to recover from (re-pick the
preset), and speculative until observed.

*Revisit only on evidence:* if the theme is genuinely lost often enough to annoy, the smallest
honest addition is rebuild-on-Save, not a scheduler-dependent config read. Note it in the progress
log if it happens.

**What this deletes from the plan:** P6 entirely, the `get_theme()`/`set_theme()` config work, the
`POST` endpoint, the "one shared serializer" for live-vs-static, and the acceptance criterion that
asserted a saved theme survives a cleared browser. `render_shell()` stays pure and I/O-free
(`web_components.py:602-645`) — it is handed a theme bootstrap by its callers and never reads
config, which is the property that made it a safe seam in the first place.

**D4 — The picker page is a new live route, `/settings`.**
Not part of the static `/`. It goes in `web.py` alongside the other live pages, using
`render_shell()` so it is itself themed. Breadcrumb `Pulse / Settings` per the mockup.

**D5 — `localStorage` key is `pulse-theme-settings-v2`**, matching the mockup, shape
`{theme: <preset key|'custom'>, colors: <7-key object|null>}`. `null` colors means "use the preset's
values" — that distinction is what makes Reset work, so preserve it rather than eagerly
materializing the preset into `colors`.

## Phases

Sequential. Each phase ends green on the [gate](#verification-gate) and is committed separately —
phase 3 in particular is large enough that bisecting matters.

### P0 — Vocabulary, full `:root`, and the rename
No behavior change. Resolve `--fg-dim` / `--shadow` against their real call sites, fix the derived
token count, and mine `FOCUS5-UI.html` for naming. Write the token table into `web_components.py`
as the `RB_TOKENS_CSS` docstring. Land the rename of the 6 existing 1:1 tokens with call sites
updated. **Also expand `:root` to the complete tier-1 + tier-2 set**, with default-preset values —
so every token any later phase will reference already exists and resolves.

Enumerate and record here (not estimate): the true inline `style=` write-set for P2, and the final
derived-token count.

**Exit:** every page renders byte-identically except for property names; every tier-1 and tier-2
token is defined in `:root`.

> **Why `:root` moved here from P1.** P1/P2/P3 are then pure literal→`var()` rewrites against a
> vocabulary that already exists, touching **disjoint files**, each depending on P0 but not on each
> other. They still *execute* sequentially — `marathon.sh` resolves `depends_on` topologically and
> runs phases one at a time, and the single driver lock deliberately stops two worktrees racing on
> the same `ROOT@HEAD` (GH-42). The decoupling buys bisectability, not wall-clock: each phase can
> be re-run, hand-taken, or fail without cascading into the others' briefs.

### P1 — Tokenize the shared shell (`web_components.py`)
Rewrite the 36 literals in `RB_CHROME_CSS` / `RB_BUTTON_CSS` / the row primitive to `var()`.
No `:root` changes — P0 already defined every token this phase consumes.
**Exit:** `/focus-5`, `/whats-next`, `/auth-log`, `/sleuth-graph` visually unchanged.

### P2 — Tokenize `web.py`
`_CSS` (`web.py:244-356`), the focus-5 inline `<style>` (`:700-731`), `_SYSLOG_TOGGLE_CSS`
(`:1473`), the inline `style=` attributes (7 literal `style="`, plus quote/f-string variants
enumerated in P0 — incl. the `#5b5750` tooltip at `:1851-1853`), and the Cytoscape `_KIND_COLOR`
emission at `:1597-1601` / `:1714-1719` per the categorical-color call. ~51 literals plus the
non-CSS surfaces.

### P3 — Tokenize `pulse_web.py` `PAGE_CSS` + the canvas palettes
The big one: 101 literals across ~690 lines, plus 7 inline `style=` attributes. Also the two
Chart.js canvases: `PIE_PALETTE` (`:1001`) reaches both charts via `:982` and `:1040`, and its
label/stroke colors must be fed from the resolved theme at render time rather than left literal
(see [Color that CSS variables cannot reach](#color-that-css-variables-cannot-reach)). Includes the
calendar module's `.cal-*` colors from GH-137 (`#e8b93a` / `#f5edd8` event tones, the now-line)
— the now-line becomes `var(--nowline)`, which is precisely why the mockup exposes it as tier 1.
**Exit:** `python3 scripts/pulse_web.py` regenerates, and a Playwright screenshot of `/` is
visually identical to a pre-change baseline captured at P0.

### P4 — Theme runtime
The pre-paint inline script (D2), the JS derivation functions (D1), the versioned record schema +
validator (D1), `localStorage` read/write (D5). No UI yet — verified by setting `localStorage`
by hand and reloading each page.

**The insertion contract, which D2 asserts but does not yet specify.** No suitable slot exists
today: `render_shell()`'s only head hook emits `head_extra` *after* the style block
(`web_components.py:617-621`, `:640-642`, and its docstring says so explicitly), and `/` uses that
hook only for deferred Chart.js while its app script sits at body-end
(`pulse_web.py:3169-3172`). Neither can theme before first paint. So P4 must **add a synchronous
pre-style head slot** to `render_shell()`, and `build_page()` must emit through the same slot —
one mechanism, both pipelines. Requirements on it:

- Synchronous and inline. No `defer`, no `async`, no external file — any of the three reintroduces
  the flash the whole decision exists to prevent.
- Emitted *before* the `<style>` block, so tokens are set when the stylesheet first resolves.
- **Passed in as an explicit argument** (a `theme_bootstrap` parameter supplied by `_page()` at
  `web.py:386-388` and `build_page()` at `pulse_web.py:3173-3182`), never read from config inside
  `render_shell()`. In v1 it is a static default-preset bootstrap for every caller; keeping it a
  parameter rather than a global preserves `render_shell()`'s I/O-free property and is the seam any
  future durable-persistence work would use.
- **Malformed-storage fallback**: absent, unparseable, schema-invalid, or partial `localStorage`
  falls back to the default preset silently. A theme picker that white-screens on a bad JSON blob
  is a worse failure than one that ignores it.

**Exit:** all 5 routes respond to a hand-set theme; the drift test from D1 passes; and **first
paint** is verified — not merely the post-load state. A post-load assertion passes even when a
flash occurred, so it cannot gate D2's central claim. Capture the first frame (Playwright
screenshot on `domcontentloaded` with the network idled, or a CDP paint trace) and assert the page
background is already the themed value.

### P5 — The Settings page
`/settings` route in `web.py`. Preset grid with the mini-dashboard previews, the 7-field
fine-tune grid, live preview section, Save / Reset with the mockup's dirty-state affordances
(`saveOpacity`, `saveCursor`). Port the mockup's markup to `render_shell()` conventions and the
shared row primitive — do not carry over its inline-style-everything approach, which is a
design-tool artifact.

### ~~P6 — Durable persistence~~ *(cut — see D3)*
`config.py` write-through, the `POST` endpoint, and build-time regeneration of `RB_TOKENS_CSS`
from config are **out of scope**. They cannot deliver their one benefit — a saved theme surviving a
cleared browser — on `/`, which is rebuilt on a 30-minute schedule. **v1 ends at P5.**

## Acceptance criteria

1. All 4 presets plus Custom apply correctly on **all 5 routes** — verified by Playwright
   screenshot, 5 routes × 5 themes = 25 renders, and **looked at** (invariant #8).
2. **No flash of default theme** on load, on any route, including the static `/`.
3. Zero hardcoded color literals remain in `PAGE_CSS`, `_CSS`, `RB_CHROME_CSS`, `RB_BUTTON_CSS`,
   `_SYSLOG_TOGGLE_CSS`, or any inline `style=` — except tier-3 status colors and any literal
   explicitly justified in this doc's progress log.
4. The default preset is **pixel-identical to today's dashboard**. This feature must be invisible
   to an operator who never opens Settings.
5. Save persists across reload; Reset returns to the selected preset's defaults without clearing
   the preset selection.
6. **A cleared browser falls back cleanly, and says so.** Clearing `localStorage` returns every
   route to the default preset with no error, no half-themed page, and no console noise. Per D3,
   v1 deliberately does *not* recover a saved theme across browsers — this criterion asserts the
   documented behavior, not the wished-for one.
   Also gate the malformed cases: absent, truncated, non-JSON, wrong `schema_version`, and missing
   an input key must each fall back to the default preset rather than render partially.
7. **The drift test exercises JS derivation**, i.e. it seeds `localStorage` before navigation and
   includes a non-default fixture with independently computed expectations. A test that loads with
   no stored theme does not satisfy this criterion.
8. **No first-paint flash**, asserted on the first frame rather than post-load, on all 5 routes.
9. **Every `var()` reference resolves.** No token is used that `:root` never defines — checked by
   asserting no resolved computed value is the empty string across the token set.
10. Chart and graph output stays legible in every preset — the pie and Cytoscape surfaces get
    screenshot coverage and a label-vs-background contrast check, not just the HTML routes.
6. The JS-vs-Python default-token drift test (D1) passes.
7. Dark mode passes a WCAG AA contrast check (4.5:1) for `--ink` on `--page`, `--ink` on `--card`,
   and `--accent-ink` on `--accent`. Custom themes are the operator's own risk and are **not**
   blocked, but the picker warns below threshold.
8. `web/pulse.html` is never hand-edited (invariant #6).

## Verification gate

Per GH-136 — `pytest tests/` carries 15 pre-existing failures in `test_auto_promote.py` +
`test_hiqs_pipeline.py`. Gate module-scoped:

```bash
python3 -m pytest tests/test_tz_utils.py tests/test_pulse_web_calendar.py \
  tests/test_pulse_web_goals.py tests/test_pulse_web_worknext.py \
  tests/test_pulse_server_figma.py tests/test_pulse_server_apple_reminders.py \
  tests/test_theme_tokens.py -q \
  && python3 scripts/pulse_web.py
```

`tests/test_theme_tokens.py` is new in P0 and grows through the phases. Plus `rebalance doctor`
and `utils/pdda/pdda.sh run` clean.

## Anti-goals

- **Not** a general design-system rewrite. Spacing, typography, radii and shadows stay as they are;
  only color is tokenized. Scope creep here would swallow the feature.
- **Not** theming the Rich terminal TUI (`scripts/dashboard.py`). Different renderer, own theme,
  own test.
- **Not** theming `experimental/` spikes or `ARCHITECTURE/` docs artifacts.
- **No** per-module theme overrides. One vocabulary, one `:root`. (Invariant #3's logic applied
  to color.)
- **No** `prefers-color-scheme` auto-switching in v1. Explicit operator choice only — auto-switching
  interacts with the saved-custom-theme case in ways worth designing separately.
- **No** new time helper, no import workarounds (invariants #1, #5) — restated because every day
  of this epic has been tempted by one or the other.

## Risks

1. **The collapse is lossy in a way that shows.** ~190 literals onto ~10 tokens means colors that
   are currently subtly distinct become identical. Most of that is unintentional drift worth
   removing; some of it is deliberate. The P0→P3 screenshot baseline is what tells them apart, and
   acceptance criterion 4 is the backstop.
2. **`--fg-dim` may not collapse cleanly** into `--timestamp`. If its call sites include non-time
   text, the vocabulary needs an 11th derived token. Resolve in P0, before anything depends on it.
3. **Pre-paint script placement is fragile.** `build_page()` composes the static file; the script
   must land in `<head>` ahead of the stylesheet. Easy to regress silently — the only symptom is a
   flash, which no assertion catches. Needs a deliberate Playwright check, not a DOM assertion.
4. **Custom themes can be made unreadable.** Deliberately permitted (criterion 7 warns, doesn't
   block) — but Reset must be genuinely reliable, since it is the only escape from a theme so bad
   the Settings page itself is unusable. Consider a `?theme=default` URL escape hatch.
5. **`localStorage` is per-origin — accepted, not mitigated.** An operator hitting the dashboard on
   both `localhost:PORT` and a LAN IP gets two independent themes. Earlier revisions named D3's
   `config.py` write-through as the fix; since P6 is now cut (D3), this is a **known v1
   limitation** and must be stated in the release note rather than discovered. It is also the one
   real argument for reinstating durable persistence later — so if this turns out to bite in
   practice, revisit D3 with rebuild-on-Save, and note it here.

## Progress log

- **2026-07-18** — Worktree `~/wt/theme-picker` cut from `origin/development` on branch
  `feat/theme-picker`. Issue #154 filed under epic #136. CSS surface inventory taken (table above).
  This doc written; **no code written yet**. Next: QA relay on this doc via `relay-xyz` with codex
  as reviewer, then P0.
- **2026-07-18** — QA relay R1 complete (codex, *Changes requested*: 1 Blocker, 5 Shoulds, 1 Pass).
  All six folded in; still **no code written**. The substantive change is the Blocker: D1 and D3
  contradicted each other, since D3 required the server to render custom themes while D1 forbade
  the server from deriving. Resolved by making the persisted artifact a **fully-derived snapshot**
  produced only by JS — Python serializes, never computes — which keeps D1's single-implementation
  goal and makes D3 actually buildable. Also: `--shadow` promoted to an explicit derived token with
  the count deferred to P0; the drift test rewritten to seed `localStorage` (the original was
  tautological — it asserted Python's defaults against themselves and never ran JS); P4 given a
  concrete pre-style head-slot contract, since no existing hook emits before the stylesheet; and a
  new section added for color that `var()` cannot reach (`PIE_PALETTE` on both Chart.js canvases,
  Cytoscape `_KIND_COLOR`, inline `style=`), which the original inventory missed entirely.
  Two corrections to *my own* claims: `web.py` has 7 literal `style="` occurrences, not the 5 I
  wrote (codex's 14 counts quote/f-string variants — the P2 write-set is enumerated in P0 rather
  than guessed); and the mockup's `PIE_PALETTE` reach was verified directly at `:982`/`:1040`
  rather than taken on the reviewer's word, per invariant #10 applied to findings as well as
  approvals.
- **2026-07-18** — Design consult (codex, one-shot advisory via `consult.sh`, no relay loop) on the
  D1/D3 persistence design alone. Two Blockers, both verified against source and both accepted;
  **the design I committed hours earlier was wrong in two ways.** Worth recording, because the
  error has a shape that will recur.
  1. **Durable cross-browser theming can't work for `/`.** It's a `FileResponse` of a pre-built
     file (`pulse_server.py:268`) on a 30-minute rebuild (`install_pulse_web_scheduler.sh:27`), so
     a config write leaves it stale for up to half an hour. Acceptance criterion 6 as I wrote it
     was unsatisfiable. **P6 is cut**; v1 is `localStorage`-only and ends at P5. The tell was there
     to be noticed: the only case durable persistence served was the only case it failed at.
  2. **The derived snapshot was strictly worse than persisting inputs.** Freezing derived output at
     Save time cannot survive a formula change — every stored snapshot goes silently stale, the
     drift test can't see it, and with the inputs discarded the theme can never be regenerated.
     Now a versioned `{schema_version, derivation_version, preset, inputs}` record; JS derives from
     it before paint. Python still never derives — it moves data instead of results.
  The meta-lesson: the snapshot was introduced *as the fix to the previous review's Blocker*, and I
  defended it on that basis. A fix that resolves a contradiction is not thereby a good design, and
  the second reviewer had to be pointed at that one decision to see it. Consult cost ~40k tokens
  against ~88k for a full relay round, and found more.
  Also verified independently: `_page()` (`web.py:386-388`) and `build_page()`
  (`pulse_web.py:3173-3182`) both route through `render_shell()`, so the shared seam is real —
  P4's pre-paint slot is now an explicit `theme_bootstrap` parameter, keeping `render_shell()`
  I/O-free. (`consult.sh` stamped `NO FIRSTHAND VERIFICATION CITED` on this answer; that was a
  false positive — the `[Pass]` did carry `file:line`, and all citations checked out.)
