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
    let onHide: () -> Void
    @State private var showingResetPinsConfirm = false
    @State private var promptLogFilter = ""

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: Theme.Radius.window, style: .continuous)
                .fill(.ultraThinMaterial)
            RoundedRectangle(cornerRadius: Theme.Radius.window, style: .continuous)
                .fill(Theme.glassFill)
            VStack(spacing: 0) {
                header
                Divider().overlay(Theme.separator)
                content
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.window, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: Theme.Radius.window, style: .continuous)
                .strokeBorder(Theme.glassEdge, lineWidth: 0.5)
        }
        .shadow(color: .black.opacity(0.24), radius: 30, x: 0, y: 18)
        // GH-187 REGRESSION GUARD: no top gutter here. FirstMouseHostingView
        // suppresses the hidden titlebar's 28pt safe area; adding the old 6pt
        // all-edge padding back would recreate a visible gap even though the
        // actual NSPanel frame is correctly flush with the menu bar. Keep only
        // the side/bottom gutters needed by the glass shadow.
        .padding(.horizontal, 6)
        .padding(.bottom, 6)
        .background(Color.clear)
        .overlay(alignment: .bottom) {
            if let banner = model.banner {
                TopBanner(text: banner)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .zIndex(1)
            }
        }
        .animation(.easeInOut(duration: 0.35), value: model.banner)
    }

    // MARK: Bottom sections (Reminders + Note)

    /// The bottom drawer sections — Apple Reminders, Obsidian Reminders, then the
    /// focus5.md note — rendered inline at the end of the single roster scroll so
    /// they size to their content (liquid) and flow right under the cards with no
    /// dead space. Non-telemetry only; the note appears once its first fetch lands.
    @ViewBuilder private var bottomSections: some View {
        RemindersSection(store: model.reminders)
        ObsidianRemindersSection(store: model.obsidianReminders)
        if model.noteLoaded {
            Focus5NoteView(exists: model.noteExists, content: model.noteContent)
        }
    }

    // MARK: Header

    private var header: some View {
        VStack(spacing: Theme.Space.s) {
            HStack(spacing: Theme.Space.s) {
                ToolbarIconButton(systemName: "xmark", isDestructive: true, action: onHide)
                    .help("Hide panel")
                    .accessibilityLabel("Hide panel")

                ModeSegmentedControl(selected: model.viewMode, onSelect: selectMode)

                Spacer(minLength: Theme.Space.xs)

                ToolbarIconButton(systemName: "arrow.clockwise", action: refreshPanel)
                    .help(refreshHelpText)

                ToolbarIconButton(systemName: "arrow.up.left.and.arrow.down.right", action: togglePanelWidth)
                    .help("Toggle panel width")
            }

            HStack(spacing: Theme.Space.s) {
                if model.viewMode == .telemetry {
                    telemetryStatus
                    Spacer(minLength: Theme.Space.xs)
                    telemetryBadge
                } else if model.viewMode == .promptLog {
                    promptLogStatus
                    Spacer(minLength: Theme.Space.xs)
                } else {
                    rosterStatus
                    Spacer(minLength: Theme.Space.xs)
                    rosterAttentionBadge
                }
            }
        }
        .padding(.horizontal, Theme.Space.l)
        .padding(.top, Theme.Space.l)
        .padding(.bottom, Theme.Space.m)
    }

    // GH-121 Phase 2: names both the file AND its kind, so which viewer mode is
    // active ("markdown" text vs. "signals" structured) is legible at a glance —
    // not just the filename, which doesn't reliably signal kind at small sizes /
    // truncation. `telemetryIsMarkdown` is the same single-source-of-truth
    // discriminator the load/render branches use, so this can't drift from them.
    @ViewBuilder private var telemetryStatus: some View {
        if let url = model.telemetryFileURL {
            Text(url.lastPathComponent)
                .font(.system(size: 12.5, weight: .semibold))
                .foregroundStyle(Theme.text2)
                .lineLimit(1)
                .truncationMode(.middle)
            if model.telemetryIsMarkdown {
                Text("· markdown")
                    .font(.system(size: 12.5))
                    .foregroundStyle(Theme.text3)
            } else if model.telemetryLoadError == nil {
                Text(model.telemetryEntries.isEmpty
                     ? "· signals"
                     : "· signals · \(model.telemetryEntries.count)")
                    .font(.system(size: 12.5))
                    .foregroundStyle(Theme.text3)
            }
        } else {
            Text("No file selected")
                .font(.system(size: 12.5))
                .foregroundStyle(Theme.text3)
        }
    }

    @ViewBuilder private var promptLogStatus: some View {
        if let url = model.promptLogFileURL {
            Text(url.lastPathComponent)
                .font(.system(size: 12.5, weight: .semibold))
                .foregroundStyle(Theme.text2)
                .lineLimit(1)
                .truncationMode(.middle)
            if model.promptLogLoadError == nil {
                Text("· \(model.promptLogEntries.count) prompts · \(model.pinnedPromptLogEntries.count) pinned")
                    .font(.system(size: 12.5))
                    .foregroundStyle(Theme.text3)
            }
        } else {
            Text("No file selected")
                .font(.system(size: 12.5))
                .foregroundStyle(Theme.text3)
        }
    }

    private var rosterStatus: some View {
        HStack(spacing: 6) {
            Text("\(model.roster.count) repos")
                .font(.system(size: 12.5, weight: .semibold))
                .foregroundStyle(Theme.text)
                .fixedSize()
            if !model.lastUpdatedAgo.isEmpty {
                Text("·")
                    .font(.system(size: 12.5))
                    .foregroundStyle(Theme.text3)
                Text("synced \(model.lastUpdatedAgo)")
                    .font(.system(size: 12.5))
                    .foregroundStyle(Theme.text3)
                    .lineLimit(1)
                    .truncationMode(.tail)
            }
            if model.showingCache {
                Text("· cached")
                    .font(.system(size: 12.5))
                    .foregroundStyle(Theme.attention)
                    .help("Showing cached roster from \(model.cachedAgo)")
            } else if model.isOffline {
                Text("· offline")
                    .font(.system(size: 12.5))
                    .foregroundStyle(Theme.diffRemove)
            } else if model.isStale {
                Text("· stale")
                    .font(.system(size: 12.5))
                    .foregroundStyle(Theme.attention)
                    .help("Roster is stale")
            }
        }
    }

    @ViewBuilder private var telemetryBadge: some View {
        if !model.telemetryEntries.isEmpty {
            let nonGreen = model.telemetryEntries.filter { $0.health != .green }.count
            statusBadge(
                count: nonGreen,
                tint: nonGreen == 0 ? Theme.diffAdd : Theme.attention,
                help: "\(nonGreen) of \(model.telemetryEntries.count) signals need attention"
            )
        }
    }

    private var rosterAttentionBadge: some View {
        let attentionCount = model.offRoster.count
        return statusBadge(
            count: attentionCount,
            tint: attentionCount == 0 ? Theme.diffAdd : Theme.attention,
            help: attentionCount == 0
                ? "No off-roster repos currently need attention"
                : "\(attentionCount) off-roster repos need attention"
        )
        .accessibilityLabel(attentionCount == 0 ? "No repos need attention" : "\(attentionCount) repos need attention")
    }

    private var refreshHelpText: String {
        switch model.viewMode {
        case .telemetry: return "Re-read telemetry files"
        case .promptLog: return "Re-read prompt log file"
        default: return "Re-pull /focus-5.json"
        }
    }

    private func refreshPanel() {
        Task {
            await model.refresh()
            if model.viewMode == .telemetry || !model.isOffline {
                model.flashBanner("Repos refreshed")
            }
        }
    }

    private func selectMode(_ mode: ViewMode) {
        model.viewMode = mode
        switch mode {
        case .focus5:
            Task { await model.setMode(dirty: false) }
        case .dirtyFive:
            Task { await model.setMode(dirty: true) }
        case .telemetry:
            model.refreshTelemetry()
        case .promptLog:
            model.refreshPromptLog()
        }
    }

    /// Toggle between the reference width (340) and a bounded wider mode for
    /// longer repo names / telemetry descriptions.
    private func togglePanelWidth() {
        guard let panel = NSApp.windows.first(where: { $0 is FloatingPanel }) else { return }
        var frame = panel.frame
        frame.size.width = frame.width < 380 ? 420 : 340
        panel.setFrame(frame, display: true, animate: true)
    }

    private func statusBadge(count: Int, tint: Color, help: String) -> some View {
        HStack(spacing: 7) {
            Text("\(count)")
                .font(.system(size: 12.5, weight: .semibold))
                .foregroundStyle(Theme.text)
            Circle()
                .fill(tint)
                .frame(width: 10, height: 10)
        }
        .fixedSize()
        .help(help)
    }

    // MARK: Content

    @ViewBuilder private var content: some View {
        if model.viewMode == .telemetry {
            telemetryContent
        } else if model.viewMode == .promptLog {
            promptLogContent
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
                        if let banner = model.dirtyBanner {
                            DirtyBannerView(warning: banner)
                        }
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
                Text("Choose a .json file for health signals, or a .md file for notes.")
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
        } else if model.telemetryIsMarkdown {
            // GH-121 Phase 2 large-file safety: `Focus5Model.telemetryMarkdownByteCeiling`
            // (1MB, in `refreshTelemetry()`) is the actual bound here — `text` below
            // is never larger than that ceiling, since the synchronous
            // `Data(contentsOf:)` read is already truncated (byte-safe, never
            // mid-codepoint) BEFORE this view ever sees the string. So this
            // ScrollView + MarkdownBody render is bounded by the same 1MB cap that
            // already bounds the read: at most a few thousand short lines, which is
            // the exact rendering path already shipped (unbounded) for the vault
            // focus5.md note. No additional chunking/pagination/lazy-loading is
            // needed for Phase 2 — the ceiling IS the safety mechanism end-to-end.
            if let text = model.telemetryMarkdownContent,
               !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.Space.xs) {
                        MarkdownBody(content: text)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(Theme.Space.m)
                }
            } else {
                emptyState(icon: "doc.text",
                           title: "Empty file",
                           detail: "The selected file has no content.")
            }
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

    @ViewBuilder private var promptLogContent: some View {
        if model.promptLogFileURL == nil {
            VStack(spacing: Theme.Space.m) {
                Image(systemName: "text.bubble")
                    .font(.system(size: 22)).foregroundStyle(Theme.text3)
                Text("No file selected")
                    .font(Theme.bodyMed).foregroundStyle(Theme.text)
                Text("Choose the CLIO-rendered prompt log Markdown file.")
                    .font(Theme.monoSmall).foregroundStyle(Theme.text3)
                    .multilineTextAlignment(.center)
                Button("Select Prompt Log File…") { model.openPromptLogFilePicker() }
                    .buttonStyle(.borderedProminent)
                    .tint(Theme.accent)
            }
            .padding()
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else if let err = model.promptLogLoadError {
            emptyState(icon: "exclamationmark.triangle",
                       title: "Can't read prompt log file",
                       detail: err)
        } else if model.promptLogEntries.isEmpty {
            emptyState(icon: "text.bubble",
                       title: "No prompts yet",
                       detail: "The selected file has no entries.")
        } else {
            // Filter field + pinned section both live OUTSIDE the ScrollView so
            // they're a true fixed header (like a sticky nav bar) — only the
            // feed below scrolls. Putting the pinned section inside the same
            // LazyVStack/ScrollView (the original bug) just made it scroll away
            // with everything else.
            VStack(alignment: .leading, spacing: 0) {
                promptLogFilterField
                    .padding(.horizontal, Theme.Space.m)
                    .padding(.top, Theme.Space.m)
                    .padding(.bottom, Theme.Space.s)

                if !filteredPinnedEntries.isEmpty {
                    VStack(alignment: .leading, spacing: Theme.Space.s) {
                        pinnedSectionHeader
                        ForEach(filteredPinnedEntries) { entry in
                            PromptLogRowView(entry: entry, isPinned: true, openInfo: model.vscodeOpenInfo(forRepoName: entry.repo)) {
                                model.togglePin(entry)
                            }
                        }
                    }
                    .padding(.horizontal, Theme.Space.m)
                    .padding(.bottom, Theme.Space.m)
                    Divider().overlay(Theme.separator)
                }

                if filteredPinnedEntries.isEmpty && filteredUnpinnedEntries.isEmpty {
                    emptyState(icon: "magnifyingglass",
                               title: "No matches",
                               detail: "No prompts from a repo matching \"\(promptLogFilter)\".")
                } else {
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: Theme.Space.s) {
                            ForEach(Array(filteredUnpinnedEntries.enumerated()), id: \.element.id) { index, entry in
                                PromptLogRowView(entry: entry, isPinned: false, darker: !index.isMultiple(of: 2), openInfo: model.vscodeOpenInfo(forRepoName: entry.repo)) {
                                    model.togglePin(entry)
                                }
                            }
                        }
                        .padding(Theme.Space.m)
                    }
                }
            }
        }
    }

    // Text field filtering the prompt log feed (both pinned and unpinned) by
    // repo name — case-insensitive substring match, empty string shows all.
    private var promptLogFilterField: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 12))
                .foregroundStyle(Theme.text3)
            TextField("Filter by repo…", text: $promptLogFilter)
                .textFieldStyle(.plain)
                .font(Theme.body)
                .foregroundStyle(Theme.text)
            if !promptLogFilter.isEmpty {
                Button { promptLogFilter = "" } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.text3)
                }
                .buttonStyle(.plain)
                .help("Clear filter")
            }
        }
        .padding(.horizontal, Theme.Space.s)
        .padding(.vertical, 6)
        .background(Theme.elevated, in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
                .strokeBorder(Theme.separator, lineWidth: 0.5)
        )
    }

    private var filteredPinnedEntries: [PromptLogEntry] {
        filterByRepo(model.pinnedPromptLogEntries)
    }
    private var filteredUnpinnedEntries: [PromptLogEntry] {
        filterByRepo(model.unpinnedPromptLogEntries)
    }
    private func filterByRepo(_ entries: [PromptLogEntry]) -> [PromptLogEntry] {
        let needle = promptLogFilter.trimmingCharacters(in: .whitespaces)
        guard !needle.isEmpty else { return entries }
        return entries.filter { $0.repo.localizedCaseInsensitiveContains(needle) }
    }

    // "PINNED (n/5)" caption + a reset-all control that reuses the header's
    // refresh glyph — gated behind a confirmation dialog since it's destructive
    // to the operator's manually-curated anchor list, unlike the header refresh.
    private var pinnedSectionHeader: some View {
        HStack(spacing: 6) {
            Text("PINNED (\(model.pinnedPromptLogEntries.count)/\(Focus5Model.maxPinnedPromptLogEntries))")
                .font(Theme.caption).foregroundStyle(Theme.text3).tracking(0.5)
            Spacer(minLength: 0)
            Button { showingResetPinsConfirm = true } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(Theme.text3)
            }
            .buttonStyle(.plain)
            .help("Release all pins")
        }
        .confirmationDialog(
            "Release all pins?",
            isPresented: $showingResetPinsConfirm,
            titleVisibility: .visible
        ) {
            Button("Release All Pins", role: .destructive) { model.resetAllPromptLogPins() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This removes all \(model.pinnedPromptLogEntries.count) pinned entries. This can't be undone.")
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

// MARK: - Header controls

private struct ToolbarIconButton: View {
    let systemName: String
    var isDestructive = false
    let action: () -> Void

    @State private var hovered = false

    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 13, weight: .semibold))
                .frame(width: 16, height: 16)
                .frame(width: 28, height: 28)
                .contentShape(RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous))
        }
        .buttonStyle(.plain)
        .foregroundStyle(hovered ? foregroundHover : Theme.text2)
        .background(hovered ? backgroundHover : Color.clear,
                    in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous))
        .onHover { hovered = $0 }
    }

    private var backgroundHover: Color {
        isDestructive ? Theme.destructiveHover : Theme.hover
    }

    private var foregroundHover: Color {
        isDestructive ? Theme.destructiveText : Theme.text
    }
}

