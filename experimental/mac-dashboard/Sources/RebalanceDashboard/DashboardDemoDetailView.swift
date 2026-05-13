import SwiftUI
import HypercartMacOSDashboard

struct DashboardDemoDetailView: View
{
    let item: DashboardDemoItem
    let inlineErrorMessage: String?
    let onDismissInlineError: () -> Void
    let onShowAlert: () -> Void
    let onShowInlineError: () -> Void
    let onRemove: () -> Void

    var body: some View
    {
        ScrollView
        {
            VStack(alignment: .leading, spacing: 20)
            {
                IconDetailRow(icon: .systemSymbol(symbolName))
                {
                    VStack(alignment: .leading, spacing: 8)
                    {
                        Text(item.name)
                            .font(.largeTitle.weight(.semibold))

                        Text(item.summary)
                            .foregroundStyle(.secondary)

                        Text("Status: \(item.status.rawValue.capitalized)")
                            .font(.subheadline.weight(.medium))
                    }
                }

                if let inlineErrorMessage
                {
                    VStack(alignment: .leading, spacing: 10)
                    {
                        InlineErrorView(
                            title: "Inline failure",
                            message: inlineErrorMessage,
                            retryTitle: "Dismiss",
                            retryAction: onDismissInlineError
                        )
                        .frame(height: 220)
                    }
                }

                GroupBox("Why this flow matters")
                {
                    VStack(alignment: .leading, spacing: 8)
                    {
                        ForEach(item.notes, id: \.self) { note in
                            Text("• \(note)")
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                HStack(spacing: 12)
                {
                    AppKitButton(title: "Show Alert") {
                        onShowAlert()
                    }

                    Button("Show Inline Error") {
                        onShowInlineError()
                    }

                    Button("Remove…", role: .destructive) {
                        onRemove()
                    }
                }
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var symbolName: String
    {
        switch item.kind
        {
        case .service:
            return "bolt.horizontal.circle"
        case .task:
            return "checklist"
        case .dataSource:
            return "shippingbox"
        }
    }
}
