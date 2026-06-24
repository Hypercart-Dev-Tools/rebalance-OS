// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "TextReplacementStudio",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "TextReplacementCore",
            targets: ["TextReplacementCore"]
        ),
        .executable(
            name: "TextReplacementStudio",
            targets: ["TextReplacementStudio"]
        ),
        .executable(
            name: "trstudio",
            targets: ["TextReplacementCLI"]
        )
    ],
    dependencies: [
        .package(url: "https://github.com/groue/GRDB.swift.git", from: "6.29.0"),
        .package(url: "https://github.com/SwiftyJSON/SwiftyJSON.git", from: "5.0.2"),
        .package(url: "https://github.com/apple/swift-argument-parser.git", from: "1.3.0")
    ],
    targets: [
        .target(
            name: "TextReplacementCore",
            dependencies: [
                .product(name: "GRDB", package: "GRDB.swift"),
                "SwiftyJSON"
            ],
            path: "Sources/TextReplacementCore"
        ),
        .executableTarget(
            name: "TextReplacementStudio",
            dependencies: [
                "TextReplacementCore"
            ],
            path: "Apps/TextReplacementStudio",
            resources: [
                .process("Resources")
            ]
        ),
        .executableTarget(
            name: "TextReplacementCLI",
            dependencies: [
                "TextReplacementCore",
                .product(name: "ArgumentParser", package: "swift-argument-parser")
            ],
            path: "Sources/TextReplacementCLI"
        ),
        .testTarget(
            name: "TextReplacementCoreTests",
            dependencies: [
                "TextReplacementCore"
            ],
            path: "Tests/TextReplacementCoreTests"
        )
    ]
)
