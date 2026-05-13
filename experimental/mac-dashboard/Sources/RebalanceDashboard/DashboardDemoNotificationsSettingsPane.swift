import SwiftUI
import HypercartMacOSDashboard

struct DashboardDemoNotificationsSettingsPane: View
{
    @Bindable var store: DashboardDemoStore
    @State private var isShowingHelpPopover: Bool = false

    var body: some View
    {
        SettingsPaneTemplate
        {
            VStack(alignment: .center, spacing: 10)
            {
                VStack(alignment: .center, spacing: 5)
                {
                    Toggle(
                        "Enable notifications",
                        isOn: Binding(
                            get: { store.areNotificationsEnabled },
                            set: { newValue in
                                Task {
                                    await store.updateNotificationToggle(newValue)
                                }
                            }
                        )
                    )
                    .toggleStyle(.switch)
                    .disabled(store.notificationAuthorizationState == .denied)

                    if store.notificationAuthorizationState == .denied
                    {
                        Text("Notifications are denied at the system level in this demo state.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Divider()

                Form
                {
                    Picker("Notification style", selection: $store.notificationDeliveryMode)
                    {
                        ForEach(DashboardDemoNotificationDeliveryMode.allCases) { mode in
                            Text(mode.title)
                                .tag(mode)
                        }
                    }

                    LabeledContent("Notify after actions")
                    {
                        VStack(alignment: .leading)
                        {
                            Toggle("Package upgrade results", isOn: $store.notifyAboutUpgradeResults)
                            Toggle("Package installation results", isOn: $store.notifyAboutInstallResults)
                            Toggle("Mass adoption results", isOn: $store.notifyAboutMassAdoptionResults)
                        }
                    }

                    Picker(
                        "Simulated system authorization",
                        selection: Binding(
                            get: { store.notificationAuthorizationState },
                            set: { store.applySimulatedNotificationAuthorizationState($0) }
                        )
                    ) {
                        ForEach(DashboardDemoNotificationAuthorizationState.allCases) { state in
                            Text(state.title)
                                .tag(state)
                        }
                    }
                }
                .disabled(!store.areNotificationsEnabled)

                HStack
                {
                    Spacer()

                    Button("Why?") {
                        isShowingHelpPopover.toggle()
                    }
                    .popover(isPresented: $isShowingHelpPopover, arrowEdge: .bottom)
                    {
                        Text("This pane ports the Cork notifications settings shape into the extracted shell, including permission-sensitive UI state.")
                            .padding()
                            .frame(width: 320)
                    }
                }
            }
        }
    }
}
