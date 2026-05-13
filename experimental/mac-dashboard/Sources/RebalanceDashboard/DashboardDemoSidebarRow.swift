import SwiftUI

struct DashboardDemoSidebarRow: View
{
    let item: DashboardDemoItem
    let isSelected: Bool

    var body: some View
    {
        HStack(spacing: 10)
        {
            Circle()
                .fill(statusColor)
                .frame(width: 10, height: 10)

            VStack(alignment: .leading, spacing: 2)
            {
                Text(item.name)
                    .font(.body.weight(.medium))

                Text(item.summary)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer()

            Text(item.kind.rawValue.capitalized)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 8)
        .background(isSelected ? Color.accentColor.opacity(0.16) : Color.clear)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var statusColor: Color
    {
        switch item.status
        {
        case .healthy:
            return .green
        case .warning:
            return .orange
        case .failed:
            return .red
        }
    }
}
