---
name: clio
description: Install, verify, or uninstall a Claude Code hook that logs prompts to centralized JSONL and optionally renders them into a readable Markdown note.
---

# CLIO

CLIO installs a user-scope `UserPromptSubmit` hook, which appends every submitted
prompt to `~/.claude/prompt-log.jsonl`. An optional exporter renders that JSONL as
Markdown at a location you choose. The capture hook stays fast; formatting happens
later, on demand or on a schedule.

## What gets logged

One line per prompt:

```json
{"timestamp":"2026-07-09T18:42:11Z","repo":"hypercart","branch":"main","machine":"Noels-MacBook-Pro","session_id":"abc123","prompt":"..."}
```

## Install

Run once from the root of this CLIO checkout (macOS/Linux). CLIO requires `jq`:

```bash
command -v jq >/dev/null 2>&1 || { echo "jq is required. Install it: brew install jq (macOS) / apt install jq (Linux)"; return 1 2>/dev/null || exit 1; }

mkdir -p ~/.claude/hooks

cat > ~/.claude/hooks/log-prompt.sh << 'EOF'
#!/bin/bash
# Logs Claude Code prompts to a centralized JSONL file.
# Never blocks prompt submission (always exits 0) — failures go to a
# separate error log instead of silently dropping the prompt.
#
# CAPTURE FILTERS (a skipped prompt is never written to the raw JSONL, so
# this is a permanent drop, not a render-time hide — see INSTALL.md Notes):
#   1. Automated, non-user turns (background-task notifications, monitor
#      events) are skipped outright. Matched on the RAW prompt, before tag
#      stripping, because stripping would remove the evidence.
#   2. Prompts shorter than CLIO_MIN_PROMPT_CHARS (default 100) after
#      cleaning are skipped. Intent: capture substantive session-opening
#      prompts, not "yes" / "push it" / "do it".
# Set CLIO_MIN_PROMPT_CHARS=0 to capture everything again.
input=$(cat)
errlog="$HOME/.claude/prompt-log-errors.log"
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
minchars="${CLIO_MIN_PROMPT_CHARS:-100}"

if ! command -v jq >/dev/null 2>&1; then
  echo "$ts jq not found — prompt not logged" >> "$errlog"
  exit 0
fi

repo=$(basename "$(git -C "$CLAUDE_PROJECT_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$CLAUDE_PROJECT_DIR")")
branch=$(git -C "$CLAUDE_PROJECT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
machine=$(scutil --get ComputerName 2>/dev/null || hostname -s 2>/dev/null || hostname)

# Strips auto-injected context blocks (ide_selection, system-reminder, local
# command wrappers, etc.) so only what you actually typed gets logged.
if ! echo "$input" | jq -c \
  --arg ts "$ts" --arg repo "$repo" --arg branch "$branch" --arg machine "$machine" \
  --arg minchars "$minchars" \
  '
  def clean_prompt:
    gsub("(?i)<(ide_selection|system-reminder|task-notification|local-command-stdout|local-command-caveat|command-name|command-message|command-args|command-contents|function_results)[^>]*>.*?</\\1>"; ""; "gm")
    | gsub("\\n[ \\t]*\\n[ \\t]*\\n+"; "\\n\\n")
    | sub("^\\s+"; "") | sub("\\s+$"; "");
  ($minchars | tonumber) as $min
  | (.prompt // "") as $raw
  | ($raw | clean_prompt) as $cleaned
  # 1. drop automated, non-user turns (checked on $raw, pre-strip)
  | select($raw | test("<task-notification>|\\[SYSTEM NOTIFICATION - NOT USER INPUT\\]"; "i") | not)
  # 2. drop anything too short to be a substantive prompt
  | select(($cleaned | length) >= $min)
  | {timestamp:$ts, repo:$repo, branch:$branch, machine:$machine, session_id:.session_id, prompt:$cleaned}
  ' \
  >> "$HOME/.claude/prompt-log.jsonl" 2>>"$errlog"; then
  echo "$ts failed to log prompt (malformed input?)" >> "$errlog"
fi

exit 0
EOF

chmod +x ~/.claude/hooks/log-prompt.sh

SETTINGS=~/.claude/settings.json
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"

if grep -q "log-prompt.sh" "$SETTINGS" 2>/dev/null; then
  echo "Hook already registered in $SETTINGS — skipping."
else
  jq '.hooks.UserPromptSubmit = ((.hooks.UserPromptSubmit // []) + [{"hooks":[{"type":"command","command":"$HOME/.claude/hooks/log-prompt.sh"}]}])' \
    "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
  echo "Hook registered in $SETTINGS."
fi

install -m 0755 utils/CLIO/prompt-log-to-md.sh ~/.claude/hooks/prompt-log-to-md.sh

echo "✅ Installed. Smoke test:"
echo '{"prompt":"test","session_id":"install-check"}' | ~/.claude/hooks/log-prompt.sh
tail -1 ~/.claude/prompt-log.jsonl
```

## Verify (real session)

Start a new Claude Code session anywhere, submit any prompt, then:

```bash
tail -f ~/.claude/prompt-log.jsonl
```

## Optional: export to human-readable Markdown

