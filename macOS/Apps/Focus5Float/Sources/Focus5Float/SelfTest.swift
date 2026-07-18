import Foundation
import SwiftUI

// Headless decode smoke test so the Codable contract can be verified without a
// GUI:  FOCUS5_SELFTEST=1 swift run Focus5Float
// Decodes the bundled fixture, prints a summary, and exits (0 ok / 1 fail).
enum Focus5SelfTest {
    static func runIfRequested() {
        // Live decode test: FOCUS5_LIVETEST=1 swift run Focus5Float — fetches the
        // running server's /focus-5.json and prints the real roster, then exits.
        if ProcessInfo.processInfo.environment["FOCUS5_LIVETEST"] != nil {
            let sem = DispatchSemaphore(value: 0)
            Task {
                defer { sem.signal() }
                do {
                    let resp = try await Focus5Client().fetch(dirty: false)
                    print("LIVETEST OK — \(Focus5Client.defaultBaseURL) roster=\(resp.roster.count) "
                          + "mode=\(resp.rankingMode ?? "nil") discovered=\(resp.summary.discovered)")
                    for c in resp.roster {
                        print("  #\(c.position) \(c.repoName) dirty=\(c.isDirty) "
                              + "↑\(c.ahead)↓\(c.behind) \(c.modifiedCount)M \(c.untrackedCount)U")
                    }
                    exit(0)
                } catch {
                    print("LIVETEST FAIL — \(error) (is `rebalance serve` running?)")
                    exit(1)
                }
            }
            sem.wait()
        }

        // Offline-cache round-trip test: FOCUS5_CACHETEST=1 swift run Focus5Float —
        // saves the fixture through RosterCache and loads it back (no server needed).
        if ProcessInfo.processInfo.environment["FOCUS5_CACHETEST"] != nil {
            do {
                let sample = try SampleData.load()
                let tmp = FileManager.default.temporaryDirectory
                    .appendingPathComponent("f5-cache-roundtrip.json")
                let cache = RosterCache(url: tmp)
                cache.save(sample, fetchedAt: Date())
                guard let loaded = cache.load() else {
                    print("CACHETEST FAIL — load returned nil"); exit(1)
                }
                try? FileManager.default.removeItem(at: tmp)
                let ok = loaded.response.roster.count == sample.roster.count
                    && loaded.response.roster.first?.repoName == sample.roster.first?.repoName
                    && loaded.response.summary.rosterSize == sample.summary.rosterSize
                print("CACHETEST \(ok ? "OK" : "FAIL") — round-tripped \(loaded.response.roster.count) "
                      + "repos (first=\(loaded.response.roster.first?.repoName ?? "—")), "
                      + "fetchedAt \(RelTime.ago(loaded.fetchedAt))")
                exit(ok ? 0 : 1)
            } catch {
                print("CACHETEST FAIL — \(error)"); exit(1)
            }
        }

        // Binary-resolution test: FOCUS5_RESOLVETEST=1 swift run Focus5Float —
        // prints where ServerLauncher would find `rebalance` (does NOT start it).
        if ProcessInfo.processInfo.environment["FOCUS5_RESOLVETEST"] != nil {
            let bin = ServerLauncher.resolveBinary()
            print("RESOLVETEST — rebalance = \(bin ?? "NOT FOUND")")
            exit(bin == nil ? 1 : 0)
        }

        // Roster-health rollup test: FOCUS5_HEALTHTEST=1 swift run Focus5Float
        if ProcessInfo.processInfo.environment["FOCUS5_HEALTHTEST"] != nil {
            let ok = RosterHealth.tint(dirty: 0, total: 5) == Theme.diffAdd      // green
                && RosterHealth.tint(dirty: 5, total: 5) == Theme.diffRemove     // red
                && RosterHealth.tint(dirty: 2, total: 5) == Color.orange         // orange
            print("HEALTHTEST \(ok ? "OK" : "FAIL") — clean=green, all-dirty=red, some=orange")
            exit(ok ? 0 : 1)
        }

        // VS Code launcher test: FOCUS5_VSCODETEST=1 swift run Focus5Float — asserts the
        // candidate ORDER + argv SHAPE (focus-if-open is `code <folder>`, no -n/-r, no shell).
        // Does NOT launch VS Code; resolveBinary() is reported for diagnosis only.
        if ProcessInfo.processInfo.environment["FOCUS5_VSCODETEST"] != nil {
            let argv = VSCodeLauncher.arguments(forRepoPath: "/repos/demo repo")
            let argvOK = argv == ["/repos/demo repo"]      // exactly the folder; spaces safe (argv array)
            let c = VSCodeLauncher.candidates
            let orderOK = c.count == 3
                && c.first == "/opt/homebrew/bin/code"
                && c.last == "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
            let bin = VSCodeLauncher.resolveBinary()
            print("VSCODETEST \(argvOK && orderOK ? "OK" : "FAIL") — argv=\(argv) candidates=\(c.count) "
                  + "resolved=\(bin ?? "none (vscode:// fallback)")")
            exit(argvOK && orderOK ? 0 : 1)
        }

        // GH-121 Phase 2 kind-discriminator test: FOCUS5_KINDTEST=1 swift run
        // Focus5Float — pure extension-string assertion, no file dialog, no disk
        // I/O, no MainActor context needed. Exercises the real production
        // discriminator `Focus5Model.isMarkdownKind(_:)` (the same one
        // `telemetryIsMarkdown` calls) rather than a re-implementation, so this
        // can't silently drift from the live load/render branching.
        if ProcessInfo.processInfo.environment["FOCUS5_KINDTEST"] != nil {
            let cases: [(url: URL?, wantMarkdown: Bool, label: String)] = [
                (URL(fileURLWithPath: "/tmp/foo.json"), false, "foo.json → structured"),
                (URL(fileURLWithPath: "/tmp/foo.md"), true, "foo.md → text"),
                (URL(fileURLWithPath: "/tmp/FOO.MD"), true, "FOO.MD → text (case-insensitive)"),
                (URL(fileURLWithPath: "/tmp/signals.JSON"), false, "signals.JSON → structured (case-insensitive)"),
                (URL(fileURLWithPath: "/tmp/notes.markdown"), false, "notes.markdown → structured (only \"md\" counts)"),
                (URL(fileURLWithPath: "/tmp/no-extension"), false, "no-extension → structured"),
                (nil, false, "nil (no file selected) → structured"),
            ]
            var ok = true
            for c in cases {
                let got = Focus5Model.isMarkdownKind(c.url)
                if got != c.wantMarkdown {
                    ok = false
                    print("  MISMATCH \(c.label): got markdown=\(got) want markdown=\(c.wantMarkdown)")
                }
            }
            print("KINDTEST \(ok ? "OK" : "FAIL") — \(cases.count) cases: foo.json→structured, foo.md→text")
            exit(ok ? 0 : 1)
        }

        // Prompt Log parser test: FOCUS5_PROMPTLOGTEST=1 swift run Focus5Float —
        // parses a fixture matching the real CLIO exporter output (utils/CLIO/
        // INSTALL.md), including a multi-line prompt, and asserts field-level
        // extraction plus newest-first ordering (no re-sort — the fixture is
        // already in the file's natural newest-first order).
        if ProcessInfo.processInfo.environment["FOCUS5_PROMPTLOGTEST"] != nil {
            let fixture = """
            # Claude Code Prompt Log

            Generated by CLIO (A member of the rebalanceOS | XYZ | HiQS family)
            https://github.com/Claude-AI-Tools-Ventura-County/clio

            <!-- CLIO:ENTRIES -->

            ## REBALANCE-OS
            2026-07-18T03:09:07Z
            noel's Mac Studio · development

            > "single-line prompt"

            ## REBALANCE-OS
            2026-07-09T18:42:11Z
            Noels-MacBook-Pro · main

            > "line one
            > line two"
            """
            let entries = PromptLogReader.parse(fixture)
            let ok = entries.count == 2
                && entries[0].repo == "REBALANCE-OS"
                && entries[0].timestamp == "2026-07-18T03:09:07Z"
                && entries[0].machine == "noel's Mac Studio"
                && entries[0].branch == "development"
                && entries[0].prompt == "single-line prompt"
                && entries[1].prompt == "line one\nline two"
                && entries[1].branch == "main"
            print("PROMPTLOGTEST \(ok ? "OK" : "FAIL") — parsed \(entries.count) entries")
            exit(ok ? 0 : 1)
        }

        guard ProcessInfo.processInfo.environment["FOCUS5_SELFTEST"] != nil else { return }
        do {
            let resp = try SampleData.load()
            print("SELFTEST OK — roster=\(resp.roster.count) mode=\(resp.rankingMode ?? "nil") "
                  + "offRoster=\(resp.offRosterWarnings.count) discovered=\(resp.summary.discovered) "
                  + "dirtyBanner=\(resp.dirtyBanner?.repoName ?? "nil")")
            for c in resp.roster {
                print("  #\(c.position) \(c.repoName) dirty=\(c.isDirty) "
                      + "drift=↑\(c.ahead)↓\(c.behind) pr=\(c.newestPr?.number.description ?? "—") "
                      + "activity=\(c.recentActivity.count) fullName=\(c.repoFullName ?? "nil")")
            }
            exit(0)
        } catch {
            print("SELFTEST FAIL — \(error)")
            exit(1)
        }
    }
}
