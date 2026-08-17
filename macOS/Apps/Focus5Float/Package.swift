// swift-tools-version:5.10
import PackageDescription

// Focus 5 Float — a standalone SwiftPM package (copy-first reuse of the
// TextReplacementStudio design system; see CONTRACT.md and the project plan).
// No external dependencies in Phase 1: the UI renders from a bundled fixture.
let package = Package(
    name: "Focus5Float",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "Focus5Float",
            resources: [.process("Resources")]
        ),
        .testTarget(
            name: "Focus5FloatTests",
            dependencies: ["Focus5Float"]
        ),
    ]
)
