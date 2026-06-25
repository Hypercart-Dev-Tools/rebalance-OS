---
title: "Focus 5 Float — Standalone Mac Product (Developer ID, not App Store)"
doc_type: plan
status: not-started
owner: noel@neochro.me
created: 2026-06-24
updated: 2026-06-24
goal: "Turn Focus 5 Float from a rebalance-OS-coupled thin client into a sellable, standalone Mac app — shipped via Developer ID + direct sale (.dmg), with App Store kept as a deliberate, deferred native-rewrite option."
priority: P3
branch: development
recommendation: "Developer ID + direct sale. Keep the scan-anywhere feature, avoid the Swift rewrite, avoid Apple's 30% + review friction. App Store reach is a later, deliberate native rewrite (Phase 5) — do not start there."
rollout_rule: "Each phase leaves Focus 5 Float buildable + launchable (`./make-app.sh` succeeds, the .app opens and renders). Distribution changes are additive to make-app.sh and reversible; no change to the rebalance-OS backend's own contracts."
---

## Status

| What was just completed | What's next |
|---|---|
| **Triage note converted to this plan (2026-06-24).** Architecture confirmed: Focus 5 Float is a pure-Swift SwiftUI menu-bar app ([macOS/Apps/Focus5Float/](../../../macOS/Apps/Focus5Float/)) with zero deps, ad-hoc signed (`codesign --sign -`), polling `http://localhost:8787/focus-5.json` from `rebalance serve`. All real work (disk walk, git probe, ranking) lives server-side in [focus5_scan.py](../../../src/rebalance/ingest/focus5_scan.py). No product work started yet. | **Phase 1 — Product Decision & PII Boundary.** Lock the route (Developer ID) and design the local-PII boundary *before* any packaging work, since buyers will point this at their own repos. |

## Table of Contents

