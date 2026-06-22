---
title: "Front-Door Onboarding Remediation Plan"
doc_type: audit-remediation-plan
status: active
owner: Noel Saw
last_updated: 2026-06-21
supersedes: []
related:
  - README.md
  - GMAIL.md
  - GOOGLE_CALENDAR.md
  - UPGRADE.md
  - MCP.md
  - src/rebalance/cli/onboard.py
  - src/rebalance/ingest/gmail.py
  - src/rebalance/ingest/calendar.py
---

# Front-Door Onboarding Remediation

| Most recently completed phase | What's next |
|---|---|
| **Front-door audit complete (2026-06-21).** A cold-newcomer walk of the clone→working path. Verdict: ⚠️ Bumpy — on macOS Apple Silicon with an agent a newcomer reaches a verified state in ~20–30 min; secrets scan clean (tree + history). Bumps found: README drift from the recent auth-storage hardening, an Apple-Silicon/MLX platform gate that's disclosed but buried, undocumented first-run network egress, and a Calendar/Gmail local-OAuth wall that Claude-Desktop users could skip via host MCP connectors. | **Phase 1 — doc-drift quick wins.** Reconcile the canonical README with the shipped keyring + secret-store + JSON-OAuth model (two stale lines at README:262 and :321). |

## Table of Contents

