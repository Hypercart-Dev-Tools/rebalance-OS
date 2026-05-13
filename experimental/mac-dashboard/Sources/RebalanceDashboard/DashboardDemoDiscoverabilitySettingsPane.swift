import SwiftUI
import HypercartMacOSDashboard

struct DashboardDemoDiscoverabilitySettingsPane: View
{
    @Bindable var store: DashboardDemoStore

    var body: some View
    {
        SettingsPaneTemplate
        {
            VStack(alignment: .center, spacing: 10)
            {
                Toggle(
                    "Enable discoverability",
                    isOn: Binding(
                        get: { store.enableDiscoverability },
                        set: { store.updateDiscoverabilityEnabled($0) }
                    )
                )
                .toggleStyle(.switch)
                .disabled(store.isLoadingTopItems)

                Divider()

                Form
                {
                    LabeledContent("Mass adoption")
                    {
                        VStack(alignment: .leading, spacing: 6)
                        {
                            Toggle("Allow mass adoption", isOn: $store.allowMassPackageAdoption)
                                .disabled(!store.enableDiscoverability)

                            Toggle(
                                "Hide section when only excluded items remain",
                                isOn: $store.hideAdoptableSectionWhenOnlyExcludedItemsRemain
                            )
                        }
                    }

                    Picker("Time span", selection: $store.discoverabilityDaySpan)
                    {
                        ForEach(DashboardDemoDiscoverabilityDaySpan.allCases) { span in
                            Text(span.title)
                                .tag(span)
                        }
                    }

                    Picker("Sorting", selection: $store.sortTopItemsBy)
                    {
                        ForEach(DashboardDemoTopItemSortMode.allCases) { mode in
                            Text(mode.title)
                                .tag(mode)
                        }
                    }
                }
                .disabled(!store.enableDiscoverability || store.isLoadingTopItems)

                HStack
                {
                    Spacer()

                    if store.isLoadingTopItems
                    {
                        ProgressView()
                            .controlSize(.small)
                    }

                    Button("Simulate Refresh") {
                        Task {
                            await store.simulateTopItemsRefresh()
                        }
                    }
                }
            }
        }
    }
}
