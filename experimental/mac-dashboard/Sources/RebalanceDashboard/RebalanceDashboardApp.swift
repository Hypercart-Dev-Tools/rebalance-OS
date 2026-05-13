import SwiftUI

@main
struct RebalanceDashboardApp: App
{
    var body: some Scene
    {
        WindowGroup("Rebalance")
        {
            DashboardDemoRootView()
        }
        .windowResizability(.contentSize)
    }
}
