import Foundation
import HypercartMacOSDashboard

enum DashboardDemoMaintenanceStepID: String, CaseIterable, Hashable, Sendable
{
    case pruneArtifacts
    case clearDownloads
    case validateSources
}

extension DashboardOperationStore where StepID == DashboardDemoMaintenanceStepID
{
    static func maintenanceDemoDefault() -> DashboardOperationStore<DashboardDemoMaintenanceStepID>
    {
        DashboardOperationStore(
            configuredSteps: [
                .init(id: .pruneArtifacts, title: "Prune stale artifacts", isEnabled: true),
                .init(id: .clearDownloads, title: "Clear cached downloads", isEnabled: true),
                .init(id: .validateSources, title: "Run source health check", isEnabled: false)
            ]
        )
    }
}
