---
title: Repo links open VS Code with "focus-if-open" — Build Plan
status: Phase 1 code complete (operator GUI litmus pending) · Phase 2 code complete + agy QA Approved (operator browser litmus pending)
owner: noel
created: 2026-06-27
updated: 2026-06-29
reversibility: Easy (Mac app) · Costly (web exec endpoint — see §Blast) — both are flag/fallback-shielded
goal: >
  Make the repo-card "Open ↗" button focus an already-open VS Code window for that
  repo (or spawn exactly one new one) on both the Focus 5 Mac app and the pulse web
  dashboard, replacing the window-hijacking vscode:// URI scheme.
---

# Repo links open VS Code with "focus-if-open" — Build Plan

Make the "Open ↗" button on a repo card land you in the *right* VS Code window:
focus the window if that repo is already open, spawn exactly one new window if
it isn't. Today both surfaces fire the `vscode://file/{path}` URI scheme, which
either hijacks the active window or always spawns a new one.

## Status

| What was just completed | What's next |
| --- | --- |
| **Phase 2 (web app) code shipped 2026-06-29** (operator chose GO on the gate): `POST /api/focus5/open` resolves a card **identity → local_path from the server's own roster** (allowlist; union of Focus 5 + Dirty Five boards), rejects unknown ids (404, logged as a tripwire), and runs **`code <path>` via direct-argv `subprocess`** (`shell=False`); 409 when `code` is absent. **Two-layer local-only guard** (`_request_is_local`): client host must be loopback AND (if present) the `Origin` must be loopback — refuses cross-origin POSTs **and** a non-loopback `curl` (403). The Open button + repo-name link carry `data-f5-open`; click JS POSTs the id and **falls back to the `vscode://` href on any non-200** (never dead). **agy relay QA (2026-06-29): Approved (round 2/4).** r1 raised the loopback gap [Should] + a `_resolve_code_binary` directory-vs-file nit [Nit] (both fixed: restored client-host check + `os.path.isfile` guard); the EventKit fade/double-tap, XSS-escaping, and JS fallback all passed. Tests: now **91 passed** (added `test_request_is_local_guard` + `test_resolve_code_binary_rejects_directory`; launch tests bypass the guard, cross-origin→`test_open_non_local_request_is_403`). _Prior:_ **Phase 1 (Mac app) shipped 2026-06-29** (`VSCodeLauncher`; `swift build` + `FOCUS5_VSCODETEST`/`FOCUS5_SELFTEST` green). | **Operator litmus, both surfaces:** (web) browser Open → already-open repo focuses, not-open spawns one window, `code` absent → `vscode://` fallback, cross-origin POST rejected; (Mac app) the same three eyeball checks. |

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

