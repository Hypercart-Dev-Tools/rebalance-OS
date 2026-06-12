# rebalance OS Diagram

## Contents
- System Spine
- Refresh Fanout
- Query And Publish Paths

Derived from [ARCHITECTURE.md](/Users/noelsaw/Documents/rebalance-OS/ARCHITECTURE.md), [src/rebalance/ingest/index_ops.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/index_ops.py), [src/rebalance/ingest/semantic_index.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/semantic_index.py), [src/rebalance/ingest/querier.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/querier.py), [src/rebalance/mcp/server.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/mcp/server.py), [scripts/daily_sync.sh](/Users/noelsaw/Documents/rebalance-OS/scripts/daily_sync.sh), and [scripts/pulse_sync.sh](/Users/noelsaw/Documents/rebalance-OS/scripts/pulse_sync.sh).

## System Spine

```text
                             rebalance OS

  Human / Agent Hosts                         Scheduled Jobs
  -------------------                         --------------
  VS Code / Claude / Codex                    launchd
  CLI: rebalance ...                          - daily_sync.sh
  MCP tools                                   - pulse_sync.sh
  - ask                                       - vault_sync.sh
  - index_status                              - github_sync.sh
  - refresh_index
  - semantic_query
  - publish_pulse
           \                                      /
            \                                    /
             v                                  v
        +--------------------------------------------------+
        | Runtime entry points                             |
        | - src/rebalance/mcp/server.py                    |
        | - src/rebalance/mcp/tools/*                      |
        | - scripts/*.sh -> Python calls                   |
        +--------------------------+-----------------------+
                                   |
                                   v
        +--------------------------------------------------+
        | src/rebalance/ingest/index_ops.py                |
        | Central orchestration spine                      |
        | - Collector registry: COLLECTORS                 |
        | - get_index_status()                             |
        | - refresh_index(scope=[...])                     |
        | - get_watched_repos()                            |
        +--------------------------+-----------------------+
                                   |
                                   v
        +--------------------------------------------------+
        | Local data plane                                 |
        | SQLite + sqlite-vec                              |
        | - source-native tables                           |
        | - legacy vector tables                           |
        | - unified semantic index                         |
        +--------------------------+-----------------------+
                                   |
                  +----------------+----------------+
                  |                                 |
                  v                                 v
        +--------------------------+      +-----------------------------+
        | Query / synthesis        |      | Publish / operator outputs  |
        | src/rebalance/ingest/    |      | dashboard notes, pulse,     |
        | querier.py               |      | reports, MCP responses      |
        +--------------------------+      +-----------------------------+
```

## Refresh Fanout

```text
refresh_index(scope=[...])
        |
        +--> vault
        |    note_ingester.py
        |      -> vault_files
        |      -> chunks / keywords / links
        |    embedder.py
        |      -> embeddings
        |    semantic_index.py
        |      -> semantic_documents(source=vault)
        |      -> semantic_embeddings
        |
        +--> github
        |    github_scan.py
        |      -> github_activity
        |      -> github_pushed_repos
        |    github_knowledge.py
        |      -> github_items / comments / commits / checks / branches
        |      -> github_documents
        |      -> github_embeddings
        |    semantic_index.py
        |      -> semantic_documents(source=github)
        |      -> semantic_embeddings
        |
        +--> calendar
        |    calendar.py
        |      -> calendar_events
        |
        +--> sleuth
        |    sleuth_reminders.py
        |      -> sleuth_reminders
        |
        +--> email
        |    gmail.py
        |      -> email_messages
        |    semantic_index.py
        |      -> semantic_documents(source=email)
        |
        \--> semantic
             semantic_index.py
             - backfill_semantic_documents(all)
             - embed_pending(all)

Other registry-fed inputs
  vault project registry markdown
      -> preflight.py / registry.py
      -> project_registry
```

## Query And Publish Paths

```text
                            LOCAL SQLITE DATA

   project_registry      github_activity      github_documents
   vault_files/chunks    calendar_events      email_messages
   embeddings            github_embeddings    semantic_documents
                                               semantic_embeddings
             \                |                /
              \               |               /
               +--------------+--------------+
                              |
                              v
                 src/rebalance/ingest/querier.py::ask()
                              |
         +--------------------+--------------------+
         |                    |                    |
         v                    v                    v
  _gather_project_context  _gather_github_*   _gather_vault_*
         |                    |                    |
         +---------+----------+----------+---------+
                   |                     |
                   v                     v
          _gather_calendar_context   _gather_temporal_context
                   \                     /
                    \                   /
                     +--------+--------+
                              |
                              v
                         _build_prompt()
                              |
                              v
                  optional local Qwen first-pass synthesis
                              |
                              v
                     host agent reviews + presents


publish_pulse()
    reads SQLite + temp/rbos.config
        -> render markdown for today + yesterday
        -> commit/push private pulse repo only if changed

index_status()
    reads SQLite only
        -> per-source counts
        -> semantic index health
        -> drift/freshness diagnostics
```
