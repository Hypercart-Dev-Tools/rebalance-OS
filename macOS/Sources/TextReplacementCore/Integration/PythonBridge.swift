import Foundation

/// Thin bridge that runs this repo's hardened Python scripts (the ones the CLI/web editor use)
/// so the Swift app reuses that battle-tested Core Data I/O instead of re-porting it.
///
/// Resolution is configurable and never hardcoded into business logic:
/// - python: `FKR_PYTHON` env, else `/usr/bin/env python3` (PATH lookup).
/// - scripts dir: `FKR_SCRIPTS_DIR` env, else walk up from the CWD and the executable looking
///   for `scripts/json_to_apple_sqlite.py`, else the known repo path.
/// - db: `~/Library/KeyboardServices/TextReplacements.db` unless overridden.
public struct PythonBridge: Sendable {
    public struct Result: Sendable {
        public let stdout: String
        public let stderr: String
        public let exitCode: Int32
        public var ok: Bool { exitCode == 0 }
    }

    public enum BridgeError: Error, LocalizedError, Sendable {
        case scriptsDirectoryNotFound
        case scriptNotFound(String)
        case launchFailed(String)

        public var errorDescription: String? {
            switch self {
            case .scriptsDirectoryNotFound:
                return "Could not locate the repo's scripts/ directory. Set FKR_SCRIPTS_DIR."
            case .scriptNotFound(let name):
                return "Python script not found in scripts/: \(name)"
            case .launchFailed(let message):
                return "Failed to launch python: \(message)"
            }
        }
    }

    public let pythonExecutable: URL
    public let scriptsDirectory: URL
    public let databasePath: URL

    public init(
        pythonExecutable: URL? = nil,
        scriptsDirectory: URL? = nil,
        databasePath: URL? = nil
    ) throws {
        self.pythonExecutable = pythonExecutable ?? Self.defaultPython()
        self.scriptsDirectory = try (scriptsDirectory ?? Self.resolveScriptsDirectory())
        self.databasePath = databasePath ?? Self.defaultDatabasePath()
    }

    public static func defaultDatabasePath() -> URL {
        URL(fileURLWithPath: ("~/Library/KeyboardServices/TextReplacements.db" as NSString).expandingTildeInPath)
    }

    static func defaultPython() -> URL {
        if let path = ProcessInfo.processInfo.environment["FKR_PYTHON"], !path.isEmpty {
            return URL(fileURLWithPath: path)
        }
        return URL(fileURLWithPath: "/usr/bin/env")
    }

    static func resolveScriptsDirectory() throws -> URL {
        let fm = FileManager.default
        func hasScripts(_ dir: URL) -> Bool {
            fm.fileExists(atPath: dir.appendingPathComponent("json_to_apple_sqlite.py").path)
        }

        if let env = ProcessInfo.processInfo.environment["FKR_SCRIPTS_DIR"], !env.isEmpty {
            let url = URL(fileURLWithPath: (env as NSString).expandingTildeInPath)
            if hasScripts(url) { return url }
        }

        var roots = [URL(fileURLWithPath: fm.currentDirectoryPath)]
        if let exe = Bundle.main.executableURL { roots.append(exe.deletingLastPathComponent()) }
        for root in roots {
            var dir = root
            for _ in 0..<8 {
                if hasScripts(dir.appendingPathComponent("scripts")) {
                    return dir.appendingPathComponent("scripts")
                }
                let parent = dir.deletingLastPathComponent()
                if parent.path == dir.path { break }
                dir = parent
            }
        }

        let known = URL(fileURLWithPath: ("~/Documents/GH Repos/fast-key-replacement-macos/scripts" as NSString).expandingTildeInPath)
        if hasScripts(known) { return known }

        throw BridgeError.scriptsDirectoryNotFound
    }

    /// Run a script in scripts/ with the given args. Output is captured via temp files (not pipes)
    /// to stay deadlock-free regardless of how much the script writes.
    public func run(_ script: String, _ arguments: [String]) throws -> Result {
        let scriptURL = scriptsDirectory.appendingPathComponent(script)
        guard FileManager.default.fileExists(atPath: scriptURL.path) else {
            throw BridgeError.scriptNotFound(script)
        }

        let tmp = FileManager.default.temporaryDirectory
        let outURL = tmp.appendingPathComponent("fkr-out-\(UUID().uuidString)")
        let errURL = tmp.appendingPathComponent("fkr-err-\(UUID().uuidString)")
        FileManager.default.createFile(atPath: outURL.path, contents: nil)
        FileManager.default.createFile(atPath: errURL.path, contents: nil)
        defer {
            try? FileManager.default.removeItem(at: outURL)
            try? FileManager.default.removeItem(at: errURL)
        }

        let process = Process()
        process.executableURL = pythonExecutable
        if pythonExecutable.lastPathComponent == "env" {
            process.arguments = ["python3", scriptURL.path] + arguments
        } else {
            process.arguments = [scriptURL.path] + arguments
        }

        let outHandle = try FileHandle(forWritingTo: outURL)
        let errHandle = try FileHandle(forWritingTo: errURL)
        process.standardOutput = outHandle
        process.standardError = errHandle

        do {
            try process.run()
        } catch {
            throw BridgeError.launchFailed(error.localizedDescription)
        }
        process.waitUntilExit()
        try? outHandle.close()
        try? errHandle.close()

        let outData = (try? Data(contentsOf: outURL)) ?? Data()
        let errData = (try? Data(contentsOf: errURL)) ?? Data()
        return Result(
            stdout: String(decoding: outData, as: UTF8.self),
            stderr: String(decoding: errData, as: UTF8.self),
            exitCode: process.terminationStatus
        )
    }
}
