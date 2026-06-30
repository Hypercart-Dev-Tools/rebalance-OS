import SwiftUI
import TextReplacementCore

/// Monospaced key-cap: a shortcut rendered in SF Mono inside a rounded fill with a
/// hairline border and a 1px bottom highlight. Sized by `font` / `padding`.
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

/// Group tag chip: a colored dot + the group name in a soft capsule.
struct GroupTag: View {
    let name: String

    var body: some View {
        HStack(spacing: 5) {
            Circle()
                .fill(Theme.groupColor(name))
                .frame(width: 7, height: 7)
            Text(name)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(Theme.text2)
                .lineLimit(1)
        }
        .padding(.vertical, 2)
        .padding(.leading, 6)
        .padding(.trailing, 7)
        .background(Theme.hover, in: Capsule())
    }
}

/// A compact switch matching the comp's row/inspector toggles — native control,
/// accent-tinted, label hidden.
struct StudioToggle: View {
    @Binding var isOn: Bool
    var controlSize: ControlSize = .small

    var body: some View {
        Toggle("", isOn: $isOn)
            .toggleStyle(.switch)
            .labelsHidden()
            .controlSize(controlSize)
            .tint(Theme.accent)
    }
}
