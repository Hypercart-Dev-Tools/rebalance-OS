# macOS Text Replacement Studio: Build Notes and Implementation Sketch

## Bottom line

Build this as a native SwiftUI macOS app that manages a local source of truth for text replacements, then imports and exports Apple-compatible plist files. Apple documents plist-based export and import through System Settings, and also notes that iCloud can sync text replacements across Apple devices when iCloud Drive is enabled and the same Apple Account is used: https://support.apple.com/guide/mac-help/back-up-and-share-text-replacements-on-mac-mchl2a7bd795/mac

Avoid direct writes to Apple private storage in the first version. A developer forum thread identifies the current local database as `~/Library/KeyboardServices/TextReplacements.db` and shows `sqlite3` queries against `ZTEXTREPLACEMENTENTRY`, but that is forum-derived storage knowledge rather than a stable public API: https://developer.apple.com/forums/thread/765688

## Product concept

Working name: **Text Replacement Studio**.

The goal is not to replace the underlying Apple text expansion behavior. The goal is to replace Apple's terrible management UI with something built for power users:

- Fast search across shortcut and phrase.
- Bulk edit operations.
- Duplicate detection.
- Grouping, tagging, and notes.
- Safe imports and exports.
- Diff previews before changes.
- Git-friendly backups.
- Optional read-only import from Apple's current local database.

## Safe integration model

### Primary source of truth

Use your own local database as the canonical data store. The Apple system list should be treated as an import/export target.

Benefits:

- You control schema migrations.
- You can support disabled entries even though Apple plist import does not.
- You can support groups, notes, tags, history, and lint state.
- You can keep predictable backups.
- You avoid depending on private Apple DB schema behavior.

### Apple-compatible export

Generate a plist containing an array of dictionaries:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<array>
  <dict>
    <key>phrase</key>
    <string>On my way!</string>
    <key>shortcut</key>
    <string>omw</string>
  </dict>
