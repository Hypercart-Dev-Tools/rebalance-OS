---
gh_issue: NEXT
title: Simplify Intake, Definition, and Exclusion of Repos
status: Proposed (1-INBOX)
created: 2026-07-22
owner: Noel
goal: >
  Unify the confusing 4-source repository watching logic into a single, explicit file-based flow: 
  Auto-discovered -> Confirmed Monitor List <-> Exclude List.
doc_type: project
effort: 3
complexity: 3
risk: 4
phases: 3
---

# Simplify Intake, Definition, and Exclusion of Repos

## The Problem
Right now, the system uses 4 different sources to decide what a "watched repo" is (`project`, `activity`, `pushed`, `external`) AND an exclusion list (`github_ignored_repos`) that lives in a completely different location (`temp/rbos.config`). This is overkill, confusing, and makes it hard for the operator to know exactly what is being monitored and why.

## Proposed New Flow
1. **Auto-Populated List (Inbox):** GitHub CLI and desktop app activity are scanned and written to a visible list.
2. **Confirmed Monitor List:** Operator moves repos from the Auto list into this explicit inclusion list.
3. **Exclude List:** Operator moves repos they never want to see again into an explicit exclusion list.
*All three lists live in the exact same folder for easy operator management.*

## Brainstorming & Open Questions for the Operator

> [!WARNING]
> **Vault Dependency vs. Control Plane**
> The current `00-project-registry.md` lives in the Obsidian Vault, while the exclude list lives in `temp/rbos.config`. If we centralize them into the same folder, where should that folder be? 
> **Option A (Vault-first):** Put them all in the Vault (`Projects/`). *Risk:* Violates the existing architectural constraint that "Obsidian is an optional output, not a control-plane dependency" (if your Vault is unmounted, background ingest might fail or lose its config).
> **Option B (Repo-first):** Put them all in a dedicated `config/` or `registry/` folder inside the `rebalance-OS` repo, and just project/sync a readable copy to the Vault.
> **Question:** Which location do you prefer?

> [!IMPORTANT]
> **Killing the Auto-Watch Magic**
> Currently, the system automatically watches any repo you have activity in for 14 days, without you ever confirming it. 
> **Question:** If we move to this new flow, should we STRICTLY enforce that the collector ONLY watches the "Confirmed Monitor List"? (Meaning, new activity just lands in the Auto-Populated file and waits for you to explicitly move it to Confirmed, otherwise it doesn't get synced to the DB?)

> [!NOTE]
> **File Format**
> Since you want to manually manage these lists, plain Markdown files with bullet points (like the current project registry) seem best.
> e.g. `01-auto-discovered.md`, `02-confirmed-monitored.md`, `03-excluded.md`. Do you like this 3-file setup?

## System Design & Constraints
*(To be filled out based on brainstorm answers)*

## Phases
*(To be filled out based on brainstorm answers)*
