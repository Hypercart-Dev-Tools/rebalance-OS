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
    case focus5, dirtyFive, telemetry, promptLog
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
    // GH-105: single newest dirty off-roster repo, or nil — already nil on a
    // Dirty Five rerank (rankingMode == "dirty_first"), so no extra view guard
    // is needed at the call site.
    var dirtyBanner: OffRosterWarning?
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
    // Raw text of the selected file when it's a .md note rather than JSON telemetry
    // rows — rendered via the same MarkdownLine path as the vault focus5.md note.
    var telemetryMarkdownContent: String?
    var telemetryIsMarkdown: Bool { Self.isMarkdownKind(telemetryFileURL) }

    // Prompt Log tab (CLIO) — reads the CLIO-rendered Markdown export (the same
    // file the operator's Obsidian vault shows) as source of truth, so the tab
    // is a 1:1 mirror rather than a second rendering of the raw JSONL.
    var promptLogEntries: [PromptLogEntry] = []
    var promptLogFileURL: URL? {
        didSet {
            UserDefaults.standard.set(promptLogFileURL?.path, forKey: "promptLogFilePath")
            refreshPromptLog()
        }
    }
    var promptLogLoadError: String?
    // FIFO pin queue, max 5, newest pin at index 0 (rendered top), oldest pin at
    // the end (rendered bottom, and the one released when a 6th is pinned).
    var pinnedPromptLogIDs: [String] = [] {
        didSet {
            UserDefaults.standard.set(pinnedPromptLogIDs, forKey: "pinnedPromptLogIDs")
        }
    }
    static let maxPinnedPromptLogEntries = 5

    var pinnedPromptLogEntries: [PromptLogEntry] {
        let byID = Dictionary(uniqueKeysWithValues: promptLogEntries.map { ($0.id, $0) })
        return pinnedPromptLogIDs.compactMap { byID[$0] }
    }
    var unpinnedPromptLogEntries: [PromptLogEntry] {
        let pinned = Set(pinnedPromptLogIDs)
        return promptLogEntries.filter { !pinned.contains($0.id) }
    }

    /// Pure extension-string discriminator: `.md` (any case) → markdown/text
    /// viewer, everything else (incl. `.json`, no extension, or `nil`) →
    /// structured signals viewer. `nonisolated` (despite living on this
    /// `@MainActor` class) so GH-121 Phase 2's headless self-test can call the
    /// real production logic — same single source of truth `telemetryIsMarkdown`
    /// uses — with no MainActor context, no `Focus5Model` instance, and no file
    /// dialog or disk I/O required.
    nonisolated static func isMarkdownKind(_ url: URL?) -> Bool {
        url?.pathExtension.lowercased() == "md"
    }

    // Bottom note — the operator's vault `focus5.md`, projected by GET /focus-5/note.
    var noteContent = ""              // raw markdown (empty until first load / when absent)
    var noteExists = false            // true once the vault actually has a focus5.md
    var noteLoaded = false            // true after the first successful note fetch

    // Bottom Apple Reminders — read+write DIRECTLY via EventKit (not the server).
    // See RemindersStore for why the app is the runtime that can hold the grant.
    let reminders = RemindersStore()

    // Bottom Obsidian Reminders — top open tasks from vault `0. Goals.md`,
    // read+complete via the shared localhost Focus 5 routes.
    let obsidianReminders = ObsidianRemindersStore()

    // Transient top banner ("Repos refreshed") — set after a successful *manual*
    // refresh so the recycle button gives visible feedback; the view fades it out
    // on clear. Background polling never sets it (it'd flash unprompted every 90s).
    var banner: String?
    private var bannerToken = 0       // guards a rapid re-flash from clearing early

    private let client = Focus5Client()
    private let cache = RosterCache()
    private var fetchGeneration = 0    // guards against out-of-order fetch results

    init() {
        if let path = UserDefaults.standard.string(forKey: "telemetryFilePath") {
            telemetryFileURL = URL(fileURLWithPath: path)
        }
        pinnedPromptLogIDs = UserDefaults.standard.stringArray(forKey: "pinnedPromptLogIDs") ?? []
        if let path = UserDefaults.standard.string(forKey: "promptLogFilePath") {
            promptLogFileURL = URL(fileURLWithPath: path)
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
        } else if viewMode == .promptLog {
            refreshPromptLog()
        } else {
            _ = await fetchAndApply(dirty: isDirtyView)
            await refreshNote()
            await reminders.refresh()   // EventKit; no-ops until access granted
            await obsidianReminders.refresh()
        }
    }

    /// Show a transient top banner for ~3s, then clear it (the view fades it out).
    /// A token guards against a second flash's timer being cancelled by the first:
    /// only the most recent flash may clear the banner.
    func flashBanner(_ text: String) {
        banner = text
        bannerToken += 1
        let token = bannerToken
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            guard token == bannerToken else { return }
            banner = nil
        }
    }

    /// Re-pull the bottom note (`focus5.md`) from the server's read-only route.
    /// A fetch failure (server down) keeps the last-known note on screen rather
    /// than flashing the empty-state hint — `noteLoaded` only ever goes true.
    func refreshNote() async {
        guard let note = try? await client.fetchNote() else { return }
        noteExists = note.exists
        noteContent = note.content
        noteLoaded = true
    }

    /// Open an NSOpenPanel to pick a .json telemetry file or a .md note, persist
    /// it, and refresh. Called from both the in-panel button and the F5 menu bar
    /// action. Selection persists across relaunches/reboots via UserDefaults
    /// (see `telemetryFileURL.didSet` + `init()`).
    func openFilePicker() {
        let panel = NSOpenPanel()
        panel.title = "Select Telemetry or Markdown File"
        let markdownType = UTType(filenameExtension: "md") ?? .plainText
        panel.allowedContentTypes = [UTType.json, markdownType]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        telemetryFileURL = url   // didSet persists + refreshes
        viewMode = .telemetry
    }

    /// Re-read the selected telemetry-tab file. A `.md` file is read as raw text
    /// into `telemetryMarkdownContent` (rendered via the shared MarkdownLine path,
    /// same as the vault focus5.md note); anything else decodes as telemetry JSON
    /// into `telemetryEntries`. No-op (clears both) when no file is selected.
    func refreshTelemetry() {
        guard let url = telemetryFileURL else {
            telemetryEntries = []
            telemetryMarkdownContent = nil
            telemetryLoadError = nil
            return
        }
        if url.pathExtension.lowercased() == "md" {
            telemetryEntries = []
            // GH-121 agy [Should] #2: the read is synchronous on @MainActor, so cap
            // it — a giant vault/telemetry .md would otherwise freeze the panel with
            // no bound. Shared bounded read (see FileLoad); assumes .md < 1MB and
            // truncates above that.
            guard let (text, truncated) =
                FileLoad.boundedText(url, byteCeiling: Self.telemetryMarkdownByteCeiling) else {
                telemetryMarkdownContent = nil
                telemetryLoadError = "Could not read \"\(url.lastPathComponent)\"."
                return
            }
            telemetryMarkdownContent = truncated
                ? text + "\n\n…truncated (file exceeds 1 MB)"
                : text
            telemetryLoadError = nil
            return
        }
        telemetryMarkdownContent = nil
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

    /// Open an NSOpenPanel to pick the CLIO-rendered prompt log .md file, persist
    /// it, and refresh. Mirrors `openFilePicker()`'s telemetry-file selection.
    func openPromptLogFilePicker() {
        let panel = NSOpenPanel()
        panel.title = "Select Prompt Log Markdown File"
        let markdownType = UTType(filenameExtension: "md") ?? .plainText
        panel.allowedContentTypes = [markdownType]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        promptLogFileURL = url   // didSet persists + refreshes
        viewMode = .promptLog
    }

    /// Re-read and re-parse the selected prompt log file. No-op (clears state)
    /// when no file is selected.
    func refreshPromptLog() {
        guard let url = promptLogFileURL else {
            promptLogEntries = []
            promptLogLoadError = nil
            return
        }
        guard let entries = PromptLogReader.load(from: url) else {
            promptLogLoadError = "Could not read \"\(url.lastPathComponent)\"."
            return
        }
        promptLogLoadError = nil
        promptLogEntries = entries
    }

    /// Pin/unpin an entry. Pinning a 6th evicts the oldest pin (index `count-1`,
    /// the one rendered at the bottom of the pinned section) — a FIFO queue, not
    /// an arbitrary eviction.
    func togglePin(_ entry: PromptLogEntry) {
        if let idx = pinnedPromptLogIDs.firstIndex(of: entry.id) {
            pinnedPromptLogIDs.remove(at: idx)
        } else {
            pinnedPromptLogIDs.insert(entry.id, at: 0)
            if pinnedPromptLogIDs.count > Self.maxPinnedPromptLogEntries {
                pinnedPromptLogIDs.removeLast()
            }
        }
    }

    func isPinned(_ entry: PromptLogEntry) -> Bool {
        pinnedPromptLogIDs.contains(entry.id)
    }

    func resetAllPromptLogPins() {
        pinnedPromptLogIDs = []
    }

    /// Resolves a Prompt Log entry's repo NAME (CLIO only ever logs the name,
    /// never a path) back to a real local path + vscode:// URL, by matching
    /// against the roster/off-roster repos the live Focus 5 payload already
    /// knows about — the same "Open ↗" data `RepoCardView` uses, reused as-is
    /// rather than a second path-resolution mechanism. Best-effort: a repo
    /// that's fully clean, not in the top 5, and never off-roster-flagged
    /// isn't resolvable from here — same ceiling the rest of the app has.
    func vscodeOpenInfo(forRepoName repoName: String) -> (localPath: String, vscodeURL: String)? {
        let key = repoName.lowercased()
        if let card = roster.first(where: { $0.repoName.lowercased() == key }) {
            return (card.localPath, card.vscodeUrl)
        }
        if let w = offRoster.first(where: { $0.repoName.lowercased() == key }) {
            return (w.localPath, VSCodeLauncher.fileURL(forLocalPath: w.localPath))
        }
        return nil
    }

    /// Max telemetry rows held in memory / rendered (newest-first after sort).
    /// Aliases the shared feed cap so both file-backed viewers stay in lockstep.
    static let telemetryRowCap = FileLoad.feedRowCap

    /// Max bytes read from a telemetry-tab `.md` file before truncating (GH-121).
    /// Aliases the shared Markdown ceiling (single source of truth in FileLoad).
    static let telemetryMarkdownByteCeiling = FileLoad.markdownByteCeiling

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
        dirtyBanner = resp.dirtyBanner
        rankingMode = resp.rankingMode
        lastUpdated = resp.computedAt
    }

    static let offlineMessage =
        "Can't reach the local Focus 5 servers on localhost:8787 or 127.0.0.1:8767.\nStart rebalance serve, or verify the pulse server is running."
}
