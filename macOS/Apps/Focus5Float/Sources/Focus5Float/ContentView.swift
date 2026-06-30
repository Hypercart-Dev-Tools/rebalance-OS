import SwiftUI
import AppKit
import EventKit

// Phase 3 UI: vertical stack of collapsible repo cards over the live
// /focus-5.json (Phase 4), using the harvested Theme + components. Collapsed
// rows show position / name / status / drift; tapping expands into the web
// card's sub-sections (Tree health / Newest PR / Recent activity). In-panel
// ranking toggle + refresh + staleness badge mirror the web header.

struct ContentView: View {
    let model: Focus5Model

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider().overlay(Theme.separator)
            content
        }
        .background(Theme.window)
        .overlay(alignment: .top) {
            if let banner = model.banner {
                TopBanner(text: banner)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .zIndex(1)
            }
        }
        .animation(.easeInOut(duration: 0.35), value: model.banner)
    }

    // MARK: Bottom sections (Reminders + Note)

    /// The two bottom sections — Apple Reminders (A) over the focus5.md note (B) —
    /// rendered inline at the end of the single roster scroll so they size to
    /// their content (liquid) and flow right under the cards with no dead space.
    /// Non-telemetry only; the note appears once its first fetch lands.
    @ViewBuilder private var bottomSections: some View {
        RemindersSection(store: model.reminders)
        if model.noteLoaded {
            Focus5NoteView(exists: model.noteExists, content: model.noteContent)
        }
    }

    // MARK: Header

    private var header: some View {
        VStack(spacing: Theme.Space.xs) {
            // Row 1 — compact tab switcher + actions. Emoji-only labels keep the
            // 3-segment picker narrow enough for a ~180-wide panel; the tab names
            // live in the help tooltips + accessibility labels.
            HStack(spacing: Theme.Space.s) {
                Picker("", selection: Binding(
                    get: { model.viewMode },
                    set: { mode in
                        model.viewMode = mode
                        switch mode {
                        case .focus5:    Task { await model.setMode(dirty: false) }
                        case .dirtyFive: Task { await model.setMode(dirty: true) }
                        case .telemetry: model.refreshTelemetry()
                        }
                    }
                )) {
                    Text("🎯").tag(ViewMode.focus5)
                        .help("Focus 5").accessibilityLabel("Focus 5")
                    Text("🧹").tag(ViewMode.dirtyFive)
                        .help("Dirty Five").accessibilityLabel("Dirty Five")
                    Text("📊").tag(ViewMode.telemetry)
                        .help("Telemetry").accessibilityLabel("Telemetry")
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .fixedSize(horizontal: true, vertical: false)

                Button {
                    Task {
                        await model.refresh()
                        // Confirm the manual refresh did something — the button
                        // otherwise gives no visible feedback. Skip when offline so
                        // we never claim success the fetch didn't actually achieve.
                        if model.viewMode == .telemetry || !model.isOffline {
                            model.flashBanner("Repos refreshed")
                        }
                    }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
                .foregroundStyle(Theme.text2)
                .help(model.viewMode == .telemetry ? "Re-read telemetry files" : "Re-pull /focus-5.json")

                Button {
                    narrowWindow()
                } label: {
                    Text("「」")
                        .font(.system(size: 13))
                        .fixedSize()
                }
                .buttonStyle(.borderless)
                .foregroundStyle(Theme.text2)
                .help("Snap to narrowest width (keeps height)")

                if model.viewMode != .telemetry && model.isOffline {
                    Button {
                        Task { await model.startServer() }
                    } label: {
                        Image(systemName: model.isStartingServer ? "hourglass" : "play.circle")
                    }
                    .buttonStyle(.borderless)
                    .foregroundStyle(Theme.accent)
                    .disabled(model.isStartingServer)
                    .help("Start rebalance serve")
                }

                Spacer(minLength: 0)
            }

            // Row 2 — status line. Wrapped down off the tab row so the panel can
            // shrink to ~180 wide: count/updated on the left (truncates first),
            // the health light pinned right.
            HStack(spacing: Theme.Space.s) {
                if model.viewMode == .telemetry {
                    if let url = model.telemetryFileURL {
                        Text(url.lastPathComponent)
                            .font(Theme.caption).foregroundStyle(Theme.text2)
                            .lineLimit(1).truncationMode(.middle)
                        if !model.telemetryEntries.isEmpty {
                            Text("· \(model.telemetryEntries.count)")
                                .font(Theme.caption).foregroundStyle(Theme.text3)
                        }
                    } else {
                        Text("No file selected")
                            .font(Theme.caption).foregroundStyle(Theme.text3)
                    }
                } else {
                    Text("\(model.roster.count) repos")
                        .font(Theme.caption).foregroundStyle(Theme.text2).fixedSize()
                    if !model.lastUpdatedAgo.isEmpty {
                        Text("· \(model.lastUpdatedAgo)")
                            .font(Theme.caption).foregroundStyle(Theme.text3)
                            .lineLimit(1).truncationMode(.tail)
                    }
                    if model.isStale {
                        Text("⚠").font(Theme.caption).foregroundStyle(Theme.diffUpdate)
                            .help("Roster is stale")
                    }
                    if model.showingCache {
                        Text("cached").font(Theme.caption).foregroundStyle(Theme.diffUpdate)
                            .help("Showing cached roster from \(model.cachedAgo)")
                    } else if model.isOffline {
                        Text("offline").font(Theme.caption).foregroundStyle(Theme.diffRemove)
                    }
                }
                Spacer(minLength: Theme.Space.xs)
                healthLight
            }
        }
        .padding(Theme.Space.m)
    }

    /// Snap the floating panel to its minimum width, leaving height + position
    /// otherwise as-is (the bottom-left corner stays put, the right edge moves in).
    private func narrowWindow() {
        guard let panel = NSApp.windows.first(where: { $0 is FloatingPanel }) else { return }
        var frame = panel.frame
        frame.size.width = panel.minSize.width   // height unchanged
        panel.setFrame(frame, display: true, animate: true)
    }

    /// The roster/telemetry health light — a dirty-count + tinted dot, adapting to
    /// the active tab. Lives on the status row (row 2) so it no longer widens the
    /// tab row.
    @ViewBuilder private var healthLight: some View {
        if model.viewMode == .telemetry {
            if !model.telemetryEntries.isEmpty {
                let nonGreen = model.telemetryEntries.filter { $0.health != .green }.count
                healthBadge(count: nonGreen,
                            tint: RosterHealth.tint(dirty: nonGreen, total: model.telemetryEntries.count),
                            help: "\(nonGreen) of \(model.telemetryEntries.count) signals need attention")
            }
        } else if !model.roster.isEmpty {
            let dirty = model.roster.filter(\.isDirty).count
            healthBadge(count: dirty,
                        tint: RosterHealth.tint(dirty: dirty, total: model.roster.count),
                        help: "\(dirty) of \(model.roster.count) roster repos dirty")
                .accessibilityLabel("Status: \(dirty) of \(model.roster.count) roster repos dirty")
        }
    }

    private func healthBadge(count: Int, tint: Color, help: String) -> some View {
        HStack(spacing: 5) {
            Text("\(count)")
                .font(Theme.caption).foregroundStyle(Theme.text2)
            Circle().fill(tint).frame(width: 11, height: 11)
        }
        .fixedSize()
        .help(help)
    }

    // MARK: Content

    @ViewBuilder private var content: some View {
        if model.viewMode == .telemetry {
            telemetryContent
        } else {
            switch model.loadState {
            case .idle, .loading:
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            case .failed(let message):
                VStack(spacing: Theme.Space.m) {
                    emptyState(icon: "bolt.horizontal.circle",
                               title: "Can't reach the Focus 5 server",
                               detail: message)
                        .frame(maxHeight: .infinity)
                    startServerButton
                        .padding(.bottom, Theme.Space.xl)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            case .loaded where model.roster.isEmpty:
                ScrollView {
                    LazyVStack(spacing: Theme.Space.s) {
                        emptyState(icon: "tray",
                                   title: model.isDirtyView ? "Nothing at risk" : "No active repos found",
                                   detail: "The server roster is empty. Build it server-side (open /focus-5 in the browser or run a Focus 5 sync), then Refresh here to re-pull.")
                            .frame(minHeight: 160)
                        bottomSections
                    }
                    .padding(Theme.Space.m)
                }
            case .loaded:
                ScrollView {
                    LazyVStack(spacing: Theme.Space.s) {
                        ForEach(Array(model.roster.enumerated()), id: \.element.id) { index, card in
                            RepoCardView(card: card, darker: !index.isMultiple(of: 2))
                        }
                        if !model.offRoster.isEmpty {
                            OffRosterFooter(warnings: model.offRoster)
                        }
                        bottomSections
                    }
                    .padding(Theme.Space.m)
                }
            }
        }
    }

    @ViewBuilder private var telemetryContent: some View {
        if model.telemetryFileURL == nil {
            VStack(spacing: Theme.Space.m) {
                Image(systemName: "doc.badge.plus")
                    .font(.system(size: 22)).foregroundStyle(Theme.text3)
                Text("No file selected")
                    .font(Theme.bodyMed).foregroundStyle(Theme.text)
                Text("Choose a .json file to display health signals.")
                    .font(Theme.monoSmall).foregroundStyle(Theme.text3)
                    .multilineTextAlignment(.center)
                Button("Select Telemetry File…") { model.openFilePicker() }
                    .buttonStyle(.borderedProminent)
                    .tint(Theme.accent)
            }
            .padding()
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else if let err = model.telemetryLoadError {
            emptyState(icon: "exclamationmark.triangle",
                       title: "Can't read telemetry file",
                       detail: err)
        } else if model.telemetryEntries.isEmpty {
            emptyState(icon: "waveform.path.ecg",
                       title: "No signals",
                       detail: "The selected file has no entries.")
        } else {
            ScrollView {
                LazyVStack(spacing: Theme.Space.s) {
                    ForEach(Array(model.telemetryEntries.enumerated()), id: \.offset) { index, entry in
                        TelemetryRowView(entry: entry, darker: !index.isMultiple(of: 2))
                    }
                }
                .padding(Theme.Space.m)
            }
        }
    }

    private func emptyState(icon: String, title: String, detail: String) -> some View {
        VStack(spacing: Theme.Space.s) {
            Image(systemName: icon).font(.system(size: 22)).foregroundStyle(Theme.text3)
            Text(title).font(Theme.bodyMed).foregroundStyle(Theme.text)
            Text(detail)
                .font(Theme.monoSmall)
                .foregroundStyle(Theme.text3)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    /// Starts the local `rebalance serve`, with an in-flight spinner + error.
    @ViewBuilder var startServerButton: some View {
        VStack(spacing: Theme.Space.xs) {
            Button {
                Task { await model.startServer() }
            } label: {
                HStack(spacing: 6) {
                    if model.isStartingServer {
                        ProgressView().controlSize(.small)
                        Text("Starting server…")
                    } else {
                        Image(systemName: "play.circle.fill")
                        Text("Start rebalance serve")
                    }
                }
            }
            .buttonStyle(.borderedProminent)
            .tint(Theme.accent)
            .disabled(model.isStartingServer)

            if let err = model.startError {
                Text(err)
                    .font(Theme.monoSmall)
                    .foregroundStyle(Theme.diffRemove)
                    .multilineTextAlignment(.center)
            }
        }
    }
}

// MARK: - Repo card (collapsible)

struct RepoCardView: View {
    let card: RepoCard
    var darker: Bool = false        // zebra stripe — alternate rows use elevatedAlt
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            // Row 1 — position badge + actions (Open / status / chevron), so the
            // controls share one slim row regardless of how wide the name is.
            HStack(spacing: Theme.Space.s) {
                KeyCap(text: "#\(card.position)")
                Spacer(minLength: Theme.Space.s)
                Button("Open ↗") { VSCodeLauncher.launch(repoPath: card.localPath, fallbackURL: card.vscodeUrl) }
                    .buttonStyle(.borderless)
                    .font(Theme.caption)
                    .foregroundStyle(Theme.accent)
                    .fixedSize()
                    .help("Open \(card.repoName) in VS Code")
                StatusDot(isDirty: card.isDirty, healthAvailable: card.healthAvailable)
                Image(systemName: expanded ? "chevron.down" : "chevron.right")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(Theme.text3)
            }

            // Row 2 — repo name, full width + prominent; wraps in the narrow panel
            // instead of competing with the badge/controls for horizontal space.
            Text(card.repoName)
                .font(Theme.display).foregroundStyle(Theme.text)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)

            // Rank reason / last-commit line — smaller + greyer (a caption, not body).
            Text(card.rankReason)
                .font(.system(size: 11)).foregroundStyle(Theme.text3)
                .lineLimit(2).fixedSize(horizontal: false, vertical: true)

            HStack(spacing: Theme.Space.m) {
                if let branch = card.branch { GroupTag(name: branch) }
                Text("↑\(card.ahead) ↓\(card.behind)")
                Text("\(card.modifiedCount)M \(card.untrackedCount)U")
                Spacer(minLength: 0)
            }
            .font(Theme.monoSmall).foregroundStyle(Theme.text3)

            if expanded { detail }
        }
        .padding(Theme.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(darker ? Theme.elevatedAlt : Theme.elevated, in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous)
                .strokeBorder(Theme.separator, lineWidth: 1)
        )
        .contentShape(Rectangle())
        .onTapGesture { withAnimation(Theme.spring) { expanded.toggle() } }
    }

    // Expanded sub-sections — mirrors the web card.
    @ViewBuilder private var detail: some View {
        Divider().overlay(Theme.separator).padding(.vertical, 2)

        CardSection(label: "Tree health") {
            HStack(spacing: 6) {
                StatusDot(isDirty: card.isDirty, healthAvailable: card.healthAvailable)
                Text(healthText).font(Theme.body).foregroundStyle(Theme.text2)
            }
            if let branch = card.branch {
                Text("\(branch) · ↑\(card.ahead) ↓\(card.behind)")
                    .font(Theme.monoSmall).foregroundStyle(Theme.text3)
            }
        }

        CardSection(label: "Newest PR") {
            if let pr = card.newestPr {
                Button("#\(pr.number) \(pr.title)") { open(pr.htmlUrl) }
                    .buttonStyle(.borderless)
                    .font(Theme.body).foregroundStyle(Theme.accent)
                    .multilineTextAlignment(.leading)
                Text("(\(pr.isMerged ? "merged" : pr.isDraft ? "draft" : pr.state))")
                    .font(Theme.monoSmall).foregroundStyle(Theme.text3)
            } else {
                Text(prFallback).font(Theme.body).foregroundStyle(Theme.text3)
            }
        }

        CardSection(label: "Recent activity") {
            if card.recentActivity.isEmpty {
                Text("no recent commits").font(Theme.body).foregroundStyle(Theme.text3)
            } else {
                ForEach(card.recentActivity) { c in
                    VStack(alignment: .leading, spacing: 1) {
                        Text(c.subject).font(Theme.body).foregroundStyle(Theme.text2).lineLimit(2)
                        Text("\(c.sha) · \(RelTime.ago(c.committedAt))")
                            .font(Theme.monoSmall).foregroundStyle(Theme.text3)
                    }
                }
            }
        }
    }

    private var healthText: String {
        guard card.healthAvailable else { return "unavailable" }
        return card.isDirty ? "\(card.modifiedCount) modified, \(card.untrackedCount) untracked" : "clean"
    }

    private var prFallback: String {
        if card.repoFullName != nil { return "no open PR synced yet" }
        if card.remoteUrl != nil { return "non-GitHub remote" }
        return "no remote configured"
    }

    private func open(_ urlString: String) {
        if let url = URL(string: urlString) { NSWorkspace.shared.open(url) }
    }
}

/// Labeled section block inside the expanded card.
struct CardSection<Content: View>: View {
    let label: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label.uppercased())
                .font(Theme.caption).foregroundStyle(Theme.text3)
                .tracking(0.5)
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 4)
    }
}

