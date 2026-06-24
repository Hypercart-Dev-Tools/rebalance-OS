# Spec: Stickies-to-Obsidian Bash Script

**Project:** `stickies2obsidian.sh`  
**Platform:** macOS (Apple Silicon, Sequoia/Sonoma+)  
**Purpose:** Incrementally sync Apple Stickies note content into a target Obsidian Markdown vault file, prepending new content at the top and deduplicating via deterministic hashing.

---

## Overview

This script reads all `.rtfd` note packages from the macOS Stickies container, extracts plain text from each, and prepends any **new** notes to a designated Obsidian `.md` file. A SHA-256 hash of each note's content acts as a stable, deterministic deduplication key stored in a local state file, preventing re-imports on subsequent runs.

---

## Data Sources & Paths

| Resource | Path |
|---|---|
| Stickies notes directory | `~/Library/Containers/com.apple.stickies/Data/Library/Stickies/` |
| Each note | A UUID-named `.rtfd` package containing `TXT.rtf` |
| Obsidian target file | Configurable — default: `~/Documents/ObsidianVault/Stickies.md` |
| State/hash ledger | `~/.stickies2obsidian.state` (hidden dot-file, JSON-like flat format) |

---

## Configuration Variables

Defined at the top of the script for easy user customization:

```bash
STICKIES_DIR="$HOME/Library/Containers/com.apple.stickies/Data/Library/Stickies"
OBSIDIAN_FILE="$HOME/Documents/ObsidianVault/Stickies.md"
STATE_FILE="$HOME/.stickies2obsidian.state"
TIMESTAMP_FORMAT="%Y-%m-%d %H:%M"   # Used in Obsidian note headers
DRY_RUN=false                         # Set to true to preview without writing
```

---

## Dependencies

The script must check for these at startup and exit with a clear error if missing:

| Tool | Purpose | macOS availability |
|---|---|---|
| `textutil` | Convert `.rtf` → plain text | Built-in macOS |
| `shasum` | Generate SHA-256 content hashes | Built-in macOS |
| `sed`, `awk`, `date` | Text processing and formatting | Built-in macOS |

No Homebrew packages required — all dependencies are native to macOS.

---

## Script Logic & Flow

### 1. Startup Checks

- Verify `STICKIES_DIR` exists; exit with a message if not (Stickies app may never have been opened).
- Verify `OBSIDIAN_FILE`'s parent directory exists; create it with `mkdir -p` if needed.
- Create `STATE_FILE` if it does not exist (empty file is valid).
- Check all required tools are available via `command -v`.

### 2. State File Format

A plain-text ledger, one entry per line:

```
<SHA256_HASH> <UUID_OF_NOTE_PACKAGE>
```

Example:
```
a3f1bc9e...  A1B2C3D4-XXXX-XXXX-XXXX-XXXXXXXXXXXX.rtfd
9d72ef01...  B2C3D4E5-XXXX-XXXX-XXXX-XXXXXXXXXXXX.rtfd
```

This format is `grep`-able, `awk`-able, and human-readable. No JSON dependency needed.

### 3. Per-Note Processing Loop

For each `.rtfd` package found in `STICKIES_DIR`:

```
for each UUID.rtfd in STICKIES_DIR:
  RTF_FILE = UUID.rtfd/TXT.rtf
  skip if RTF_FILE does not exist (malformed package)

  PLAIN_TEXT = textutil -convert txt -stdout RTF_FILE
  skip if PLAIN_TEXT is empty or whitespace-only

  HASH = echo "$PLAIN_TEXT" | shasum -a 256 | awk '{print $1}'

  if HASH found in STATE_FILE → skip (already imported)

  TIMESTAMP = date formatted with TIMESTAMP_FORMAT
  build OBSIDIAN_BLOCK (see format below)

  prepend OBSIDIAN_BLOCK to OBSIDIAN_FILE (atomic write — see section 5)
  append "HASH UUID.rtfd" to STATE_FILE
  log: "Imported: UUID.rtfd"
```

### 4. Obsidian Note Block Format

Each imported note is wrapped in a clear, scannable Markdown block:

```markdown
---
**📝 Sticky Note** · `2025-06-04 21:00`
<!-- stickies-hash: a3f1bc9e... -->

<plain text content of the sticky note>

---
```

- The `<!-- stickies-hash: ... -->` HTML comment embeds the hash inline for secondary verification.
- The `---` HR lines create visual separation between notes in Obsidian's preview.
- The UUID is **not** shown in rendered Obsidian output (stays in state file only).

### 5. Atomic Prepend Strategy

Direct in-place prepending is risky. Use a temp file swap:

```bash
TMPFILE=$(mktemp)
cat <new_block> "$OBSIDIAN_FILE" > "$TMPFILE"
mv "$TMPFILE" "$OBSIDIAN_FILE"
```

`mv` on the same filesystem is atomic on macOS (POSIX rename). This prevents data loss if the script is interrupted mid-write.

### 6. Dry Run Mode

When `DRY_RUN=true`:
- Print each block that **would** be written to stdout.
- Print a count of new vs. skipped notes.
- Make **zero** writes to `OBSIDIAN_FILE` or `STATE_FILE`.

---

## Deduplication Strategy & Reliability Analysis

