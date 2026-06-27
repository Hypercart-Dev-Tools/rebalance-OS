import Foundation
import AppKit
import UniformTypeIdentifiers
import Observation

// Clones the StudioModel pattern: @Observable + @MainActor. Phase 4: the live
// source is GET /focus-5.json (the same summarize_focus5() behind the web
// /focus-5 page). The bundled fixture is retained ONLY for previews / the
// headless self-test — never as the app's data path.

/// Which panel the user has selected. Separate from `rankingMode` (server-side
/// sort order) so switching to Telemetry and back preserves the last ranking.
enum ViewMode: String {
    case focus5, dirtyFive, telemetry
}

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
    var showingCache = false          // currently displaying the on-disk cache
    var cachedFetchedAt: Date?        // when the displayed cache was last fetched
    var isStartingServer = false      // a manual "Start server" is in flight
    var startError: String?           // last start failure (nil when none)
    var viewMode: ViewMode = .focus5
    var telemetryEntries: [TelemetryEntry] = []
    var telemetryFileURL: URL? {
        didSet {
            UserDefaults.standard.set(telemetryFileURL?.path, forKey: "telemetryFilePath")
            refreshTelemetry()
        }
    }
    var telemetryLoadError: String?

    private let client = Focus5Client()
    private let cache = RosterCache()
    private var fetchGeneration = 0    // guards against out-of-order fetch results

    init() {
        if let path = UserDefaults.standard.string(forKey: "telemetryFilePath") {
            telemetryFileURL = URL(fileURLWithPath: path)
        }
    }

    var isDirtyView: Bool { rankingMode == "dirty_first" }

    /// Roster snapshot older than 24h (matches the web "⚠ stale" threshold).
    var isStale: Bool { RelTime.isOlderThan(lastUpdated, hours: 24) }
    var lastUpdatedAgo: String { RelTime.ago(lastUpdated) }
    var cachedAgo: String { RelTime.ago(cachedFetchedAt) }

    /// Synchronously load the on-disk cache so a cold launch renders instantly,
    /// before the first network fetch resolves. Only fills an empty roster; a
    /// successful fetch then overwrites it and clears `showingCache`.
    func loadCache() {
        guard roster.isEmpty, let cached = cache.load() else { return }
        apply(cached.response)
        cachedFetchedAt = cached.fetchedAt
        showingCache = true
        loadState = .loaded
    }

    private enum FetchOutcome { case applied, failed, superseded }

    /// Live fetch of GET /focus-5.json — the same roster the web /focus-5 shows.
    /// On failure the last-known roster stays on screen with an offline flag; an
    /// empty roster degrades to a `.failed` state with an actionable message.
    /// When telemetry is selected, re-reads ~/Documents/telemetry/ instead.
    func refresh() async {
        if viewMode == .telemetry {
            refreshTelemetry()
        } else {
            _ = await fetchAndApply(dirty: isDirtyView)
        }
    }

    /// Open an NSOpenPanel to pick a telemetry .json file, persist it, and refresh.
    /// Called from both the in-panel button and the F5 menu bar action.
    func openFilePicker() {
        let panel = NSOpenPanel()
        panel.title = "Select Telemetry JSON File"
        panel.allowedContentTypes = [UTType.json]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        telemetryFileURL = url   // didSet persists + refreshes
        viewMode = .telemetry
    }

    /// Re-read the selected telemetry file into telemetryEntries.
    /// No-op (clears entries) when no file is selected.
    func refreshTelemetry() {
        guard let url = telemetryFileURL else {
            telemetryEntries = []
            telemetryLoadError = nil
            return
        }
        guard let data = try? Data(contentsOf: url) else {
            telemetryLoadError = "Could not read \"\(url.lastPathComponent)\"."
            return
        }
        guard let entries = try? JSONDecoder().decode([TelemetryEntry].self, from: data) else {
            telemetryLoadError = "\"\(url.lastPathComponent)\" is not valid telemetry JSON.\nExpected an array: [{\"health\":\"green|orange|red\",\"title\":\"...\",\"description\":\"...\"}]"
            return
        }
        telemetryLoadError = nil
        let sorted = entries.sorted { a, b in
            switch (a.updatedAt, b.updatedAt) {
            case (let la?, let lb?): return la > lb
            case (nil, _):           return false
            case (_, nil):           return true
            }
        }
        // Cap at the newest 10k rows so decode/render stay bounded even if the
        // source file grows unbounded. Sort is newest-first, so prefix == newest.
        telemetryEntries = Array(sorted.prefix(Self.telemetryRowCap))
    }

    /// Max telemetry rows held in memory / rendered (newest-first after sort).
    static let telemetryRowCap = 10_000

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
            cache.save(resp)              // persist for the next cold/offline start
            isOffline = false
            showingCache = false          // now showing server-fresh data
            cachedFetchedAt = nil
            loadState = .loaded
            return .applied
        } catch {
            guard gen == fetchGeneration else { return .superseded }
            isOffline = true              // keep the last-known/cached roster on screen
            loadState = roster.isEmpty ? .failed(Self.offlineMessage) : .loaded
            return .failed
        }
    }

    /// Start the local `rebalance serve`, then poll (via `refresh()`) until it
    /// answers and the roster is applied. Bounded so it never hangs.
    func startServer() async {
        guard !isStartingServer else { return }
        isStartingServer = true
        startError = nil
        defer { isStartingServer = false }

        do {
            try ServerLauncher.start()
        } catch {
            startError = String(describing: error)
            return
        }

        let deadline = Date().addingTimeInterval(20)
        while Date() < deadline {
            await refresh()
            if !isOffline { return }                 // server answered; roster applied
            try? await Task.sleep(nanoseconds: 1_500_000_000)
        }
        startError = "Server didn't respond within 20s — try Refresh."
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
