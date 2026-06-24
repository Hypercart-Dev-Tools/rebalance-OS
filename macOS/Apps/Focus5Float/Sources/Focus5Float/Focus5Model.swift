import Foundation
import Observation

// Clones the StudioModel pattern: @Observable + @MainActor. Phase 4: the live
// source is GET /focus-5.json (the same summarize_focus5() behind the web
// /focus-5 page). The bundled fixture is retained ONLY for previews / the
// headless self-test — never as the app's data path.

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
    var isOffline = false             // last fetch couldn't reach the server

    private let client = Focus5Client()

    var isDirtyView: Bool { rankingMode == "dirty_first" }

    /// Live fetch of GET /focus-5.json — the same roster the web /focus-5 shows.
    /// On failure the last-known roster stays on screen with an offline flag; an
    /// empty roster degrades to a `.failed` state with an actionable message.
    func refresh() async {
        if roster.isEmpty { loadState = .loading }
        do {
            apply(try await client.fetch(dirty: isDirtyView))
            isOffline = false
            loadState = .loaded
        } catch {
            isOffline = true
            loadState = roster.isEmpty ? .failed(Self.offlineMessage) : .loaded
        }
    }

    /// Switch board + re-fetch so the server does the re-rank (?view=dirty),
    /// never the client.
    func setMode(dirty: Bool) async {
        rankingMode = dirty ? "dirty_first" : "recent_activity"
        await refresh()
    }

    /// Fixture loader — previews / FOCUS5_SELFTEST only, NOT the app data path.
    func loadSample() {
        loadState = .loading
        do { apply(try SampleData.load()); loadState = .loaded }
        catch { loadState = .failed(String(describing: error)) }
    }

    private func apply(_ resp: Focus5Response) {
        roster = resp.roster
        offRoster = resp.offRosterWarnings
        rankingMode = resp.rankingMode
        lastUpdated = resp.computedAt
    }

    static let offlineMessage =
        "Can't reach rebalance serve at localhost:8787.\nStart it with:  rebalance serve"
}
