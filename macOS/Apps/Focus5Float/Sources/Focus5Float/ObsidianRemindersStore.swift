import Foundation
import os

private let obsidianLog = Logger(subsystem: "me.neochro.Focus5Float", category: "obsidian-reminders")

@MainActor
@Observable
final class ObsidianRemindersStore {
    var items: [ObsidianReminder] = []
    var fileExists = false
    var path: String?
    var totalOpen = 0
    var isLoaded = false
    var loadError: String?
    var missingReason: String?
    var missingMessage: String?
    var completingLineIndexes: Set<Int> = []

    private let client: Focus5Client
    static let maxItems = 8

    init(client: Focus5Client = Focus5Client()) {
        self.client = client
    }

    func refresh() async {
        do {
            let response = try await client.fetchGoals()
            apply(response)
            loadError = nil
            obsidianLog.info("obsidian reminders refreshed: \(self.items.count) of \(self.totalOpen)")
        } catch {
            isLoaded = true
            loadError = error.localizedDescription
            obsidianLog.error("obsidian reminders refresh failed: \(String(describing: error), privacy: .public)")
        }
    }

    func complete(_ reminder: ObsidianReminder) async {
        let lineIndex = reminder.lineIndex
        guard !completingLineIndexes.contains(lineIndex) else { return }

        let response: Focus5GoalCompleteResponse
        do {
            response = try await client.completeGoal(title: reminder.title, lineIndex: lineIndex)
            obsidianLog.info("obsidian reminder completed: \(lineIndex)")
        } catch {
            loadError = error.localizedDescription
            obsidianLog.error("obsidian reminder complete failed: \(String(describing: error), privacy: .public)")
            return
        }

        completingLineIndexes.insert(lineIndex)
        try? await Task.sleep(nanoseconds: 1_200_000_000)
        completingLineIndexes.remove(lineIndex)
        apply(response)
        loadError = nil
    }

    private func apply(_ response: Focus5GoalsResponse) {
        fileExists = response.exists
        path = response.path
        totalOpen = response.totalOpen
        missingReason = response.reason
        missingMessage = response.message
        items = Array(response.items.prefix(Self.maxItems))
        isLoaded = true
    }

    private func apply(_ response: Focus5GoalCompleteResponse) {
        fileExists = response.exists
        path = response.path
        totalOpen = response.totalOpen
        missingReason = response.reason
        missingMessage = response.message
        items = Array(response.items.prefix(Self.maxItems))
        isLoaded = true
    }

    var emptyStateMessage: String {
        switch missingReason {
        case "vault_not_configured":
            return "Obsidian vault path isn't configured, so 0. Goals.md can't be read."
        case "file_missing":
            if let path, !path.isEmpty {
                return "No 0. Goals.md found at \(path)."
            }
            return "No 0. Goals.md found in the configured vault."
        case "read_failed":
            if let missingMessage, !missingMessage.isEmpty {
                return "Couldn't read 0. Goals.md: \(missingMessage)"
            }
            return "Couldn't read 0. Goals.md from the configured vault."
        default:
            return "To show tasks here, add a 0. Goals.md file at the root of your Obsidian vault."
        }
    }
}
