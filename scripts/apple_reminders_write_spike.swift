import EventKit
import Foundation

struct ExtractedReminder: Decodable {
    let reminder_id: String
    let title: String
    let list_name: String?
    let notes: String?
    let is_completed: Bool
    let created_at: String?
    let updated_at: String?
}

struct ExtractorPayload: Decodable {
    let matches: [ExtractedReminder]
    let extract: [String: AnyDecodable]
}

struct SpikeReport: Encodable {
    struct Probe: Encodable {
        let phase: String
        let success: Bool
        let detail: String
    }

    let started_at: String
    let finished_at: String
    let host_runtime: String
    let authorization_status_before: String
    let authorization_status_after: String
    let calendar_title: String
    let eventkit_calendar_item_identifier: String?
    let eventkit_external_identifier: String?
    let extractor_reminder_id: String?
    let extractor_matches_eventkit_identifier: Bool
    let extractor_matches_external_identifier: Bool
    let probes: [Probe]
}

struct AnyDecodable: Decodable {}

enum SpikeError: Error, CustomStringConvertible {
    case permissionDenied(String)
    case missingCalendar
    case extractorFailure(String)
    case timeout(String)
    case cleanupFailure(String)

    var description: String {
        switch self {
        case .permissionDenied(let message):
            return message
        case .missingCalendar:
            return "No default Reminders calendar is available for new reminders."
        case .extractorFailure(let message):
            return "Extractor call failed: \(message)"
        case .timeout(let message):
            return message
        case .cleanupFailure(let message):
            return message
        }
    }
}

func isoNow() -> String {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return formatter.string(from: Date())
}

func repoRoot() throws -> URL {
    let cwd = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).standardizedFileURL
    if FileManager.default.fileExists(atPath: cwd.appendingPathComponent("pyproject.toml").path),
       FileManager.default.fileExists(atPath: cwd.appendingPathComponent("src/rebalance").path) {
        return cwd
    }
    let scriptURL = URL(fileURLWithPath: CommandLine.arguments[0]).standardizedFileURL
    return scriptURL.deletingLastPathComponent().deletingLastPathComponent()
}

func pythonPath(repoRoot: URL) -> String {
    let venv = repoRoot.appendingPathComponent(".venv/bin/python").path
    if FileManager.default.isExecutableFile(atPath: venv) {
        return venv
    }
    return "/usr/bin/python3"
}

func statusName(_ status: EKAuthorizationStatus) -> String {
    switch status {
    case .notDetermined: return "not_determined"
    case .restricted: return "restricted"
    case .denied: return "denied"
    case .authorized: return "authorized"
    case .fullAccess: return "full_access"
    case .writeOnly: return "write_only"
    @unknown default: return "unknown"
    }
}

func requestRemindersAccess(store: EKEventStore) throws -> Bool {
    let semaphore = DispatchSemaphore(value: 0)
    var granted = false
    var capturedError: Error?

    if #available(macOS 14.0, *) {
        store.requestFullAccessToReminders { ok, error in
            granted = ok
            capturedError = error
            semaphore.signal()
        }
    } else {
        store.requestAccess(to: .reminder) { ok, error in
            granted = ok
            capturedError = error
            semaphore.signal()
        }
    }

    semaphore.wait()
    if let error = capturedError {
        throw error
    }
    return granted
}

func runExtractor(prefix: String, snapshotDir: URL, repoRoot: URL) throws -> ExtractorPayload {
    let process = Process()
    process.currentDirectoryURL = repoRoot
    process.executableURL = URL(fileURLWithPath: pythonPath(repoRoot: repoRoot))
    process.environment = [
        "PYTHONPATH": repoRoot.appendingPathComponent("src").path
    ]

    let python = """
import json, sys
from pathlib import Path
from rebalance.ingest.apple_reminders import extract_apple_reminders

prefix = sys.argv[1]
snapshot_dir = Path(sys.argv[2])
result, reminders = extract_apple_reminders(snapshot_dir=snapshot_dir)
matches = []
for r in reminders:
    if prefix not in (r.title or ""):
        continue
    matches.append({
        "reminder_id": r.reminder_id,
        "title": r.title,
        "list_name": r.list_name,
        "notes": r.notes,
        "is_completed": r.is_completed,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    })
print(json.dumps({"matches": matches, "extract": result.as_dict()}))
"""
    process.arguments = ["-c", python, prefix, snapshotDir.path]

    let stdout = Pipe()
    let stderr = Pipe()
    process.standardOutput = stdout
    process.standardError = stderr
    try process.run()
    process.waitUntilExit()

    let outData = stdout.fileHandleForReading.readDataToEndOfFile()
    let errData = stderr.fileHandleForReading.readDataToEndOfFile()
    let out = String(decoding: outData, as: UTF8.self)
    let err = String(decoding: errData, as: UTF8.self)
    guard process.terminationStatus == 0 else {
        throw SpikeError.extractorFailure(err.isEmpty ? out : err)
    }
    do {
        return try JSONDecoder().decode(ExtractorPayload.self, from: outData)
    } catch {
        throw SpikeError.extractorFailure("decode failed: \(error)\nstdout:\n\(out)\nstderr:\n\(err)")
    }
}

