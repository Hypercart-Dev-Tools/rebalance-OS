---
title: Web app theme color picker — tokenize the UI CSS, then ship Settings → Color theme
status: "Planning — no code written. Worktree ~/wt/theme-picker on branch feat/theme-picker (from origin/development). Awaiting QA relay on this doc before build."
gh_issue: 154
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

**Tier 2 — derived (3), never settable.** Per the mockup's `themeOf()`:

- `--muted` = `mix(ink, page, 0.45)`
- `--accent-ink` = `#ffffff` if `isDark(accent)` else `#111111`
- `--zebra` = `mix(card, isDark(page) ? #ffffff : #000000, 0.96)`

`isDark(hex)` is the standard luminance test `0.299R + 0.587G + 0.114B < 128`.

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

## Design decisions

**D1 — Where derivation lives: JavaScript, single implementation.**
The live preview re-derives on every color-input drag. A server round-trip per drag is not viable,
so derivation must exist in JS. Having it *also* in Python guarantees drift. Therefore: **JS owns
derivation**, and Python's `RB_TOKENS_CSS` ships only the *default preset*, fully pre-derived, as
literal values — a no-JS fallback that renders exactly today's appearance.

The drift risk this creates is real and must be gated, not trusted: a Playwright test loads a page,
reads `getComputedStyle(document.documentElement)` for every tier-1 and tier-2 token, and asserts it
equals the Python `RB_TOKENS_CSS` defaults. Playwright is already available (see
[[reference-playwright-install]]) and invariant #8 already requires rendering.

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

**D3 — Persistence: `localStorage` is the applied layer; `config.py` is the durable record.**
`localStorage` alone is per-browser and invisible to the rest of the system. `config.py` alone
can't be read by a static page. So: the picker writes `localStorage` immediately (that's what
applies), and Save also `POST`s to a new endpoint that writes through `get_theme()`/`set_theme()`
in `config.py`. On a browser with no `localStorage` entry, the server-rendered default in
`RB_TOKENS_CSS` is regenerated from `config.py` at build time, so a saved theme survives a cleared
browser.

*If the QA relay finds this over-built for v1:* the fallback is `localStorage`-only, and
`config.py` write-through moves to a phase 6. It is deliberately the last phase for that reason.

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

### P0 — Vocabulary and derivation contract
No behavior change. Write the token table into `web_components.py` as the docstring of
`RB_TOKENS_CSS`, resolve the `--fg-dim` / `--shadow` calls against their real call sites, and mine
`FOCUS5-UI.html` for naming. Land the rename of the 6 existing 1:1 tokens with call sites updated.
**Exit:** every page renders byte-identically except for property names.

### P1 — Tokenize the shared shell (`web_components.py`)
Expand `:root` to the full tier-1 + tier-2 set with default-preset values. Rewrite the 36 literals
in `RB_CHROME_CSS` / `RB_BUTTON_CSS` / the row primitive to `var()`.
**Exit:** `/focus-5`, `/whats-next`, `/auth-log`, `/sleuth-graph` visually unchanged.

### P2 — Tokenize `web.py`
`_CSS` (`web.py:244-356`), the focus-5 inline `<style>` (`:700-731`), `_SYSLOG_TOGGLE_CSS`
(`:1473`), and the 5 inline `style=` attributes. 51 literals.

### P3 — Tokenize `pulse_web.py` `PAGE_CSS`
The big one: 101 literals across ~690 lines, plus 7 inline `style=` attributes. Includes the
calendar module's `.cal-*` colors from GH-137 (`#e8b93a` / `#f5edd8` event tones, the now-line)
— the now-line becomes `var(--nowline)`, which is precisely why the mockup exposes it as tier 1.
**Exit:** `python3 scripts/pulse_web.py` regenerates, and a Playwright screenshot of `/` is
visually identical to a pre-change baseline captured at P0.

### P4 — Theme runtime
The pre-paint inline script (D2), the JS derivation functions (D1), `localStorage` read/write
(D5). No UI yet — verified by setting `localStorage` by hand and reloading each page.
**Exit:** all 5 routes respond to a hand-set theme; the drift test from D1 passes.

### P5 — The Settings page
`/settings` route in `web.py`. Preset grid with the mini-dashboard previews, the 7-field
fine-tune grid, live preview section, Save / Reset with the mockup's dirty-state affordances
(`saveOpacity`, `saveCursor`). Port the mockup's markup to `render_shell()` conventions and the
shared row primitive — do not carry over its inline-style-everything approach, which is a
design-tool artifact.

### P6 — Durable persistence
`get_theme()` / `set_theme()` in `config.py`, the `POST` endpoint, build-time regeneration of
`RB_TOKENS_CSS` defaults from config. Split out per D3 so v1 can ship without it.

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
5. **`localStorage` is per-origin.** An operator hitting the dashboard on both `localhost:PORT` and
   a LAN IP gets two independent themes. D3's `config.py` write-through is what fixes this; if P6
   is deferred, this is a known v1 limitation and should be stated in the release note rather than
   discovered.

## Progress log

- **2026-07-18** — Worktree `~/wt/theme-picker` cut from `origin/development` on branch
  `feat/theme-picker`. Issue #154 filed under epic #136. CSS surface inventory taken (table above).
  This doc written; **no code written yet**. Next: QA relay on this doc via `relay-xyz` with codex
  as reviewer, then P0.
