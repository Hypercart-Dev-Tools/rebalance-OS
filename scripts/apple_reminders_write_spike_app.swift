import AppKit
import EventKit
import Foundation
import Darwin

struct AppSpikeReport: Encodable {
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

struct AppExtractedReminder: Decodable {
    let reminder_id: String
    let title: String
    let list_name: String?
    let is_completed: Bool
}

struct AppExtractorPayload: Decodable {
    let matches: [AppExtractedReminder]
}

struct AnyDecodable: Decodable {}

enum AppSpikeError: Error, CustomStringConvertible {
    case permissionDenied(String)
    case missingCalendar
    case extractorFailure(String)
    case timeout(String)

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
        }
    }
}

func appIsoNow() -> String {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return formatter.string(from: Date())
}

func appStatusName(_ status: EKAuthorizationStatus) -> String {
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

func appLooksLikeRepoRoot(_ url: URL) -> Bool {
    FileManager.default.fileExists(atPath: url.appendingPathComponent("pyproject.toml").path)
        && FileManager.default.fileExists(atPath: url.appendingPathComponent("src/rebalance").path)
}

func appRepoRoot() -> URL {
    // 1. Explicit env override (only reachable when launched from a shell — NOT under
    //    LaunchServices, which gives the app no cwd/env. Kept for terminal-side testing.)
    let env = ProcessInfo.processInfo.environment
    if let explicit = env["RBOS_REPO_ROOT"], !explicit.isEmpty {
        return URL(fileURLWithPath: explicit).standardizedFileURL
    }
    // 2. Repo root baked into the bundle at build time. This is the canonical path under a
    //    LaunchServices launch (`open`), where cwd is `/` and there is no inherited env.
    //    The build harness injects RBOSRepoRoot into Info.plist as an absolute path.
    if let baked = Bundle.main.object(forInfoDictionaryKey: "RBOSRepoRoot") as? String, !baked.isEmpty {
        let url = URL(fileURLWithPath: baked).standardizedFileURL
        if appLooksLikeRepoRoot(url) {
            return url
        }
    }
    // 3. cwd heuristic (shell launch from inside the repo).
    let cwd = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).standardizedFileURL
    if appLooksLikeRepoRoot(cwd) {
        return cwd
    }
    // 4. Last-resort: walk up from the bundle location looking for a repo root.
    var probe = Bundle.main.bundleURL.standardizedFileURL
    for _ in 0..<8 {
        probe = probe.deletingLastPathComponent()
        if appLooksLikeRepoRoot(probe) {
            return probe
        }
    }
    return Bundle.main.bundleURL
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
}

func appPythonPath(repoRoot: URL) -> String {
    let venv = repoRoot.appendingPathComponent(".venv/bin/python").path
    if FileManager.default.isExecutableFile(atPath: venv) {
        return venv
    }
    return "/usr/bin/python3"
}

func appSaveReport(_ report: AppSpikeReport, to path: URL) {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    if let data = try? encoder.encode(report) {
        try? FileManager.default.createDirectory(
            at: path.deletingLastPathComponent(),
            withIntermediateDirectories: true,
            attributes: nil
        )
        try? data.write(to: path)
    }
}

func appRequestAccess(store: EKEventStore) async throws -> Bool {
    try await withCheckedThrowingContinuation { continuation in
        if #available(macOS 14.0, *) {
            store.requestFullAccessToReminders { granted, error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: granted)
                }
            }
        } else {
            store.requestAccess(to: .reminder) { granted, error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: granted)
                }
            }
        }
    }
}

func appRunExtractor(prefix: String, snapshotDir: URL, repoRoot: URL) throws -> AppExtractorPayload {
    let process = Process()
    process.currentDirectoryURL = repoRoot
    process.executableURL = URL(fileURLWithPath: appPythonPath(repoRoot: repoRoot))
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
        "is_completed": r.is_completed,
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
        throw AppSpikeError.extractorFailure(err.isEmpty ? out : err)
    }
    do {
        return try JSONDecoder().decode(AppExtractorPayload.self, from: outData)
    } catch {
        throw AppSpikeError.extractorFailure("decode failed: \(error)\nstdout:\n\(out)\nstderr:\n\(err)")
    }
}

func appWaitForMatch(
    prefix: String,
    snapshotDir: URL,
    repoRoot: URL,
    timeoutSeconds: TimeInterval,
    predicate: (AppExtractedReminder?) -> Bool
) throws -> AppExtractedReminder? {
    let deadline = Date().addingTimeInterval(timeoutSeconds)
    var lastSeen: AppExtractedReminder?
    while Date() < deadline {
        let payload = try appRunExtractor(prefix: prefix, snapshotDir: snapshotDir, repoRoot: repoRoot)
        lastSeen = payload.matches.first
        if predicate(lastSeen) {
            return lastSeen
        }
        Thread.sleep(forTimeInterval: 0.5)
    }
    return lastSeen
}

