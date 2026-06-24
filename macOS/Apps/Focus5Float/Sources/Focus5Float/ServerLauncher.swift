import Foundation
import os

private let launchLog = Logger(subsystem: "me.neochro.Focus5Float", category: "launcher")

/// Starts the local `rebalance serve` on demand. A GUI app does NOT inherit the
/// shell `PATH`, so the binary is resolved via an explicit override, a login-shell
/// lookup, then known locations. The server is spawned **detached** (its own
/// lifetime, like the operator's normal `serve`) with a FIXED argument list — no
/// user input ever reaches the command line, and no shell string is interpolated.
enum ServerLauncher {
    enum LaunchError: Error, CustomStringConvertible {
        case binaryNotFound
        var description: String {
            switch self {
            case .binaryNotFound:
                return "Couldn't find the `rebalance` binary.\nSet REBALANCE_BIN or make sure it's on your login PATH."
            }
        }
    }

    /// Resolve the `rebalance` executable path, or nil.
    ///
    /// A Finder-launched GUI app inherits NO shell `PATH`, so we can't rely on it.
    /// Order: explicit override → fast known-path probe (no subprocess) → an
    /// *interactive* login-shell lookup as the general catch-all.
    static func resolveBinary() -> String? {
        let fm = FileManager.default

        // 1. Explicit override (operator-set).
        if let p = ProcessInfo.processInfo.environment["REBALANCE_BIN"],
           fm.isExecutableFile(atPath: p) {
            return p
        }
        // 2. Known locations — instant, and covers the common installs (~/bin is
        //    where this operator's launcher lives).
        for c in [NSHomeDirectory() + "/bin/rebalance",
                  "/opt/homebrew/bin/rebalance",
                  "/usr/local/bin/rebalance",
                  NSHomeDirectory() + "/.local/bin/rebalance"] {
            if fm.isExecutableFile(atPath: c) { return c }
        }
        // 3. Interactive login-shell lookup — picks up a PATH set in .zshrc
        //    (pipx / venv / asdf / mise / custom dirs) that a GUI app lacks.
        if let p = loginShellWhich("rebalance") { return p }
        return nil
    }

    /// Spawn a detached `rebalance serve`. Returns the child PID.
    @discardableResult
    static func start() throws -> Int32 {
        guard let bin = resolveBinary() else {
            launchLog.error("rebalance binary not found")
            throw LaunchError.binaryNotFound
        }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: bin)
        proc.arguments = ["serve"]                 // fixed args — no user input
        proc.standardInput = FileHandle.nullDevice
        proc.standardOutput = FileHandle.nullDevice
        proc.standardError = FileHandle.nullDevice
        try proc.run()                             // not awaited → survives app quit
        launchLog.info("started `\(bin) serve` (pid \(proc.processIdentifier))")
        return proc.processIdentifier
    }

    /// `<login-shell> -ilc 'command -v rebalance'` — the name is a fixed literal.
    /// `-i` (interactive) is required so `.zshrc` is sourced: a plain `-lc` login
    /// shell is NON-interactive and skips `.zshrc`, where most users' PATH lives.
    private static func loginShellWhich(_ name: String) -> String? {
        let shell = ProcessInfo.processInfo.environment["SHELL"] ?? "/bin/zsh"
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: shell)
        proc.arguments = ["-ilc", "command -v \(name)"]
        let out = Pipe()
        proc.standardOutput = out
        proc.standardError = Pipe()              // swallow job-control / banner noise
        do {
            try proc.run()
            proc.waitUntilExit()
            let data = out.fileHandleForReading.readDataToEndOfFile()
            let text = String(decoding: data, as: UTF8.self)
            // A noisy .zshrc may print banners to stdout, so take the LAST line
            // that is an absolute, executable path.
            for line in text.split(separator: "\n").reversed() {
                let p = line.trimmingCharacters(in: .whitespaces)
                if p.hasPrefix("/"), FileManager.default.isExecutableFile(atPath: p) { return p }
            }
            return nil
        } catch {
            return nil
        }
    }
}
