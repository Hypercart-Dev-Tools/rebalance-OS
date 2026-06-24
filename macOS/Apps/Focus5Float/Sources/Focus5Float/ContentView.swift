import SwiftUI
import AppKit

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
    }

    // MARK: Header

    private var header: some View {
        VStack(spacing: Theme.Space.s) {
            HStack(spacing: Theme.Space.s) {
                Picker("", selection: Binding(
                    get: { model.isDirtyView },
                    set: { dirty in Task { await model.setMode(dirty: dirty) } }
                )) {
                    Text("🎯 Focus 5").tag(false)
                    Text("🧹 Dirty Five").tag(true)
                }
                .pickerStyle(.segmented)
                .labelsHidden()

                Button {
                    Task { await model.refresh() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
                .foregroundStyle(Theme.text2)
                .help("Re-pull /focus-5.json")
            }

            HStack(spacing: Theme.Space.s) {
                Text("\(model.roster.count) repos")
                    .font(Theme.caption)
                    .foregroundStyle(Theme.text2)
                if !model.lastUpdatedAgo.isEmpty {
                    Text("· updated \(model.lastUpdatedAgo)")
                        .font(Theme.caption)
                        .foregroundStyle(Theme.text3)
                }
                Spacer(minLength: 0)
                if model.isStale {
                    Text("⚠ stale").font(Theme.caption).foregroundStyle(Theme.diffUpdate)
                }
                if model.isOffline {
                    Text("offline").font(Theme.caption).foregroundStyle(Theme.diffRemove)
                }
            }
        }
        .padding(Theme.Space.m)
    }

    // MARK: Content

    @ViewBuilder private var content: some View {
        switch model.loadState {
        case .idle, .loading:
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
        case .failed(let message):
            emptyState(icon: "bolt.horizontal.circle",
                       title: "Can't reach the Focus 5 server",
                       detail: message)
        case .loaded where model.roster.isEmpty:
            emptyState(icon: "tray",
                       title: model.isDirtyView ? "Nothing at risk" : "No active repos found",
                       detail: "The server roster is empty. Build it server-side (open /focus-5 in the browser or run a Focus 5 sync), then Refresh here to re-pull.")
        case .loaded:
            ScrollView {
                LazyVStack(spacing: Theme.Space.s) {
                    ForEach(Array(model.roster.enumerated()), id: \.element.id) { index, card in
                        RepoCardView(card: card, darker: !index.isMultiple(of: 2))
                    }
                    if !model.offRoster.isEmpty {
                        OffRosterFooter(warnings: model.offRoster)
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
}

// MARK: - Repo card (collapsible)

struct RepoCardView: View {
    let card: RepoCard
    var darker: Bool = false        // zebra stripe — alternate rows use elevatedAlt
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            // Always-visible summary
            HStack(spacing: Theme.Space.s) {
                KeyCap(text: "#\(card.position)")
                Text(card.repoName)
                    .font(Theme.bodyMed).foregroundStyle(Theme.text).lineLimit(1)
                Spacer(minLength: Theme.Space.s)
                Button("Open ↗") { open(card.vscodeUrl) }
                    .buttonStyle(.borderless)
                    .font(Theme.caption)
                    .foregroundStyle(Theme.accent)
                    .help("Open \(card.repoName) in VS Code")
                StatusDot(isDirty: card.isDirty, healthAvailable: card.healthAvailable)
                Image(systemName: expanded ? "chevron.down" : "chevron.right")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(Theme.text3)
            }

            Text(card.rankReason)
                .font(Theme.body).foregroundStyle(Theme.text2)
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
