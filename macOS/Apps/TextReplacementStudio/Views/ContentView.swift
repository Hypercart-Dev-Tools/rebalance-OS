import SwiftUI
import TextReplacementCore

/// Exposes ContentView's "add" action to the menu bar so File ▸ New Replacement (⌘N)
/// drives the same code path as the in-window affordances.
struct NewReplacementKey: FocusedValueKey { typealias Value = () -> Void }
extension FocusedValues {
    var newReplacement: (() -> Void)? {
        get { self[NewReplacementKey.self] }
        set { self[NewReplacementKey.self] = newValue }
    }
}

struct ContentView: View {
    @State private var model = StudioModel()
    @State private var searchText = ""
    @State private var selectedFilter: ReplacementFilter = .all
    @State private var selectedReplacementID: Replacement.ID?
    @State private var showPreview = false
    @State private var confirmApply = false

    private var strategyBinding: Binding<AppleDatabaseWriter.Strategy> {
        Binding(get: { model.strategy }, set: { model.strategy = $0 })
    }

    var body: some View {
        NavigationSplitView {
            SidebarView(model: model, selectedFilter: $selectedFilter)
                .navigationSplitViewColumnWidth(min: 200, ideal: 230, max: 300)
        } content: {
            ReplacementListView(
                model: model,
                searchText: $searchText,
                selectedFilter: selectedFilter,
                selectedReplacementID: $selectedReplacementID,
                onAdd: newReplacement
            )
            .navigationSplitViewColumnWidth(min: 340, ideal: 392, max: 520)
        } detail: {
            ReplacementDetailEditor(model: model, replacementID: selectedReplacementID)
                .navigationSplitViewColumnWidth(min: 380, ideal: 520)
        }
        .navigationSplitViewStyle(.balanced)
        .navigationTitle("Text Replacements")
        .navigationSubtitle("\(model.replacements.count) replacement\(model.replacements.count == 1 ? "" : "s")")
        .frame(minWidth: 820, minHeight: 520)
        .tint(Theme.accent)
        .toolbar { toolbarContent }
        .focusedValue(\.newReplacement, newReplacement)
        .overlay(alignment: .bottom) { toastOverlay }
        .task {
            if model.replacements.isEmpty { await model.importFromMacOS() }
            if selectedReplacementID == nil { selectedReplacementID = model.replacements.first?.id }
        }
        .task(id: model.toast?.id) { await autoDismissToast() }
        .sheet(isPresented: $showPreview) {
            PreviewPlanSheet(
                model: model,
                strategy: model.strategy,
                onApply: { showPreview = false; confirmApply = true },
                onCancel: { showPreview = false }
            )
        }
        .confirmationDialog(
            "Write to your live macOS Text Replacements database?",
            isPresented: $confirmApply,
            titleVisibility: .visible
        ) {
            Button("Apply (\(model.strategy.rawValue))", role: .destructive) {
                Task { await model.pushToMacOS(strategy: model.strategy, write: true) }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("A timestamped backup is written first. Afterward you may need to quit and reopen System Settings and affected apps for changes to show.")
        }
    }

    // MARK: Toolbar — Import · Merge/Replace · Preview · Apply

    @ToolbarContentBuilder private var toolbarContent: some ToolbarContent {
        ToolbarItemGroup(placement: .primaryAction) {
            if model.isBusy {
                ProgressView().controlSize(.small)
            }

            Button {
                Task { await model.importFromMacOS() }
            } label: {
                Label("Import", systemImage: "square.and.arrow.down")
            }
            .disabled(model.isBusy)
            .help("Re-read the live macOS Text Replacements database.")

            Picker("Strategy", selection: strategyBinding) {
                Text("Merge").tag(AppleDatabaseWriter.Strategy.merge)
                Text("Replace").tag(AppleDatabaseWriter.Strategy.replace)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .fixedSize()
            .help("Merge adds & updates; Replace also removes shortcuts no longer present.")

            Button("Preview Plan") { showPreview = true }
                .disabled(model.replacements.isEmpty)
                .help("See what Apply would change — writes nothing.")

            Button("Apply to macOS…") { confirmApply = true }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.return, modifiers: .command)
                .disabled(model.isBusy || model.replacements.isEmpty)
                .help("Write your edits to the live macOS database (backup made first).")
        }
    }

    // MARK: Toast

    @ViewBuilder private var toastOverlay: some View {
        if let toast = model.toast {
            ToastView(
                toast: toast,
                onAction: { action in
                    withAnimation(Theme.spring) { model.toast = nil }
                    switch action {
                    case .retryApply:  confirmApply = true
                    case .retryImport: Task { await model.importFromMacOS() }
                    }
                },
                onDismiss: { withAnimation(Theme.spring) { model.toast = nil } }
            )
            .transition(.move(edge: .bottom).combined(with: .opacity))
        }
    }

    private func autoDismissToast() async {
        guard let toast = model.toast, toast.style != .error else { return }
        try? await Task.sleep(for: .seconds(4))
        if model.toast?.id == toast.id {
            withAnimation(Theme.spring) { model.toast = nil }
        }
    }

    // MARK: New replacement

    /// Add a blank replacement and select it for editing. Clears the search and makes
    /// sure the new row is visible: if a Group is filtered, the row joins that group;
    /// otherwise the view falls back to All (so it isn't hidden by Disabled/Duplicates/etc.).
    private func newReplacement() {
        searchText = ""
        let group: String?
        if case let .group(name) = selectedFilter {
            group = name
        } else {
            group = nil
            if selectedFilter != .all { selectedFilter = .all }
        }
        selectedReplacementID = model.addReplacement(groupName: group)
    }
}
