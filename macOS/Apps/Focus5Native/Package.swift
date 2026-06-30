// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Focus5Native",
    platforms: [
        .macOS(.v11)
    ],
    targets: [
        .executableTarget(
            name: "Focus5Native"
        ),
    ]
)
