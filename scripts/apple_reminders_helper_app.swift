import AppKit
import EventKit
import Foundation
import Darwin

// Apple Reminders write helper (Phase 5.1) — the single out-of-process writer.
//
// Runtime contract (proven Phase 5.0): EventKit writes succeed only from a
// signed, LaunchServices-launched app bundle holding a Reminders TCC grant. The
// rebalance Python orchestrator (apple_reminders_write.py) invokes this bundle
// via `open -a <bundle> --args --request <path>`, then polls for the response.
//
// This helper:
//   * reads a JSON request (schema_version 1) from --request <path>
//   * dispatches create/update/complete/delete via EventKit (plan = no mutation)
//   * confirms each write by EventKit read-back (no Full Disk Access needed)
//   * is idempotent by request_id (a replay re-emits the prior response, no
//     re-mutation) and serializes concurrent launches via a single-instance lock
//   * writes the response atomically next to the request (<id>.resp.json), exits.

let WRITE_SCHEMA_VERSION = 1

// MARK: - Wire types

struct WireOp: Decodable {
    let op: String
    let client_token: String?
    let reminder_id: String?
    let list_name: String?
    let fields: [String: AnyCodable]?
}

struct WireRequest: Decodable {
    let schema_version: Int
    let request_id: String
    let mode: String                 // "plan" | "apply"
    let confirm_destructive: Bool?
    let operations: [WireOp]
}

struct WireOpResult: Encodable {
    let op: String
    let client_token: String?
    var reminder_id: String?
    var status: String               // "ok" | "skipped" | "error"
    var readback_ok: Bool
    var detail: String
}

struct WireResponse: Encodable {
    let schema_version: Int
    let request_id: String
    let mode: String
    let host_runtime: String
    let authorization_status: String
    let started_at: String
    let finished_at: String
    var results: [WireOpResult]
}

// Minimal JSON value decoder for the per-op `fields` bag.
struct AnyCodable: Decodable {
    let value: Any
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let s = try? c.decode(String.self) { value = s }
        else if let b = try? c.decode(Bool.self) { value = b }
        else if let i = try? c.decode(Int.self) { value = i }
        else if let d = try? c.decode(Double.self) { value = d }
        else if c.decodeNil() { value = NSNull() }
        else { value = NSNull() }
    }
}

// MARK: - Helpers

func isoNow() -> String {
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return f.string(from: Date())
}

func statusName(_ s: EKAuthorizationStatus) -> String {
    switch s {
    case .notDetermined: return "not_determined"
    case .restricted: return "restricted"
    case .denied: return "denied"
    case .authorized: return "authorized"
    case .fullAccess: return "full_access"
    case .writeOnly: return "write_only"
    @unknown default: return "unknown"
    }
}

func argValue(_ flag: String) -> String? {
    let args = CommandLine.arguments
    guard let i = args.firstIndex(of: flag), i + 1 < args.count else { return nil }
    return args[i + 1]
}

