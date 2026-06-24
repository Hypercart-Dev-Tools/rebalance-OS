import Foundation
import Observation

// Clones the StudioModel pattern: @Observable + @MainActor, heavy I/O off-main
// (Phase 4), derived state on the model. Phase 1 is fed from the bundled fixture
// only — no networking yet.

enum LoadState: Equatable {
    case idle
    case loading
    case loaded
    case failed(String)
}

@MainActor
@Observable
final class Focus5Model {
    var roster: [RepoCard] = []
    var offRoster: [OffRosterWarning] = []
    var rankingMode: String?          // "recent_activity" | "dirty_first"
    var lastUpdated: String?          // computed_at from the payload
    var loadState: LoadState = .idle

    var isDirtyView: Bool { rankingMode == "dirty_first" }

    /// Phase 1: load the bundled `/focus-5.json` fixture (zero network).
    /// Phase 4 replaces this with a live `Focus5Client.fetch()`.
    func loadSample() {
        loadState = .loading
        do {
            apply(try SampleData.load())
            loadState = .loaded
        } catch {
            loadState = .failed(String(describing: error))
        }
    }

    private func apply(_ resp: Focus5Response) {
        roster = resp.roster
        offRoster = resp.offRosterWarnings
        rankingMode = resp.rankingMode
        lastUpdated = resp.computedAt
    }
}