The exporter appends only entries not already identified in the note, with newest
ones immediately below `<!-- CLIO:ENTRIES -->`. It preserves everything above that
marker, reconciles full entries found in matching conflict siblings, and quarantines
those siblings under `.clio-reconciled/`.

Its cursor (`~/.claude/prompt-log-to-md.state`) is only a scan optimization. The
source-owned `~/.claude/prompt-log-manifest.txt` is an append-only delivery receipt:
one rendered `clio:id` per line, no prompt text. It remains if the cursor is deleted.

**Run it** — default location:

```bash
~/.claude/hooks/prompt-log-to-md.sh
```

**Run it** — custom location, for example an Obsidian vault:

```bash
~/.claude/hooks/prompt-log-to-md.sh ~/vault/_meta/prompt-log/prompt-log.md
```

**Preview conflict recovery without changing the note or moving files:**

```bash
CLIO_RECONCILE_DRY_RUN=1 ~/.claude/hooks/prompt-log-to-md.sh ~/vault/_meta/prompt-log/prompt-log.md
```

The first run creates a fixed header and marker, then one `## <REPO>` block per
prompt. To sync on a schedule, point a launchd job (macOS) or cron entry at the
same exporter command and output path. On a shared synced file, run it on every
machine; each device adds its own local prompts without regenerating the note.

### Auto-sync every 1 minute (macOS launchd)

Replace `OUT_PATH` with your chosen output file:

```bash
OUT_PATH="$HOME/vault/_meta/prompt-log/prompt-log.md"
PLIST=~/Library/LaunchAgents/com.claude.prompt-log-to-md.plist

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude.prompt-log-to-md</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/.claude/hooks/prompt-log-to-md.sh</string>
        <string>$OUT_PATH</string>
    </array>
    <key>StartInterval</key>
    <integer>60</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/.claude/prompt-log-to-md.out.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.claude/prompt-log-to-md.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"
```

Check it is running:

```bash
launchctl list | grep com.claude.prompt-log-to-md
```

Stop and remove it:

```bash
launchctl unload ~/Library/LaunchAgents/com.claude.prompt-log-to-md.plist
rm ~/Library/LaunchAgents/com.claude.prompt-log-to-md.plist
rm -f ~/.claude/prompt-log-to-md.out.log ~/.claude/prompt-log-to-md.err.log
```

## Uninstall

This removes only the `log-prompt.sh` entry from `UserPromptSubmit`; it does not
touch other registered hooks.

```bash
tmp=$(mktemp)
jq '.hooks.UserPromptSubmit = ((.hooks.UserPromptSubmit // [])
      | map(.hooks = ((.hooks // []) | map(select(((.command // "") == "$HOME/.claude/hooks/log-prompt.sh") | not))))
      | map(select((.hooks // []) | length > 0)))
    | if (.hooks.UserPromptSubmit // []) == [] then del(.hooks.UserPromptSubmit) else . end' \
  ~/.claude/settings.json > "$tmp" && mv "$tmp" ~/.claude/settings.json

rm ~/.claude/hooks/log-prompt.sh
rm -f ~/.claude/hooks/prompt-log-to-md.sh ~/.claude/prompt-log-to-md.state ~/.claude/prompt-log-manifest.txt ~/.claude/prompt-log-errors.log
```

## Notes

- **Scope:** `~/.claude/settings.json` is user-level, so one log covers every repo.
- **Machine and branch:** both are recorded with each prompt for later context.
- **Timestamps:** the raw JSONL and every `clio:id` stay **UTC** — the ID is `session_id:timestamp`, so localizing it would change all IDs, break dedup, and re-emit the note as duplicates. Only the *displayed* line is localized (`2026-07-19 14:27:50 PDT`). Conversion uses `python3` (`datetime.astimezone()`), **not** jq: jq's `strflocaltime` is not DST-aware here and renders July as `PST / -0800`. Without `python3` the display falls back to UTC. Entries rendered before this change keep their original UTC display; history is not rewritten.
- **Capture filtering (permanent):** the hook skips two classes of prompt outright, so they never reach the raw JSONL:
  - *Automated turns* — anything containing `<task-notification>` or the `[SYSTEM NOTIFICATION - NOT USER INPUT]` preamble (background-task and monitor events). Matched on the raw prompt before tag stripping.
  - *Short prompts* — under `CLIO_MIN_PROMPT_CHARS` (default **100**) after injected blocks are stripped, so `yes` / `push it` are dropped while substantive session-opening prompts are kept. Set `CLIO_MIN_PROMPT_CHARS=0` to capture everything again.

  This is a **drop, not a hide** — unlike `PROMPT_LOG_EXCLUDE` below, a skipped prompt is unrecoverable. Prefer the render-side filter if you might want the text back later. Covered by `test/clio-capture.sh`.
- **Render filtering (reversible):** `PROMPT_LOG_EXCLUDE` defaults to `file-based relay|cross-agent dependency drift`; matching text stays in raw JSONL but is omitted from the Markdown (reported as `state: excluded` by `--status`). Set it empty to render all prompts.
- **Resetting:** deleting the state file rescans JSONL, but ID-based note deduplication prevents a duplicate rendered entry. The manifest is intentionally independent of that cursor.
- **Errors:** the capture hook always exits 0, writing failures to `~/.claude/prompt-log-errors.log`; a manifest receipt failure is reported but never rolls back a successful export.
