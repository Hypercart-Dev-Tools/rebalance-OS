import SwiftUI
import HypercartMacOSDashboard

struct DashboardDemoSettingsView: View
{
    @Bindable var store: DashboardDemoStore

    var body: some View
    {
        SheetContainer(showsTitleBar: false)
        {
            VStack(alignment: .leading, spacing: 18)
            {
                VStack(alignment: .leading, spacing: 4)
                {
                    Text("General Preferences")
                        .font(.title2.weight(.semibold))
                    Text("Ported from Cork's General settings pane and re-bound to the extracted dashboard shell.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                DashboardDemoGeneralSettingsPane(store: store)

                Divider()

                VStack(alignment: .leading, spacing: 4)
                {
                    Text("Notifications")
                        .font(.title3.weight(.semibold))
                    Text("Ported from Cork's Notifications pane with demo-owned permission state.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                DashboardDemoNotificationsSettingsPane(store: store)

                Divider()

                VStack(alignment: .leading, spacing: 4)
                {
                    Text("Discoverability")
                        .font(.title3.weight(.semibold))
                    Text("Ported from Cork's Discoverability pane with demo-owned loading and ranking state.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                DashboardDemoDiscoverabilitySettingsPane(store: store)

                Divider()

                SettingsPaneTemplate
                {
                    Form
                    {
                        Toggle("Compact metrics", isOn: $store.isCompactMetricsEnabled)
                        Toggle("Verbose logging", isOn: $store.isVerboseLoggingEnabled)
                    }
                }
            }
        }
    }
}