private struct ModeSegmentedControl: View {
    let selected: ViewMode
    let onSelect: (ViewMode) -> Void

    var body: some View {
        HStack(spacing: 0) {
            SegmentedModeButton(systemName: "scope",
                                label: "Focus",
                                isSelected: selected == .focus5) { onSelect(.focus5) }
            divider
            SegmentedModeButton(systemName: "paintbrush",
                                label: "Tidy",
                                isSelected: selected == .dirtyFive) { onSelect(.dirtyFive) }
            divider
            SegmentedModeButton(systemName: "chart.bar",
                                label: "Stats",
                                isSelected: selected == .telemetry) { onSelect(.telemetry) }
            divider
            SegmentedModeButton(systemName: "text.bubble",
                                label: "Prompts",
                                isSelected: selected == .promptLog) { onSelect(.promptLog) }
        }
        .padding(2)
        .background(Theme.hover, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .strokeBorder(Theme.separator, lineWidth: 0.5)
        )
    }

    private var divider: some View {
        Rectangle()
            .fill(Theme.separator)
            .frame(width: 0.5, height: 16)
    }
}

private struct SegmentedModeButton: View {
    let systemName: String
    let label: String
    let isSelected: Bool
    let action: () -> Void

    @State private var hovered = false

    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 13, weight: .semibold))
                .frame(width: 30, height: 26)
                .contentShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
        }
        .buttonStyle(.plain)
        .foregroundStyle(isSelected ? Theme.text : Theme.text2)
        .background(background,
                    in: RoundedRectangle(cornerRadius: 7, style: .continuous))
        .help(label)
        .accessibilityLabel(label)
        .onHover { hovered = $0 }
    }

    private var background: Color {
        if isSelected { return Theme.hover }
        return hovered ? Theme.hover : .clear
    }
}