func waitForMatch(
    prefix: String,
    snapshotDir: URL,
    repoRoot: URL,
    timeoutSeconds: TimeInterval,
    predicate: (ExtractedReminder?) -> Bool
) throws -> ExtractedReminder? {
    let deadline = Date().addingTimeInterval(timeoutSeconds)
    var lastSeen: ExtractedReminder?
    while Date() < deadline {
        let payload = try runExtractor(prefix: prefix, snapshotDir: snapshotDir, repoRoot: repoRoot)
        lastSeen = payload.matches.first
        if predicate(lastSeen) {
            return lastSeen
        }
        usleep(500_000)
    }
    return lastSeen
}

func saveReport(_ report: SpikeReport, to path: URL) throws {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    let data = try encoder.encode(report)
    try FileManager.default.createDirectory(
        at: path.deletingLastPathComponent(),
        withIntermediateDirectories: true,
        attributes: nil
    )
    try data.write(to: path)
}

let startedAt = isoNow()
let store = EKEventStore()
let statusBefore = statusName(EKEventStore.authorizationStatus(for: .reminder))
var probes: [SpikeReport.Probe] = []
var createdIdentifier: String?
var createdExternalIdentifier: String?
var extractorReminderID: String?
var calendarTitle = ""
var resolvedRoot: URL?

