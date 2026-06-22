# PROJECT — plan-doc index

Execution plans live here in a simple kanban: **1-INBOX** (proposed / not started),
**2-WORKING** (in progress), **3-DONE** (shipped). The repo-wide execution
source-of-truth is [../PROJECT.md](../PROJECT.md); end-user setup guides are at
the repo root (see [../README.md → Documentation](../README.md#documentation)).

> When a plan ships, move its file to `3-DONE/` and add a one-line status banner
> at the top so this index stays accurate.

## 1-INBOX — proposed / not started

| Doc | Topic |
|-----|-------|
| [P1-SIGNAL.md](./1-INBOX/P1-SIGNAL.md) | P1 signal layer |
| [P1-SQLITE.md](./1-INBOX/P1-SQLITE.md) | Git pulse historical retrieval (SQLite) |
| [P2-GRAPHQL.md](./1-INBOX/P2-GRAPHQL.md) | GitHub GraphQL ingest |
| [P2-LOVABLE-APP.md](./1-INBOX/P2-LOVABLE-APP.md) | Lovable app mirror |
| [P2-SEMANTIC-INDEX.md](./1-INBOX/P2-SEMANTIC-INDEX.md) | Unified semantic index |
| [P3-GOAL-LAYER.md](./1-INBOX/P3-GOAL-LAYER.md) | Coaching signals / goal layer |
| [EMAIL-INGEST.md](./1-INBOX/EMAIL-INGEST.md) | Gmail ingest plan — **shipped** (auth model now desktop-OAuth→keyring; see [../GMAIL.md](../GMAIL.md)) |

## 2-WORKING — in progress

| Doc | Topic |
|-----|-------|
| [CLAUDE-ONBOARDING.md](./2-WORKING/CLAUDE-ONBOARDING.md) | Onboarding flow (GitHub repos, registry) |
| [CHAT-WITH-DATA.md](./2-WORKING/CHAT-WITH-DATA.md) | "Chat with your rebalance data" — scoped, citations-first retrieval (`chat_with_data`) + dashboard Filter\|Ask switch. **Phase 0 done** (federated 7/10 vs 4/10 work-only); Phase 1 (hybrid FTS5+vec) next |
| [CLAUDE-REFACTOR.md](./2-WORKING/CLAUDE-REFACTOR.md) | Codebase refactor (CLI decomposition, observability) |
| [DECOUPLE-OBSIDIAN-AS-SOT.md](./2-WORKING/DECOUPLE-OBSIDIAN-AS-SOT.md) | Decouple Obsidian as source of truth for GitHub activity |
| [GH-SYNC-DELTA.md](./2-WORKING/GH-SYNC-DELTA.md) | Incremental GitHub sync (delta) |
| [GMAIL-INGEST.md](./2-WORKING/GMAIL-INGEST.md) | Gmail auth options research — **resolved**: desktop-OAuth→keyring (see [../GMAIL.md](../GMAIL.md)) |
| [MAC-DASHBOARD-PORT.md](./2-WORKING/MAC-DASHBOARD-PORT.md) | Mac SwiftUI dashboard port |
| [P1-MODULE-REGISTRY.md](./2-WORKING/P1-MODULE-REGISTRY.md) | Module registry |
| [P1-MORNING-BRIEFING.md](./2-WORKING/P1-MORNING-BRIEFING.md) | Morning briefing pipeline |
| [PRIORITIZATION.md](./2-WORKING/PRIORITIZATION.md) | Signal-agnostic project prioritization |

## 3-DONE — shipped

| Doc | Topic |
|-----|-------|
| [SIMPLIFICATION-AUDIT.md](./3-DONE/SIMPLIFICATION-AUDIT.md) | Read/display layer simplification audit |
| [SLEUTH-PRODUCTION.md](./3-DONE/SLEUTH-PRODUCTION.md) | Sleuth → rebalance-OS production cutover |
