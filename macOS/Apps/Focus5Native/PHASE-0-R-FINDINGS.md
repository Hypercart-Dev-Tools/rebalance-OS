# Phase 0-R — Sandboxed Re-Spike Findings

**Task:** MARATHON-A (xyz-tick). Agent: claude-a. Lane: `macOS/Apps/Focus5Native/**`.
**Machine:** macOS 15.6.1 (24G90), arm64 (Apple Silicon).
**Toolchain:** Apple Swift 6.2.4 (swiftlang-6.2.4.1.4), Xcode 26.3 (17C519).
**Date:** 2026-07-01 (UTC captured in each run below).
**Signing:** ad-hoc (`codesign -s -`); no Developer ID identity present on this
machine (`security find-identity -v -p codesigning` → `0 valid identities`).
Ad-hoc + App Sandbox entitlement is sufficient to *enforce* the sandbox locally,
which is what this spike needs to observe.

> This doc records what a **real, codesigned, App-Sandboxed run** observed —
> replacing the prior spike's asserted conclusions. Every finding cites the
> command run and its verbatim output.

---

## What was built (this lane)

| File | Purpose |
|---|---|
| `Package.swift` | Rewired: adds `Clibgit2` (C shim), `Focus5Core` (probe lib), `Focus5Probe` (headless sandbox harness). Original `Focus5Native` GUI target unchanged. |
| `Sources/Clibgit2/include/clibgit2_shim.h` | Hand-declared minimal libgit2 C prototypes (no public `git2.h` exists here). |
| `Sources/Clibgit2/include/module.modulemap` | Module map exposing the shim to Swift. |
| `Sources/Clibgit2/shim.c` | Empty TU; symbols resolve at link time against the Xcode libgit2 dylib. |
| `Sources/Focus5Core/GitProbe.swift` | In-process libgit2 probe → typed `RepoFacts` (branch, ahead/behind, modified, untracked, dirty, **last-commit timestamp**). |
| `Sources/Focus5Probe/main.swift` | Headless harness: runs [A] embedded probe, [B] `Process`→`/usr/bin/git`, [C] security-scoped bookmark round-trip. Output is written with `Darwin.write`/`SIGPIPE` ignore instead of Foundation `print`, so sandboxed or detached app launches do not abort on missing stdio. |
| `Focus5.entitlements` | `com.apple.security.app-sandbox` + `files.user-selected.read-write`. |
| `Info.probe.plist` | Minimal bundle Info.plist (a bare Mach-O CLI cannot host the sandbox — see Finding 3). |
| `build-and-run-sandboxed.sh` | Reproduces the whole thing (clean build → wrap `.app` → sign sandboxed → run). |

---

## Environment reality checks (cited)

