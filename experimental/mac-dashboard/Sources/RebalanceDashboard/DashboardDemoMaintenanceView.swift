import SwiftUI
import HypercartMacOSDashboard

struct DashboardDemoMaintenanceView: View
{
    @Environment(\.dismiss) private var dismiss
    @Bindable var store: DashboardDemoStore

    var body: some View
    {
        NavigationStack
        {
            SheetContainer(showsTitleBar: store.maintenanceOperation.phase == .ready)
            {
                Group
                {
                    switch store.maintenanceOperation.phase
                    {
                    case .ready:
                        readyView
                    case .running:
                        runningView
                    case .finished:
                        finishedView
                    }
                }
                .navigationTitle(store.maintenanceOperation.phase == .ready ? "Maintenance" : "")
                .toolbar
                {
                    if store.maintenanceOperation.phase != .running
                    {
                        ToolbarItem(placement: .cancellationAction)
                        {
                            Button(store.maintenanceOperation.phase == .finished ? "Close" : "Cancel")
                            {
                                dismiss()
                            }
                            .keyboardShortcut(.cancelAction)
                        }
                    }

                    if store.maintenanceOperation.phase == .ready
                    {
                        ToolbarItem(placement: .primaryAction)
                        {
                            Button("Start")
                            {
                                Task {
                                    await store.runMaintenanceDemo()
                                }
                            }
                            .keyboardShortcut(.defaultAction)
                            .disabled(!store.maintenanceOperation.canStart)
                        }
                    }
                }
            }
        }
        .frame(minWidth: 520, minHeight: 360)
    }

    private var readyView: some View
    {
        Form
        {
            LabeledContent("Artifacts")
            {
                Toggle(
                    store.maintenanceOperation.configuredSteps.first(where: { $0.id == .pruneArtifacts })?.title ?? "Prune stale artifacts",
                    isOn: Binding(
                        get: { store.isMaintenanceStepEnabled(.pruneArtifacts) },
                        set: { store.maintenanceOperation.updateStep(id: .pruneArtifacts, isEnabled: $0) }
                    )
                )
            }

            LabeledContent("Downloads")
            {
                Toggle(
                    store.maintenanceOperation.configuredSteps.first(where: { $0.id == .clearDownloads })?.title ?? "Clear cached downloads",
                    isOn: Binding(
                        get: { store.isMaintenanceStepEnabled(.clearDownloads) },
                        set: { store.maintenanceOperation.updateStep(id: .clearDownloads, isEnabled: $0) }
                    )
                )
            }

            LabeledContent("Validation")
            {
                Toggle(
                    store.maintenanceOperation.configuredSteps.first(where: { $0.id == .validateSources })?.title ?? "Run source health check",
                    isOn: Binding(
                        get: { store.isMaintenanceStepEnabled(.validateSources) },
                        set: { store.maintenanceOperation.updateStep(id: .validateSources, isEnabled: $0) }
                    )
                )
            }
        }
    }

    private var runningView: some View
    {
        DashboardOperationProgressPanel(title: store.maintenanceOperation.currentStepTitle)
    }

    private var finishedView: some View
    {
        DashboardOperationStatusCard(
            systemImage: store.maintenanceOperation.foundNoProblems ? "checkmark.seal" : "exclamationmark.triangle",
            title: store.maintenanceOperation.foundNoProblems ? "Maintenance completed" : "Maintenance completed with issues"
        ) {
            DashboardOperationSummaryList(items: store.maintenanceOperation.summaryItems)
        }
    }
}
