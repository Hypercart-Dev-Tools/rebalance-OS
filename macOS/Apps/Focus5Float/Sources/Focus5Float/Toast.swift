import SwiftUI

// Harvested from TextReplacementStudio/Views/ToastView.swift, re-flavored for
// Focus 5 (its ToastMessage.Action was app-specific). Not wired into the UI yet
// — it's ready for Phase 4 (refresh / "server offline" feedback).

struct ToastMessage: Identifiable {
    enum Style { case success, error, info }
    enum Action { case retryRefresh }

    let id = UUID()
    let text: String
    var style: Style = .info
    var action: Action?
}

extension ToastMessage.Action {
    var title: String {
        switch self {
        case .retryRefresh: return "Retry"
        }
    }
}

/// Transient top banner — a compact confirmation pill (e.g. "Repos refreshed")
/// that slides down from the top, holds, and fades out. Unlike `ToastView` it has
/// no dismiss/action chrome: it's pure lightweight feedback for an action (the
/// recycle button) that otherwise gives no visible sign it did anything.
struct TopBanner: View {
    let text: String

    var body: some View {
        HStack(spacing: 7) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Theme.diffAdd)
            Text(text)
                .font(Theme.bodyMed)
                .foregroundStyle(Theme.text)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(.regularMaterial, in: Capsule())
        .overlay(Capsule().strokeBorder(Theme.separator, lineWidth: 1))
        .shadow(color: .black.opacity(0.18), radius: 12, x: 0, y: 6)
        .padding(.top, Theme.Space.s)
    }
}

/// Bottom feedback capsule. Success/info auto-dismiss; errors keep an action.
struct ToastView: View {
    let toast: ToastMessage
    let onAction: (ToastMessage.Action) -> Void
    let onDismiss: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(tint)
            Text(toast.text)
                .font(Theme.bodyMed)
                .foregroundStyle(Theme.text)
                .fixedSize(horizontal: false, vertical: true)

            if let action = toast.action {
                Button(action.title) { onAction(action) }
                    .buttonStyle(.borderless)
                    .font(Theme.bodyMed)
                    .foregroundStyle(Theme.accent)
            }
            Button { onDismiss() } label: {
                Image(systemName: "xmark").font(.system(size: 11, weight: .bold))
            }
            .buttonStyle(.plain)
            .foregroundStyle(Theme.text3)
            .accessibilityLabel("Dismiss")
        }
        .padding(.leading, 16)
        .padding(.trailing, 12)
        .padding(.vertical, 11)
        .background(.regularMaterial, in: Capsule())
        .overlay(Capsule().strokeBorder(Theme.separator, lineWidth: 1))
        .shadow(color: .black.opacity(0.18), radius: 16, x: 0, y: 8)
        .padding(.bottom, Theme.Space.xl)
    }

    private var icon: String {
        switch toast.style {
        case .success: return "checkmark.circle.fill"
        case .error:   return "exclamationmark.triangle.fill"
        case .info:    return "info.circle.fill"
        }
    }
    private var tint: Color {
        switch toast.style {
        case .success: return Theme.diffAdd
        case .error:   return Theme.diffRemove
        case .info:    return Theme.accent
        }
    }
}