func atomicWrite(_ data: Data, to url: URL) {
    try? FileManager.default.createDirectory(
        at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
    let tmp = url.appendingPathExtension("tmp")
    if (try? data.write(to: tmp, options: .atomic)) != nil {
        try? FileManager.default.removeItem(at: url)
        try? FileManager.default.moveItem(at: tmp, to: url)
    }
}

func respURL(forRequest reqURL: URL) -> URL {
    // <id>.req.json -> <id>.resp.json
    let name = reqURL.lastPathComponent
    let base = name.hasSuffix(".req.json")
        ? String(name.dropLast(".req.json".count))
        : reqURL.deletingPathExtension().lastPathComponent
    return reqURL.deletingLastPathComponent().appendingPathComponent("\(base).resp.json")
}

func processedURL(forRequest reqURL: URL, id: String) -> URL {
    reqURL.deletingLastPathComponent()
        .appendingPathComponent("processed", isDirectory: true)
        .appendingPathComponent("\(id).resp.json")
}

func dueComponents(from iso: String) -> DateComponents? {
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    let date = f.date(from: iso) ?? {
        let g = ISO8601DateFormatter(); g.formatOptions = [.withInternetDateTime]
        return g.date(from: iso)
    }()
    guard let d = date else { return nil }
    return Calendar.current.dateComponents(
        [.year, .month, .day, .hour, .minute, .second], from: d)
}

// MARK: - Write dispatcher

final class HelperApp: NSObject, NSApplicationDelegate {
    private let store = EKEventStore()

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        Task {
            await self.run()
            NSApp.terminate(nil)
        }
    }

    private func requestAccess() async -> Bool {
        await withCheckedContinuation { cont in
            if #available(macOS 14.0, *) {
                store.requestFullAccessToReminders { granted, _ in cont.resume(returning: granted) }
            } else {
                store.requestAccess(to: .reminder) { granted, _ in cont.resume(returning: granted) }
            }
        }
    }

    private func reminder(byID id: String) -> EKReminder? {
        store.calendarItem(withIdentifier: id) as? EKReminder
    }

    private func calendar(named name: String?) -> EKCalendar? {
        if let name {
            let match = store.calendars(for: .reminder).first { $0.title == name }
            if let match { return match }
        }
        return store.defaultCalendarForNewReminders()
    }

    private func applyFields(_ r: EKReminder, _ fields: [String: AnyCodable]?) {
        guard let fields else { return }
        if let t = fields["title"]?.value as? String { r.title = t }
        if let n = fields["notes"]?.value as? String { r.notes = n }
        if let due = fields["due_at"]?.value as? String, let dc = dueComponents(from: due) {
            r.dueDateComponents = dc
        }
        if let p = fields["priority"]?.value as? Int { r.priority = p }
    }

    private func handle(_ op: WireOp, mode: String, confirmDestructive: Bool) -> WireOpResult {
        var res = WireOpResult(op: op.op, client_token: op.client_token,
                               reminder_id: op.reminder_id, status: "error",
                               readback_ok: false, detail: "")
        let planning = (mode == "plan")
        switch op.op {
        case "create":
            guard let cal = calendar(named: op.list_name) else {
                res.detail = "no calendar for new reminders"; return res
            }
            let title = (op.fields?["title"]?.value as? String) ?? ""
            if title.isEmpty { res.detail = "create requires a title"; return res }
            if planning {
                res.status = "ok"; res.detail = "would create in '\(cal.title)'"; return res
            }
            let r = EKReminder(eventStore: store)
            r.calendar = cal
            r.title = title
            applyFields(r, op.fields)
            do {
                try store.save(r, commit: true)
                res.reminder_id = r.calendarItemIdentifier
                res.readback_ok = (reminder(byID: r.calendarItemIdentifier) != nil)
                res.status = "ok"; res.detail = "created in '\(cal.title)'"
            } catch { res.detail = "save failed: \(error)" }
            return res

        case "update", "complete":
            guard let id = op.reminder_id, let r = reminder(byID: id) else {
                res.detail = "no such reminder: \(op.reminder_id ?? "nil")"; return res
            }
            if planning {
                res.status = "ok"; res.detail = "would \(op.op)"; return res
            }
            if op.op == "complete" {
                r.isCompleted = true
                if r.completionDate == nil { r.completionDate = Date() }
            } else {
                applyFields(r, op.fields)
            }
            do {
                try store.save(r, commit: true)
                res.readback_ok = (reminder(byID: id) != nil)
                res.status = "ok"; res.detail = "\(op.op)d"
            } catch { res.detail = "save failed: \(error)" }
            return res

        case "delete":
            guard let id = op.reminder_id, let r = reminder(byID: id) else {
                res.detail = "no such reminder: \(op.reminder_id ?? "nil")"; return res
            }
            if planning {
                res.status = "ok"; res.detail = "would delete"; return res
            }
            if !confirmDestructive {
                res.status = "skipped"; res.detail = "delete needs confirm_destructive"; return res
            }
            do {
                try store.remove(r, commit: true)
                res.readback_ok = (reminder(byID: id) == nil)  // gone == good
                res.status = "ok"; res.detail = "deleted"
            } catch { res.detail = "remove failed: \(error)" }
            return res

        case "list-active":
            guard let cal = calendar(named: op.list_name) else {
                res.detail = "no calendar found for list-active"; return res
            }
            if planning {
                res.status = "ok"; res.detail = "would list active from '\(cal.title)'"; return res
            }
            let predicate = store.predicateForIncompleteReminders(withDueDateStarting: nil, ending: nil, calendars: [cal])
            let semaphore = DispatchSemaphore(value: 0)
            var fetched: [EKReminder]? = nil
            store.fetchReminders(matching: predicate) { result in
                fetched = result
                semaphore.signal()
            }
            // Bound the EventKit callback wait to 4.5s (within the Python invoker's 5s cap).
            if semaphore.wait(timeout: .now() + 4.5) == .timedOut {
                res.status = "error"; res.detail = "list-active timed out waiting for EventKit"; return res
            }

            var items: [[String: Any]] = []
            if let fetched = fetched {
                for r in fetched {
                    var dict: [String: Any] = [
                        "reminder_id": r.calendarItemIdentifier,
                        "title": r.title ?? ""
                    ]
                    if let due = r.dueDateComponents, let d = due.date {
                        let f = ISO8601DateFormatter()
                        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                        dict["due_at"] = f.string(from: d)
                    } else {
                        dict["due_at"] = NSNull()
                    }
                    items.append(dict)
                }
            }

            if let data = try? JSONSerialization.data(withJSONObject: items, options: []),
               let jsonStr = String(data: data, encoding: .utf8) {
                res.detail = jsonStr
                res.status = "ok"
                res.readback_ok = true
            } else {
                res.detail = "[]"
                res.status = "error"
            }
            return res

        default:
            res.detail = "unknown op: \(op.op)"; return res
        }
    }

    private func run() async {
        let startedAt = isoNow()
        guard let reqPath = argValue("--request") else {
            FileHandle.standardError.write(Data("helper: missing --request <path>\n".utf8))
            return
        }
        let reqURL = URL(fileURLWithPath: reqPath).standardizedFileURL
        let respPath = respURL(forRequest: reqURL)

        guard let reqData = try? Data(contentsOf: reqURL),
              let req = try? JSONDecoder().decode(WireRequest.self, from: reqData) else {
            FileHandle.standardError.write(Data("helper: cannot read/parse request\n".utf8))
            return
        }

        // Idempotency: a replay of an already-processed request re-emits the
        // stored response without re-mutating Apple Reminders.
        let processed = processedURL(forRequest: reqURL, id: req.request_id)
        if let prior = try? Data(contentsOf: processed) {
            atomicWrite(prior, to: respPath)
            return
        }

        // Single-instance write lock: serialize concurrent helper launches.
        let lockURL = reqURL.deletingLastPathComponent().appendingPathComponent(".helper.lock")
        let lockFD = open(lockURL.path, O_CREAT | O_RDWR, 0o644)
        if lockFD >= 0 { flock(lockFD, LOCK_EX) }
        defer { if lockFD >= 0 { flock(lockFD, LOCK_UN); close(lockFD) } }

        let confirm = req.confirm_destructive ?? false
        var results: [WireOpResult] = []

        if req.schema_version != WRITE_SCHEMA_VERSION {
            for op in req.operations {
                results.append(WireOpResult(op: op.op, client_token: op.client_token,
                    reminder_id: op.reminder_id, status: "error", readback_ok: false,
                    detail: "schema_version \(req.schema_version) != \(WRITE_SCHEMA_VERSION)"))
            }
            writeResponse(req: req, startedAt: startedAt, auth: "n/a",
                          results: results, respPath: respPath, processed: processed)
            return
        }

        let granted = await requestAccess()
        let auth = statusName(EKEventStore.authorizationStatus(for: .reminder))
        if !granted {
            for op in req.operations {
                results.append(WireOpResult(op: op.op, client_token: op.client_token,
                    reminder_id: op.reminder_id, status: "error", readback_ok: false,
                    detail: "Reminders access not granted (status=\(auth))"))
            }
            writeResponse(req: req, startedAt: startedAt, auth: auth,
                          results: results, respPath: respPath, processed: processed)
            return
        }

        for op in req.operations {
            results.append(handle(op, mode: req.mode, confirmDestructive: confirm))
        }
        writeResponse(req: req, startedAt: startedAt, auth: auth,
                      results: results, respPath: respPath, processed: processed)
    }

    private func writeResponse(req: WireRequest, startedAt: String, auth: String,
                               results: [WireOpResult], respPath: URL, processed: URL) {
        let response = WireResponse(
            schema_version: WRITE_SCHEMA_VERSION,
            request_id: req.request_id,
            mode: req.mode,
            host_runtime: Bundle.main.bundleIdentifier ?? "apple-reminders-helper",
            authorization_status: auth,
            started_at: startedAt,
            finished_at: isoNow(),
            results: results
        )
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? enc.encode(response) else { return }
        // Persist the processed record FIRST (idempotency), but only for apply
        // runs that actually mutated — plan runs are safe to re-run.
        if req.mode == "apply" {
            atomicWrite(data, to: processed)
        }
        atomicWrite(data, to: respPath)
    }
}

@main
enum AppleRemindersHelperMain {
    static func main() {
        let app = NSApplication.shared
        let delegate = HelperApp()
        app.delegate = delegate
        app.run()
    }
}