final class AppleRemindersWriteSpikeApp: NSObject, NSApplicationDelegate {
    private let store = EKEventStore()
    private var startedAt = appIsoNow()
    private var probes: [AppSpikeReport.Probe] = []
    private var createdIdentifier: String?
    private var createdExternalIdentifier: String?
    private var extractorReminderID: String?
    private var calendarTitle = ""
    private var window: NSWindow?
    private var currentRepoRoot: URL?
    private let debugStatusURL = URL(fileURLWithPath: "/tmp/apple-reminders-write-spike-app.status.txt")

    func applicationDidFinishLaunching(_ notification: Notification) {
        writeStatus("applicationDidFinishLaunching entered cwd=\(FileManager.default.currentDirectoryPath) env_repo=\(ProcessInfo.processInfo.environment["RBOS_REPO_ROOT"] ?? "nil")")
        NSApp.setActivationPolicy(.regular)
        let rect = NSRect(x: 0, y: 0, width: 520, height: 180)
        let window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = "Apple Reminders Write Spike"
        window.center()
        window.makeKeyAndOrderFront(nil)
        let label = NSTextField(wrappingLabelWithString:
            "Requesting Reminders access for the rebalance-OS write spike.\n\nIf macOS shows a permission prompt, choose Allow. This window will close automatically after the spike completes."
        )
        label.frame = NSRect(x: 24, y: 44, width: 472, height: 88)
        label.isEditable = false
        label.isBordered = false
        label.drawsBackground = false
        label.font = .systemFont(ofSize: 15)
        window.contentView?.addSubview(label)
        self.window = window
        NSApp.activate(ignoringOtherApps: true)
        Task {
            self.writeStatus("task launched from applicationDidFinishLaunching")
            await runSpike()
            NSApp.terminate(nil)
        }
    }

    private func reportURL(repoRoot: URL) -> URL {
        repoRoot.appendingPathComponent("temp/apple-reminders/PHASE5-WRITE-SPIKE-APP.json")
    }

    private func statusURL(repoRoot: URL) -> URL {
        repoRoot.appendingPathComponent("temp/apple-reminders/PHASE5-WRITE-SPIKE-APP.status.txt")
    }

    private func writeStatus(_ line: String) {
        let stamp = "[\(appIsoNow())] \(line)\n"
        fputs(stamp, stderr)
        fflush(stderr)
        let urls = [debugStatusURL, currentRepoRoot.map(statusURL(repoRoot:))].compactMap { $0 }
        for url in urls {
            try? FileManager.default.createDirectory(
                at: url.deletingLastPathComponent(),
                withIntermediateDirectories: true,
                attributes: nil
            )
            if let handle = try? FileHandle(forWritingTo: url) {
                _ = try? handle.seekToEnd()
                try? handle.write(contentsOf: Data(stamp.utf8))
                try? handle.close()
            } else {
                try? Data(stamp.utf8).write(to: url)
            }
        }
    }

    private func buildReport() -> AppSpikeReport {
        AppSpikeReport(
            started_at: startedAt,
            finished_at: appIsoNow(),
            host_runtime: Bundle.main.bundleIdentifier ?? ProcessInfo.processInfo.processName,
            authorization_status_before: appStatusName(EKEventStore.authorizationStatus(for: .reminder)),
            authorization_status_after: appStatusName(EKEventStore.authorizationStatus(for: .reminder)),
            calendar_title: calendarTitle,
            eventkit_calendar_item_identifier: createdIdentifier,
            eventkit_external_identifier: createdExternalIdentifier,
            extractor_reminder_id: extractorReminderID,
            extractor_matches_eventkit_identifier: extractorReminderID == createdIdentifier && extractorReminderID != nil,
            extractor_matches_external_identifier: extractorReminderID == createdExternalIdentifier && extractorReminderID != nil,
            probes: probes
        )
    }

    private func cleanupLeftover() {
        guard let createdIdentifier,
              let leftover = store.calendarItem(withIdentifier: createdIdentifier) as? EKReminder else {
            return
        }
        do {
            try store.remove(leftover, commit: true)
            probes.append(.init(phase: "cleanup_after_failure", success: true, detail: "Removed leftover spike reminder after failure."))
        } catch {
            probes.append(.init(phase: "cleanup_after_failure", success: false, detail: "Cleanup failed: \(error)"))
        }
    }

    private func persistAndExit(repoRoot: URL, error: Error?) {
        if let error {
            probes.append(.init(phase: "failure", success: false, detail: String(describing: error)))
        }
        writeStatus("persistAndExit error=\(String(describing: error))")
        appSaveReport(buildReport(), to: reportURL(repoRoot: repoRoot))
    }