// MARK: - Telemetry row

struct TelemetryRowView: View {
    let entry: TelemetryEntry
    var darker: Bool = false

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Space.s) {
            HealthDot(health: entry.health)
                .padding(.top, 3)
            VStack(alignment: .leading, spacing: 2) {
                Text(entry.title)
                    .font(Theme.bodyMed).foregroundStyle(Theme.text)
                Text(entry.description)
                    .font(Theme.body).foregroundStyle(Theme.text2)
                    .lineLimit(3).fixedSize(horizontal: false, vertical: true)
                if let ts = entry.updatedAt {
                    Text(RelTime.ago(ts))
                        .font(Theme.monoSmall).foregroundStyle(Theme.text3)
                }
            }
        }
        .padding(Theme.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(darker ? Theme.elevatedAlt : Theme.elevated,
                    in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous)
                .strokeBorder(Theme.separator, lineWidth: 1)
        )
    }
}

// MARK: - Apple Reminders (section A)

/// Section A — the 10 most-recent active tasks from the default Apple Reminders
/// list, read+written LIVE via EventKit (see `RemindersStore`). Branches on the
/// TCC authorization state: an enable button before the grant, a System-Settings
/// hint if denied, the bounded scrollable task list once granted. Each row's
/// checkbox completes the reminder (the only mutation in v1).
struct RemindersSection: View {
    let store: RemindersStore

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.xs) {
            Text("REMINDERS")
                .font(Theme.caption).foregroundStyle(Theme.text3).tracking(0.5)
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, Theme.Space.s)
    }

    @ViewBuilder private var content: some View {
        switch store.access {
        case .notDetermined:
            Button {
                // A non-activating accessory panel must come forward so the
                // system TCC prompt is presented frontmost.
                NSApp.activate(ignoringOtherApps: true)
                Task { await store.requestAccess() }
            } label: {
                Label("Enable Apple Reminders", systemImage: "checklist")
            }
            .buttonStyle(.borderless)
            .font(Theme.body).foregroundStyle(Theme.accent)
            .help("Grant Reminders access to show your default list here")

        case .denied:
            Text("Reminders access is off. Enable it in System Settings ▸ Privacy & Security ▸ Reminders, then Refresh.")
                .font(Theme.monoSmall).foregroundStyle(Theme.text3)
                .fixedSize(horizontal: false, vertical: true)

        case .granted:
            if store.items.isEmpty {
                Text("No active reminders.")
                    .font(Theme.body).foregroundStyle(Theme.text3)
                    .padding(.vertical, 2)
            } else {
                // Inline (no inner scroll) so the section sizes to its content and
                // flows within the single panel scroll — liquid, no reserved slab.
                VStack(spacing: 4) {
                    ForEach(store.items, id: \.calendarItemIdentifier) { reminder in
                        ReminderRow(reminder: reminder, store: store)
                    }
                }
            }
            if let err = store.loadError {
                Text(err)
                    .font(Theme.monoSmall).foregroundStyle(Theme.diffRemove)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

/// One reminder: a tap-to-complete checkbox + title (+ relative due date). The
/// checkbox is the single write surface — completing drops the row on re-read.
struct ReminderRow: View {
    let reminder: EKReminder
    let store: RemindersStore

    /// True during the ~2s check-then-fade beat after the user completes it.
    private var isCompleting: Bool {
        store.completingIDs.contains(reminder.calendarItemIdentifier)
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Space.s) {
            Button {
                Task { await store.complete(reminder) }
            } label: {
                Image(systemName: isCompleting ? "circle.inset.filled" : "circle")
                    .font(.system(size: 13))
                    .foregroundStyle(isCompleting ? Theme.accent : Theme.text3)
            }
            .buttonStyle(.borderless)
            .disabled(isCompleting)
            .help("Mark complete")

            VStack(alignment: .leading, spacing: 1) {
                Text(reminder.title ?? "(untitled)")
                    .font(Theme.body).foregroundStyle(isCompleting ? Theme.text3 : Theme.text)
                    .strikethrough(isCompleting)
                    .lineLimit(2).fixedSize(horizontal: false, vertical: true)
                if let due = dueText {
                    Text(due).font(Theme.monoSmall).foregroundStyle(Theme.text3)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(Theme.Space.s)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.elevated, in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
        .opacity(isCompleting ? 0.6 : 1)
        .animation(.easeInOut(duration: 0.2), value: isCompleting)
    }

    /// "due <relative>" for a dated reminder (past or future), else nil.
    private var dueText: String? {
        guard let comps = reminder.dueDateComponents,
              let date = Calendar.current.date(from: comps) else { return nil }
        let f = RelativeDateTimeFormatter()
        f.unitsStyle = .short
        return "due \(f.localizedString(for: date, relativeTo: Date()))"
    }
}

// MARK: - Bottom note (vault focus5.md)

/// Free-form note pulled from the operator's Obsidian vault (`focus5.md`), shown
/// as the last card in the roster scroll (Focus 5 / Dirty Five). Renders light
/// markdown (headings, bullets, inline emphasis/links); falls back to a one-line
/// hint when the vault has no such note. Content-hugging — it takes only the
/// vertical space its text needs and scrolls with the roster above it, so it
/// never reserves a fixed slab of the panel.
struct Focus5NoteView: View {
    let exists: Bool
    let content: String

    private var hasText: Bool {
        !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.xs) {
            Text("NOTE")
                .font(Theme.caption).foregroundStyle(Theme.text3).tracking(0.5)
            if exists && hasText {
                let lines = content.split(separator: "\n", omittingEmptySubsequences: false)
                ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                    MarkdownLine(raw: line)
                }
            } else {
                Text("To show a text file here, add a doc called focus5.md into your Obsidian vault.")
                    .font(Theme.body)
                    .foregroundStyle(Theme.text3)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Space.s)
            }
        }
        .padding(Theme.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.elevated, in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous)
                .strokeBorder(Theme.separator, lineWidth: 1)
        )
    }
}

/// One source line of the note. Recognizes `#`/`##` headings and `-`/`*`/`+`
/// bullets; everything else is body text. Inline emphasis/links route through
/// AttributedString's markdown parser (block syntax stays literal, by design).
private struct MarkdownLine: View {
    let raw: String
    init(raw: Substring) { self.raw = String(raw) }

    var body: some View {
        if raw.trimmingCharacters(in: .whitespaces).isEmpty {
            Spacer().frame(height: Theme.Space.xs)
        } else if let heading = heading(raw) {
            Text(inline(heading.text))
                .font(.system(size: heading.level == 1 ? 16 : 14, weight: .semibold))
                .foregroundStyle(Theme.text)
                .fixedSize(horizontal: false, vertical: true)
        } else if let bullet = bullet(raw) {
            HStack(alignment: .top, spacing: 6) {
                Text("•").foregroundStyle(Theme.text3)
                Text(inline(bullet)).foregroundStyle(Theme.text2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .font(Theme.body)
        } else {
            Text(inline(raw))
                .font(Theme.body)
                .foregroundStyle(Theme.text2)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    /// Inline-only markdown → AttributedString (bold/italic/code/links). Falls back
    /// to plain text if the line isn't valid markdown.
    private func inline(_ s: String) -> AttributedString {
        (try? AttributedString(
            markdown: s,
            options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        )) ?? AttributedString(s)
    }

    private func heading(_ s: String) -> (level: Int, text: String)? {
        let t = s.drop(while: { $0 == " " })
        guard t.first == "#" else { return nil }
        let hashes = t.prefix(while: { $0 == "#" })
        let rest = t.dropFirst(hashes.count)
        guard rest.first == " " else { return nil }   // "# foo", not "#foo"/"#tag"
        return (min(hashes.count, 2), String(rest).trimmingCharacters(in: .whitespaces))
    }

    private func bullet(_ s: String) -> String? {
        let t = s.drop(while: { $0 == " " })
        for marker in ["- ", "* ", "+ "] where t.hasPrefix(marker) {
            return String(t.dropFirst(2))
        }
        return nil
    }
}

// MARK: - Off-roster footer (collapsible)

struct OffRosterFooter: View {
    let warnings: [OffRosterWarning]
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.xs) {
            HStack(spacing: 6) {
                Image(systemName: expanded ? "chevron.down" : "chevron.right")
                    .font(.system(size: 10, weight: .semibold)).foregroundStyle(Theme.text3)
                Text("\(warnings.count) outside top 5 need attention")
                    .font(Theme.caption).foregroundStyle(Theme.text2)
                Spacer(minLength: 0)
            }
            .contentShape(Rectangle())
            .onTapGesture { withAnimation(Theme.spring) { expanded.toggle() } }

            if expanded {
                ForEach(warnings) { w in
                    HStack(spacing: Theme.Space.s) {
                        StatusDot(isDirty: w.isDirty, healthAvailable: true)
                        Text(w.repoName).font(Theme.body).foregroundStyle(Theme.text).lineLimit(1)
                        Spacer(minLength: 0)
                        Text("↑\(w.ahead) · \(w.modifiedCount)M \(w.untrackedCount)U")
                            .font(Theme.monoSmall).foregroundStyle(Theme.text3)
                    }
                }
            }
        }
        .padding(Theme.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.hover, in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
    }
}
