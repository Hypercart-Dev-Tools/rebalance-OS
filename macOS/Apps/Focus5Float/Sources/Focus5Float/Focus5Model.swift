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
    private var fetchGeneration = 0    // guards against out-of-order fetch results

    var isDirtyView: Bool { rankingMode == "dirty_first" }

    /// Roster snapshot older than 24h (matches the web "⚠ stale" threshold).
    var isStale: Bool { RelTime.isOlderThan(lastUpdated, hours: 24) }
    var lastUpdatedAgo: String { RelTime.ago(lastUpdated) }

    private enum FetchOutcome { case applied, failed, superseded }

    /// Live fetch of GET /focus-5.json — the same roster the web /focus-5 shows.
    /// On failure the last-known roster stays on screen with an offline flag; an
    /// empty roster degrades to a `.failed` state with an actionable message.
    func refresh() async {
        _ = await fetchAndApply(dirty: isDirtyView)
    }

    /// Switch board + re-fetch so the SERVER does the re-rank (?view=dirty), never
    /// the client. The mode is flipped optimistically and reverted if the fetch
    /// actually fails (a superseded fetch leaves it alone — a newer call owns it).
    func setMode(dirty: Bool) async {
        let previous = rankingMode
        rankingMode = dirty ? "dirty_first" : "recent_activity"
        if await fetchAndApply(dirty: dirty) == .failed {
            rankingMode = previous
        }
    }

    /// Generation-guarded fetch: only the latest in-flight request may apply its
    /// result, so an older response can't clobber a newer selection (poll vs
    /// refresh vs mode-switch race).
    @discardableResult
    private func fetchAndApply(dirty: Bool) async -> FetchOutcome {
        fetchGeneration += 1
        let gen = fetchGeneration
        if roster.isEmpty { loadState = .loading }
        do {
            let resp = try await client.fetch(dirty: dirty)
            guard gen == fetchGeneration else { return .superseded }
            apply(resp)
            isOffline = false
            loadState = .loaded
            return .applied
        } catch {
            guard gen == fetchGeneration else { return .superseded }
            isOffline = true
            loadState = roster.isEmpty ? .failed(Self.offlineMessage) : .loaded
            return .failed
        }
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
