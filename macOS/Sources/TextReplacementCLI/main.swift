import ArgumentParser
import Foundation
import TextReplacementCore

@main
struct TRStudioCLI: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "trstudio",
        abstract: "Manage macOS text replacements with a better workflow.",
        version: TextReplacementCore.version,
        subcommands: [
            List.self,
            Add.self,
            Import.self,
            Export.self,
            Apply.self,
            Lint.self,
            Backup.self
        ],
        defaultSubcommand: List.self
    )
}

struct List: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "list",
        abstract: "List local text replacements."
    )

    func run() async throws {
        print("List is not implemented yet. Wire this to ReplacementStore.fetchAll().")
    }
}

struct Add: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "add",
        abstract: "Add a text replacement."
    )

    @Argument(help: "Shortcut, such as ';sig'.")
    var shortcut: String

    @Argument(help: "Expanded phrase.")
    var phrase: String

    func run() async throws {
        let replacement = Replacement(shortcut: shortcut, phrase: phrase)
        print("Prepared replacement: \(replacement.shortcut) -> \(replacement.phrase)")
        print("Add is not implemented yet. Wire this to ReplacementStore.save(_:).")
    }
}

struct Import: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "import",
        abstract: "Import replacements from a supported source."
    )

    @Option(help: "Import source: apple-database, apple-plist, csv, or json.")
    var source: String = ReplacementImportSource.appleDatabase.rawValue

    @Option(help: "Input path. For apple-database this overrides the live DB path; otherwise a file.")
    var input: String?

    @Option(help: "Write the imported replacements as canonical keyboard-replacements.v1 JSON here.")
    var output: String?

    func run() async throws {
        guard let src = ReplacementImportSource(rawValue: source) else {
            throw ValidationError("Unknown source '\(source)'. Try apple-database.")
        }
        guard src == .appleDatabase else {
            print("Import for source '\(source)' is not wired to the Python bridge yet (apple-database is).")
            return
        }

        let dbURL = input.map { URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath) }
        let bridge = try PythonBridge(databasePath: dbURL)
        let importer = AppleDatabaseImporter(bridge: bridge)
        let result = try await importer.importReplacements(request: ReplacementImportRequest(source: .appleDatabase))

        print("Imported \(result.imported.count) replacements from the live macOS DB.")
        if !result.validationIssues.isEmpty {
            print("Validation issues: \(result.validationIssues.count)")
        }
        if let output {
            try CanonicalReplacementCodec().encode(result.imported)
                .write(to: URL(fileURLWithPath: (output as NSString).expandingTildeInPath))
            print("Wrote canonical JSON to \(output)")
        }
    }
}

struct Export: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "export",
        abstract: "Export replacements to a supported format."
    )

    @Option(help: "Export format: apple-plist, csv, json, or markdown.")
    var format: String = ReplacementExportFormat.applePlist.rawValue

    @Option(help: "Output file path.")
    var output: String?

    @Flag(help: "Include disabled entries in export.")
    var includeDisabled = false

    func run() async throws {
        print("Export is not implemented yet. Format: \(format), output: \(output ?? "<stdout>"), includeDisabled: \(includeDisabled)")
    }
}

struct Apply: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "apply",
        abstract: "Plan or write replacements to the live macOS Text Replacements DB (via json_to_apple_sqlite.py)."
    )

    @Option(help: "Canonical v1 JSON to apply. If omitted, the current live DB is read and round-tripped.")
    var input: String?

    @Option(help: "Strategy: merge (add/update) or replace (also remove missing).")
    var strategy: String = AppleDatabaseWriter.Strategy.merge.rawValue

    @Option(help: "Override the target DB path.")
    var db: String?

    @Flag(help: "Actually write the live DB. Without this, only the plan is printed (dry-run).")
    var write = false

    @Flag(help: "Include disabled entries.")
    var includeDisabled = false

    func run() async throws {
        guard let strat = AppleDatabaseWriter.Strategy(rawValue: strategy) else {
            throw ValidationError("strategy must be 'merge' or 'replace'")
        }
        let dbURL = db.map { URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath) }
        let bridge = try PythonBridge(databasePath: dbURL)

        let replacements: [Replacement]
        if let input {
            let data = try Data(contentsOf: URL(fileURLWithPath: (input as NSString).expandingTildeInPath))
            replacements = try CanonicalReplacementCodec().decode(data)
        } else {
            let importer = AppleDatabaseImporter(bridge: bridge)
            replacements = try await importer.importReplacements(request: ReplacementImportRequest(source: .appleDatabase)).imported
        }

        let writer = AppleDatabaseWriter(bridge: bridge)
        let outcome = write
            ? try writer.apply(replacements, strategy: strat, includeDisabled: includeDisabled)
            : try writer.plan(replacements, strategy: strat, includeDisabled: includeDisabled)

        print(outcome.applied
            ? "Applied to macOS (strategy=\(strat.rawValue)):"
            : "Dry-run plan (strategy=\(strat.rawValue), nothing written):")
        print(outcome.output)
        if !outcome.stderr.isEmpty {
            FileHandle.standardError.write(Data(outcome.stderr.utf8))
        }
    }
}

struct Lint: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "lint",
        abstract: "Validate replacements for duplicates and common issues."
    )

    func run() async throws {
        print("Lint is not implemented yet. Wire this to DefaultReplacementLinter.")
    }
}

struct Backup: AsyncParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "backup",
        abstract: "Create a snapshot backup of the local replacement database."
    )

    @Option(help: "Backup label.")
    var label: String = "Manual backup"

    func run() async throws {
        print("Backup is not implemented yet. Label: \(label)")
    }
}
