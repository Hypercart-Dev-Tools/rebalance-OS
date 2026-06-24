import Foundation

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

        guard ProcessInfo.processInfo.environment["FOCUS5_SELFTEST"] != nil else { return }
        do {
            let resp = try SampleData.load()
            print("SELFTEST OK — roster=\(resp.roster.count) mode=\(resp.rankingMode ?? "nil") "
                  + "offRoster=\(resp.offRosterWarnings.count) discovered=\(resp.summary.discovered)")
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
