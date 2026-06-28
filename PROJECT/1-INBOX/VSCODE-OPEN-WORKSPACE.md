---
title: Repo links open VS Code with "focus-if-open" — Build Plan
status: Not started
owner: noel
created: 2026-06-27   # UTC
updated: 2026-06-27   # UTC — bump every time the plan changes
reversibility: Easy (Mac app) · Costly (web exec endpoint — see §Blast) — both are flag/fallback-shielded
---

# Repo links open VS Code with "focus-if-open" — Build Plan

Make the "Open ↗" button on a repo card land you in the *right* VS Code window:
focus the window if that repo is already open, spawn exactly one new window if
it isn't. Today both surfaces fire the `vscode://file/{path}` URI scheme, which
either hijacks the active window or always spawns a new one.

| Most recently completed phase | What's next |
| --- | --- |
| — (not started) | Phase 1: Mac app (Focus 5 Float) |

## Table of contents
- [The protocol (from research)](#the-protocol-from-research)
- [Reality check — the protocol does not drop into a browser](#reality-check--the-protocol-does-not-drop-into-a-browser)
- [Phase 1: Mac app (Focus 5 Float)](#phase-1-mac-app-focus-5-float)
- [Phase 2: Web app (pulse dashboard)](#phase-2-web-app-pulse-dashboard)
- [What we deliberately are NOT building](#what-we-deliberately-are-not-building)

## The protocol (from research)

The research established **why** every naïve launcher gets this wrong and the
one-line fix:

- `code <file>` (file only) → VS Code forces the file into the **currently
  active window**, hijacking whatever unrelated project is open.
- `code -n <folder>` (forced new window) → spawns a **new window every time**,
  even when the repo is already open.
- **`code <folder>` (folder, no `-n`/`-r`)** → VS Code's IPC routes to the
  existing window if that folder is open (focus), else spawns one new window.
  This is the behavior we want.

We only ever have the **repo folder** (the cards carry `local_path`, never a
specific file), so the command is exactly `code <repoPath>` — the file argument
in the raw research is moot here and is cut.

Refs: [VS Code CLI](https://code.visualstudio.com/docs/editor/command-line) ·
[window.openFoldersInNewWindow](https://code.visualstudio.com/docs/getstarted/userinterface#_window-management)
(default `"default"` is the protective behavior we rely on).

## Reality check — the protocol does not drop into a browser

`code <folder>` is a **shell command**. The native Mac app can run it
(`Process`); a **browser cannot**. So the protocol applies cleanly to exactly
one of the two surfaces:

| Surface | Can run `code`? | Mechanism |
| --- | --- | --- |
| Focus 5 Float (native SwiftUI, ad-hoc signed, no sandbox) | Yes | `Process` → `code <repoPath>` |
| Pulse web dashboard (runs in a browser) | No | Must POST to the local pulse server, which runs `code` on its behalf |

**Phase 1 is the real win and is cheap.** Phase 2 buys window-focus parity for
the web app at the cost of a localhost endpoint that executes `code` — a new
exec surface that must be locked down. Build Phase 1 first; Phase 2 is gated on
whether the web app's current `vscode://` behavior is actually annoying enough
to justify the exec endpoint (see [§Blast](#phase-2--blast)).

---

## Phase 1: Mac app (Focus 5 Float)
**Goal:** Clicking "Open ↗" on a repo card runs `code <repoPath>` via a direct
argv `Process` (no shell), focusing an already-open window or spawning exactly
one new one — with a graceful fallback to the current `vscode://` URI when the
`code` binary can't be found.

Touch points (already located):
- [ContentView.swift:286](macOS/Apps/Focus5Float/Sources/Focus5Float/ContentView.swift#L286) — the "Open ↗" button, currently `open(card.vscodeUrl)`.
- [ContentView.swift:376](macOS/Apps/Focus5Float/Sources/Focus5Float/ContentView.swift#L376) — the `open(_:)` helper (`NSWorkspace.shared.open`).
- [Models.swift](macOS/Apps/Focus5Float/Sources/Focus5Float/Models.swift) — `RepoCard.localPath` is already on the model; `vscodeUrl` stays as the fallback.

- [ ] Add `localPath` use to the launch path: the button calls a new
      `launchInVSCode(repoPath:fallbackURL:)` instead of `open(card.vscodeUrl)`.
- [ ] Resolve the `code` binary once from a fixed candidate list — first that
      exists wins: `/opt/homebrew/bin/code`, `/usr/local/bin/code`,
      `/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code`.
      Output: a helper returning `URL?` (nil ⇒ none found).
- [ ] Launch with a **direct argv** `Process`: `executableURL` = resolved
      binary, `arguments = [repoPath]`. **No `/bin/sh -c`, no string escaping** —
      argv arrays are immune to the quoting/injection class the raw research's
      `sh -c` reintroduced. Run off the main thread.
- [ ] If the binary is nil, fall back to `NSWorkspace.shared.open(fallbackURL)`
      (today's `vscode://` path) so the button is **never dead**.
- [ ] Log each launch: chosen binary (or "fallback"), repoPath, and
      `process.terminationStatus`. One line, to the app's existing log sink.
- [ ] *Deferred (YAGNI):* foreground-pull via `NSRunningApplication … activate`.
      `code <folder>` usually raises its own window. Add this **only if** you
      observe VS Code launching behind the app — don't pre-build it.

### Phase 1 — QA checklist
- [ ] **Observed:** repo already open in VS Code → click focuses that window,
      **no** new window (eyeball test, recorded in the PR description).
- [ ] **Observed:** repo not open → click spawns **exactly one** new window.
- [ ] **Observed:** rename/quit the `code` symlink so resolution returns nil →
      click still opens the repo via the `vscode://` fallback.
- [ ] Self-check on the pure logic (binary resolution + argv assembly) — a tiny
      Swift `assert`-based check or XCTest that fails if the candidate order or
      argv shape regresses. Point to the run, not an assertion.
- [ ] Diagnosable: launch log line present; one-shot launch has **no retry
      loop** (stop-condition trivially satisfied — note it in the PR).
- [ ] Blast: undo = revert one Swift file (Easy). Shield = `vscode://` fallback.
      No tripwire needed (no shared state touched).
- [ ] Status table + `updated:` bumped before marking this phase done.

---

## Phase 2: Web app (pulse dashboard)
**Goal:** The web "Open ↗" button gets the same focus-if-open behavior by POSTing
a **repo id** to a new localhost-only pulse endpoint that runs `code <repoPath>`,
where `repoPath` is resolved **server-side from the already-scanned repo set** —
never from a client-supplied path.

> Gate: only build this if the web app's current `vscode://` behavior is
> measurably annoying. If `vscode://file/{folder}` already focuses-or-opens
> acceptably in your setup, **skip Phase 2** — the exec endpoint is not worth its
> blast radius for a cosmetic window-management gain. Decide before coding.

Touch points (already located):
- [web.py:466](src/rebalance/web.py#L466) / [web.py:476](src/rebalance/web.py#L476) — card renders `button_link(..., href=vscode_url)`.
- [web_components.py:65](src/rebalance/web_components.py#L65) — `button_link()` (the `<a>` helper).
- [focus5_scan.py:808](src/rebalance/ingest/focus5_scan.py#L808) — `vscode_url()`; the scan already owns the repo→`local_path` mapping (the allowlist).

- [ ] Add a `POST /open-repo` handler to the pulse server that takes a **repo
      identifier** (the scan's stable key / `repo_full_name` or row id), looks up
      its `local_path` from the **server's own scanned-repo set**, and rejects any
      id not in that set (404). The client never sends a path.
- [ ] Run the launch with a **direct argv** subprocess:
      `subprocess.run([code_bin, local_path])` — `shell=False`, argv list, no
      string interpolation. Resolve `code_bin` from the same fixed candidate list
      as Phase 1; if absent, return 409 and let the button keep the `vscode://`
      fallback (below).
- [ ] **Bind the endpoint to loopback only** and require a same-origin check
      (the dashboard is already localhost). Reject cross-origin / non-loopback.
- [ ] Web button: on click, `fetch('/open-repo', {repoId})`; on any non-200,
      fall through to the existing `vscode://` href. Keep the `<a href="vscode://…">`
      as the no-JS / failure fallback so the button is **never dead**.
- [ ] Log each request with a correlation id: repo id, resolved path,
      allowlist hit/miss, exit code. To the pulse server log.

### Phase 2 — Blast
- **Undo class:** Costly — this adds a request handler that **executes a binary**.
  Backing it out is one route removal, but the exposure window while it's live is
  the cost being priced.
- **Blast radius:** anything that can reach `localhost:<pulse-port>` can ask the
  server to open repos in your editor. The **allowlist (resolve id → scanned
  path, reject unknown)** collapses this from "open/exec arbitrary path" to "open
  one of N already-discovered repos." Argv-list (no shell) removes the command-
  injection class entirely.
- **Shield:** loopback-only bind + same-origin check + argv allowlist + `vscode://`
  client fallback. (Explicitly **not** a public-facing endpoint.)
- **Tripwire:** log allowlist **misses**; any miss = someone is probing the
  endpoint with ids the server didn't issue. Alert/disable if misses appear.

### Phase 2 — QA checklist
- [ ] **Observed:** click in browser → repo focuses-or-opens via the server, no
      new window when already open.
- [ ] **Observed:** POST a repo id **not** in the scanned set → 404, nothing runs
      (negative test, recorded).
- [ ] **Observed:** cross-origin / non-loopback POST → rejected.
- [ ] **Observed:** `code` binary absent → 409, button falls back to `vscode://`.
- [ ] Test the allowlist resolver (`pytest`): known id → path, unknown id → reject.
      Point to the run.
- [ ] Diagnosable: correlation-id log line per request; one-shot, **no retry loop**.
- [ ] House: single write/exec path — `/open-repo` is the **only** route that
      shells out; `local_path` comes only from the scan, never the client.
- [ ] Status table + `updated:` bumped before marking this phase done.

---

## What we deliberately are NOT building

- **No file-deep-linking.** The raw research passed `code <folder> <file>`; the
  cards only carry the repo folder, so we pass `code <folder>` and cut the file
  argument. Add it only if a card ever links to a specific file. *(YAGNI)*
- **No `/bin/sh -c` + manual shell-escaping** (as the raw research used).
  Direct argv `Process`/`subprocess` is shorter *and* removes the entire
  quoting/injection failure class. The escaping helper is not needed.
- **No new repo→path mapping or config.** Both phases reuse the scan's existing
  `local_path` data ([focus5_scan.py:808](src/rebalance/ingest/focus5_scan.py#L808)).
- **No Sandbox/entitlements work** for Focus 5 Float — it is already ad-hoc
  signed with no sandbox, so `Process` is already permitted. The research's
  "Phase 1: disable App Sandbox" is a no-op here.
- **No web exec endpoint at all** if Phase 2's gate says the `vscode://`
  behavior is fine. Phase 1 alone is a complete, shippable improvement.
