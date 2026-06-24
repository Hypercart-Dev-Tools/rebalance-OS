import SwiftUI
import TextReplacementCore

/// Preview Plan sheet: a summary of what Apply will change (diffed against the last
/// import), shown as four stat tiles plus per-section disclosure lists. No raw log.
struct PreviewPlanSheet: View {
    let model: StudioModel
    let strategy: AppleDatabaseWriter.Strategy
    let onApply: () -> Void
    let onCancel: () -> Void

    private var diff: PlanDiff { model.planDiff(strategy: strategy) }

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Space.xl) {
                    statTiles
                    sections
                }
                .padding(Theme.Space.xl)
            }
            Divider()
            footer
        }
        .frame(width: 580, height: 600)
        .background(Theme.window)
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 3) {
                Text("Preview Plan").font(Theme.display).foregroundStyle(Theme.text)
                Text("Strategy · \(strategy == .merge ? "Merge (add / update)" : "Replace (add / update / remove)")")
                    .font(Theme.body).foregroundStyle(Theme.text2)
            }
            Spacer()
        }
        .padding(.horizontal, Theme.Space.xl)
        .padding(.vertical, 18)
    }

    private var statTiles: some View {
        HStack(spacing: Theme.Space.m) {
            StatTile(value: diff.adds.count,    label: "Add",       color: Theme.diffAdd)
            StatTile(value: diff.updates.count, label: "Update",    color: Theme.diffUpdate)
            StatTile(value: diff.removes.count, label: "Remove",    color: Theme.diffRemove)
            StatTile(value: diff.unchanged,     label: "Unchanged", color: Theme.text3)
        }
    }

    @ViewBuilder private var sections: some View {
        if diff.isEmpty {
            VStack(spacing: Theme.Space.s) {
                Image(systemName: "checkmark.circle").font(.system(size: 26)).foregroundStyle(Theme.diffAdd)
                Text("No changes since last import").font(Theme.bodyMed).foregroundStyle(Theme.text2)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Space.xl)
        } else {
            VStack(alignment: .leading, spacing: Theme.Space.m) {
                if !diff.adds.isEmpty {
                    DiffSection(title: "Added", color: Theme.diffAdd,
                                items: diff.adds.map { DiffLine(shortcut: $0.shortcut, detail: $0.phrase) })
                }
                if !diff.updates.isEmpty {
                    DiffSection(title: "Updated", color: Theme.diffUpdate,
                                items: diff.updates.map {
                                    DiffLine(shortcut: $0.after.shortcut, detail: $0.after.phrase)
                                })
                }
                if !diff.removes.isEmpty {
                    DiffSection(title: "Removed", color: Theme.diffRemove,
                                items: diff.removes.map { DiffLine(shortcut: $0.shortcut, detail: $0.phrase) })
                } else if strategy == .merge && model.importedBaseline.count > model.replacements.count {
                    Text("Deletions are ignored under Merge. Switch to Replace to remove shortcuts.")
                        .font(Theme.body).foregroundStyle(Theme.text3)
                }
            }
        }
    }

    private var footer: some View {
        HStack {
            Spacer()
            Button("Cancel", action: onCancel)
                .keyboardShortcut(.cancelAction)
            Button("Apply to macOS", action: onApply)
                .keyboardShortcut(.defaultAction)
                .buttonStyle(.borderedProminent)
                .disabled(diff.isEmpty)
        }
        .padding(.horizontal, Theme.Space.xl)
        .padding(.vertical, Theme.Space.l)
    }
}

private struct StatTile: View {
    let value: Int
    let label: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text("\(value)").font(.system(size: 28, weight: .semibold)).foregroundStyle(color).monospacedDigit()
            Text(label.uppercased()).font(.system(size: 11, weight: .semibold)).tracking(0.5).foregroundStyle(Theme.text2)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Space.l)
        .background(Theme.elevated, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 11, style: .continuous).strokeBorder(Theme.separator2, lineWidth: 1)
        )
    }
}

private struct DiffLine: Identifiable {
    let id = UUID()
    let shortcut: String
    let detail: String
}

private struct DiffSection: View {
    let title: String
    let color: Color
    let items: [DiffLine]
    @State private var expanded = true

    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            VStack(spacing: 0) {
                ForEach(items) { line in
                    HStack(spacing: 11) {
                        KeyCap(text: line.shortcut)
                        Text(line.detail)
                            .font(.system(size: 13))
                            .foregroundStyle(Theme.text2)
                            .lineLimit(1).truncationMode(.tail)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(.vertical, 7)
                }
            }
            .padding(.top, 4)
        } label: {
            HStack(spacing: 8) {
                RoundedRectangle(cornerRadius: 3).fill(color).frame(width: 10, height: 10)
                Text("\(title) · \(items.count)").font(Theme.bodyMed).foregroundStyle(Theme.text)
            }
        }
        .tint(Theme.text2)
    }
}
