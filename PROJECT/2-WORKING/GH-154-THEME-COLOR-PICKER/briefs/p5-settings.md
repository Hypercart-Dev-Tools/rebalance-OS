# Phase 5 — The Settings page (`/settings`)

Part of **GH-154**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/154
Runs after P4 (complete). **Artifacts: `src/rebalance/web.py` and `scripts/pulse_server.py` only.**

Read first: `PROJECT/2-WORKING/GH-154-THEME-COLOR-PICKER.md` (decisions **D1–D7**, acceptance
criteria) and `PROJECT/2-WORKING/GH-136-DASHBOARD-REDESIGN.md` (the 10 standing invariants).
Design source: `PROJECT/1-INBOX/dashboard-redesign-2026-07-18/Settings Theme.dc.html`.

**P4 is already built and working — do not rebuild it.** The runtime exists in
`src/rebalance/web_components.py` as `RB_THEME_BOOTSTRAP_JS`: it reads the record, derives tier-2,
and applies before paint on every route. Your job is the UI that *writes* that record.

## The contract you must write to

`localStorage['pulse-theme-settings-v2']`, exactly this shape — P4's validator rejects anything else
wholesale and falls back to the default preset:

```json
{ "schema_version": 1, "derivation_version": 1, "preset": "dark",
  "inputs": { "page":"#191713","card":"#242019","ink":"#f0ece1","accent":"#6f97ea",
              "border":"#3a3529","nowline":"#e05a48","timestamp":"#8f887a" } }
```

**Only the 7 tier-1 inputs are persisted** (D1). Never write derived values — a frozen snapshot
cannot survive a formula change. All 7 keys must be present and match `^#[0-9a-fA-F]{6}$`.

## Tasks

1. **Route.** `@app.get("/settings")` in `scripts/pulse_server.py`, delegating to a
   `settings_page()` renderer in `src/rebalance/web.py` — mirror the `/focus-5` shape at
   `pulse_server.py:108`. Add "Settings" to the sidebar nav.
2. **Render through `render_shell()`** so the page is itself themed. Breadcrumb `Pulse / Settings`.
3. **Preset grid** — the 4 presets from the mockup's `PRESETS` (default / dark / grey / lightblue),
   each with its mini-dashboard preview swatch. Selecting one applies it live.
4. **Fine-tune grid** — 7 colour inputs, labelled per the plan's tier-1 table. Editing any field
   switches the selection to Custom.
5. **Live preview** — re-derive and apply on every `input` event, so the whole page updates as the
   operator drags. This is the mockup's central value; a round-trip per drag is not acceptable (D1).
6. **Save / Reset** with the mockup's dirty-state affordances (`saveOpacity`, `saveCursor`).
   **Reset returns to the selected preset's defaults without clearing the preset selection** —
   preserve that distinction (D5), it is what makes Reset useful.
7. **Reuse P4's derivation.** Do not write a second copy of `mix()` / `isDark()`. Factor the
   functions out of `RB_THEME_BOOTSTRAP_JS` into a shared constant both it and this page emit, or
   have the page call into what the bootstrap already defined. **Two derivation implementations is
   the exact failure D1 exists to prevent** — a reviewer should reject a duplicate outright.

## Anti-goals

- **Do not port the mockup's inline-style-everything approach.** It is a design-tool artifact.
  Real CSS rules, tokens via `var()`, and the shared row primitive (invariant #3).
- **Do not add colour literals.** Every colour on this page comes from a token. The Settings page
  being off-theme would be a self-own.
- **Do not touch `RB_THEME_BOOTSTRAP_JS`'s validation or storage contract.** If you believe it is
  wrong, report it — changing it silently breaks all five routes.
- No `config.py`, no `POST` endpoint, no server-side persistence. **P6 was cut** (D3); v1 is
  `localStorage`-only and ends here.

## Exit conditions

- [ ] `/settings` renders, is in the nav, and is itself themed by whatever theme is active
- [ ] All 4 presets apply live on the page; the 7 fields edit; changes reach every other route on reload
- [ ] Save writes a record P4's validator accepts; Reset restores the preset's defaults without
      clearing the selection
- [ ] **Exactly one** derivation implementation exists in the codebase
- [ ] No colour literals added; no `var()` resolves to empty
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

- **#1** Time display goes through `format_timestamp()`. **#3** Use the shared row primitive.
- **#5** No `sys.path` / `importlib` workarounds. **#6** Never hand-edit `web/pulse.html`.
- **#8 Verify by rendering** — and note honestly that you cannot *see* the result. Report what you
  built and what you could not verify; **the operator does the visual pass.** Do not claim the page
  looks correct. An overclaim here is worse than an omission: on Day 0 the automated reviewer
  approved two defects that only a human looking at the render caught.
