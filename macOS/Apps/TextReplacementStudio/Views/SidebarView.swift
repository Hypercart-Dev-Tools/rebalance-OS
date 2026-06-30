import SwiftUI
import TextReplacementCore

/// Left column: Library smart-filters with live counts, then user Groups (colored
/// dots), then a "last applied" footer. Custom-styled for the comp's calm look while
/// staying keyboard- and VoiceOver-navigable (each row is a labeled Button).
struct SidebarView: View {
    let model: StudioModel
    @Binding var selectedFilter: ReplacementFilter

    private struct Smart: Identifiable {
        let id = UUID()
        let filter: ReplacementFilter
        let title: String
        let icon: String
    }

    private var smartFilters: [Smart] {
        [
            .init(filter: .all,             title: "All",              icon: "square.grid.2x2"),
            .init(filter: .recentlyChanged, title: "Recently Changed", icon: "clock.arrow.circlepath"),
            .init(filter: .duplicates,      title: "Duplicates",       icon: "doc.on.doc"),
            .init(filter: .disabled,        title: "Disabled",         icon: "nosign"),
            .init(filter: .ungrouped,       title: "Ungrouped",        icon: "tray"),
        ]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 1) {
            sectionLabel("LIBRARY")
            ForEach(smartFilters) { f in
                FilterRow(
                    icon: f.icon,
                    title: f.title,
                    count: model.count(for: f.filter),
                    dotColor: nil,
                    isSelected: selectedFilter == f.filter
                ) { selectedFilter = f.filter }
            }

            if !model.groups.isEmpty {
                Spacer().frame(height: Theme.Space.l)
                sectionLabel("GROUPS")
                ForEach(model.groups) { g in
                    FilterRow(
                        icon: nil,
                        title: g.name,
                        count: g.count,
                        dotColor: g.color,
                        isSelected: selectedFilter == .group(g.name)
                    ) { selectedFilter = .group(g.name) }
                }
            }

            Spacer(minLength: Theme.Space.m)
            footer
        }
        .padding(.horizontal, 10)
        .padding(.top, Theme.Space.l)
        .padding(.bottom, 10)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Theme.sidebar)
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11, weight: .semibold))
            .tracking(0.5)
            .foregroundStyle(Theme.text2)
            .padding(.horizontal, 8)
            .padding(.bottom, Theme.Space.s)
    }

    private var footer: some View {
        Text(lastAppliedText)
            .font(.system(size: 11))
            .foregroundStyle(Theme.text3)
            .padding(.horizontal, 9)
            .padding(.vertical, Theme.Space.s)
    }

    private var lastAppliedText: String {
        guard let date = model.lastAppliedAt else { return "Not yet applied to macOS" }
        let f = DateFormatter()
        f.dateStyle = .none
        f.timeStyle = .short
        if Calendar.current.isDateInToday(date) { return "Last applied · today, \(f.string(from: date))" }
        let d = DateFormatter(); d.dateStyle = .medium; d.timeStyle = .short
        return "Last applied · \(d.string(from: date))"
    }
}

/// One sidebar row — an icon or color dot, a title, and a trailing count. The whole
/// row is a borderless button; selection paints a soft accent fill.
private struct FilterRow: View {
    let icon: String?
    let title: String
    let count: Int
    let dotColor: Color?
    let isSelected: Bool
    let action: () -> Void

    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 9) {
                if let dotColor {
                    RoundedRectangle(cornerRadius: 3, style: .continuous)
                        .fill(dotColor)
                        .frame(width: 9, height: 9)
                } else if let icon {
                    Image(systemName: icon)
                        .font(.system(size: 13))
                        .foregroundStyle(isSelected ? Theme.accent : Theme.text2)
                        .frame(width: 16, height: 16)
                }
                Text(title)
                    .font(isSelected ? Theme.bodyMed : Theme.body)
                    .foregroundStyle(Theme.text)
                    .lineLimit(1)
                Spacer(minLength: 4)
                Text("\(count)")
                    .font(Theme.body)
                    .foregroundStyle(isSelected ? Theme.accent : Theme.text2)
                    .monospacedDigit()
            }
            .padding(.horizontal, 8)
            .frame(height: 30)
            .frame(maxWidth: .infinity)
            .background(rowBackground)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hovering = $0 }
        .accessibilityLabel("\(title), \(count) items")
        .accessibilityAddTraits(isSelected ? [.isSelected, .isButton] : .isButton)
    }

    @ViewBuilder private var rowBackground: some View {
        if isSelected {
            RoundedRectangle(cornerRadius: 7, style: .continuous).fill(Theme.accentSoft)
        } else if hovering {
            RoundedRectangle(cornerRadius: 7, style: .continuous).fill(Theme.hover)
        }
    }
}
