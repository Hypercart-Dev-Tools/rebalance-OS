import Foundation
import Observation
import SwiftUI
import TextReplacementCore

/// App state + the actions that bridge to the hardened Python scripts. The blocking subprocess
/// work runs off the main actor (Task.detached) so the UI stays responsive; results are applied
/// back on the main actor.
@MainActor
@Observable
final class StudioModel {
    var replacements: [Replacement] = []
    /// Snapshot of the live macOS DB taken at the last import/apply. Edits are diffed against
    /// this for the Preview Plan sheet and the "recently changed" filter.
    var importedBaseline: [Replacement] = []
    var statusText: String = "Import your replacements from macOS to begin."
    var isBusy = false
    /// Set after a successful Apply; shown in the sidebar footer.
    var lastAppliedAt: Date?
    /// Transient feedback shown as a bottom overlay capsule.
    var toast: ToastMessage?
    /// Push strategy — Merge (add/update) or Replace (add/update/remove).
    var strategy: AppleDatabaseWriter.Strategy = .merge

    // MARK: - macOS bridge

    func importFromMacOS() async {
        isBusy = true
        statusText = "Importing from the live macOS database…"
        do {
            let imported = try await Task.detached(priority: .userInitiated) {
                try await AppleDatabaseImporter().importReplacements(
                    request: ReplacementImportRequest(source: .appleDatabase)
                ).imported
            }.value
            replacements = imported
            importedBaseline = imported
            statusText = "Imported \(imported.count) replacements from the live macOS database."
            showToast(.init(text: "Imported \(imported.count) replacements", style: .success))
        } catch {
            statusText = "Import failed: \(error.localizedDescription)"
            showToast(.init(text: "Import failed", style: .error, action: .retryImport))
        }
        isBusy = false
    }

    func pushToMacOS(strategy: AppleDatabaseWriter.Strategy, write: Bool) async {
        guard !replacements.isEmpty else {
            statusText = "Nothing to push — import first."
            return
        }
        isBusy = true
        statusText = write ? "Applying to the live macOS database…" : "Computing dry-run plan…"
        let items = replacements
        do {
            let outcome = try await Task.detached(priority: .userInitiated) {
                let writer = try AppleDatabaseWriter()
                return write
                    ? try writer.apply(items, strategy: strategy)
                    : try writer.plan(items, strategy: strategy)
            }.value
            let header = outcome.applied
                ? "Applied to macOS (strategy=\(strategy.rawValue)). Quit/reopen System Settings & affected apps to see changes."
                : "Dry-run plan (strategy=\(strategy.rawValue)) — nothing written:"
            statusText = header + "\n" + outcome.output
            if write {
                lastAppliedAt = Date()
                importedBaseline = items          // edits are now the on-disk truth
                showToast(.init(text: "Applied to macOS — quit & reopen apps to see changes",
                                style: .success))
            }
        } catch {
            statusText = (write ? "Apply failed: " : "Plan failed: ") + error.localizedDescription
            if write { showToast(.init(text: "Apply failed", style: .error, action: .retryApply)) }
        }
        isBusy = false
    }

    // MARK: - Editing

    func index(of id: Replacement.ID?) -> Int? {
        guard let id else { return nil }
        return replacements.firstIndex { $0.id == id }
    }

    func toggleEnabled(_ id: Replacement.ID) {
        guard let i = index(of: id) else { return }
        replacements[i].enabled.toggle()
        replacements[i].updatedAt = Date()
    }

    /// Create a blank replacement at the top of the library and return its id so the
    /// caller can select it and drop the cursor into the shortcut field.
    @discardableResult
    func addReplacement(groupName: String? = nil) -> Replacement.ID {
        let new = Replacement(shortcut: "", phrase: "", enabled: true, groupName: groupName)
        replacements.insert(new, at: 0)
        return new.id
    }

    /// Validation issues (empty/whitespace/duplicate) for one row — reuses the core
    /// `DefaultReplacementLinter` so the editor's inline hints match what Apply enforces.
    func issues(for id: Replacement.ID?) -> [ReplacementValidationIssue] {
        guard let id else { return [] }
        return DefaultReplacementLinter().validate(replacements).filter { $0.replacementID == id }
    }

    private func showToast(_ toast: ToastMessage) {
        withAnimation(Theme.spring) { self.toast = toast }
    }

