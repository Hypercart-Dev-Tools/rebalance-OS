import SwiftUI
import HypercartMacOSDashboard

struct DashboardDemoGeneralSettingsPane: View
{
    @Bindable var store: DashboardDemoStore

    var body: some View
    {
        SettingsPaneTemplate
        {
            Form
            {
                Picker("Sort dashboard modules", selection: $store.sortMode)
                {
                    ForEach(DashboardDemoPackageSortMode.allCases) { mode in
                        Text(mode.title)
                    }
                }

                Picker("Show only manually pinned modules", selection: $store.displayOnlyPrimaryItemsByDefault)
                {
                    Text("Yes").tag(true)
                    Text("No").tag(false)
                }
                .pickerStyle(.radioGroup)

                LabeledContent("Dependency detail")
                {
                    Toggle("Show advanced dependency chains", isOn: $store.displayAdvancedDependencies)
                }

                Picker("Inline notes", selection: $store.caveatDisplayMode)
                {
                    ForEach(DashboardDemoCaveatDisplayMode.allCases) { mode in
                        Text(mode.title).tag(mode)
                    }
                }
                .pickerStyle(.radioGroup)

                if store.caveatDisplayMode == .compact
                {
                    Text("Compact notes keep the dashboard denser but hide some supporting detail.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                LabeledContent("Search results")
                {
                    Toggle("Show descriptions in results", isOn: $store.showDescriptionsInSearchResults)
                }

                LabeledContent("Update display")
                {
                    VStack(alignment: .leading, spacing: 6)
                    {
                        Picker("Info amount", selection: Binding(
                            get: { store.outdatedInfoMode },
                            set: { store.updateOutdatedInfoMode($0) }
                        ))
                        {
                            ForEach(DashboardDemoOutdatedInfoMode.allCases) { mode in
                                Text(mode.title).tag(mode)
                            }
                        }
                        .labelsHidden()

                        Toggle("Also show previous versions", isOn: $store.showPreviousVersionsInUpdateList)
                            .disabled(store.outdatedInfoMode != .versionOnly)
                            .padding(.leading)
                    }
                }

                LabeledContent("Module details")
                {
                    VStack(alignment: .leading)
                    {
                        Toggle("Show dependency search field", isOn: $store.showDependencySearchField)
                        Toggle("Enable Reveal in Finder actions", isOn: $store.enableRevealInFinder)
                        Toggle("Enable swipe actions", isOn: $store.enableSwipeActions)
                        Toggle("Enable extra animations", isOn: $store.enableExtraAnimations)
                    }
                }

                LabeledContent("Menu bar")
                {
                    Toggle("Show dashboard in menu bar", isOn: $store.showInMenuBar)
                }

                LabeledContent("App startup")
                {
                    Toggle("Launch at login", isOn: $store.launchAtLogin)
                }

                LabeledContent("Backup date format")
                {
                    VStack(alignment: .leading, spacing: 6)
                    {
                        Picker("Date style", selection: $store.backupDateStyle)
                        {
                            ForEach(DashboardDemoBackupDateStyle.allCases) { dateStyle in
                                Text(dateStyle.title)
                                    .tag(dateStyle)
                            }
                        }
                        .labelsHidden()

                        if let demoDate = Calendar.current.date(from: .init(calendar: .current, timeZone: .gmt, year: 2022, month: 7, day: 3)),
                           store.backupDateStyle != .omitted
                        {
                            Text(demoDate.formatted(date: store.backupDateStyle.dateStyle, time: .omitted))
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
    }
}