// MARK: - Repo card (collapsible)

struct RepoCardView: View {
    let card: RepoCard
    var darker: Bool = false
    @State private var expanded = false
    @State private var hovered = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: Theme.Space.s) {
                KeyCap(text: "#\(card.position)", font: Theme.monoSmall, height: 24)
                Spacer(minLength: Theme.Space.s)
                OpenRepoButton(repoName: card.repoName, localPath: card.localPath, vscodeURL: card.vscodeUrl)
                StatusDot(isDirty: card.isDirty, healthAvailable: card.healthAvailable)
                Image(systemName: expanded ? "chevron.down" : "chevron.right")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(Theme.text3)
            }

            Text(card.repoName)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Theme.text)
                .lineSpacing(1)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 9)

            Text(commitLine)
                .font(.system(size: 12.5))
                .foregroundStyle(Theme.text3)
                .padding(.top, 8)

            HStack(spacing: Theme.Space.m) {
                if let branch = card.branch { GroupTag(name: branch) }
                Text("↑\(card.ahead) ↓\(card.behind)")
                Text("\(card.modifiedCount)M \(card.untrackedCount)U")
                Spacer(minLength: 0)
            }
            .font(Theme.monoSmall)
            .foregroundStyle(Theme.text2)
            .padding(.top, 10)

            if expanded {
                detail
                    .padding(.top, 10)
            }
        }
        .padding(Theme.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(rowBackground, in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
        .contentShape(Rectangle())
        .onTapGesture { withAnimation(Theme.spring) { expanded.toggle() } }
        .onHover { hovered = $0 }
    }

    // Expanded sub-sections — mirrors the web card.
    @ViewBuilder private var detail: some View {
        Divider().overlay(Theme.separator).padding(.bottom, 2)

        CardSection(label: "Why ranked") {
            Text(card.rankReason)
                .font(Theme.body)
                .foregroundStyle(Theme.text2)
                .fixedSize(horizontal: false, vertical: true)
        }

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

    private var commitLine: String {
        if let ts = card.myLastCommitTs {
            return "your commit \(RelTime.ago(Date(timeIntervalSince1970: TimeInterval(ts))))"
        }
        if let last = card.lastCommitAt {
            return "recent commit \(RelTime.ago(last))"
        }
        return card.rankReason
    }

    private var rowBackground: Color {
        if hovered { return Theme.hover }
        return darker ? Theme.hover : .clear
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

private struct OpenRepoButton: View {
    let repoName: String
    let localPath: String
    let vscodeURL: String

    @State private var hovered = false

    var body: some View {
        Button {
            VSCodeLauncher.launch(repoPath: localPath, fallbackURL: vscodeURL)
        } label: {
            HStack(spacing: 3) {
                Text("Open")
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 10, weight: .bold))
            }
            .font(.system(size: 12.5, weight: .semibold))
            .foregroundStyle(Theme.accent)
            .padding(.horizontal, 5)
            .padding(.vertical, 2)
            .background(hovered ? Theme.accentSoft : .clear,
                        in: RoundedRectangle(cornerRadius: 6, style: .continuous))
        }
        .buttonStyle(.plain)
        .fixedSize()
        .help("Open \(repoName) in VS Code")
        .onHover { hovered = $0 }
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

// MARK: - Prompt Log row (CLIO)

/// Reuses `RepoCardView`'s exact visual language (top badge + spacer + action
/// control, bold title, `Theme.monoSmall` meta row, zebra/hover background) —
/// the only differences are the pin control in place of the open/expand
/// controls, and the data being a logged prompt instead of a repo.
struct PromptLogRowView: View {
    let entry: PromptLogEntry
    let isPinned: Bool
    var darker: Bool = false
    // Resolved via Focus5Model.vscodeOpenInfo(forRepoName:) — nil when the
    // repo isn't in the current roster/off-roster payload, in which case the
    // "Open ↗" button just doesn't render (best-effort, not a dead button).
    var openInfo: (localPath: String, vscodeURL: String)? = nil
    let onTogglePin: () -> Void

    @State private var hovered = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: Theme.Space.s) {
                KeyCap(text: RelTime.ago(entry.timestamp), font: Theme.monoSmall, height: 24)
                Spacer(minLength: Theme.Space.s)
                if let openInfo {
                    OpenRepoButton(repoName: entry.repo, localPath: openInfo.localPath, vscodeURL: openInfo.vscodeURL)
                }
                Button(action: onTogglePin) {
                    Image(systemName: isPinned ? "pin.fill" : "pin")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(isPinned ? Theme.accent : Theme.text3)
                }
                .buttonStyle(.plain)
                .help(isPinned ? "Unpin" : "Pin (max 5 — pinning a 6th releases the oldest pin)")
            }

            Text(entry.truncatedPrompt)
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(Theme.text)
                .lineSpacing(1)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 9)

            HStack(spacing: Theme.Space.m) {
                GroupTag(name: entry.repo)
                if let branch = entry.branch { GroupTag(name: branch) }
                if !entry.machine.isEmpty { Text(entry.machine) }
                Spacer(minLength: 0)
            }
            .font(Theme.monoSmall)
            .foregroundStyle(Theme.text2)
            .padding(.top, 10)
        }
        .padding(Theme.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(rowBackground, in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
        .onHover { hovered = $0 }
    }

    private var rowBackground: Color {
        if isPinned { return Theme.accentSoft }
        if hovered { return Theme.hover }
        return darker ? Theme.hover : .clear
    }
}

// MARK: - Apple Reminders (section A)

/// Section A — the 8 most-recent active tasks from the default Apple Reminders
/// list, read+written LIVE via EventKit (see `RemindersStore`). Branches on the
/// TCC authorization state: an enable button before the grant, a System-Settings
/// hint if denied, the bounded scrollable task list once granted. Each row's
/// checkbox completes the reminder (the only mutation in v1).
struct RemindersSection: View {
    let store: RemindersStore

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.xs) {
            Text("APPLE REMINDERS")
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

// MARK: - Obsidian Reminders (section B)

/// Section B — the top 8 unchecked tasks from the vault-root `0. Goals.md`,
/// read + checkbox-complete through the shared localhost Focus 5 routes.
struct ObsidianRemindersSection: View {
    let store: ObsidianRemindersStore

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.xs) {
            Text("OBSIDIAN REMINDERS")
                .font(Theme.caption).foregroundStyle(Theme.text3).tracking(0.5)
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, Theme.Space.s)
    }

    @ViewBuilder private var content: some View {
        if !store.isLoaded && store.items.isEmpty {
            Text("Loading 0. Goals.md…")
                .font(Theme.body).foregroundStyle(Theme.text3)
                .padding(.vertical, 2)
        } else if let err = store.loadError, store.items.isEmpty {
            Text(err)
                .font(Theme.monoSmall).foregroundStyle(Theme.diffRemove)
                .fixedSize(horizontal: false, vertical: true)
        } else if !store.fileExists {
            Text(store.emptyStateMessage)
                .font(Theme.body).foregroundStyle(Theme.text3)
                .fixedSize(horizontal: false, vertical: true)
        } else if store.items.isEmpty {
            Text("No open tasks in 0. Goals.md.")
                .font(Theme.body).foregroundStyle(Theme.text3)
                .padding(.vertical, 2)
        } else {
            VStack(spacing: 4) {
                ForEach(store.items) { reminder in
                    ObsidianReminderRow(reminder: reminder, store: store)
                }
            }
        }

        if let err = store.loadError, !store.items.isEmpty {
            Text(err)
                .font(Theme.monoSmall).foregroundStyle(Theme.diffRemove)
                .fixedSize(horizontal: false, vertical: true)
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

struct ObsidianReminderRow: View {
    let reminder: ObsidianReminder
    let store: ObsidianRemindersStore

    private var isCompleting: Bool {
        store.completingLineIndexes.contains(reminder.lineIndex)
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
            .help("Mark complete in 0. Goals.md")

            VStack(alignment: .leading, spacing: 2) {
                Text(reminder.title)
                    .font(Theme.body).foregroundStyle(isCompleting ? Theme.text3 : Theme.text)
                    .strikethrough(isCompleting)
                    .lineLimit(2).fixedSize(horizontal: false, vertical: true)
                if !reminder.description.isEmpty {
                    Text(reminder.description)
                        .font(Theme.monoSmall).foregroundStyle(Theme.text3)
                        .lineLimit(3).fixedSize(horizontal: false, vertical: true)
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
                MarkdownBody(content: content)
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

/// Shared markdown renderer — used by both the vault focus5.md note
/// (`Focus5NoteView`) and the telemetry tab's `.md` viewer so there's a single
/// rendering path for freeform notes in the panel. GFM pipe tables render as a
/// real `MarkdownTableView` grid; everything else falls through to `MarkdownLine`.
private struct MarkdownBody: View {
    let content: String

    var body: some View {
        let blocks = MarkdownTableParser.parse(content)
        ForEach(Array(blocks.enumerated()), id: \.offset) { _, block in
            switch block {
            case .table(let table):
                MarkdownTableView(table: table)
            case .line(let raw):
                MarkdownLine(raw: Substring(raw))
            }
        }
    }
}

/// Renders a parsed GFM table as a scrollable grid — a real table instead of
/// literal `|` text — matching the panel's card styling (elevated background,
/// hairline border). Column count comes from the header; ragged data rows are
/// already padded/truncated to match by `MarkdownTableParser`.
private struct MarkdownTableView: View {
    let table: MarkdownTable

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            Grid(alignment: .leading, horizontalSpacing: Theme.Space.s, verticalSpacing: 4) {
                GridRow {
                    ForEach(Array(table.header.enumerated()), id: \.offset) { i, cell in
                        Text(cell)
                            .font(.system(size: 12.5, weight: .semibold))
                            .foregroundStyle(Theme.text)
                            .lineLimit(1)
                            .gridColumnAlignment(horizontalAlignment(for: i))
                    }
                }
                Divider().gridCellColumns(max(table.header.count, 1)).overlay(Theme.separator)
                ForEach(Array(table.rows.enumerated()), id: \.offset) { _, row in
                    GridRow {
                        ForEach(Array(row.enumerated()), id: \.offset) { _, cell in
                            Text(cell)
                                .font(Theme.body)
                                .foregroundStyle(Theme.text2)
                                .lineLimit(3)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }
            .padding(Theme.Space.s)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.elevated, in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous)
                .strokeBorder(Theme.separator, lineWidth: 1)
        )
    }

    private func horizontalAlignment(for column: Int) -> HorizontalAlignment {
        guard column < table.alignments.count else { return .leading }
        switch table.alignments[column] {
        case .leading:  return .leading
        case .center:   return .center
        case .trailing: return .trailing
        }
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

// MARK: - Dirty banner (GH-105)

/// Slim single-row "BTW, this went dirty" nudge shown above card #1 — the
/// single most-recently-touched dirty repo outside the top 5 (already picked
/// server-side; this view only renders it). Deliberately lighter/friendlier
/// than `OffRosterFooter` (accent tint, not warning) and never collapsible —
/// it's a passive nudge, not a full list.
struct DirtyBannerView: View {
    let warning: OffRosterWarning

    private var detail: String {
        var bits: [String] = []
        if warning.modifiedCount > 0 { bits.append("\(warning.modifiedCount) modified") }
        if warning.untrackedCount > 0 { bits.append("\(warning.untrackedCount) untracked") }
        return bits.isEmpty ? "uncommitted changes" : bits.joined(separator: ", ")
    }

    private var ago: String {
        guard let ts = warning.myLocalCommitTs else { return "" }
        return RelTime.ago(Date(timeIntervalSince1970: TimeInterval(ts)))
    }

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "exclamationmark.circle.fill")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(Theme.attention)
            Text(warning.repoName)
                .font(Theme.bodyMed).foregroundStyle(Theme.text)
            Text("left it dirty (\(detail))" + (ago.isEmpty ? "" : " — last commit \(ago)"))
                .font(Theme.caption).foregroundStyle(Theme.text2)
                .lineLimit(1)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, Theme.Space.m)
        .padding(.vertical, Theme.Space.xs)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.accent.opacity(0.08), in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous)
                .strokeBorder(Theme.accent.opacity(0.2), lineWidth: 1)
        )
    }
}

// MARK: - Off-roster footer (collapsible)

struct OffRosterFooter: View {
    let warnings: [OffRosterWarning]
    @State private var expanded = false

    private func detail(for warning: OffRosterWarning) -> String {
        if let reason = warning.warningReason, !reason.isEmpty {
            return reason
        }
        return "↑\(warning.ahead) · \(warning.modifiedCount)M \(warning.untrackedCount)U"
    }

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
                        VStack(alignment: .leading, spacing: 2) {
                            Text(w.repoName)
                                .font(Theme.body)
                                .foregroundStyle(Theme.text)
                                .lineLimit(1)
                            Text(detail(for: w))
                                .font(Theme.caption)
                                .foregroundStyle(Theme.text3)
                                .lineLimit(1)
                        }
                        Spacer(minLength: 0)
                    }
                }
            }
        }
        .padding(Theme.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.hover, in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
    }
}