    // MARK: - Derived collections

    /// Distinct groups present in the library, with counts, sorted by size then name.
    var groups: [GroupSummary] {
        var counts: [String: Int] = [:]
        for r in replacements {
            guard let g = r.groupName, !g.isEmpty else { continue }
            counts[g, default: 0] += 1
        }
        return counts
            .map { GroupSummary(name: $0.key, count: $0.value) }
            .sorted { $0.count == $1.count ? $0.name < $1.name : $0.count > $1.count }
    }

    func count(for filter: ReplacementFilter) -> Int { filtered(filter, search: "").count }

    /// Rows for the middle list: the active filter narrowed by the search query.
    func filtered(_ filter: ReplacementFilter, search: String) -> [Replacement] {
        let base: [Replacement]
        switch filter {
        case .all:
            base = replacements
        case .disabled:
            base = replacements.filter { !$0.enabled }
        case .ungrouped:
            base = replacements.filter { ($0.groupName ?? "").isEmpty }
        case .recentlyChanged:
            base = replacements.filter { changedSinceImport($0) }
        case .duplicates:
            let dupes = duplicateShortcuts
            base = replacements.filter { dupes.contains($0.normalizedShortcut.lowercased()) }
        case .group(let name):
            base = replacements.filter { $0.groupName == name }
        }
        guard !search.isEmpty else { return base }
        return base.filter {
            $0.shortcut.localizedCaseInsensitiveContains(search)
                || $0.phrase.localizedCaseInsensitiveContains(search)
        }
    }

    private var duplicateShortcuts: Set<String> {
        var seen: [String: Int] = [:]
        for r in replacements {
            seen[r.normalizedShortcut.lowercased(), default: 0] += 1
        }
        return Set(seen.filter { $0.value > 1 }.keys)
    }

    private func changedSinceImport(_ r: Replacement) -> Bool {
        guard let original = importedBaseline.first(where: { $0.id == r.id }) else { return true }
        return !original.contentEquals(r)
    }

    // MARK: - Preview diff (current edits vs. the imported baseline)

    func planDiff(strategy: AppleDatabaseWriter.Strategy) -> PlanDiff {
        let baselineByID = Dictionary(uniqueKeysWithValues: importedBaseline.map { ($0.id, $0) })
        let currentIDs = Set(replacements.map(\.id))

        var adds: [Replacement] = []
        var updates: [ReplacementUpdate] = []
        var unchanged = 0
        for r in replacements {
            if let original = baselineByID[r.id] {
                if original.contentEquals(r) { unchanged += 1 }
                else { updates.append(.init(before: original, after: r)) }
            } else {
                adds.append(r)
            }
        }
        // Removes only take effect under the Replace strategy.
        let removes = strategy == .replace
            ? importedBaseline.filter { !currentIDs.contains($0.id) }
            : []
        return PlanDiff(adds: adds, updates: updates, removes: removes, unchanged: unchanged)
    }
}

// MARK: - Supporting value types

struct GroupSummary: Identifiable, Hashable {
    var name: String
    var count: Int
    var id: String { name }
    var color: Color { Theme.groupColor(name) }
}

struct ToastMessage: Identifiable, Equatable {
    enum Style { case success, error, info }
    enum Action: Equatable { case retryApply, retryImport }
    let id = UUID()
    var text: String
    var style: Style
    var action: Action?

    init(text: String, style: Style, action: Action? = nil) {
        self.text = text
        self.style = style
        self.action = action
    }
}

struct ReplacementUpdate: Identifiable {
    var before: Replacement
    var after: Replacement
    var id: UUID { after.id }
}

struct PlanDiff {
    var adds: [Replacement]
    var updates: [ReplacementUpdate]
    var removes: [Replacement]
    var unchanged: Int
    var total: Int { adds.count + updates.count + removes.count }
    var isEmpty: Bool { total == 0 }
}

extension Replacement {
    /// Equality on user-meaningful fields, ignoring `createdAt` / `updatedAt`.
    func contentEquals(_ other: Replacement) -> Bool {
        shortcut == other.shortcut
            && phrase == other.phrase
            && enabled == other.enabled
            && (groupName ?? "") == (other.groupName ?? "")
            && (notes ?? "") == (other.notes ?? "")
    }
}
