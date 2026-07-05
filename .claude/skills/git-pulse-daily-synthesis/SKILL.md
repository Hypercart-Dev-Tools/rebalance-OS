---
name: git-pulse-daily-synthesis
aliases:
  - daily-recap
description: >
  Generates a daily summary of Git Pulse multi-device activity using Gemini and appends it to today's Obsidian note.
  Use this to manually trigger the daily synthesis. Pass flags like --dry-run or --force as needed.
---

# `git-pulse-daily-synthesis` Skill

This skill invokes the `utils/git_pulse_daily_synthesis.py` script.

**Important Note:** This skill complements (but does not replace) `git-pulse-exec-recap` and `git-pulse-team-recap`. Those skills generate narrative prose into standalone recap files, whereas this skill generates a small daily block appended to your Obsidian Daily Note.

## Execution

When the user calls `/git-pulse-daily-synthesis [flags]`, execute the following bash script to invoke the python script.

```bash
# Resolve repo root relative to the skill execution context
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"

# Pass arguments directly to the python script
cd "$REPO_ROOT" && .venv/bin/python utils/git_pulse_daily_synthesis.py $ARGUMENTS
```

If the `--dry-run` flag is passed, ensure you print the output of the script back to the user, as the block will not be written to the vault.