</array>
</plist>
```

Apple's import flow is manual: open System Settings, go to Keyboard, open Text Replacements, then drag the plist file into the Text Replacements window: https://support.apple.com/guide/mac-help/back-up-and-share-text-replacements-on-mac-mchl2a7bd795/mac

### Read-only Apple import

Offer an "Import from Apple Text Replacements" command that reads the current Apple database and merges it into your app's local database.

Known current path:

```bash
~/Library/KeyboardServices/TextReplacements.db
```

Known current query:

```sql
SELECT ZSHORTCUT, ZPHRASE
FROM ZTEXTREPLACEMENTENTRY;
```

This path and query come from Apple Developer Forums discussion, not official API documentation: https://developer.apple.com/forums/thread/765688

## MVP feature set

### Core UI

- Sidebar filters:
  - All
  - Recently changed
  - Duplicates
  - Disabled
  - Ungrouped
  - Groups
- Main table:
  - Enabled
  - Shortcut
  - Phrase
  - Group
  - Updated
  - Status
- Detail editor:
  - Shortcut field
  - Phrase editor with multiline support
  - Group picker
  - Notes
  - Validation warnings
- Toolbar:
  - Add
  - Import
  - Export
  - Lint
  - Backup
  - Search

### Importers

- Apple plist import.
- CSV import.
- JSON import.
- Read-only Apple DB import.

### Exporters

- Apple plist export.
- CSV export.
- JSON export.
- Markdown report export.

### Safety features

- Snapshot before every import.
- Snapshot before every destructive bulk operation.
- Preview diff before merge.
- Duplicate shortcut detection.
- Invalid plist validation.
- Empty phrase and empty shortcut warnings.
- Whitespace normalization warnings.

## Local database schema

Use SQLite. If you want a very native Swift path, use GRDB or SQLite.swift. If you want direct control and no magic, use raw SQLite through a tiny repository layer.

```sql
CREATE TABLE replacements (
  id TEXT PRIMARY KEY,
  shortcut TEXT NOT NULL,
  phrase TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  group_name TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX idx_replacements_shortcut
ON replacements(shortcut);

CREATE TABLE snapshots (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  created_at TEXT NOT NULL,
  replacement_count INTEGER NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE import_runs (
  id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_label TEXT,
  created_at TEXT NOT NULL,
  added_count INTEGER NOT NULL,
  updated_count INTEGER NOT NULL,
  skipped_count INTEGER NOT NULL
);
```

## Swift model sketch

```swift
import Foundation

struct Replacement: Identifiable, Codable, Hashable {
    var id: UUID
    var shortcut: String
    var phrase: String
    var enabled: Bool
    var groupName: String?
    var notes: String?
    var createdAt: Date
    var updatedAt: Date
}

struct ReplacementValidationIssue: Identifiable, Hashable {
    enum Severity: String, Codable {
        case warning
        case error
    }

    var id = UUID()
    var severity: Severity
    var message: String
}
```

## Plist import and export sketch

Use `PropertyListEncoder` and `PropertyListDecoder`, but keep a separate DTO for Apple's plist shape.

```swift
import Foundation

struct AppleTextReplacementItem: Codable, Hashable {
    let phrase: String
    let shortcut: String
}

enum ApplePlistCodec {
    static func decode(_ data: Data) throws -> [AppleTextReplacementItem] {
        try PropertyListDecoder().decode([AppleTextReplacementItem].self, from: data)
    }

    static func encode(_ items: [AppleTextReplacementItem]) throws -> Data {
        let encoder = PropertyListEncoder()
        encoder.outputFormat = .xml
        return try encoder.encode(items)
    }
}

extension Replacement {
    var appleItem: AppleTextReplacementItem {
        AppleTextReplacementItem(phrase: phrase, shortcut: shortcut)
    }
}
```

Important behavior:

- Export only `enabled == true` entries by default.
- Offer an export option to include disabled entries, but warn that Apple does not preserve your disabled state.
- Sort exports by shortcut for stable diffs.
- Escape nothing manually. Let `PropertyListEncoder` handle XML escaping.

## Apple DB read-only import sketch

Use this only as an import source. Do not mutate Apple's database in v1.

```swift
import Foundation
import SQLite3

final class AppleTextReplacementImporter {
    struct ImportedItem: Hashable {
        let shortcut: String
        let phrase: String
    }

    func importItems(from dbURL: URL) throws -> [ImportedItem] {
        var db: OpaquePointer?
        guard sqlite3_open_v2(dbURL.path, &db, SQLITE_OPEN_READONLY, nil) == SQLITE_OK else {
            throw ImportError.openFailed
        }
        defer { sqlite3_close(db) }

        let sql = "SELECT ZSHORTCUT, ZPHRASE FROM ZTEXTREPLACEMENTENTRY;"
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK else {
            throw ImportError.queryFailed
        }
        defer { sqlite3_finalize(statement) }

        var results: [ImportedItem] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            guard
                let shortcutCString = sqlite3_column_text(statement, 0),
                let phraseCString = sqlite3_column_text(statement, 1)
            else {
                continue
            }

            let shortcut = String(cString: shortcutCString)
            let phrase = String(cString: phraseCString)
            results.append(ImportedItem(shortcut: shortcut, phrase: phrase))
        }

        return results
    }

    enum ImportError: Error {
        case openFailed
        case queryFailed
    }
}
```

Sandbox note:

- For App Store sandboxing, you likely need user-granted file access via `NSOpenPanel`.
- For a developer-distributed power-user tool, an unsandboxed app is simpler.

## SwiftUI layout sketch

```swift
import SwiftUI

struct ContentView: View {
    @State private var searchText = ""
    @State private var selectedFilter: ReplacementFilter = .all
    @State private var selectedReplacementID: Replacement.ID?

    var body: some View {
        NavigationSplitView {
            ReplacementSidebar(selectedFilter: $selectedFilter)
        } content: {
            VStack(spacing: 0) {
                SearchBar(text: $searchText)
                ReplacementTable(
                    searchText: searchText,
                    selectedFilter: selectedFilter,
                    selectedReplacementID: $selectedReplacementID
                )
            }
        } detail: {
            ReplacementDetailEditor(replacementID: selectedReplacementID)
        }
        .toolbar {
            Button("Add") {
                // create replacement
            }

            Menu("Import") {
                Button("Apple plist") {}
                Button("CSV") {}
                Button("JSON") {}
                Button("Current Apple Text Replacements") {}
            }

            Menu("Export") {
                Button("Apple plist") {}
                Button("CSV") {}
                Button("JSON") {}
            }
        }
    }
}

enum ReplacementFilter: Hashable {
    case all
    case duplicates
    case disabled
    case recentlyChanged
    case ungrouped
    case group(String)
}
```

## CLI companion sketch

A small CLI makes this useful in dotfiles and automation.

Command ideas:

```bash
trstudio list
trstudio add ';sig' 'Noel Saw'
trstudio import apple-db
trstudio import plist ./Text\ Substitutions.plist
trstudio export plist ./Text\ Substitutions.plist
trstudio export json ./text-replacements.json
trstudio lint
trstudio backup
trstudio diff ./Text\ Substitutions.plist
```

Swift ArgumentParser command structure:

```swift
import ArgumentParser

@main
struct TRStudioCLI: ParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "trstudio",
        abstract: "Manage macOS text replacements with a better workflow.",
        subcommands: [
            List.self,
            Add.self,
            Import.self,
            Export.self,
            Lint.self,
            Backup.self
        ]
    )
}
```

## Suggested package layout

```text
TextReplacementStudio/
  Package.swift
  README.md
  Sources/
    TextReplacementCore/
      Models/
        Replacement.swift
        ReplacementValidationIssue.swift
      Storage/
        ReplacementStore.swift
        SQLiteReplacementStore.swift
        SnapshotStore.swift
      Codecs/
        ApplePlistCodec.swift
        CSVCodec.swift
        JSONCodec.swift
      Importers/
        AppleDBImporter.swift
        MergeEngine.swift
      Validation/
        ReplacementLinter.swift
      Diff/
        ReplacementDiff.swift
    TextReplacementCLI/
      main.swift
  Apps/
    TextReplacementStudio/
      TextReplacementStudioApp.swift
      Views/
        ContentView.swift
        ReplacementSidebar.swift
        ReplacementTable.swift
        ReplacementDetailEditor.swift
        ImportPreviewView.swift
        ExportOptionsView.swift