1. [Scope and Source](#scope-and-source)
2. [Audit Findings Being Remediated](#audit-findings-being-remediated)
3. [Phase 1 - Front-Door Doc-Drift Quick Wins](#phase-1---front-door-doc-drift-quick-wins)
4. [Phase 2 - Install-Path Clarity: Platform Gate, Cross-Platform Minimal Path, Egress](#phase-2---install-path-clarity-platform-gate-cross-platform-minimal-path-egress)
5. [Phase 3 - Lower the Calendar/Gmail Wall via Host MCP Connectors](#phase-3---lower-the-calendargmail-wall-via-host-mcp-connectors)
6. [Phase 4 - Repo-Root Tidiness](#phase-4---repo-root-tidiness)
7. [Cross-Phase Risks](#cross-phase-risks)
8. [Definition of Done](#definition-of-done)

## Scope and Source

This plan remediates the **Bumpy** items from the 2026-06-21 front-door audit. It does **not** try to remove the audit's **human-gated walls** (a GitHub PAT, a Google account/OAuth consent, an Obsidian vault, Apple-Silicon hardware) — those are inherent to what the tool does and are already honestly disclosed. The job here is to (a) kill doc drift so the canonical front door tells the truth, (b) make the platform gate and first-run network egress unmissable, and (c) give Claude-Desktop users a lower-friction Calendar/Gmail consumption path via the host's native connectors — without silently pushing privacy-first users onto a cloud path.

Audited tree: `main` (the default branch a cloner gets). Findings reflect committed content.

## Audit Findings Being Remediated

- **Doc drift (quick win).** `README.md:262` still names the retired pickle path `~/.config/rebalance-os/google-calendar-oauth`; `README.md:321` still tells users to run `migrate-to-keyring` as a required step. Both contradict the shipped Phase-3 model (keyring + JSON secret store, written in one pass). This drift was introduced by the auth-storage hardening — the topic docs (GOOGLE_CALENDAR/GMAIL/UPGRADE) were updated; the README was not.
- **Platform gate is disclosed but buried.** `pip install -e ".[embeddings,...]"` pulls `mlx-embeddings` (Apple-Silicon only). It's stated in Prerequisites but the broad "Who this is for" framing invites off-platform readers who only discover the wall at install.
- **First-run network egress undocumented.** The embeddings step downloads `Qwen3-Embedding-0.6B` from HuggingFace on first run; `github-scan`/`calendar-sync` reach `api.github.com` / `*.googleapis.com`. A sandboxed agent's network allowlist can block these, and the failure can read as an unrelated error.
- **Calendar/Gmail local-OAuth wall.** Both require a local OAuth flow today (Gmail also offers an `mcp` mode that's under-promoted; Calendar has no connector path). Claude Desktop ships first-party Google Calendar + Gmail connectors that could supply this data instead.
- **Repo-root clutter (lower priority).** 20 root `.md` files; the README hub only indexes 8.

## Phase 1 - Front-Door Doc-Drift Quick Wins

Goal: the canonical README matches the shipped auth-storage model so the front door stops lying.

- [ ] Fix the Calendar token-location line.
  Observable result: `README.md:262` says the token lives in the OS keyring + the JSON secret store (`~/.config/rebalance-os/secrets/google-calendar-oauth`, `0600`), not the retired pickle path — matching [GOOGLE_CALENDAR.md](/Users/noelsaw/Documents/rebalance-OS/GOOGLE_CALENDAR.md:93).
- [ ] Remove the stale `migrate-to-keyring` step.
  Observable result: `README.md:321` no longer instructs a follow-up `migrate-to-keyring`; setup writes keyring + JSON in one pass — matching [GMAIL.md](/Users/noelsaw/Documents/rebalance-OS/GMAIL.md:96) and [UPGRADE.md](/Users/noelsaw/Documents/rebalance-OS/UPGRADE.md:49).
- [ ] Tighten the Gmail Step 5 fallback wording.
  Observable result: "launchd-reachable file fallback" names the JSON secret store specifically, not a vague file.
- [ ] Sweep the README (and any root doc the hub links) for remaining stale credential-model wording.
  Observable result: no `pickle`, no retired `~/.config/rebalance-os/google-*-oauth` path, and no "migrate-to-keyring is required" phrasing survive in newcomer-facing docs; `gmail_query_filter` → `temp/rbos.config` stays (it is a non-secret config key, correct as-is).

### QA Checklist

- [ ] README Calendar/Gmail token-storage statements match GOOGLE_CALENDAR/GMAIL/UPGRADE verbatim on the storage location.
- [ ] `rebalance doctor`'s OAuth source labels (`keyring` / `secret-store JSON` / `legacy pickle`) are consistent with what the README claims.
- [ ] A reader who only reads the README ends up with a correct mental model of where secrets live.
- [ ] No newcomer-facing doc still references the retired pickle fallback as the live path.

## Phase 2 - Install-Path Clarity: Platform Gate, Cross-Platform Minimal Path, Egress

Goal: a newcomer knows in one glance whether the tool runs on their machine, what subset works off-platform, and what the network touches on first run.

- [ ] Surface the supported platform before Step 1.
  Observable result: a "Supported platform" callout at the top of Getting Started states macOS Apple Silicon is required for the MLX embeddings stack — not only buried in Prerequisites.
- [ ] Document the cross-platform minimal install and feature subset.
  Observable result: the docs state that `pip install -e .` (or `.[calendar]`) works without MLX, and name which features work without embeddings (vault metadata ingest, GitHub sync, calendar, `doctor`) vs which require it (semantic search/embeddings). Off-platform readers can find a working subset instead of a dead end.
- [ ] Document first-run network egress.
  Observable result: Step 3 notes that the embeddings step downloads `Qwen3-Embedding-0.6B` from HuggingFace (host + approx. size), and that `api.github.com` / `*.googleapis.com` are reached during sync — so an agent-sandbox or allowlisted environment can permit those hosts (or run the step outside the sandbox).
- [ ] Tie the egress note to the agent path.
  Observable result: the `/welcome` / `rebalance onboard` sections flag that a sandboxed agent may be blocked from the model download and name the remedy (allowlist the host, or run the download outside the sandbox once).

### QA Checklist

- [ ] The supported platform is stated above the first install command, not only in Prerequisites.
- [ ] A non-Apple-Silicon reader can identify the working feature subset and the minimal install in under a minute.
- [ ] The model-download host and approximate size are stated where the download happens.
- [ ] An agent-sandbox user can self-serve the egress allowlist from the docs without hitting a misleading error first.
- [ ] No claim implies full functionality on unsupported platforms.

## Phase 3 - Lower the Calendar/Gmail Wall via Host MCP Connectors

Goal: let Claude-Desktop (and other native-Google-connector) users consume Calendar/Gmail through the host's connectors instead of the local OAuth flow — **as an explicit, trade-off-aware option**, not a silent default swap.

**Design note (recommendation).** rebalance already proves the pattern for Gmail: `set-gmail-method mcp` makes the scheduled job a no-op and expects an agent to pull messages via the host's Gmail connector and call the `ingest_gmail_messages` MCP tool — no local OAuth, no bundled-client trust, no keyring/secret-store token. So **the Gmail host-connector path is available today.** Claude Desktop also ships a first-party **Google Calendar** connector, so the same pattern *could* extend to Calendar — but **no Calendar `mcp` consumption mode exists yet** (`calendar_ingest_method` and an `ingest_calendar_events` tool are unbuilt). This plan therefore: (1) **promotes** the existing Gmail `mcp` mode for host-connector users (today it is under-advertised behind the `oauth` default), and (2) **specs the Calendar `mcp` mode and explicitly defers the build** — Calendar host-connector consumption must be documented as **"planned, not yet supported," never as a current path**, until the mode and tool ship.

**Precondition — state it wherever the connector path is offered.** The host-connector route is not free of gates; it trades a different one: the user's MCP host must actually ship Google connectors, and the user must have **connected and consented** their Google account inside that host. So this path fits "I already use Claude Desktop with its Google connectors connected," not "any agent user skips OAuth for free."

The deliberate **trade-off** must be stated **inline, not hidden behind a link**: native connectors route Google data through the host's cloud (claude.ai), which conflicts with rebalance's local-first / no-cloud value proposition. So the **local OAuth + SQLite ingest path stays the default for privacy-first users**, and the **connector path is the recommended default only for users who already trust their host with Google data**. Steering everyone to the cloud path would betray the core promise; offering it as an informed choice removes a real wall for the users it fits.

- [ ] Promote Gmail `mcp` mode (available today) for host-connector users.
  Observable result: README Step 5 and GMAIL.md present `mcp` mode as the recommended path for Claude-Desktop / MCP-host users (it removes the local OAuth flow entirely), with a one-line "when to pick which" that names **both** the connector precondition (host ships Google connectors + your Google account is connected there) **and** the privacy trade-off.
- [ ] Add a consumption-path decision callout to README Steps 4 and 5 — with an **inline** trade-off sentence.
  Observable result: before each OAuth flow, a callout states inline (not behind a link): "the host-connector path routes your Google data through the host's cloud; local OAuth + SQLite keeps it on this machine." For **Gmail** the callout offers `mcp` mode as **available now**; for **Calendar** it labels host-connector consumption **planned, not yet supported** and points to local OAuth as the current path.
- [ ] Carry the connector precondition everywhere the connector path is recommended.
  Observable result: each connector recommendation names the precondition (host must ship Google connectors; user must have connected/consented their Google account in the host) so no reader concludes any agent user skips OAuth for free.
- [ ] Spec the Calendar `mcp` consumption mode — **build explicitly deferred**.
  Observable result: a written spec for a `calendar_ingest_method = oauth | mcp` setting and an `ingest_calendar_events` MCP tool fed by the host's Calendar connector — naming the tool surface, the row shape it writes into `calendar_events`, and the cloud-vs-local data-flow boundary. The build is **deferred (not in this plan)**; **revisit trigger:** a user asks for Claude-Desktop Calendar consumption, or Gmail `mcp` mode proves the pattern in the field. Until it ships, no doc presents Calendar host-connector as available.

### QA Checklist

- [ ] Gmail presents both consumption paths clearly (local OAuth + host-connector `mcp` mode, **available now**); Calendar presents local OAuth now and labels host-connector consumption **planned, not yet supported**. No doc offers a Calendar connector path that does not exist.
- [ ] The privacy trade-off (connector = data through host cloud) is stated **inline** everywhere the connector path is offered — never only behind a link, never silent.
- [ ] The connector precondition (host ships Google connectors + account connected/consented there) appears wherever the connector path is recommended.
- [ ] **Doc-walk gate:** a reader starting from the README can tell, for Gmail and Calendar **separately**, whether the host-connector path is available now, what host preconditions apply, and whether data stays local — without opening code.
- [ ] Gmail `mcp` mode is discoverable as a first-class option, not a footnote.
- [ ] The Calendar `mcp` spec names the new tool, the `calendar_events` write shape, and the data-flow boundary, and carries a revisit trigger for its deferred build.

## Phase 4 - Repo-Root Tidiness

Goal: the repo root reads as cleanly as the README hub implies, so a newcomer browsing the tree isn't lost among internal docs.

- [ ] Inventory and classify the root `.md` files.
  Observable result: each of the ~20 root `.md` files is tagged newcomer-facing (keep in root / hub) or internal (e.g. `AGENTS`, `CLAUDE`, `MEMORY`, `HONEST`, `AUDIT-*`, `4X4`, `DIAGRAM`, `ASK_SELF_INTEGRATION`).
- [ ] Relocate internal docs.
  Observable result: internal docs move into `docs/internal/` (or similar) with inbound links updated; agent-convention files that tools expect at root (`AGENTS.md`, `CLAUDE.md`) stay where their loaders require.
- [ ] Keep one index.
  Observable result: the README Documentation hub remains the single newcomer index, and every kept root doc is either in the hub or linked from one that is.

### QA Checklist

- [ ] The repo root shows only newcomer-relevant docs plus the canonical README and required agent-convention files.
- [ ] No dead links anywhere after the move (README hub, cross-doc links, tool loaders).
- [ ] Anything a tool/skill loads by path (e.g. `AGENTS.md`, `CLAUDE.md`) still resolves.
- [ ] The README hub resolves to every kept doc.

## Cross-Phase Risks

- The main correctness risk is **steering privacy-first users to the cloud connector path by accident** — every connector mention must carry the trade-off, or the plan undermines the product's core promise.
- The main drift risk is **fixing the README but missing a sibling doc**, leaving two docs disagreeing again; Phase 1's sweep and QA exist to prevent that.
- The main scope risk is **Phase 3's Calendar `mcp` mode quietly turning into a build** mid-plan; the explicit in-scope/defer decision keeps the phase closable on docs.
- The main regression risk is **the Phase 4 doc move breaking a path a tool loads**; the QA checks for tool-loaded files guard it.

Mitigation rules:

- doc-only phases close on a doc sweep + a doctor/source-label cross-check, not on a single edit
- every connector recommendation states the cloud-vs-local trade-off in the same place
- a relocation is verified by a link-and-loader check before the phase closes
- a design item that may become a build carries an explicit in-scope-or-defer decision

## Definition of Done

- [ ] The canonical README agrees with GOOGLE_CALENDAR/GMAIL/UPGRADE on where every credential lives — no stale pickle path, no required `migrate-to-keyring`.
- [ ] The supported platform and the cross-platform minimal subset are stated before the first install command.
- [ ] First-run network egress (HuggingFace model, GitHub, Google APIs) is documented for allowlisted/agent-sandbox users.
- [ ] Gmail presents both a local-OAuth path and an available host-connector (`mcp`) path; Calendar presents local OAuth now with host-connector consumption labeled "planned, not yet supported." No doc offers a Calendar connector path that is not built.
- [ ] Wherever the connector path appears, the cloud-vs-local-first trade-off **and** the host-connector precondition are stated inline (not behind a link).
- [ ] Gmail `mcp` mode is first-class; the Calendar `mcp` mode is specced-and-deferred with a revisit trigger.
- [ ] The repo root is newcomer-clean with one README hub and no broken links or tool-loader breakage.
