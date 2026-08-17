import SwiftUI

// Harvested from TextReplacementStudio/Views/StudioComponents.swift — the
// `import TextReplacementCore` dependency was dropped (these use only SwiftUI +
// Theme). KeyCap → position badge; GroupTag → branch/tag chip; StatusDot is new
// for the Focus 5 health signal.

/// Monospaced key-cap: text in SF Mono inside a rounded fill with a hairline
/// border and a 1px bottom highlight. Used here for the `#1`…`#5` position badge.
struct KeyCap: View {
    let text: String
    var font: Font = Theme.mono
    var paddingH: CGFloat = 7
    var height: CGFloat = 23

    var body: some View {
        Text(text)
            .font(font)
            .foregroundStyle(Theme.text)
            .lineLimit(1)
            .fixedSize()
            .padding(.horizontal, paddingH)
            .frame(height: height)
            .background(Theme.keycapBG, in: RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.control, style: .continuous)
                    .strokeBorder(Theme.keycapBorder, lineWidth: 1)
            )
            .shadow(color: Theme.keycapShadow, radius: 0, x: 0, y: 1)
    }
}

/// Group/branch chip: a colored dot + a label in a soft capsule.
struct GroupTag: View {
    let name: String

    var body: some View {
        HStack(spacing: 5) {
            Circle()
                .fill(Theme.groupColor(name))
                .frame(width: 7, height: 7)
            Text(name)
                .font(Theme.monoSmall)
                .foregroundStyle(Theme.text2)
                .lineLimit(1)
        }
        .padding(.vertical, 3)
        .padding(.leading, 7)
        .padding(.trailing, 8)
        .background(Theme.hover, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
    }
}

/// Overall roster-health rollup colour. `dirty` is the count of dirty roster
/// repos (shown as "Status: N", so all-clean reads "Status: 0").
/// green = none dirty · red = all dirty · orange = some dirty.
enum RosterHealth {
    static func tint(dirty: Int, total: Int) -> Color {
        if dirty == 0 { return Theme.diffAdd }       // green — all clean
        if dirty >= total { return Theme.diffRemove } // red — all dirty
        return .orange                                // some dirty
    }
}

/// Tree-health dot: green = clean, red = dirty/needs attention, grey = no signal.
/// Color is never the only cue — callers pair it with adjacent text.
struct StatusDot: View {
    let isDirty: Bool
    let healthAvailable: Bool

    private var color: Color {
        guard healthAvailable else { return Theme.text3 }
        return isDirty ? Theme.diffRemove : Theme.diffAdd
    }

    var body: some View {
        Circle().fill(color).frame(width: 11, height: 11)
            .accessibilityLabel(healthAvailable ? (isDirty ? "dirty" : "clean") : "unavailable")
    }
}

/// Telemetry health dot: maps HealthStatus directly to green / orange / red.
/// Color is never the only cue — callers pair it with adjacent text.
struct HealthDot: View {
    let health: HealthStatus

    private var color: Color {
        switch health {
        case .green:  return Theme.diffAdd
        case .orange: return .orange
        case .red:    return Theme.diffRemove
        }
    }

    var body: some View {
        Circle().fill(color).frame(width: 10, height: 10)
            .accessibilityLabel(health.rawValue)
    }
}
