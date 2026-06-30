import Foundation
import EventKit
import os

// Apple Reminders, read + write, DIRECTLY via EventKit — not through `rebalance
// serve`. Focus 5 Float is a signed, LaunchServices-launched app bundle with a
// stable bundle id, which is exactly the runtime the Apple Reminders plan
// (Phase 5.0) proved can hold the Reminders TCC grant; the Python/server path
// can't write (suppressed under the agent tree) and reads stale by design. We
// need only the Reminders (EventKit) grant — NOT Full Disk Access — because the
// read-back here goes through EventKit, not the SQLite extractor.
//
// Scope v1: show the 8 most-recent ACTIVE tasks from the default list; the only
// mutation is `complete` (least destructive). create/edit/delete stay with the
// `rebalance apple-reminders` CLI (human-in-the-loop).

private let log = Logger(subsystem: "me.neochro.Focus5Float", category: "reminders")

@MainActor
@Observable
final class RemindersStore {
    /// Coarse authorization state the UI branches on. Collapses EventKit's many
    /// raw statuses into the three the bottom panel actually renders.
    enum Access { case notDetermined, denied, granted }

    var access: Access = .notDetermined
    var items: [EKReminder] = []        // ≤8, newest-first, active only
    var listName: String?               // default list title, for the header
    var loadError: String?              // last read/write failure (nil when none)
    /// Reminders saved as complete but still shown (filled) for a brief beat
    /// before they drop off — mirrors Apple Reminders' check-then-fade.
    var completingIDs: Set<String> = []

    private let store = EKEventStore()
    static let maxItems = 8

    init() { syncAuthorization() }

    /// Map EventKit's raw status onto our 3-state enum. Read needs full access;
    /// `.writeOnly` can't list reminders, so it counts as "needs access".
    func syncAuthorization() {
        switch EKEventStore.authorizationStatus(for: .reminder) {
        case .notDetermined:
            access = .notDetermined
        case .fullAccess, .authorized:
            access = .granted
        case .denied, .restricted, .writeOnly:
            access = .denied
        @unknown default:
            access = .notDetermined
        }
    }

    /// Present the system TCC prompt. Must be reached from a LaunchServices-
    /// launched bundle (an installed `.app`), not `swift run` under a terminal/
    /// agent tree — there the prompt is suppressed (see Phase 5.0 findings).
    func requestAccess() async {
        do {
            let granted = try await store.requestFullAccessToReminders()
            access = granted ? .granted : .denied
            log.info("reminders access request → \(granted ? "granted" : "denied")")
            if granted { await refresh() }
        } catch {
            access = .denied
            loadError = error.localizedDescription
            log.error("reminders access request failed: \(error.localizedDescription)")
        }
    }

    /// Re-read the ≤8 most-recent active reminders from the default list.
    /// No-op (keeps the UI in its access-prompt state) until access is granted.
    func refresh() async {
        syncAuthorization()
        guard access == .granted else { return }
        guard let calendar = store.defaultCalendarForNewReminders() else {
            items = []; listName = nil
            return
        }
        listName = calendar.title

        let predicate = store.predicateForIncompleteReminders(
            withDueDateStarting: nil, ending: nil, calendars: [calendar])
        let fetched: [EKReminder] = await withCheckedContinuation { cont in
            store.fetchReminders(matching: predicate) { reminders in
                cont.resume(returning: reminders ?? [])
            }
        }

        // "Most recent" = newest creationDate first; nils sort oldest. Keep any
        // row mid-fade (in `completingIDs`) on screen even though EventKit no
        // longer returns it as incomplete, so the check-then-fade beat survives a
        // poll/refresh landing inside the 2s window.
        let sorted = fetched.sorted {
            ($0.creationDate ?? .distantPast) > ($1.creationDate ?? .distantPast)
        }
        var next = Array(sorted.prefix(Self.maxItems))
        if !completingIDs.isEmpty {
            let shown = Set(next.map(\.calendarItemIdentifier))
            let held = items.filter {
                completingIDs.contains($0.calendarItemIdentifier)
                    && !shown.contains($0.calendarItemIdentifier)
            }
            next = held + next
        }
        items = next
        loadError = nil
        log.info("reminders refreshed: \(self.items.count) of list \"\(calendar.title)\"")
    }

    /// Mark one reminder done via EventKit, then hold it on screen (filled) for
    /// ~2s before re-reading so it fades like Apple Reminders. On failure, revert
    /// and surface the error — never claim a success the store disagrees with.
    func complete(_ reminder: EKReminder) async {
        let id = reminder.calendarItemIdentifier
        guard !completingIDs.contains(id) else { return }   // ignore double-taps
        reminder.isCompleted = true
        do {
            try store.save(reminder, commit: true)
            log.info("reminder completed: \(id)")
        } catch {
            reminder.isCompleted = false
            loadError = "Couldn't complete: \(error.localizedDescription)"
            log.error("reminder complete failed: \(error.localizedDescription)")
            return
        }
        completingIDs.insert(id)                       // show it filled, keep it visible
        try? await Task.sleep(nanoseconds: 2_000_000_000)
        completingIDs.remove(id)
        await refresh()                                // now let it drop off
    }
}
