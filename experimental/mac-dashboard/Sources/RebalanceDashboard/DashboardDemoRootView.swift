import SwiftUI
import HypercartMacOSDashboard

struct DashboardDemoRootView: View
{
    @State private var store: DashboardDemoStore = .init()

    var body: some View
    {
        @Bindable var store = store

        NavigationSplitView
        {
            sidebar(store: store)
        } detail: {
            detail(store: store)
        }
        .frame(minWidth: 1000, minHeight: 640)
        .sheet(item: $store.presentation.activeSheet) { sheet in
            switch sheet.payload
            {
            case .settings:
                DashboardDemoSettingsView(store: store)
            case .maintenance:
                DashboardDemoMaintenanceView(store: store)
            }
        }
        .alert(item: $store.presentation.activeAlert) { alert in
            Alert(
                title: Text(alert.title),
                message: alert.message.map(Text.init),
                dismissButton: .default(Text(alert.recoveryActionTitle ?? "OK"))
            )
        }
        .confirmationDialog(
            store.presentation.activeConfirmation?.title ?? "Confirm",
            isPresented: Binding(
                get: { store.presentation.activeConfirmation != nil },
                set: { isPresented in
                    if !isPresented
                    {
                        store.presentation.dismissConfirmation()
                    }
                }
            ),
            titleVisibility: .visible
        ) {
            Button(
                store.presentation.activeConfirmation?.confirmLabel ?? "Confirm",
                role: store.presentation.activeConfirmation?.role == .destructive ? .destructive : nil
            ) {
                store.confirmRemoval()
            }

            Button(store.presentation.activeConfirmation?.cancelLabel ?? "Cancel", role: .cancel) {
                store.presentation.dismissConfirmation()
            }
        } message: {
            if let message = store.presentation.activeConfirmation?.message
            {
                Text(message)
            }
        }
        .task {
            if case .idle = store.loadState
            {
                await store.refresh()
            }
        }
    }

    @ViewBuilder
    private func sidebar(store: DashboardDemoStore) -> some View
    {
        VStack(alignment: .leading, spacing: 12)
        {
            Text("Hypercart Dashboard")
                .font(.title2.weight(.semibold))

            MacSearchField(
                text: Binding(
                    get: { store.presentation.searchQuery },
                    set: { store.presentation.searchQuery = $0 }
                ),
                prompt: "Search modules"
            )

            List(store.filteredItems) { item in
                Button {
                    store.select(item)
                } label: {
                    DashboardDemoSidebarRow(
                        item: item,
                        isSelected: store.selectedItem?.id == item.id
                    )
                }
                .buttonStyle(.plain)
                .contextMenu {
                    Button("Remove…") {
                        store.promptRemoval(of: item)
                    }
                }
            }
            .listStyle(.sidebar)
        }
        .padding()
        .toolbar {
            ToolbarItemGroup {
                Button("Refresh") {
                    Task {
                        await store.refresh()
                    }
                }

                Button("Settings") {
                    store.presentSettings()
                }

                Button("Maintenance") {
                    store.presentMaintenance()
                }
            }
        }
    }

    @ViewBuilder
    private func detail(store: DashboardDemoStore) -> some View
    {
        if let item = store.selectedItem
        {
            DashboardDemoDetailView(
                item: item,
                inlineErrorMessage: store.presentation.inlineErrorMessage,
                onDismissInlineError: store.dismissInlineError,
                onShowAlert: store.simulateAlert,
                onShowInlineError: store.simulateInlineFailure,
                onRemove: { store.promptRemoval(of: item) }
            )
        }
        else
        {
            InlineErrorView(
                title: "Select a module",
                message: "This placeholder stands in for the main dashboard detail pane."
            )
        }
    }
}
