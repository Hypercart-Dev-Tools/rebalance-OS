import AppKit
import SwiftUI
import Foundation

@main
struct Focus5NativeApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    @State private var selectedFolder: URL?
    @State private var gitStatus: String = ""
    @AppStorage("bookmarkData") private var bookmarkData: Data = Data()
    
    var body: some View {
        VStack(spacing: 20) {
            Text("Focus 5 Native Spike")
                .font(.largeTitle)
            
            if let folder = selectedFolder {
                Text("Selected: \(folder.path)")
            } else {
                Text("No folder selected")
            }
            
            Button("Pick Folder") {
                pickFolder()
            }
            
            if !gitStatus.isEmpty {
                ScrollView {
                    Text(gitStatus)
                        .font(.system(.body, design: .monospaced))
                        .padding()
                }
            }
        }
        .padding()
        .frame(minWidth: 400, minHeight: 300)
        .onAppear {
            restoreBookmark()
        }
    }
    
    func pickFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        // In a sandboxed app without com.apple.security.files.user-selected.read-write,
        // this panel wouldn't work properly unless configured. But a pure swift package executable
        // is unsandboxed by default. We are proving out the bookmark flow.
        
        if panel.runModal() == .OK, let url = panel.url {
            saveBookmark(url: url)
            selectedFolder = url
            scanRepo(at: url)
        }
    }
    
    func saveBookmark(url: URL) {
        do {
            let data = try url.bookmarkData(options: .withSecurityScope, includingResourceValuesForKeys: nil, relativeTo: nil)
            bookmarkData = data
        } catch {
            print("Failed to save bookmark: \(error)")
        }
    }
    
    func restoreBookmark() {
        guard !bookmarkData.isEmpty else { return }
        var isStale = false
        do {
            let url = try URL(resolvingBookmarkData: bookmarkData, options: .withSecurityScope, relativeTo: nil, bookmarkDataIsStale: &isStale)
            if url.startAccessingSecurityScopedResource() {
                selectedFolder = url
                scanRepo(at: url)
                // In a real app, keep it open or stopAccessing... when done.
            } else {
                print("Failed to start accessing security scoped resource.")
            }
        } catch {
            print("Failed to restore bookmark: \(error)")
        }
    }
    
    func scanRepo(at url: URL) {
        let task = Process()
        task.currentDirectoryURL = url
        task.executableURL = URL(fileURLWithPath: "/usr/bin/git")
        task.arguments = ["status", "--short", "--branch"]
        
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        
        do {
            try task.run()
            task.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            if let output = String(data: data, encoding: .utf8) {
                gitStatus = output.isEmpty ? "Clean repository (or not a git repo)" : output
            }
        } catch {
            gitStatus = "Error running git: \(error)"
        }
    }
}
