// swift-tools-version: 5.9
import PackageDescription

// Phase 0-R spike: the embedded libgit2 path is proven by linking against the
// arm64 libgit2.dylib Xcode ships (there is no public libgit2 SDK / SwiftPM
// SwiftGit2 macOS slice available in this environment — see
// PHASE-0-R-FINDINGS.md). We link it via an rpath + -lgit2. This is a SPIKE
// wiring, not the shippable dependency graph.
let xcodeLibDir = "/Applications/Xcode.app/Contents/Developer/usr/lib"

let package = Package(
    name: "Focus5Native",
    platforms: [
        .macOS(.v12)
    ],
    targets: [
        // C shim: hand-declared minimal libgit2 prototypes (no public header).
        .target(
            name: "Clibgit2",
            path: "Sources/Clibgit2",
            publicHeadersPath: "include"
        ),
        // In-process git fact extractor built on the shim.
        .target(
            name: "Focus5Core",
            dependencies: ["Clibgit2"],
            linkerSettings: [
                .unsafeFlags([
                    "-L", xcodeLibDir,
                    "-lgit2",
                    "-Xlinker", "-rpath", "-Xlinker", xcodeLibDir,
                ])
            ]
        ),
        // Headless Phase 0-R harness: runs embedded probe + Process-exec so the
        // codesigned+sandboxed binary can be OBSERVED (not asserted).
        .executableTarget(
            name: "Focus5Probe",
            dependencies: ["Focus5Core"]
        ),
        // Original GUI spike (unchanged behavior; still the SwiftUI shell).
        .executableTarget(
            name: "Focus5Native"
        ),
        .testTarget(
            name: "Focus5CoreTests",
            dependencies: ["Focus5Core"]
        ),
    ]
)