```

If you want both a GUI app and CLI, keep almost everything in `TextReplacementCore`. The app and CLI should be thin shells around the same store, codecs, linter, and merge engine.

## Merge engine behavior

Import should never blindly overwrite.

Suggested rules:

- Match by `shortcut`.
- If shortcut is new, add it.
- If shortcut exists and phrase is identical, skip it.
- If shortcut exists and phrase differs, show conflict.
- User can choose:
  - Keep local
  - Replace local
  - Duplicate with suffix
  - Apply to all conflicts

Diff model:

```swift
enum ReplacementChange: Hashable {
    case add(Replacement)
    case update(old: Replacement, new: Replacement)
    case skip(existing: Replacement)
    case conflict(local: Replacement, incoming: Replacement)
}
```

## Lint rules

Useful default rules:

- Shortcut is empty.
- Phrase is empty.
- Shortcut contains whitespace.
- Shortcut is longer than phrase.
- Duplicate shortcut.
- Shortcut has leading or trailing whitespace.
- Phrase has accidental trailing whitespace.
- Phrase contains suspicious invisible Unicode.
- Shortcut is too generic, such as `a`, `the`, or `ok`.
- Shortcut does not use preferred prefix convention.

For your own workflow, I would make prefix conventions configurable. Examples:

- `;sig`
- `;addr`
- `;gh`
- `:shrug`
- `,,date`

## Experimental direct-sync mode

Do not include this in v1 unless you explicitly want a hacky power-user mode.

If added, make it opt-in and label it experimental.

Required safeguards:

1. Quit System Settings before writing.
2. Backup Apple's database.
3. Backup app database.
4. Apply SQLite transaction.
5. Re-read the DB and verify.
6. Warn that iCloud sync may overwrite changes.
7. Provide rollback.

Potential problems:

- Apple may change the schema.
- iCloud may re-sync old values.
- System Settings may cache state.
- Text replacement services may need restart or logout.
- App sandboxing complicates filesystem access.

## Build order

### Milestone 1

- Swift package with `TextReplacementCore`.
- `Replacement` model.
- Apple plist import/export.
- JSON import/export.
- Linter.
- Unit tests around plist round-trip behavior.

### Milestone 2

- SQLite local store.
- Snapshot support.
- Merge engine.
- CLI import/export/lint.

### Milestone 3

- SwiftUI app shell.
- Sidebar, table, detail editor.
- Import preview.
- Export flow.

### Milestone 4

- Read-only Apple DB import.
- Conflict UI.
- Bulk operations.
- Preferences.

### Milestone 5

- Menu bar quick-add helper.
- Hotkey support.
- Selected-text capture.
- Optional direct-sync experiment.

## Testing checklist

- Plist export imports successfully through System Settings.
- Multiline phrases survive plist round trip.
- Unicode symbols survive plist round trip.
- Quotes, ampersands, angle brackets, and emoji survive plist round trip.
- Duplicate shortcuts are detected.
- Disabled entries are excluded from default Apple export.
- Import diff does not mutate local data before confirmation.
- Snapshots can restore state.
- Apple DB import failure shows a useful error.

## Strategic recommendation

Ship the safe version first: local database, polished UI, Apple-compatible plist import and export, and read-only Apple DB import. That already solves the main pain without depending on private writes.

After that works, decide whether direct Apple DB sync is worth it. It is probably useful for a personal power tool, but risky for a broadly distributed app.
