import SwiftUI
import AppKit

// Vertical stack of repo cards, using the harvested Theme + components. Data is
// the live GET /focus-5.json (Phase 4) via Focus5Model. The full collapsible
// card (tree-health / PR / activity sub-sections) is Phase 3.

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

    private var header: some View {
        HStack(spacing: Theme.Space.s) {
            Text(model.isDirtyView ? "🧹 Dirty Five" : "🎯 Focus 5")
                .font(Theme.display)
                .foregroundStyle(Theme.text)
            Spacer(minLength: Theme.Space.s)
            if model.isOffline {
                Text("offline")
                    .font(Theme.caption)
                    .foregroundStyle(Theme.diffRemove)
            }
            Text("\(model.roster.count) repos")
                .font(Theme.caption)
                .foregroundStyle(Theme.text2)
        }
        .padding(Theme.Space.m)
    }

    @ViewBuilder private var content: some View {
        switch model.loadState {
        case .idle, .loading:
            ProgressView()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        case .failed(let message):
            VStack(spacing: Theme.Space.s) {
                Image(systemName: "bolt.horizontal.circle")
                    .font(.system(size: 22))
                    .foregroundStyle(Theme.diffRemove)
                Text("Can't reach the Focus 5 server")
                    .font(Theme.bodyMed)
                    .foregroundStyle(Theme.text)
                Text(message)
                    .font(Theme.monoSmall)
                    .foregroundStyle(Theme.text3)
                    .multilineTextAlignment(.center)
            }
            .padding()
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        case .loaded:
            ScrollView {
                LazyVStack(spacing: Theme.Space.s) {
                    ForEach(model.roster) { RepoCardView(card: $0) }
                    if !model.offRoster.isEmpty {
                        OffRosterStrip(warnings: model.offRoster)
                    }
                }
                .padding(Theme.Space.m)
            }
        }
    }
}

/// One repo row — Phase 1 collapsed form: position, name, status dot, drift/dirty
/// metrics, and the rank reason.
struct RepoCardView: View {
    let card: RepoCard

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: Theme.Space.s) {
                KeyCap(text: "#\(card.position)")
                Text(card.repoName)
                    .font(Theme.bodyMed)
                    .foregroundStyle(Theme.text)
                    .lineLimit(1)
                Spacer(minLength: Theme.Space.s)
                StatusDot(isDirty: card.isDirty, healthAvailable: card.healthAvailable)
            }

            Text(card.rankReason)
                .font(Theme.body)
                .foregroundStyle(Theme.text2)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: Theme.Space.m) {
                if let branch = card.branch { GroupTag(name: branch) }
                Text("↑\(card.ahead) ↓\(card.behind)")
                Text("\(card.modifiedCount)M \(card.untrackedCount)U")
                Spacer(minLength: 0)
            }
            .font(Theme.monoSmall)
            .foregroundStyle(Theme.text3)
        }
        .padding(Theme.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.elevated, in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous)
                .strokeBorder(Theme.separator, lineWidth: 1)
        )
        .contentShape(Rectangle())
        .onTapGesture { open(card.vscodeUrl) }   // click → open repo in VS Code
        .help("Open \(card.repoName) in VS Code")
    }

    private func open(_ urlString: String) {
        if let url = URL(string: urlString) { NSWorkspace.shared.open(url) }
    }
}

/// Compact footer for repos outside the top-5 that still need attention.
struct OffRosterStrip: View {
    let warnings: [OffRosterWarning]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.xs) {
            Text("\(warnings.count) outside top 5 need attention")
                .font(Theme.caption)
                .foregroundStyle(Theme.text2)
            ForEach(warnings) { w in
                HStack(spacing: Theme.Space.s) {
                    StatusDot(isDirty: w.isDirty, healthAvailable: true)
                    Text(w.repoName).font(Theme.body).foregroundStyle(Theme.text)
                    Spacer(minLength: 0)
                    Text("↑\(w.ahead) · \(w.modifiedCount)M \(w.untrackedCount)U")
                        .font(Theme.monoSmall)
                        .foregroundStyle(Theme.text3)
                }
            }
        }
        .padding(Theme.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.hover, in: RoundedRectangle(cornerRadius: Theme.Radius.row, style: .continuous))
    }
}
