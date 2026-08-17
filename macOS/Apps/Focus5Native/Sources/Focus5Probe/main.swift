import Foundation
import Focus5Core

// Headless Phase 0-R harness. Runs BOTH git paths against a repo path so the
// binary can be codesigned WITH the App Sandbox entitlement and its runtime
// behavior OBSERVED (not asserted):
//   1. embedded in-process libgit2 probe  -> the Phase 0 "embedded" path
//   2. Process exec of /usr/bin/git        -> the Phase 0 "Process" path
//
// Usage: Focus5Probe <repo-path>
// Exit code is always 0; the point is the captured stdout, not pass/fail.

let repoPath = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : FileManager.default.currentDirectoryPath

SafeStdIO.installSignalHandling()

func line(_ s: String) {
    if SafeStdIO.writeLine(s, to: STDOUT_FILENO) { return }
    _ = SafeStdIO.writeLine(s, to: STDERR_FILENO)
}

line("=== Focus5Probe (Phase 0-R sandboxed harness) ===")
line("repo: \(repoPath)")
line("libgit2 version: \(GitProbe.libgit2Version())")

// --- Path A: embedded libgit2, in-process ---
line("")
line("[A] EMBEDDED libgit2 in-process probe:")
do {
    let facts = try GitProbe.probe(path: repoPath)
    line("    OK: \(facts)")
    if let data = try? JSONEncoder().encode(facts), let json = String(data: data, encoding: .utf8) {
        line("    JSON: \(json)")
    }
} catch {
    line("    FAIL: \(error)")
}

// --- Path B: Process exec of system git ---
line("")
line("[B] PROCESS exec of /usr/bin/git status --short --branch:")
let task = Process()
task.currentDirectoryURL = URL(fileURLWithPath: repoPath)
task.executableURL = URL(fileURLWithPath: "/usr/bin/git")
task.arguments = ["status", "--short", "--branch"]
let pipe = Pipe()
task.standardOutput = pipe
task.standardError = pipe
do {
    try task.run()
    task.waitUntilExit()
    let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
    line("    task.run() SUCCEEDED. exitCode=\(task.terminationStatus) reason=\(task.terminationReason.rawValue)")
    line("    git output (first 3 lines):")
    for l in out.split(separator: "\n").prefix(3) { line("      \(l)") }
} catch {
    line("    task.run() THREW: \(error)")
    let nserr = error as NSError
    line("    NSError domain=\(nserr.domain) code=\(nserr.code) desc=\(nserr.localizedDescription)")
}

// --- Path C: security-scoped bookmark round-trip (persist + restore) ---
line("")
line("[C] SECURITY-SCOPED BOOKMARK persist + restore round-trip:")
let repoURL = URL(fileURLWithPath: repoPath, isDirectory: true)
do {
    // Persist. .withSecurityScope requires the URL to have been user-granted
    // (NSOpenPanel) in a GUI app; a headless harness can't summon a panel, so
    // we exercise the bookmark data API itself (create -> serialize -> resolve)
    // to prove persistence/restore works in-sandbox. The GUI Focus5Native app
    // supplies the panel-granted URL in the real product.
    let bmURL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("bookmark.dat")
    let data = try repoURL.bookmarkData(options: [],
                                        includingResourceValuesForKeys: nil,
                                        relativeTo: nil)
    try data.write(to: bmURL)
    line("    persisted bookmark: \(data.count) bytes -> \(bmURL.lastPathComponent)")

    var stale = false
    let restored = try URL(resolvingBookmarkData: try Data(contentsOf: bmURL),
                           options: [],
                           relativeTo: nil,
                           bookmarkDataIsStale: &stale)
    let started = restored.startAccessingSecurityScopedResource()
    line("    restored: \(restored.path) stale=\(stale) startAccessing=\(started)")
    if started { restored.stopAccessingSecurityScopedResource() }
    line("    OK: bookmark round-trip completed in-sandbox")
} catch {
    line("    FAIL: \(error)")
}

line("")
line("=== done ===")
