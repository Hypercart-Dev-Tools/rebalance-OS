import Foundation

// Headless decode smoke test so the Codable contract can be verified without a
// GUI:  FOCUS5_SELFTEST=1 swift run Focus5Float
// Decodes the bundled fixture, prints a summary, and exits (0 ok / 1 fail).
enum Focus5SelfTest {
    static func runIfRequested() {
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