- **SwiftGit2 SPM path does NOT work off-the-shelf for macOS.**
  - `SwiftGit2/SwiftGit2` tag `0.6.0` (latest) has **no `Package.swift`** — Carthage/xcodeproj only. Not SwiftPM-consumable.
  - The common SPM fork `light-tech/SwiftGit2` (branch `spm`) declares `platforms: [.iOS(.v13)]` and depends on `light-tech/Clibgit2`, a `binaryTarget` xcframework.
  - That xcframework (`.../LibGit2-On-iOS/releases/download/v1.3.0/Clibgit2.xcframework.zip`, downloaded OK, 12.4 MB, http 200) contains **only** `ios-x86_64-simulator`, `ios-arm64`, `ios-x86_64-maccatalyst` — **NO native `macos` slice** (verified via its `Info.plist`). It cannot link a native AppKit macOS app.
  - **Implication:** the shippable embedded-git dependency for macOS must be a proper **macOS-sliced libgit2** (build libgit2 as a macOS xcframework, or a SwiftPM `systemLibrary` against a bundled dylib). This is real work Phase 2 must scope; "just add SwiftGit2" (Phase 0's implied plan) is wrong for macOS.
- **No public libgit2 SDK on this machine.** `git2.h` is absent everywhere on disk. The only linkable libgit2 is the arm64 dylib Xcode ships at `/Applications/Xcode.app/Contents/Developer/usr/lib/libgit2.dylib` (936 `git_*` exports; libgit2 **1.7.2** at runtime). For the spike we link that via `-lgit2` + rpath and declare the ~20 needed prototypes by hand. **NOT shippable** (private Xcode lib) — it is a spike stand-in that proves the *in-process libgit2 model* links and runs under the sandbox.

---

## Acceptance command + output

```
$ cd macOS/Apps/Focus5Native && swift build      # (outside the CI command-sandbox; see Finding 0)
[12/19] Linking Focus5Probe
[17/19] Linking Focus5Native
Build complete! (6.26s)
```
Clean sandboxed **`.app`** run (`build-and-run-sandboxed.sh`), verbatim:
```
=== Focus5Probe (Phase 0-R sandboxed harness) ===
repo: .../Containers/com.rebalance-os.focus5.probe/Data/fixture-repo
libgit2 version: 1.7.2

[A] EMBEDDED libgit2 in-process probe:
    OK: branch=main detached=false ahead=0 behind=0 modified=1 untracked=1 dirty=true lastCommitUnix=1782922603
    JSON: {"branch":"main","ahead":0,"behind":0,"modified":1,"untracked":1,"dirty":true,"lastCommitUnix":1782922603,"detachedHead":false}

[B] PROCESS exec of /usr/bin/git status --short --branch:
    task.run() SUCCEEDED. exitCode=1 reason=1
    git output (first 3 lines):
      xcrun: error: cannot be used within an App Sandbox.

[C] SECURITY-SCOPED BOOKMARK persist + restore round-trip:
    persisted bookmark: 1096 bytes -> bookmark.dat
    restored: .../fixture-repo stale=false startAccessing=true
    OK: bookmark round-trip completed in-sandbox

=== done ===
```
Entitlements confirmed embedded on the running binary:
```
$ codesign -d --entitlements - .build/Focus5Probe.app/Contents/MacOS/Focus5Probe
    [Key] com.apple.security.app-sandbox
    [Key] com.apple.security.files.user-selected.read-write
```

---

## Findings vs the Phase 0-R QA gates

### Finding 0 — the outer CI command-sandbox, not the App Sandbox, blocks `swift build`
Under this environment's default command sandbox, `swift build` fails with
`sandbox-exec: sandbox_apply: Operation not permitted` — SwiftPM wraps manifest
compilation in `sandbox-exec`, which cannot nest inside the outer sandbox. With
the outer sandbox disabled the same build succeeds (`Build complete! (0.84s)`).
This is an **environment/CI artifact**, unrelated to the macOS App Sandbox under
test. Recorded so the coordinator knows builds here must run outside the CI
command-sandbox.

### Finding 1 — Sandboxed build exists (GATE: PASS)
The harness runs as a **codesigned `.app`** carrying `com.apple.security.app-sandbox`
+ `files.user-selected.read-write` (verified via `codesign -d --entitlements`),
launched from `Contents/MacOS/` — **not** `swift run`. It executes to completion
(exit 0) inside the sandbox.

### Finding 2 — Kill criterion OBSERVED, not asserted (GATE: PASS)
Inside the sandbox, `Process` → `/usr/bin/git status` returns exit **1** with the
verbatim error **`xcrun: error: cannot be used within an App Sandbox.`** On macOS
`/usr/bin/git` is an `xcrun` shim; `xcrun` explicitly refuses to run within an App
Sandbox. This is the empirical, reproduced kill criterion the prior spike only
reasoned about. **The `Process` + system-git path is a confirmed non-starter for
the sandboxed App Store build.** (`task.run()` itself does not throw — the child
launches — but the child cannot function; either way the path is dead.)

### Finding 3 — Sandbox needs a real `.app` bundle (observed sub-finding)
A **bare ad-hoc-signed Mach-O CLI** with the sandbox entitlement **SIGTRAPs on
launch** inside `_libsecinit_appsandbox` during dyld initializers, *before* `main`
(crash report: `EXC_BREAKPOINT`, frame `_libsecinit_appsandbox.cold.6`). The App
Sandbox requires a bundle + container. Wrapping the same binary in a minimal
`.app` (with `Info.plist`/`CFBundleIdentifier`) lets `libsecinit` establish the
container and the process runs sandboxed. Confirms App Store packaging must be a
proper bundle — not a loose executable.

### Finding 4 — Embedded libgit2 path proven viable under the sandbox (GATE: PASS)
[A] runs **in-process** (no `Process`), libgit2 1.7.2 loaded, and returns the full
Focus 5 fact set on a sandbox-permitted repo:
`branch=main, ahead=0, behind=0, modified=1, untracked=1, dirty=true, lastCommitUnix=1782922603`
— matching the fixture (branch `main`, 1 modified, 1 untracked, HEAD "second").
Includes **last-commit timestamp**, which the prior spike never fetched.
Corollary observed: on a **non-granted** path the same in-process probe returns
empty (`git_repository_open` denied by the sandbox file boundary) — proving the
library is not blocked, the **file-access boundary is**, i.e. security-scoped
access (bookmarks) is mandatory.

### Finding 5 — Structured facts, not raw text (GATE: PASS)
Output is a typed `RepoFacts` (Codable) with named fields + JSON — not a raw
`git status` string dump. See `Sources/Focus5Core/GitProbe.swift`.

### Finding 6 — Security-scoped bookmark persist + restore in-sandbox (GATE: PASS, with caveat)
[C] creates bookmark data (1096 bytes), persists to the container, resolves it,
and `startAccessingSecurityScopedResource()` returns **true**, all in-sandbox.
**Caveat:** a headless CLI cannot invoke `NSOpenPanel`, so this exercises the
bookmark data API round-trip rather than a *panel-granted* `.withSecurityScope`
bookmark. The GUI `Focus5Native` target owns the panel grant; the persistence/
restore mechanism itself is proven to function under the sandbox here.

### Finding 7 — Proof artifact written (GATE: PASS)
This file, plus the reproducible `build-and-run-sandboxed.sh`.

### Finding 8 — Standalone truth (GATE: PASS)
The harness links only libgit2 + Foundation; no import of / shell into / HTTP call
to rebalance-OS, Python, or `rebalance serve`. The fixture repo is self-created.

---

## Decision re-confirmed (doc lines 124–126)

The Phase 0 decision — **use the embedded in-process libgit2 path, NOT `Process`
+ system git** — is **CONFIRMED with empirical evidence**:
- `Process`→git is genuinely dead in the sandbox (`xcrun ... cannot be used within an App Sandbox`).
- In-process libgit2 links and returns the full fact set under the sandbox.

**But the reversal/cost note the prior spike lacked:** the *SwiftPM SwiftGit2*
shortcut does **not** exist for native macOS (its xcframework is iOS-only, and
0.6.0 isn't SPM at all). Phase 2's "implement git probing using the Phase 0
decision path" must budget for **producing a macOS-sliced libgit2** (build libgit2
→ macOS xcframework, or `systemLibrary` + bundled dylib) and declaring the
prototypes / importing real `git2.h`. The Xcode-internal dylib used here is a
spike stand-in only and must not ship.

## Follow-ups for later phases (not spike-blocking)
- `restoreBookmark()` in `Focus5Native.swift` still never calls
  `stopAccessingSecurityScopedResource()` (acknowledged in-code) — fix before Phase 2.
- Replace hand-written `clibgit2_shim.h` prototypes with a proper vendored macOS
  libgit2 + real headers before shipping.