do {
    let root = try repoRoot()
    resolvedRoot = root
    let snapshotDir = root.appendingPathComponent("temp/apple-reminders/phase5-write-spike-snapshot", isDirectory: true)
    let reportPath = root.appendingPathComponent("temp/apple-reminders/PHASE5-WRITE-SPIKE.json")
    let prefix = "RBOS-WRITE-SPIKE-\(Int(Date().timeIntervalSince1970))"
    let reminderTitle = "\(prefix) create"
    let updatedTitle = "\(prefix) updated"

    let granted = try requestRemindersAccess(store: store)
    let statusAfterRequest = statusName(EKEventStore.authorizationStatus(for: .reminder))
    guard granted else {
        throw SpikeError.permissionDenied(
            "Reminders permission was not granted for this host runtime. Current status: \(statusAfterRequest)."
        )
    }

    guard let calendar = store.defaultCalendarForNewReminders() else {
        throw SpikeError.missingCalendar
    }
    calendarTitle = calendar.title

    let reminder = EKReminder(eventStore: store)
    reminder.calendar = calendar
    reminder.title = reminderTitle
    reminder.notes = "Created by rebalance-OS Apple Reminders write spike at \(startedAt)"

    try store.save(reminder, commit: true)
    createdIdentifier = reminder.calendarItemIdentifier
    createdExternalIdentifier = reminder.calendarItemExternalIdentifier
    probes.append(.init(
        phase: "create_eventkit",
        success: true,
        detail: "Created reminder in list '\(calendar.title)' with calendarItemIdentifier=\(createdIdentifier ?? "nil") externalIdentifier=\(createdExternalIdentifier ?? "nil")"
    ))

    let createdExtracted = try waitForMatch(
        prefix: prefix,
        snapshotDir: snapshotDir,
        repoRoot: root,
        timeoutSeconds: 12
    ) { match in
        guard let match else { return false }
        return match.title == reminderTitle && match.is_completed == false
    }
    guard let createdExtracted else {
        throw SpikeError.timeout("Created reminder never appeared in the read-only extractor within 12 seconds.")
    }
    extractorReminderID = createdExtracted.reminder_id
    probes.append(.init(
        phase: "create_extractor_visibility",
        success: true,
        detail: "Extractor saw created reminder with reminder_id=\(createdExtracted.reminder_id) list=\(createdExtracted.list_name ?? "nil")"
    ))

    guard let saved = createdIdentifier.flatMap({ store.calendarItem(withIdentifier: $0) as? EKReminder }) else {
        throw SpikeError.timeout("EventKit could not refetch the created reminder by calendarItemIdentifier.")
    }
    saved.title = updatedTitle
    saved.notes = "Updated by rebalance-OS Apple Reminders write spike at \(isoNow())"
    saved.completionDate = Date()
    try store.save(saved, commit: true)
    probes.append(.init(
        phase: "update_eventkit",
        success: true,
        detail: "Updated title + notes and marked completed via EventKit."
    ))

    guard try waitForMatch(
        prefix: prefix,
        snapshotDir: snapshotDir,
        repoRoot: root,
        timeoutSeconds: 12,
        predicate: { match in
            guard let match else { return false }
            return match.title == updatedTitle && match.is_completed == true
        }
    ) != nil else {
        throw SpikeError.timeout("Updated reminder never converged in the read-only extractor within 12 seconds.")
    }
    probes.append(.init(
        phase: "update_extractor_visibility",
        success: true,
        detail: "Extractor reflected updated title and completed state."
    ))

    try store.remove(saved, commit: true)
    probes.append(.init(
        phase: "delete_eventkit",
        success: true,
        detail: "Deleted reminder via EventKit."
    ))

    let deletedExtracted = try waitForMatch(
        prefix: prefix,
        snapshotDir: snapshotDir,
        repoRoot: root,
        timeoutSeconds: 12
    ) { match in
        return match == nil
    }
    if deletedExtracted != nil {
        throw SpikeError.timeout("Deleted reminder was still visible to the read-only extractor after 12 seconds.")
    }
    probes.append(.init(
        phase: "delete_extractor_visibility",
        success: true,
        detail: "Extractor no longer returned the deleted reminder."
    ))

    let statusAfter = statusName(EKEventStore.authorizationStatus(for: .reminder))
    let report = SpikeReport(
        started_at: startedAt,
        finished_at: isoNow(),
        host_runtime: ProcessInfo.processInfo.processName,
        authorization_status_before: statusBefore,
        authorization_status_after: statusAfter,
        calendar_title: calendarTitle,
        eventkit_calendar_item_identifier: createdIdentifier,
        eventkit_external_identifier: createdExternalIdentifier,
        extractor_reminder_id: extractorReminderID,
        extractor_matches_eventkit_identifier: extractorReminderID == createdIdentifier,
        extractor_matches_external_identifier: extractorReminderID == createdExternalIdentifier,
        probes: probes
    )
    try saveReport(report, to: reportPath)
    print("apple reminders write spike OK")
    print("report: \(reportPath.path)")
    print("extractor reminder_id: \(extractorReminderID ?? "nil")")
    print("eventkit calendarItemIdentifier: \(createdIdentifier ?? "nil")")
    print("eventkit externalIdentifier: \(createdExternalIdentifier ?? "nil")")
    print("calendar: \(calendarTitle)")
    exit(0)
} catch {
    probes.append(.init(
        phase: "failure",
        success: false,
        detail: String(describing: error)
    ))
    if let createdIdentifier {
        do {
            if let leftover = store.calendarItem(withIdentifier: createdIdentifier) as? EKReminder {
                try store.remove(leftover, commit: true)
                probes.append(.init(
                    phase: "cleanup_after_failure",
                    success: true,
                    detail: "Removed leftover spike reminder after failure."
                ))
            }
        } catch {
            probes.append(.init(
                phase: "cleanup_after_failure",
                success: false,
                detail: "Cleanup failed: \(error)"
            ))
        }
    }
    if let root = resolvedRoot {
        let reportPath = root.appendingPathComponent("temp/apple-reminders/PHASE5-WRITE-SPIKE.json")
        let report = SpikeReport(
            started_at: startedAt,
            finished_at: isoNow(),
            host_runtime: ProcessInfo.processInfo.processName,
            authorization_status_before: statusBefore,
            authorization_status_after: statusName(EKEventStore.authorizationStatus(for: .reminder)),
            calendar_title: calendarTitle,
            eventkit_calendar_item_identifier: createdIdentifier,
            eventkit_external_identifier: createdExternalIdentifier,
            extractor_reminder_id: extractorReminderID,
            extractor_matches_eventkit_identifier: extractorReminderID == createdIdentifier && extractorReminderID != nil,
            extractor_matches_external_identifier: extractorReminderID == createdExternalIdentifier && extractorReminderID != nil,
            probes: probes
        )
        try? saveReport(report, to: reportPath)
    }
    fputs("apple reminders write spike FAILED: \(error)\n", stderr)
    exit(1)
}