- [x] Add `localPath` use to the launch path: the button calls
      `VSCodeLauncher.launch(repoPath:fallbackURL:)` instead of `open(card.vscodeUrl)`. → [ContentView.swift:286](macOS/Apps/Focus5Float/Sources/Focus5Float/ContentView.swift#L286)
- [x] Resolve the `code` binary from a fixed candidate list — first that exists
      wins: `/opt/homebrew/bin/code`, `/usr/local/bin/code`,
      `/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code`
      (plus a `VSCODE_BIN` override + login-shell `which`, mirroring `ServerLauncher`,
      since a GUI app inherits no shell PATH). Helper `resolveBinary() -> String?` (nil ⇒ none). → [VSCodeLauncher.swift](macOS/Apps/Focus5Float/Sources/Focus5Float/VSCodeLauncher.swift)
- [x] Launch with a **direct argv** `Process`: `executableURL` = resolved binary,
      `arguments = [repoPath]`. No `/bin/sh -c`, no string escaping. Runs off the
      main thread (`DispatchQueue.global`).
- [x] If the binary is nil (or `run()` throws), fall back to
      `NSWorkspace.shared.open(fallbackURL)` (the `vscode://` path) so the button is **never dead**.
- [x] Log each launch: chosen binary (or "fallback"), repoPath, and
      `terminationStatus`, via `os.Logger` (category `vscode`).
- [ ] *Deferred (YAGNI):* foreground-pull via `NSRunningApplication … activate`.
      `code <folder>` usually raises its own window. Add this **only if** you
      observe VS Code launching behind the app — don't pre-build it.

### Phase 1 — QA checklist
- [ ] **Observed:** repo already open in VS Code → click focuses that window,
      **no** new window (eyeball test, recorded in the PR description).
- [ ] **Observed:** repo not open → click spawns **exactly one** new window.
- [ ] **Observed:** rename/quit the `code` symlink so resolution returns nil →
      click still opens the repo via the `vscode://` fallback.
- [x] Self-check on the pure logic (binary resolution + argv assembly) —
      `FOCUS5_VSCODETEST=1 swift run Focus5Float` asserts the candidate order +
      argv shape (`["<folder>"]`, no `-n`/`-r`), fails on regression. **Run: `VSCODETEST OK — argv=["/repos/demo repo"] candidates=3`.** → [SelfTest.swift](macOS/Apps/Focus5Float/Sources/Focus5Float/SelfTest.swift)
- [x] Diagnosable: launch log line present (`os.Logger` category `vscode`);
      one-shot launch, **no retry loop**.
- [x] Blast: undo = revert `VSCodeLauncher.swift` + 2 one-line call-site edits (Easy).
      Shield = `vscode://` fallback. No shared state touched (no tripwire needed).
- [x] Status table + `updated:` bumped (2026-06-29). *(The 3 unchecked `Observed:` items above are the operator GUI litmus — all that remains for Phase 1.)*

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

- [x] Add a `POST /api/focus5/open` handler that takes a **repo identifier**
      (the card's `repo_full_name`-or-`local_path` identity), looks up its
      `local_path` from the **server's own scanned-repo set** (`_focus5_open_allowlist`,
      union of the Focus 5 + Dirty Five rosters), and rejects any id not in that
      set (404). The client never sends a path. → [web.py](src/rebalance/web.py) `focus5_open_repo`
- [x] Run the launch with a **direct argv** subprocess:
      `subprocess.run([code_bin, local_path])` — `shell=False`, argv list, no
      string interpolation, `timeout=15`. `code_bin` resolved from the same fixed
      candidate list as Phase 1 (`VSCODE_BIN` → known paths → `shutil.which`); if
      absent, returns 409 and the button keeps the `vscode://` fallback.
- [x] **Endpoint guard (two-layer, hardened after agy QA r1):** `_request_is_local`
      requires (1) a loopback **client host** AND (2) a loopback `Origin` if present —
      rejects both cross-origin browser POSTs and a non-loopback `curl` with no Origin
      (403). _(Restored the client-host check agy flagged as a [Should] gap, since
      `rebalance serve` can bind non-loopback; route tests bypass the guard because
      `TestClient` reports a non-loopback host, and the gate has its own unit test.)_
- [x] Web button: on click, `fetch('/api/focus5/open', {repo})`; on any non-200,
      fall through to the element's `vscode://` href. The `<a href="vscode://…">`
      stays the no-JS / failure fallback so the button is **never dead**. Wired on
      both the Open button and the repo-name link via `data-f5-open`.
- [x] Log each request: identity, resolved path, chosen binary, exit code; **allowlist
      misses logged at WARNING** (the tripwire). To the pulse server log (`logger`).

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
- [ ] **Observed (operator):** click in browser → repo focuses-or-opens via the
      server, no new window when already open.
- [x] **POST a repo id not in the scanned set → 404, nothing runs.** `test_open_unknown_repo_is_404_and_runs_nothing` (asserts `subprocess.run` not called).
- [x] **Non-local / cross-origin POST → 403, nothing runs.** `test_open_non_local_request_is_403_and_runs_nothing` (integration) + `test_request_is_local_guard` (unit: loopback/cross-origin/non-loopback/missing-client).
- [x] **`code` binary absent → 409** (button falls back to `vscode://`). `test_open_missing_code_binary_is_409`. Directory-as-binary rejected: `test_resolve_code_binary_rejects_directory` (agy QA r1 Finding 2).
- [x] **Allowlist resolver (`pytest`): known id → real server path, unknown id → reject.** `test_open_allowlist_resolves_known_and_rejects_unknown` + `test_open_known_repo_runs_code_with_server_path` (argv = `["<bin>", "<server_path>"]`). **Run: `tests/test_focus5_scan.py` → 91 passed.**
- [x] Diagnosable: one log line per request (identity/path/bin/exit); allowlist misses at WARNING; one-shot, **no retry loop**.
- [x] House: single exec path — `/api/focus5/open` is the **only** route that shells out; `local_path` comes only from the scan, never the client.
- [x] Status table + `updated:` bumped (2026-06-29). *(The one unchecked `Observed:` item is the operator browser litmus.)*

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