### The Deterministic Hash Approach

Each note's deduplication key is a **SHA-256 hash of the note's plain text content**. This is deterministic: the same content always produces the same hash, with a collision probability of ~1 in 2^256 — effectively zero for this use case.

### What It Handles Well ✅

| Scenario | Behavior |
|---|---|
| Script runs multiple times, notes unchanged | Notes are skipped — hash already in state |
| New sticky note added | Detected on next run, prepended once |
| Stickies app re-opened after upgrade | Same content → same hash → no duplicate |
| Note UUID changes (rare) | Content hash still matches, safely skipped |
| Script interrupted mid-run | Partial state preserved; next run catches remainder |

### Known Limitations & Edge Cases ⚠️

| Scenario | Risk | Mitigation |
|---|---|---|
| User edits an existing sticky note | Hash changes → treated as a **new** note; old version remains in Obsidian | Acceptable for a sync tool; Obsidian's file history provides recovery. Optionally, add a `--update` flag in v2. |
| Two notes with identical text | Same hash → only first one is imported | Very unlikely in practice. If needed, key on `UUID + hash` instead of `hash` alone — discussed below. |
| Note is all whitespace or empty | Script skips it (whitespace-only check in step 3) | Covered by guard clause. |
| `textutil` strips some RTF formatting | Loss of bold/italic in Obsidian | Intentional — plain text is the safe default. RTF-to-MD conversion is a v2 enhancement. |
| Stickies DB migration (Mojave legacy path) | `StickiesDatabase` flat file not handled | Scope is macOS Catalina+; add a detection branch if legacy support needed. |

### Hash-Only vs. UUID+Hash Keying

The spec defaults to **hash-only** keying because:
- It naturally deduplicates identical content across different note instances.
- UUID can change in edge cases (migration, backup restore).

If the duplicate-text edge case is a concern, switch the state key to `UUID:HASH`. This makes each physical note instance uniquely tracked regardless of content identity. Recommend as a `--strict-dedup` flag option.

**Verdict:** A content hash is reliable for this use case. The only real failure mode is intentional duplicate notes with identical text, which is an unlikely authoring pattern and an acceptable tradeoff for implementation simplicity.

---

## Invocation & Automation

### Manual run

```bash
chmod +x stickies2obsidian.sh
./stickies2obsidian.sh
```

### Dry run preview

```bash
DRY_RUN=true ./stickies2obsidian.sh
```

### Custom vault path

```bash
OBSIDIAN_FILE="$HOME/Documents/MyVault/Inbox/Stickies.md" ./stickies2obsidian.sh
```

### Automated via `launchd` (recommended over cron on macOS)

Create `~/Library/LaunchAgents/com.user.stickies2obsidian.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.user.stickies2obsidian</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/path/to/stickies2obsidian.sh</string>
  </array>
  <key>StartInterval</key>
  <integer>300</integer>  <!-- Run every 5 minutes -->
  <key>StandardOutPath</key>
  <string>/tmp/stickies2obsidian.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/stickies2obsidian.err</string>
</dict>
</plist>
```

Load with: `launchctl load ~/Library/LaunchAgents/com.user.stickies2obsidian.plist`

---

## Output & Logging

- Each run prints a summary to stdout: `[stickies2obsidian] 3 imported, 5 skipped.`
- Individual note imports logged: `[+] Imported: A1B2C3D4-...rtfd (2025-06-04 21:00)`
- Skips are silent by default; add `VERBOSE=true` to log them.
- Errors (missing file, tool not found) write to stderr.

---

## Obsidian Target File Structure (Resulting Layout)

```markdown
---
**📝 Sticky Note** · `2025-06-04 21:05`
<!-- stickies-hash: 9d72ef01... -->

Buy oat milk, check Noel's PR comments, call back re: GCP billing

---
---
**📝 Sticky Note** · `2025-06-03 14:22`
<!-- stickies-hash: a3f1bc9e... -->

Research Neo Geo ROM set archival options

---
```

Newest notes always appear at the top. Obsidian renders the `---` dividers cleanly in preview mode and the HTML comments are invisible in rendered output.

---

## Future Enhancements (v2 Scope)

- **RTF → Markdown conversion**: Use `pandoc` to preserve bold/italic from sticky notes.
- **`--update` flag**: Re-import edited notes by updating the hash and inserting a new block marked `*(edited)*`.
- **Obsidian frontmatter tagging**: Add YAML frontmatter with `tags: [stickies]` and `source: stickies` for Dataview queries.
- **iCloud-synced vault detection**: Auto-detect Obsidian vault path from `~/Library/Mobile Documents/`.
- **UUID+Hash strict mode**: `--strict-dedup` flag for users who write duplicate-content notes intentionally.
- **Delete detection**: Track note UUIDs and optionally strike-through or flag notes whose source `.rtfd` package has been deleted.

## Implementation Status

- Implemented as a standalone utility project under `utils/stickies-to-obsidian/`.
- Current deliverables: `stickies2obsidian.sh`, a launchd plist template, and `install_launch_agent.sh`.
- The installer accepts `--obsidian-file`, `--state-file`, and `--stickies-dir` so launchd can target a real vault path instead of the baked-in demo default.
- Integration coverage lives in `tests/test_stickies2obsidian_cli.py`.
