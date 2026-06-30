import SwiftUI
import AppKit
import TextReplacementCore

@main
struct TextReplacementStudioApp: App {
    init() {
        // SwiftPM's generated bundle has no Info.plist icon key, so set the Dock /
        // ⌘-Tab icon at launch from the bundled artwork.
        if let url = Bundle.module.url(forResource: "AppIcon", withExtension: "png"),
           let icon = NSImage(contentsOf: url) {
            NSApplication.shared.applicationIconImage = icon
        }
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .commands {
            CommandGroup(replacing: .newItem) {
                NewReplacementCommand()
            }
        }
    }
}

/// File ▸ New Replacement (⌘N). Reads the action published by the focused window's
/// ContentView so the menu and the in-window buttons share one path.
private struct NewReplacementCommand: View {
    @FocusedValue(\.newReplacement) private var add

    var body: some View {
        Button("New Replacement") { add?() }
            .keyboardShortcut("n", modifiers: .command)
            .disabled(add == nil)
    }
}
