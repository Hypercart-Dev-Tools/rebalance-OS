# GitHub Prior-Art Scan: Local-First "Work Intelligence" System

## Verdict: Largely Whitespace, With Two Architectural Twins to Study

No open-source project hits all five match criteria. The specific combination — multi-person signal blending (teammates' calendars + GitHub + Slack + notes + email), a single ranked "what to work on next / what's about to drop" recommendation, tunable trust/weight/redundancy levers, local SQLite, and MCP exposure — does not exist on GitHub as of June 2026. **Criterion 4 (the team dimension) is universally absent**: every candidate surveyed is a single-operator tool. The redundancy-vs-net-new signal distinction and per-person trust coefficients appear in no project at all.

However, this is not empty whitespace. Two brand-new, near-zero-star projects — [OWL](https://github.com/msaule/owl) and [DevRecall](https://github.com/pavelpilyak/devrecall) — independently converged on almost the identical architecture (local SQLite world store + calendar/GitHub/Slack/email connectors + MCP server + local dashboard), confirming the design is being discovered by others right now, just without the prioritization brain or team blending. The top three to study:

1. **[OWL (msaule/owl)](https://github.com/msaule/owl)** — closest overall architecture; LLM discovery engine over a SQLite knowledge graph with an 8-tool MCP server.
2. **[DevRecall (pavelpilyak/devrecall)](https://github.com/pavelpilyak/devrecall)** — closest connector set (Git + GitHub/GitLab + Slack + Google Calendar + Jira/Linear into local SQLite, MIT-licensed, Go); the strongest privacy model.
3. **[LifeOS (nbramia/LifeOS)](https://github.com/nbramia/LifeOS)** — closest on proactive output (morning briefings, nudges) with Gmail/Calendar/Slack/Obsidian ingestion and MCP tools, but personal-CRM-oriented and no GitHub source.

![Prior-art landscape: similarity vs popularity](https://d2z0o16i8xm8ak.cloudfront.net/0ef56f6e-64ff-4bd7-bae1-c42068904629/209aa140-2236-43ff-964b-2938995751b6/prior-art-landscape.png?Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9kMnowbzE2aTh4bThhay5jbG91ZGZyb250Lm5ldC8wZWY1NmY2ZS02NGZmLTRiZDctYmFlMS1jNDIwNjg5MDQ2MjkvMjA5YWExNDAtMjIzNi00M2ZmLTk2NGItMjkzODk5NTc1MWI2L3ByaW9yLWFydC1sYW5kc2NhcGUucG5nPyoiLCJDb25kaXRpb24iOnsiRGF0ZUxlc3NUaGFuIjp7IkFXUzpFcG9jaFRpbWUiOjE3ODE4OTA4MTl9fX1dfQ__&Signature=Ws-9GtqoR-10dIVw71QqwlJjFLa~sPFwt9VLngP4i0-haOZ8zMO7iJllcKfUI~dgDyf2OVwNUC1pAmfeDHogrb3FR27P7OWqmOaiuBn1YII6hIkx7B1mOG6nAzzzt2Alp~PKCLWMxq~5iNUY4igLxKDcJtPZOP-~cR6HlKGknCZeoeX5mmqqXSqwdafmI~dj4UaFBOZ92T5~xeSPMLohZrw2odMp6OZP6mCcelKQXk9D4gTGE48Dp4zFvamifa67aO3xEPoqirh2m46H4wgkOAx9GFfYyneh2-aPt9Xt9A8BF-t8eBR0RJN-ocjAKZzisYySxkXMgwUQyqk0OFYMRQ__&Key-Pair-Id=K1BF7XGXAIMYNX)

## Match Criteria Recap

| # | Criterion |
|---|-----------|
| 1 | Aggregates heterogeneous personal/work signals (calendar + git + notes/email + chat) |
| 2 | Produces a prioritized next-action / "what to work on" recommendation |
| 3 | Local-first / self-hosted with an LLM synthesis layer |
| 4 | Team dimension — blends multiple people's activity, especially calendars |
| 5 | Exposes via MCP / agent tooling |

## Master Comparison Table

All stars, push dates, and licenses verified directly against the GitHub API on June 12, 2026. ✅ = hits criterion, ◐ = partial.

| Project | Stars | Last push | License | C1 multi-source | C2 ranked next-action | C3 local + LLM | C4 team | C5 MCP | Score |
|---|---|---|---|---|---|---|---|---|---|
| [OWL](https://github.com/msaule/owl) | 1 | 2026-03 | MIT | ✅ | ◐ urgency-scored feed | ✅ | ❌ | ✅ | **4** |
| [DevRecall](https://github.com/pavelpilyak/devrecall) | 1 | 2026-06 | MIT | ✅ | ❌ retrospective | ✅ | ❌ | ✅ | **4** |
| [LifeOS](https://github.com/nbramia/LifeOS) | 14 | 2026-06 | GPL-3.0 | ✅ (no GitHub) | ◐ briefings/nudges | ✅ | ❌ | ✅ | **3** |
| [GAIA](https://github.com/theexperiencecompany/gaia) | 211 | 2026-06 | Polyform Strict | ✅ | ✅ suggested actions | ❌ not local-first | ◐ | ✅ | **3** |
| [Onyx (ex-Danswer)](https://github.com/onyx-dot-app/onyx) | 30,274 | 2026-06 | Source-available EE | ✅ 40+ connectors, no calendar | ❌ Q&A only | ◐ self-hosted, not SQLite | ✅ org | ✅ | **3** |
| [Xyne](https://github.com/xynehq/xyne) | 669 | 2026-06 | Apache-2.0 | ✅ | ❌ search/answers | ✅ | ✅ org | ❌ | **3** |
| [Dex](https://github.com/davekilleen/dex) | 400 | 2026-06 | PolyForm Noncommercial | ❌ files + calendar only | ✅ 3 daily priorities, stall detection | ◐ markdown, no SQLite | ❌ | ✅ | **3** |
| [ai-chief-of-staff](https://github.com/mboverell/ai-chief-of-staff) | 17 | 2026-01 (stale) | MIT | ✅ cal+email+git+notes | ✅ "open loops & slippage" | ✅ | ❌ | ❌ | **3** |
| [work-dAIgest](https://github.com/tweag/work-daigest) | 7 | 2024-11 (stale) | MIT | ◐ GitHub + Calendar | ❌ retrospective | ◐ Bedrock LLM | ❌ | ❌ | **3** |
| [OpenHuman](https://github.com/tinyhumansai/openhuman) | 31,718 | 2026-06 | GPL-3.0 | ✅ 118+ integrations | ❌ context retrieval | ✅ SQLite Memory Tree | ❌ | ❌ | **2** |
| [Khoj](https://github.com/khoj-ai/khoj) | 35,089 | 2026-03 | AGPL-3.0 | ❌ docs only | ❌ | ✅ | ❌ | ◐ MCP client | **2** |
| [Apache DevLake](https://github.com/apache/incubator-devlake) | 3,032 | 2026-06 | Apache-2.0 | ✅ dev tools, no GCal/Slack | ❌ dashboards | ❌ no LLM | ✅ | ❌ | **2** |
| [GrimoireLab](https://github.com/chaoss/grimoirelab) | 602 | 2026-06 | GPL-3.0 | ✅ 30+ backends, no calendar | ❌ dashboards | ❌ no LLM | ✅ | ❌ | **2** |
| [Taskwarrior](https://github.com/GothenburgBitFactory/taskwarrior) | 5,870 | 2026-06 | MIT | ❌ manual tasks | ✅ tunable urgency polynomial | ◐ no LLM | ❌ | ❌ | **2** |
| [PersonalOS](https://github.com/amanaiproduct/personal-os) | 457 | 2026-03 | Non-standard | ❌ local files only | ✅ P0–P3 vs goals | ✅ | ❌ | ✅ | **2** |
| [claude-chief-of-staff](https://github.com/mimurchison/claude-chief-of-staff) | 410 | 2026-02 (stale) | MIT | ✅ no GitHub | ✅ goal-aligned triage | ❌ cloud MCPs | ❌ | ✅ | **2** |
| [second-brain-starter](https://github.com/coleam00/second-brain-starter) | 587 | 2026-06 | None declared | ✅ (PRD scaffold) | ❌ | ✅ | ❌ | ❌ avoids MCP | **2** |
| [Atom](https://github.com/rush86999/atom) | 761 | 2026-06 | AGPL-3.0 | ✅ | ◐ NLU-based | ❌ unverified | ◐ | ❌ | **2** |

Score-1 projects (out of scope — single-source or no work-signal angle, listed for completeness): [Logseq](https://github.com/logseq/logseq) (43.4k★), [SiYuan](https://github.com/siyuan-note/siyuan) (44.4k★), [Quivr](https://github.com/QuivrHQ/quivr) (39.2k★), [Karakeep](https://github.com/karakeep-app/karakeep) (26.0k★), [Reor](https://github.com/reorproject/reor) (8.6k★), [Leon](https://github.com/leon-ai/leon) (17.3k★), [ActivityWatch](https://github.com/ActivityWatch/activitywatch) (17.9k★), [Wakapi](https://github.com/muety/wakapi) (4.3k★), [git-standup](https://github.com/kamranahmedse/git-standup) (7.8k★), [MergeStat](https://github.com/mergestat/mergestat) (540★), [morning-digest](https://github.com/mshadmanrahman/morning-digest) (5★), [personal-ai-assistant](https://github.com/kaymen99/personal-ai-assistant) (147★, stale).

## Tier 1: The Two Architectural Twins (Score 4)

### OWL — msaule/owl

[OWL](https://github.com/msaule/owl) (1★, MIT, pushed March 2026) is a local-first Node.js daemon that stores all signals in a SQLite world model (`~/.owl/world.db`), with plugin connectors for Gmail, Google Calendar, GitHub (pushes/PRs/issues), Slack, and local files. An LLM discovery engine runs scheduled passes (quick every 30 min, deep every 6 h, daily debrief) over a knowledge graph, surfacing cross-source correlations and anomalies with urgency levels and confidence scores. It exposes a full MCP server (`owl_status`, `owl_ask`, `owl_entities`, `owl_discoveries`, `owl_events`, `owl_graph`, `owl_situations`) plus a localhost dashboard, and supports Ollama for fully local LLM operation.

**What it misses:** no team/multi-person blending, no per-source trust or redundancy levers, no Obsidian notes ingestion, and its output is a serendipitous discovery feed ("things you didn't notice") rather than a single ranked work queue. No dropped-ball/stale-delegation concept. It is brand-new and effectively unproven (1 star).

**Reuse value:** the plugin connector contract, the SQLite entity/relationship/event/situation schema, the three-tier scan scheduling, the urgency+confidence scoring pattern, and the MCP server design (8 tools, 2 resources) are all directly transferable.

### DevRecall — pavelpilyak/devrecall

[DevRecall](https://github.com/pavelpilyak/devrecall) (1★, MIT, pushed June 2026) is a Go daemon with a near-identical source set to the target system: local Git (commits/branches/files), GitHub/GitLab/Bitbucket (PRs/reviews/issues/comments), Slack, Google Calendar (meetings attended/organized/declined), Jira/Linear, and Confluence — all stored in local SQLite with no cloud sync or telemetry. It bundles ONNX embeddings for offline vector search (Ollama/OpenAI optional) and ships an MCP stdio server compatible with Claude Code, Cursor, Codex, Continue, and Zed. Its OAuth relay (a Cloudflare Worker pass-through that never sees data) is a notably clean privacy pattern.

**What it misses:** entirely retrospective — output is standups, weekly reports, brag docs, and recall chat, not a forward-looking ranked recommendation. Single-operator only, no teammate signals, no weighting levers, no email or Obsidian ingestion.

**Reuse value:** the Go ingestion adapters (especially Slack, Google Calendar, Jira/Linear), the SQLite FTS5 + vector schema, the stdio MCP server pattern, and the OAuth relay privacy model are the most production-shaped reusable components found anywhere in this scan.

## Tier 2: Strong Partial Overlaps (Score 3)

**[LifeOS](https://github.com/nbramia/LifeOS)** (14★, GPL-3.0, active) ingests Gmail, Google Calendar, Slack, an Obsidian vault, iMessage, WhatsApp, and more into SQLite FTS5 + ChromaDB with a nightly sync pipeline, exposes MCP tools to Claude Desktop/Code, and generates proactive morning briefings, pre-meeting prep, and relationship nudges — optionally fully offline via llama.cpp. It is the closest match on the proactive-output side, but it is a personal-CRM/relationship engine: no GitHub ingestion, no task ranking over engineering work, no team blending. The ingestion adapters and MCP tool definitions are highly reusable; GPL-3.0 matters if forking.

**[GAIA](https://github.com/theexperiencecompany/gaia)** (211★, Polyform Strict — noncommercial) has the best action-recommendation UX surveyed: event-driven workflows over Gmail, Calendar, Slack, Linear, Notion, and GitHub webhooks that produce suggested actions with an approve/edit/dismiss flow, plus team digests and custom MCP servers. It fails local-first (on-demand API fetches, no local store) and the license blocks commercial reuse — study the proactive-suggestion interaction pattern, don't fork.

**[Onyx (ex-Danswer)](https://github.com/onyx-dot-app/onyx)** (30.3k★) has the largest verified connector library in the category — 40+ including GitHub, Gmail, Slack, Jira, Linear, Confluence — plus agentic RAG and MCP support. But it is enterprise knowledge Q&A: no calendar connector, no prioritization output, no local-SQLite privacy posture. Its connector implementations are the single best reference codebase for writing ingestion adapters.

**[Xyne](https://github.com/xynehq/xyne)** (669★, Apache-2.0) is an open-source Glean alternative aggregating Google Workspace (including Calendar), Atlassian, Slack, and GitHub with an org-level team dimension and an entity relationship graph — the only project hitting criteria 1, 3, and 4 together. It remains a search/answer engine with no ranking layer and no MCP.

**[Dex](https://github.com/davekilleen/dex)** (400★, PolyForm Noncommercial) and **[PersonalOS](https://github.com/amanaiproduct/personal-os)** (457★) own the output side: Dex's `/daily-plan` produces exactly three priorities, auto-reduces on heavy meeting days, and flags projects stalled 12+ days (the closest thing found to "about-to-be-dropped" detection); PersonalOS answers "what should I work on?" with P0–P3 tiers against GOALS.md via an MCP server. Both are markdown-file-based with no live API ingestion and no team dimension.

**[mboverell/ai-chief-of-staff](https://github.com/mboverell/ai-chief-of-staff)** (17★, MIT, stale since Jan 2026) is the closest conceptual match on synthesis: it feeds calendar + email + git commits + Obsidian notes to Claude and runs a weekly review that explicitly catches "open loops and slippage" — the same dropped-ball framing as the target system. It is a personal Claude Code workflow (plain text, no SQLite, no MCP, no team), but its weekly-review prompt design is worth reading verbatim.

## Tier 3: Component Donors (Score 2)

- **[Taskwarrior](https://github.com/GothenburgBitFactory/taskwarrior)** (5.9k★, MIT, 20-year project) — the most mature prior art for the ranking math: a polynomial urgency score with signed, user-tunable coefficients (`urgency.due.coefficient=12.0`, `urgency.blocking.coefficient=8.0`, `urgency.age.coefficient=2.0`, negative coefficients for blocked tasks). This is conceptually identical to the target system's trust/weight/vagueness/staleness levers — just without sources, LLM, or team.
- **[Apache DevLake](https://github.com/apache/incubator-devlake)** (3.0k★, Apache-2.0) — the best-designed normalized domain schema for commits/PRs/issues/contributors and a Go+Python plugin framework for incremental source syncing. No LLM, no calendar (Feishu WIP only), no Slack, no MCP.
- **[CHAOSS GrimoireLab](https://github.com/chaoss/grimoirelab)** (602★, GPL-3.0) — Perceval's 30+ standalone Python fetch backends (Git, GitHub, Slack, Jira, Confluence, mailing lists) and SortingHat's cross-source identity resolution, which is directly relevant to mapping one teammate across GitHub/Slack/Calendar identities.
- **[OpenHuman](https://github.com/tinyhumansai/openhuman)** (31.7k★, GPL-3.0, May 2026 launch) — the most sophisticated local-first memory architecture: SQLite Memory Tree (chunks, scores, entity index, hotness), TokenJuice compression (~80% LLM cost reduction), 20-minute auto-fetch, Obsidian-compatible vault mirroring. It is a context-retrieval agent, not a prioritizer — no MCP, no ranking, no team.
- **[claude-chief-of-staff](https://github.com/mimurchison/claude-chief-of-staff)** (410★, MIT, stale) — goal-alignment triage prompts (Respond NOW / Handle today / FYI) and a composition pattern using multiple external MCP servers as data sources.
- **[second-brain-starter](https://github.com/coleam00/second-brain-starter)** (587★) — a PRD scaffold, not a product; notable for its argument for Python CLI wrappers over MCP tool calls for cost control.
- **[Khoj](https://github.com/khoj-ai/khoj)** (35.1k★, AGPL-3.0) — mature self-hosted RAG, scheduled automations, and multi-step research agents, but document-only ingestion: no calendar, GitHub, Slack, or email connectors.

## Stale or Unverifiable Candidates

| Project | Status | Note |
|---|---|---|
| [gtm (git-time-metric)](https://github.com/git-time-metric/gtm) | Abandoned (last push Jan 2022, last release 2018) | Time-attribution-to-commits concept via Git notes still instructive |
| [work-dAIgest](https://github.com/tweag/work-daigest) | Stale (Nov 2024) | Cleanest minimal GitHub+Calendar→LLM digest prompt design; hackathon PoC |
| [OpenRecall](https://github.com/openrecall/openrecall) | Stalled (Sep 2025) | Screen-capture approach, not structured signals |
| [personal-ai-assistant](https://github.com/kaymen99/personal-ai-assistant) | Stale (Jan 2025) | LangGraph supervisor/sub-agent pattern reference |
| utility-explorer ("ue") | Unverifiable | [Show HN post](https://news.ycombinator.com/item?id=46365947) describes Gmail+Calendar+GitHub→SQLite with Claude "what to work on next" — conceptually very close, but no public repo URL was discoverable; excluded from rankings |

## What the Whitespace Actually Is

Mapping criteria coverage across all 30 candidates makes the gap precise:

- **Criterion 1 (multi-source):** well covered — OWL, DevRecall, LifeOS, Onyx, Xyne, GAIA, OpenHuman all ingest 4+ heterogeneous sources.
- **Criterion 3 (local-first + LLM):** well covered — local SQLite + optional local LLM is now a recognizable pattern.
- **Criterion 5 (MCP):** increasingly common — OWL, DevRecall, LifeOS, Dex, PersonalOS all ship MCP servers.
- **Criterion 2 (ranked next-action):** covered only by file-based goal systems (Dex, PersonalOS, Taskwarrior) that don't ingest live signals. **No project ranks actions from ingested cross-source signals.**
- **Criterion 4 (team blending):** **covered by no one** in the personal-tool category. Team analytics exists only in dashboard form (DevLake, GrimoireLab, Xyne) with no recommendation output.

Three of the target system's core mechanisms have no prior art at all in this scan:

1. **Per-person trust + per-source weight blending with a redundancy penalty** — Taskwarrior's coefficient architecture is the only analogous math, applied to manually entered tasks.
2. **Redundant vs net-new signal classification** (teammate's calendar item already reflected in the operator's own GitHub/Slack vs filling a blind spot) — appears nowhere.
3. **Cross-source dropped-ball detection over delegated work** — Dex's 12-day stall threshold and ai-chief-of-staff's LLM "open loops" review are the only partial gestures, both single-person.

## Recommended Reuse Map

| Component needed | Best source | Why |
|---|---|---|
| Connector/ingestion adapters (Slack, GCal, Jira/Linear, Git) | [DevRecall](https://github.com/pavelpilyak/devrecall) (Go) or [GrimoireLab Perceval](https://github.com/chaoss/grimoirelab) (Python) | DevRecall matches the exact source set + SQLite target; Perceval backends are battle-tested standalone Python libraries |
| GitHub/Gmail/Slack connectors at production quality | [Onyx connectors directory](https://github.com/onyx-dot-app/onyx) | 40+ maintained implementations with permission syncing |
| SQLite world-model schema | [OWL](https://github.com/msaule/owl) (entities/relationships/events/situations) or [OpenHuman](https://github.com/tinyhumansai/openhuman) (Memory Tree + hotness) | Both purpose-built for cross-source local stores |
| Ranking/scoring math | [Taskwarrior urgency](https://github.com/GothenburgBitFactory/taskwarrior) | Signed tunable coefficients per attribute — direct template for trust/weight/vagueness/staleness levers |
| Cross-source identity resolution (teammate mapping) | [SortingHat / GrimoireLab](https://github.com/chaoss/grimoirelab) | Solves "same person across GitHub/Slack/Calendar" |
| Prompt design for synthesis + open-loops detection | [ai-chief-of-staff](https://github.com/mboverell/ai-chief-of-staff), [work-dAIgest](https://github.com/tweag/work-daigest) | Both publish legible prompts for multi-source work synthesis |
| MCP server patterns | [OWL](https://github.com/msaule/owl) (HTTP, 8 tools), [DevRecall](https://github.com/pavelpilyak/devrecall) (stdio subprocess), [LifeOS](https://github.com/nbramia/LifeOS) (Claude Desktop tools) | Three different transport/integration styles to compare |
| Privacy model | [DevRecall](https://github.com/pavelpilyak/devrecall) OAuth relay; [LifeOS](https://github.com/nbramia/LifeOS) local-only llama.cpp routing | Pass-through OAuth without data custody; offline LLM fallback |
| Proactive briefing UX | [LifeOS](https://github.com/nbramia/LifeOS), [GAIA](https://github.com/theexperiencecompany/gaia) | Morning briefing structure; approve/edit/dismiss suggested-action flow |

## Strategic Read

The landscape splits cleanly into two camps that have not yet merged: **ingestion-rich, recommendation-poor** (OWL, DevRecall, LifeOS, Onyx, Xyne, OpenHuman) and **recommendation-rich, ingestion-poor** (Dex, PersonalOS, Taskwarrior, claude-chief-of-staff). The target system sits exactly at the unoccupied intersection, with the team-blending and redundancy-classification layers as genuinely novel additions on top.

Two cautions follow from this. First, the appearance of OWL (March 2026) and DevRecall (June 2026) — both independently converging on local-SQLite + multi-connector + MCP — suggests this intersection is being actively discovered; the differentiation window is the synthesis/ranking brain and the team dimension, not the plumbing. Second, building the plumbing from scratch would be the lowest-value use of effort: forking or adapting DevRecall's connectors (MIT) or Perceval's backends, then investing original work in the trust/weight/redundancy ranking engine and the teammate-calendar blind-spot logic, is the path the prior art supports.
