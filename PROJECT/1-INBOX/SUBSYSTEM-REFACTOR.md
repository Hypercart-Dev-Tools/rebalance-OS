Yes. Based on the current tree, there are 5 subsystems with the same spread/duplication pattern the command system had.

1. `Config + auth + path resolution` is the strongest candidate.
   Files: [src/rebalance/ingest/config.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/config.py), [src/rebalance/paths.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/paths.py), [src/rebalance/ingest/auth_log.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/auth_log.py), [scripts/setup_calendar_oauth.py](/Users/noelsaw/Documents/rebalance-OS/scripts/setup_calendar_oauth.py), [scripts/setup_gmail_oauth.py](/Users/noelsaw/Documents/rebalance-OS/scripts/setup_gmail_oauth.py)
   Reason: credentials, token paths, keyring fallbacks, legacy config, and setup behavior are still split across runtime modules and setup scripts. This directly affects portability and onboarding.
   Effort/risk: medium effort, high payoff, moderate risk.

2. `Query / retrieval / synthesis` needs a boundary pass.
   Files: [src/rebalance/chat.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/chat.py), [src/rebalance/ingest/querier.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/querier.py), [src/rebalance/mcp/tools/retrieval.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/mcp/tools/retrieval.py), [src/rebalance/mcp/tools/index.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/mcp/tools/index.py), [src/rebalance/cli/query.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/cli/query.py)
   Reason: there are multiple read-side surfaces with overlapping concepts: semantic query, legacy source queries, `ask()`, chat-with-data, MCP wrappers, CLI wrappers.
   Effort/risk: medium effort, medium risk.

3. `Pulse / dashboard / web surface` is spread across too many runtime entry points.
   Files: [scripts/dashboard.py](/Users/noelsaw/Documents/rebalance-OS/scripts/dashboard.py), [scripts/pulse_web.py](/Users/noelsaw/Documents/rebalance-OS/scripts/pulse_web.py), [scripts/pulse_server.py](/Users/noelsaw/Documents/rebalance-OS/scripts/pulse_server.py), [src/rebalance/web.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/web.py), [src/rebalance/web_components.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/web_components.py)
   Reason: rendering, HTTP serving, refresh triggers, and UI composition are split between scripts and package modules, with multiple `sys.path` bootstrap hacks.
   Effort/risk: medium-high effort, moderate risk.

4. `Scheduler / launchd orchestration` would benefit from consolidation.
   Files: [scripts/daily_sync.sh](/Users/noelsaw/Documents/rebalance-OS/scripts/daily_sync.sh), [scripts/vault_sync.sh](/Users/noelsaw/Documents/rebalance-OS/scripts/vault_sync.sh), [scripts/github_sync.sh](/Users/noelsaw/Documents/rebalance-OS/scripts/github_sync.sh), installer scripts and plist templates under [scripts/](/Users/noelsaw/Documents/rebalance-OS/scripts)
   Reason: behavior is coherent, but policy is duplicated in shell scripts, installers, and docs. This is where freshness regressions can hide after ingest refactors.
   Effort/risk: low-medium effort, low risk.

5. `Project onboarding / registry / inference` is a good second-wave candidate.
   Files: [src/rebalance/ingest/preflight.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/preflight.py), [src/rebalance/ingest/registry.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/registry.py), [src/rebalance/ingest/project_inference.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/project_inference.py), [src/rebalance/ingest/project_classifier.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/project_classifier.py), [src/rebalance/ingest/project_priority.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/project_priority.py), [src/rebalance/mcp/tools/onboarding.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/mcp/tools/onboarding.py)
   Reason: discovery, confirmation, classification, and priority logic are related but live in separate modules with evolving contracts.
   Effort/risk: medium effort, medium risk.

If you want strict prioritization, I’d do:

1. config/auth/path
2. pulse/dashboard/web
3. query/retrieval
4. scheduler
5. onboarding/registry

The one I would not broaden casually right now is `semantic_index.py`: it still deserves work, but it is already in active contract churn from the collector refactor, so it is higher regression risk than the others.

If useful, I can turn this into a short “next subsystem audit queue” section inside the existing audit doc.

Yes. Reviewing recent collector-related work in [CHANGELOG.md](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md), the refactor already crossed into `1`, `2`, and `4`, but unevenly.

`1. Config / auth / path resolution` has already been touched heavily. The clearest entries are the portability/auth cleanup in [0.34.0](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:29), especially path resolver adoption and centralized OAuth token paths at [CHANGELOG.md](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:33), plus earlier keyring/config work in [0.31.6](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:336) and config discovery fixes in [0.31.3](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:401). So `1` is not untouched; it has already been partially refactored as part of collector portability.

`2. Pulse / dashboard / web` has also been touched, but more as feature and behavior work than as a clean architectural consolidation. Relevant entries are the dashboard/pulse fixes in [0.31.3](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:403), the pulse self-repair loop in [0.31.5](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:359), the Figma home-page integration in [0.31.9](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:307), and the dashboard/web additions in [0.32.0](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:96). So yes, `2` was touched, but it still reads like an accreted surface rather than a subsystem that got a proper unification pass.

`4. Scheduler / launchd orchestration` was definitely touched already. The big portability/scheduler cleanup is in [0.29.0](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:461), where the sync scripts and plist templates were made portable at [CHANGELOG.md](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:469). Then [0.29.1](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:454) brought pulse-server into the same template-managed pattern, and [0.32.0](/Users/noelsaw/Documents/rebalance-OS/CHANGELOG.md:80) explicitly says the collector refactor preserved scheduled/daily sync behavior.

So the short answer is: yes, all of `1`, `2`, and `4` were touched already. But only `1` and `4` look like they got deliberate refactor-level attention. `2` looks more like repeated surface changes on top of still-split architecture, so it remains a good candidate for a focused pass.