- [Context](#context)
- [Decision (why Developer ID, not App Store)](#decision-why-developer-id-not-app-store)
- [Non-Goals](#non-goals)
- [Phase 1 — Product Decision & PII Boundary](#phase-1--product-decision--pii-boundary)
- [Phase 2 — Standalone Packaging (decouple from rebalance-OS)](#phase-2--standalone-packaging-decouple-from-rebalance-os)
- [Phase 3 — Developer ID Signing & Notarization Pipeline](#phase-3--developer-id-signing--notarization-pipeline)
- [Phase 4 — Distribution & Commerce](#phase-4--distribution--commerce)
- [Phase 5 — (Deferred) App Store Native Rewrite](#phase-5--deferred-app-store-native-rewrite)
- [Open Questions](#open-questions)

## Context

Focus 5 Float is **well-architected as Mac software** — pure SwiftUI menu-bar app
(`LSUIElement`), zero external dependencies, builds via SwiftPM, bundles into
`/Applications/Focus 5 Float.app`, offline caching already in place. That part is
genuinely standalone-capable.

But it is a **thin client, not a self-contained app.** It does nothing on its own:
it polls `http://localhost:8787/focus-5.json` from a running `rebalance serve`
(the Python/FastAPI backend). All the real work — walking the disk for `.git`
repos, probing git status, ranking — happens server-side in
[focus5_scan.py](../../../src/rebalance/ingest/focus5_scan.py). The app just
renders JSON. A buyer who installs the `.app` alone gets an empty panel.

Two structural blockers make the **App Store** the hard path:

| Blocker | Detail |
|---|---|
| **Server dependency** | App Store apps must be self-contained. Focus 5 Float needs a separate Python server. Bundling a Python runtime + FastAPI + deps inside the `.app` is easily +500MB. |
| **Sandbox vs. core function** | App Store = mandatory sandbox. The whole point is scanning git repos *anywhere* on disk and spawning git processes — both largely incompatible with the sandbox. **This is the real killer / one-way door.** |
| **Signing/notarization** | Currently ad-hoc signed (`codesign --force --deep --sign -` in [make-app.sh](../../../macOS/Apps/Focus5Float/make-app.sh)), `BUNDLE_ID me.neochro.Focus5Float`, no Team ID, not notarized. A fixable checkbox — *not* a blocker. |

## Decision (why Developer ID, not App Store)

Ship via **Developer ID cert → notarize → `.dmg` from a website or Gumroad/Paddle.**
This sidesteps the sandbox entirely, keeps the scan-anywhere feature that makes
the tool useful, and still allows charging for it — the way most Mac dev tools and
menu-bar utilities actually sell (~$99/yr Apple Developer account). It avoids both
a Swift rewrite *and* Apple's 30% + review friction.

The App Store path (Phase 5) only becomes worth it as a deliberate **"Focus 5
native" rewrite** — drop the Python server, port the scan logic to Swift, use
security-scoped bookmarks, ship a single sandboxed binary. Significant work; do
**not** start there.

**One thing surfaced before any of this:** the app reads local-only PII — paths,
author emails, device IDs (already flagged in
[Focus5Float/CONTRACT.md](../../../macOS/Apps/Focus5Float/CONTRACT.md)). A sellable
product needs that boundary deliberately designed, because buyers will point it at
*their own* repos. That is Phase 1, on purpose, before packaging.

## Non-Goals

- **No App Store submission in the primary path.** Phases 1–4 target Developer ID
  direct distribution only. App Store is Phase 5, deferred and optional.
- **No change to the rebalance-OS backend's own behavior** for existing users. The
  bundled backend (Phase 2) is a packaging concern, not a rewrite of `focus5_scan`.
- **No Swift rewrite of the scan logic** unless/until Phase 5 is explicitly chosen.
- **No new ranking/feature work** — this plan is about *distribution as a product*,
  not product features.

---

## Phase 1 — Product Decision & PII Boundary

> Lock the distribution route and design the local-PII boundary before writing any
> packaging or signing code. Buyers will run this against their own repos, so the
> data boundary is a product requirement, not a nicety.

- [ ] **Route locked:** Developer ID + direct sale confirmed as the build target
      (App Store recorded as deferred Phase 5, not abandoned).
- [ ] **PII inventory:** enumerate every local-only datum the app reads/caches/emits
      — repo paths, author emails, device IDs — cross-checked against
      [Focus5Float/CONTRACT.md](../../../macOS/Apps/Focus5Float/CONTRACT.md).
- [ ] **Boundary defined:** for each datum, state where it may live (in-memory,
      on-disk cache, never-network) and confirm nothing leaves the machine.
- [ ] **Buyer-facing privacy statement drafted** (what the app reads, why, and that
      it stays local) — the basis for the eventual product page + first-run notice.
- [ ] **Pricing/commerce model chosen** at a high level (one-time vs. license),
      enough to inform Phase 4 — not a final SKU.
- [ ] **Scope cut recorded:** explicit list of what a v1 product does *not* do
      (e.g. no multi-device, no cloud sync), so packaging targets a fixed surface.

### QA Checklist — Phase 1

- [ ] **DRY:** the PII inventory references `CONTRACT.md` as the single source of
      truth — it does not re-list facts that drift from it.
- [ ] **Diagnosable:** the privacy statement makes a falsifiable claim ("no network
      egress of repo data") that Phase 2/3 can actually verify (e.g. via a network
      check), not a vague assurance.
- [ ] **Blast radius:** the route decision is documented with its reversal cost — if
      Developer ID proves wrong, what's the switch-to-App-Store path (→ Phase 5)?
- [ ] **Anti-goal honored:** no packaging or signing work has begun before the
      boundary is signed off.
- [ ] **Proof:** decision + boundary captured in this doc (or a linked decision
      record), dated, owner-attributed.

---

## Phase 2 — Standalone Packaging (decouple from rebalance-OS)

> Make the `.app` run without a separate `rebalance serve` / rebalance-OS install.
> A buyer double-clicks and it works. This is the precondition for *any* sale,
> Developer ID or App Store.

- [ ] **Backend bundled or embedded:** decide the mechanism — bundle a Python
      runtime + FastAPI + `focus5_scan` inside the `.app` (helper process), or
      embed an equivalent local service — and document the chosen approach + size
      cost (the +500MB risk).
- [ ] **App launches its own backend:** the menu-bar app starts/stops the bundled
      service instead of assuming an externally-running `rebalance serve` on
      `:8787`. Port/conflict handling defined (don't collide with a dev's real
      `rebalance serve`).
- [ ] **Config decoupled:** no hardcoded dependency on a rebalance-OS install path,
      vault, or user-specific config. First run works on a clean Mac with no
      rebalance-OS present.
- [ ] **Folder-access UX:** the user can pick which directory tree to scan (the
      product equivalent of the dev's implicit scan root).
- [ ] **`make-app.sh` extended** to assemble the bundled backend into
      `Contents/Resources` (or a helper), with the existing
      `GIT_CONFIG_*`/bare-repo safety preserved.
- [ ] **Clean-machine smoke test:** install the `.app` on a Mac (or fresh user)
      with no rebalance-OS, point it at a sample repo tree, confirm Focus 5 renders.

### QA Checklist — Phase 2

- [ ] **DRY:** the bundled backend reuses `focus5_scan.py` logic — it does not fork
      a second, divergent scanner that drifts from the rebalance-OS one.
- [ ] **SOLID:** the app→backend boundary is a clean process/HTTP seam; the Swift
      client is unchanged in how it consumes `focus-5.json`.
- [ ] **Diagnosable:** if the bundled backend fails to start, the app shows a real
      error state — it does **not** silently render an empty/stale panel
      ([[no-silent-happy-errors]]).
- [ ] **Blast radius:** bundling does not break the *existing* dev workflow
      (a running `rebalance serve` still works); behavior is additive.
- [ ] **Resource hygiene:** measured `.app` size recorded; port-conflict and
      orphaned-helper-process cases handled (no zombie backend after quit).
- [ ] **Proof:** clean-machine smoke test passes and is captured (steps + result).

---

## Phase 3 — Developer ID Signing & Notarization Pipeline

> Replace ad-hoc signing with a real Developer ID identity, hardened runtime, and
> Apple notarization so the `.dmg` opens on other people's Macs without Gatekeeper
> blocking it.

- [ ] **Apple Developer account active** (~$99/yr) and a **Developer ID Application**
      certificate installed; Team ID recorded.
- [ ] **`make-app.sh` signs with the Developer ID cert** (replacing
      `codesign --force --deep --sign -`), with the **Hardened Runtime** enabled.
- [ ] **Entitlements defined** for the non-sandboxed Developer ID build (the
      capabilities the scan + helper process actually need) — *not* App Store
      sandbox entitlements.
- [ ] **Notarization step added:** submit the build (`notarytool`), poll for
      success, and **staple** the ticket to the `.app` / `.dmg`.
- [ ] **`.dmg` build target:** `make-app.sh` (or a sibling script) produces a
      signed, stapled, distributable `.dmg`.
- [ ] **Gatekeeper verification:** on a second Mac, the downloaded `.dmg` opens and
      the app launches with **no** "unidentified developer" / quarantine block
      (`spctl -a -vv` passes).

### QA Checklist — Phase 3

- [ ] **DRY:** one signing identity + one notarize/staple path in the build script —
      no copy-pasted cert handling across scripts.
- [ ] **Diagnosable:** signing/notarization failures fail the build loudly with the
      Apple error surfaced — never a silently-unsigned artifact.
- [ ] **Blast radius:** the `--no-install` / local-dev path of `make-app.sh` still
      works without requiring the Developer ID cert (dev iteration isn't gated on
      notarization).
- [ ] **Reproducible:** the notarization pipeline is documented end-to-end so it can
      run unattended (credentials via keychain profile, not pasted secrets).
- [ ] **Proof:** `spctl`/Gatekeeper pass on a clean second machine captured; the
      stapled `.dmg` verified offline (notarization holds without network).

---

## Phase 4 — Distribution & Commerce

> Get the signed `.dmg` in front of buyers with a way to pay, plus the first-run
> privacy notice promised in Phase 1.

- [ ] **Sales channel chosen** (Gumroad / Paddle / direct site) and storefront set
      up with the `.dmg` as the deliverable.
- [ ] **Licensing model implemented** to the level decided in Phase 1 (or an
      explicit "honor-system / no license check" decision recorded).
- [ ] **Product page** with the buyer-facing privacy statement (from Phase 1),
      system requirements, and the scan-anywhere value prop.
- [ ] **First-run notice in-app:** on first launch, surface what the app reads and
      that it stays local (honoring the Phase 1 boundary).
- [ ] **Update path defined:** how buyers get a new signed/notarized `.dmg`
      (manual download vs. in-app update check) — at least documented.
- [ ] **End-to-end purchase test:** buy → download → install → run, as a fresh
      customer would, on a machine that never had rebalance-OS.

### QA Checklist — Phase 4

- [ ] **Honesty:** the product page and first-run notice match the *actual* Phase 1
      boundary — no claim the code doesn't back.
- [ ] **Diagnosable:** a failed license check (if any) degrades gracefully with a
      clear message, never a silent lockout or silent full-access.
- [ ] **Blast radius:** the commerce layer is external (Gumroad/Paddle) so it adds
      no maintenance burden to the app's core; reversal = pull the listing.
- [ ] **Privacy:** no analytics/telemetry added that would violate the stated
      local-only boundary without disclosure.
- [ ] **Proof:** a full purchase→install→run dry-run completed and captured.

---

## Phase 5 — (Deferred) App Store Native Rewrite

> Only if App Store reach is later judged worth it. This is a deliberate **"Focus 5
> native"** rewrite, not an extension of Phases 1–4. Significant work — do not start
> here.

- [ ] **Explicit go/no-go decision** that App Store reach justifies the rewrite cost
      (recorded, with the tradeoff vs. Developer ID).
- [ ] **Port scan logic to Swift:** reimplement the
      [focus5_scan.py](../../../src/rebalance/ingest/focus5_scan.py) disk-walk +
      git-probe + ranking natively, dropping the Python server dependency entirely.
- [ ] **Security-scoped bookmarks:** user grants folder access; persist the grant
      across launches within the sandbox.
- [ ] **Single sandboxed binary:** no helper backend, no spawned external git where
      the sandbox forbids it (or use the sanctioned APIs).
- [ ] **App Store entitlements + sandbox** configured; build passes App Store
      validation.
- [ ] **Parity check:** native Focus 5 ranking matches the Python implementation on
      a shared fixture set (no behavior regression).

### QA Checklist — Phase 5

- [ ] **DRY/parity:** the Swift ranking is validated against `focus5_scan.py` on
      shared fixtures — a documented equivalence, not a vibe.
- [ ] **SOLID:** scan, rank, and render are separable in the Swift port (mirrors the
      seam the Python side already has).
- [ ] **Diagnosable:** when a folder grant is missing/revoked, the app explains it
      and prompts re-grant — it does not silently show an empty board.
- [ ] **Blast radius:** Phase 5 is a *separate* product line; shipping it does not
      break or obsolete the Developer ID build still in market.
- [ ] **Sandbox honesty:** any feature lost to the sandbox vs. the Developer ID
      build is documented for buyers (no silent capability gap).
- [ ] **Proof:** App Store validation passes; parity fixtures green.

---

## Open Questions

- **Backend bundling mechanism (Phase 2):** embed a full Python runtime, or extract
  `focus5_scan` into a lighter standalone helper? The +500MB size cost may force the
  answer — and partially pre-does the Phase 5 rewrite.
- **Licensing depth (Phase 1/4):** real license-key enforcement vs. honor-system —
  affects scope materially.
- **Single vs. dual product:** if Phase 5 ever happens, is "Focus 5 native" a
  replacement or a separate sandboxed SKU alongside the Developer ID build?
- **Decoupling overlap:** how much of Phase 2's "decouple from rebalance-OS" work is
  reusable in a future Phase 5 native port vs. throwaway packaging?