    private func runSpike() async {
        let root = appRepoRoot()
        currentRepoRoot = root
        let snapshotDir = root.appendingPathComponent("temp/apple-reminders/phase5-write-spike-app-snapshot", isDirectory: true)
        let statusBefore = appStatusName(EKEventStore.authorizationStatus(for: .reminder))
        writeStatus("runSpike start root=\(root.path) status_before=\(statusBefore)")
        probes.append(.init(phase: "host_runtime", success: true, detail: "bundle=\(Bundle.main.bundleIdentifier ?? "nil") status_before=\(statusBefore)"))

        do {
            writeStatus("about to request access")
            let granted = try await appRequestAccess(store: store)
            let statusAfterRequest = appStatusName(EKEventStore.authorizationStatus(for: .reminder))
            writeStatus("request access returned granted=\(granted) status_after=\(statusAfterRequest)")
            guard granted else {
                throw AppSpikeError.permissionDenied(
                    "Reminders permission was not granted for this app runtime. Current status: \(statusAfterRequest)."
                )
            }
            probes.append(.init(phase: "permission", success: true, detail: "Granted with status=\(statusAfterRequest)"))

            guard let calendar = store.defaultCalendarForNewReminders() else {
                throw AppSpikeError.missingCalendar
            }
            calendarTitle = calendar.title
            writeStatus("default calendar title=\(calendar.title)")

            let prefix = "RBOS-WRITE-SPIKE-APP-\(Int(Date().timeIntervalSince1970))"
            let createdTitle = "\(prefix) create"
            let updatedTitle = "\(prefix) updated"

            let reminder = EKReminder(eventStore: store)
            reminder.calendar = calendar
            reminder.title = createdTitle
            reminder.notes = "Created by app-bundle write spike at \(startedAt)"
            try store.save(reminder, commit: true)
            writeStatus("created reminder eventkit_id=\(reminder.calendarItemIdentifier ?? "nil")")
            createdIdentifier = reminder.calendarItemIdentifier
            createdExternalIdentifier = reminder.calendarItemExternalIdentifier
            probes.append(.init(
                phase: "create_eventkit",
                success: true,
                detail: "Created reminder in list '\(calendar.title)' with calendarItemIdentifier=\(createdIdentifier ?? "nil") externalIdentifier=\(createdExternalIdentifier ?? "nil")"
            ))

            guard let createdExtracted = try appWaitForMatch(
                prefix: prefix,
                snapshotDir: snapshotDir,
                repoRoot: root,
                timeoutSeconds: 12,
                predicate: { match in
                    guard let match else { return false }
                    return match.title == createdTitle && match.is_completed == false
                }
            ) else {
                throw AppSpikeError.timeout("Created reminder never appeared in the read-only extractor within 12 seconds.")
            }
            writeStatus("extractor saw created reminder id=\(createdExtracted.reminder_id)")
            extractorReminderID = createdExtracted.reminder_id
            probes.append(.init(phase: "create_extractor_visibility", success: true, detail: "Extractor saw created reminder with reminder_id=\(createdExtracted.reminder_id)"))

            guard let saved = createdIdentifier.flatMap({ store.calendarItem(withIdentifier: $0) as? EKReminder }) else {
                throw AppSpikeError.timeout("EventKit could not refetch the created reminder by calendarItemIdentifier.")
            }
            saved.title = updatedTitle
            saved.notes = "Updated by app-bundle write spike at \(appIsoNow())"
            saved.completionDate = Date()
            try store.save(saved, commit: true)
            writeStatus("updated reminder eventkit")
            probes.append(.init(phase: "update_eventkit", success: true, detail: "Updated title + notes and marked completed via EventKit."))

            guard try appWaitForMatch(
                prefix: prefix,
                snapshotDir: snapshotDir,
                repoRoot: root,
                timeoutSeconds: 12,
                predicate: { match in
                    guard let match else { return false }
                    return match.title == updatedTitle && match.is_completed == true
                }
            ) != nil else {
                throw AppSpikeError.timeout("Updated reminder never converged in the read-only extractor within 12 seconds.")
            }
            writeStatus("extractor reflected update")
            probes.append(.init(phase: "update_extractor_visibility", success: true, detail: "Extractor reflected updated title and completed state."))

            try store.remove(saved, commit: true)
            writeStatus("deleted reminder eventkit")
            probes.append(.init(phase: "delete_eventkit", success: true, detail: "Deleted reminder via EventKit."))

            let deletedExtracted = try appWaitForMatch(
                prefix: prefix,
                snapshotDir: snapshotDir,
                repoRoot: root,
                timeoutSeconds: 12,
                predicate: { match in match == nil }
            )
            if deletedExtracted != nil {
                throw AppSpikeError.timeout("Deleted reminder was still visible to the read-only extractor after 12 seconds.")
            }
            writeStatus("extractor no longer sees reminder")
            probes.append(.init(phase: "delete_extractor_visibility", success: true, detail: "Extractor no longer returned the deleted reminder."))

            persistAndExit(repoRoot: root, error: nil)
        } catch {
            writeStatus("caught error \(error)")
            cleanupLeftover()
            persistAndExit(repoRoot: root, error: error)
        }
    }
}

@main
enum AppleRemindersWriteSpikeMain {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppleRemindersWriteSpikeApp()
        app.delegate = delegate
        app.run()
    }
}
