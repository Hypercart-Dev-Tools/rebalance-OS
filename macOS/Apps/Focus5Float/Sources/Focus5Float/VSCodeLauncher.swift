import Foundation
import AppKit
import os

private let vscodeLog = Logger(subsystem: "me.neochro.Focus5Float", category: "vscode")

/// Opens a repo FOLDER in VS Code with "focus-if-open" behavior: `code <folder>`
/// (no `-n`/`-r`) routes to the existing window if that folder is already open,
/// else spawns exactly one new window — the behavior the repo cards want.
///
/// A Finder-launched GUI app inherits NO shell `PATH`, so the `code` binary is
/// resolved via an explicit override → known locations → a login-shell lookup
/// (mirrors `ServerLauncher`). Launch uses a DIRECT argv `Process` — no `/bin/sh`,
/// no string escaping — so it is immune to the quoting/injection class. If `code`
/// can't be found it falls back to the `vscode://` URI, so the button is never dead.
enum VSCodeLauncher {
    /// Fixed candidate locations, first existing wins. The ORDER is part of the
    /// contract (Homebrew arm64 → Intel → app bundle); the self-test guards it.
    static let candidates = [
        "/opt/homebrew/bin/code",
        "/usr/local/bin/code",
        "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
    ]

    /// The argv passed to `code` — exactly `[repoPath]`: no `-n`/`-r`, no shell.
    /// A pure function so the self-test can assert the shape never regresses.
    static func arguments(forRepoPath repoPath: String) -> [String] { [repoPath] }

    /// Builds the same `vscode://file/...` fallback URL the server computes in
    /// `focus5_scan.vscode_url()` (`f"vscode://file{quote(local_path, safe='/')}"`)
    /// — used when a repo's `vscodeUrl` isn't already on the wire (e.g. the
    /// Prompt Log tab, which only ever gets a repo NAME from CLIO and has to
    /// derive the open action itself from a resolved local path).
    static func fileURL(forLocalPath path: String) -> String {
        var allowed = CharacterSet.alphanumerics
        allowed.insert(charactersIn: "_.-~/")
        let encoded = path.addingPercentEncoding(withAllowedCharacters: allowed) ?? path
        return "vscode://file\(encoded)"
    }

    /// Resolve the `code` executable, or nil. Override → known locations → login shell.
    static func resolveBinary() -> String? {
        let fm = FileManager.default
        if let p = ProcessInfo.processInfo.environment["VSCODE_BIN"], fm.isExecutableFile(atPath: p) {
            return p
        }
        for c in candidates where fm.isExecutableFile(atPath: c) { return c }
        return loginShellWhich("code")
    }

    /// Open `repoPath` in VS Code (focus-if-open). Falls back to `fallbackURL`
    /// (the `vscode://` URI) when `code` isn't found, so the button is never dead.
    /// Runs off the main thread — `code` talks to VS Code over IPC and we don't
    /// want a slow launch to block the UI.
    static func launch(repoPath: String, fallbackURL: String) {
        guard let bin = resolveBinary() else {
            vscodeLog.info("code binary not found — falling back to vscode:// for \(repoPath, privacy: .public)")
            openFallback(fallbackURL)
            return
        }
        DispatchQueue.global(qos: .userInitiated).async {
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: bin)
            proc.arguments = arguments(forRepoPath: repoPath)   // direct argv — no shell, no escaping
            proc.standardInput = FileHandle.nullDevice
            proc.standardOutput = FileHandle.nullDevice
            proc.standardError = FileHandle.nullDevice
            do {
                try proc.run()
                proc.waitUntilExit()                            // `code <folder>` returns promptly
                vscodeLog.info("launched `\(bin, privacy: .public) \(repoPath, privacy: .public)` (status \(proc.terminationStatus))")
            } catch {
                vscodeLog.error("launch failed (\(error.localizedDescription, privacy: .public)) — falling back to vscode://")
                self.openFallback(fallbackURL)
            }
        }
    }

    private static func openFallback(_ fallbackURL: String) {
        guard let url = URL(string: fallbackURL) else { return }
        DispatchQueue.main.async { NSWorkspace.shared.open(url) }   // AppKit on the main thread
    }

    /// `<login-shell> -ilc 'command -v code'` — picks up a PATH set in `.zshrc`
    /// (pipx / asdf / mise / custom dirs) that a Finder-launched GUI app lacks.
    /// `-i` is required so `.zshrc` is sourced. The name is a fixed literal.
    private static func loginShellWhich(_ name: String) -> String? {
        let shell = ProcessInfo.processInfo.environment["SHELL"] ?? "/bin/zsh"
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: shell)
        proc.arguments = ["-ilc", "command -v \(name)"]
        let out = Pipe()
        proc.standardOutput = out
        proc.standardError = Pipe()                 // swallow banner / job-control noise
        do {
            try proc.run()
            proc.waitUntilExit()
            let data = out.fileHandleForReading.readDataToEndOfFile()
            let text = String(decoding: data, as: UTF8.self)
            // A noisy .zshrc may print banners; take the LAST line that is an
            // absolute, executable path.
            for line in text.split(separator: "\n").reversed() {
                let p = line.trimmingCharacters(in: .whitespaces)
                if p.hasPrefix("/"), FileManager.default.isExecutableFile(atPath: p) { return p }
            }
            return nil
        } catch { return nil }
    }
}
