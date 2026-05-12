# P2 Lovable App Mirror

## TOC
- Overview
- Architecture & Stack
- Data Synchronization
  - Secure Vault Push Script
  - Git Pulse Sync Ingestion
  - Sleuth Task Fallback
- Implementation Phases
- Security Considerations

## Overview

This document outlines the plan for mirroring the local static Git Pulse dashboard (`web/pulse.html`) in a cloud-hosted web application built via Lovable. The goal is to provide a secondary, non-canonical dashboard for the operator that mirrors the current local web view while expanding read access for periods when the macOS host is offline or unavailable.

The app will ingest Git Pulse sync data, render the current dashboard state, and receive updates from the local Obsidian Vault via a secure push script. The local vault plus SQLite store remain the source of truth. The Lovable app is a projection only. As a fallback, it may pull directly from the Sleuth server for tasks when the local macOS pipeline is not running, but that fallback must remain read-only and must not become the canonical workflow.

## Architecture & Stack

- **Frontend:** React + Vite + TanStack Query (standard Lovable stack)
- **Styling:** Tailwind CSS (or Vanilla CSS if adhering strictly to current project standards, but Lovable defaults to Tailwind + shadcn/ui)
- **Backend / Database:** Supabase (typical Lovable backend) or a custom Node/Edge function layer to receive webhook pushes.
- **Hosting:** Lovable's deployment environment.

### Hard Constraints

- **Local-first remains canonical:** Obsidian, the local SQLite database, and existing MCP/CLI flows remain the system of record.
- **Cloud is a mirror, not a migration:** No cloud-hosted state should be required for the local dashboard, daily sync, or rebalance workflows to function.
- **No raw vault replication:** Push only a deliberately projected subset, not arbitrary markdown bodies or the full note corpus.
- **No cloud embeddings or second-brain logic:** The mirror may render structured state, but semantic retrieval and core reasoning stay local.

## Data Synchronization

### 1. Secure Vault Push Script

To get Obsidian Vault data to the Lovable app without exposing sensitive plain-text over insecure channels:

- **Mechanism:** A local Python script (`scripts/lovable_vault_sync.py`) running on a launchd schedule alongside the hourly vault refresh.
- **Payload:** Rather than pushing the entire raw Vault, the script will extract the essential metadata needed for the dashboard (recent notes, project status, aggregated registry). Default posture: counts, labels, timestamps, and pre-rendered dashboard fields only.
- **Security:**
  - **Transport:** HTTPS POST to a Lovable/Supabase endpoint using a secure API Key/Bearer Token.
  - **E2E / Sanitization:** Only push metadata and explicitly whitelisted published artifacts. The local SQLite projection (`project_registry`, `vault_files` recents) is the source, not the raw markdown files, preventing accidental leakage of sensitive core vault data.

### 2. Git Pulse Sync Ingestion

- The local macOS pulse sync (`scripts/pulse_sync.sh` and `pulse_web_sync.sh`) currently generates local HTML/Markdown.
- **New Path:** Update the pipeline to push a structured JSON payload (containing GitHub activity balances, recent commits, and calendar events) to the Lovable app's ingestion API.
- TanStack Query on the Lovable frontend will fetch this JSON state from its own backend to render the UI reactively, mirroring the TUI/web dashboard.

### 3. Sleuth Task Fallback

The current architecture relies on `sleuth_reminders.py` running on macOS to populate the SQLite database. If the macOS machine is asleep or offline, the Lovable app's task list will grow stale.

- **Fallback Strategy:** The Lovable app backend (Edge Function) will have the ability to poll the Sleuth Web API directly (`GET /workspace/<name>/reminders`).
- **Logic:**
  - The React app checks the `last_updated` timestamp of the macOS push.
  - If the timestamp is older than a threshold (e.g., 2 hours), TanStack Query triggers a direct fetch to the Sleuth server via the Lovable Edge Function proxy.
  - This ensures tasks are always up-to-date even if the local OS pipeline is paused.
  - Fallback results stay transient to the mirror. They do not write back into rebalance's canonical local store.

## Implementation Phases

### Phase 1: Scaffold & Static Mirror
1. Prompt Lovable to generate a React/Vite/TanStack app.
2. Provide Lovable with the layout and CSS of the current `web/pulse.html` to mirror the UI exactly.
3. Stub out the data layer in TanStack Query using hardcoded JSON that matches the output of the current `dashboard.py` / `pulse_web.py` context.

### Phase 2: Ingestion API & Git Pulse
1. Configure Lovable/Supabase with a secure ingestion endpoint (API key authenticated) to receive JSON payloads.
2. Create `scripts/lovable_push.py` on the macOS host to extract the `dashboard.py` data dictionaries into JSON.
3. Hook `lovable_push.py` into the daily/hourly launchd syncs (`daily_sync.sh`, `pulse_sync.sh`) to push state to the cloud.

### Phase 3: Secure Vault Sync
1. Define the exact vault subset needed for the Lovable view (e.g., `most_likely_active_projects`, `semi_active_projects`, recent `vault_files`).
2. Add a sanitization step to the push script to securely transmit this vault data without sending raw file contents unless explicitly tagged for the web.

### Phase 4: Sleuth Fallback
1. Integrate the Sleuth API Bearer token into Lovable's secure Secrets management.
2. Implement an Edge Function in the Lovable app to proxy requests to Sleuth.
3. Implement the TanStack Query fallback logic: if local sync is stale, fetch directly from the Sleuth Edge Function proxy.

## Security Considerations
- **No Raw Vault Exposure:** Do not push the entire Obsidian vault. Push only projected, required data.
- **Authentication:** All ingestion endpoints on the Lovable app must require a pre-shared key (PSK) generated during onboarding and stored in `temp/rbos.config` or macOS Keychain.
- **CORS & Token Leakage:** The Sleuth Bearer token must be kept out of the frontend bundle; direct Sleuth polling should occur via a server-side proxy/Edge function within the Lovable deployment.
- **Canonical Boundary:** If the cloud mirror is unavailable or stale, the local dashboard and local rebalance workflows must continue to function unchanged.
