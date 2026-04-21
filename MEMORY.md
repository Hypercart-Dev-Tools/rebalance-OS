# Memory

- Bash-script RAG spike entrypoint: `temp/bash_script_rag_spike.py`.
- Reusable spike artifacts: `temp/rag/bash-script-spike.sqlite` and `temp/logs/bash-script-spike.jsonl`.
- The spike's default extra corpus includes wp-code-check scanner patterns from `../GH Repos/wp-code-check/dist/patterns/**/*.json` plus `PATTERN-LIBRARY.json` and `PATTERN-LIBRARY.md`.
- Repo direction is pivoting from a general second-brain framing toward a GitHub sprint/deployment planner.
- Clarified product direction: primary purpose remains a second brain over work artifacts; sprint planning and deployment goal-setting are secondary outcomes, driven especially by deeper GitHub artifact ingestion and deploy-readiness inference.
- Hard requirement: do not rely on an agent skimming hundreds of live GitHub issues/PRs; ingest and vectorize GitHub artifacts into local SQLite so retrieval and recommendations are driven from the local store.
- The readiness layer should stay explicit and inspectable: computed status, confidence, evidence, and blockers from local repo signals instead of opaque hidden reasoning.
- Weekly review notes should be able to write back into the Obsidian vault as `week-of-YYYY-MM-DD.md` artifacts and immediately re-enter the retrieval pipeline so next week's knowledge includes last week's summary.
- Next planning priorities: add inferred GitHub issue<->PR reconciliation with high/medium-confidence close suggestions, and add Sleuth AI / Slack reminder ingestion as a structured signal source before broader Slack thread ingestion.
- The reviewed Sleuth reminders JSON is a list-shaped feed with fields such as `ReminderID`, `ReminderMessageText`, `ShouldPostOn`, `OriginalChannelID`, and `OriginalMessageID`; start Slack integration from this structured reminder feed before broader thread ingestion.
- Experimental next step: a deterministic GitHub Action should run every 2-3 days, emit JSON + Markdown close-candidate reports, and stay report-only until the weekly local agent review proves the thresholds.
- The git-history spike now lives under `experimental/git-history/`, and its plan file moved there as `experimental/git-history/git-history-plan.md`.
