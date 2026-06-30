import SwiftUI
import TextReplacementCore

/// Right column: the content-first inspector for the selected replacement —
/// shortcut key-cap, enable toggle, the expanded phrase in a roomy well, then
/// Group and Notes rows. Edits write straight back into the model.
struct ReplacementDetailEditor: View {
    let model: StudioModel
    let replacementID: Replacement.ID?

    private static let noneTag = "\u{0}none"   // sentinel for "Ungrouped" in the picker

    @FocusState private var shortcutFocused: Bool

    var body: some View {
        if let index = model.index(of: replacementID) {
            let issues = model.issues(for: replacementID)
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    header(index, issues: issues.filter { $0.code.hasPrefix("shortcut") })
                    Spacer().frame(height: 26)
                    phraseSection(index, issues: issues.filter { $0.code.hasPrefix("phrase") })
                    Spacer().frame(height: 18)
                    groupRow(index)
                    notesRow(index)
                }
                .padding(.horizontal, 32)
                .padding(.vertical, 26)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Theme.window)
            .onChange(of: replacementID) { focusIfBlank() }
            .onAppear { focusIfBlank() }
        } else {
            emptyState
        }
    }

    /// Drop the cursor into the shortcut field when a freshly-added (blank) row is shown.
    private func focusIfBlank() {
        guard let i = model.index(of: replacementID), model.replacements[i].shortcut.isEmpty
        else { return }
        shortcutFocused = true
    }

    // MARK: Header — shortcut + enabled

    private func header(_ index: Int, issues: [ReplacementValidationIssue]) -> some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 9) {
                caption("SHORTCUT")
                TextField("shortcut", text: stringBinding(index, \.shortcut))
                    .textFieldStyle(.plain)
                    .font(.system(size: 17, design: .monospaced).weight(.medium))
                    .foregroundStyle(Theme.text)
                    .focused($shortcutFocused)
                    .frame(minWidth: 60)
                    .fixedSize()
                    .padding(.horizontal, 15)
                    .frame(height: 40)
                    .background(Theme.keycapBG, in: RoundedRectangle(cornerRadius: 9, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 9, style: .continuous)
                            .strokeBorder(borderColor(issues, base: Theme.keycapBorder), lineWidth: 1)
                    )
                hintList(issues)
            }
            Spacer()
            HStack(spacing: 10) {
                Text("Enabled").font(Theme.bodyMed).foregroundStyle(Theme.text2)
                StudioToggle(isOn: boolBinding(index, \.enabled), controlSize: .regular)
            }
            .padding(.top, 27)
        }
    }

    // MARK: Phrase

    private func phraseSection(_ index: Int, issues: [ReplacementValidationIssue]) -> some View {
        let phrase = model.replacements[index].phrase
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                caption("EXPANDED PHRASE")
                Spacer()
                Text("\(phrase.count) character\(phrase.count == 1 ? "" : "s")")
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.text3)
                    .monospacedDigit()
            }
            TextEditor(text: stringBinding(index, \.phrase))
                .font(.system(size: 13))
                .foregroundStyle(Theme.text)
                .lineSpacing(4)
                .scrollContentBackground(.hidden)
                .padding(14)
                .frame(minHeight: 220, maxHeight: .infinity)
                .background(Theme.elevated, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 11, style: .continuous)
                        .strokeBorder(borderColor(issues, base: Theme.separator2), lineWidth: 1)
                )
            hintList(issues)
        }
    }

    // MARK: Validation hints

    /// Inline issue rows shown under a field. Errors read red, warnings amber.
    @ViewBuilder private func hintList(_ issues: [ReplacementValidationIssue]) -> some View {
        if !issues.isEmpty {
            VStack(alignment: .leading, spacing: 3) {
                ForEach(issues) { issue in
                    Label {
                        Text(issue.message).font(.system(size: 11))
                    } icon: {
                        Image(systemName: issue.severity == .error
                              ? "exclamationmark.octagon.fill" : "exclamationmark.triangle.fill")
                            .font(.system(size: 10))
                    }
                    .labelStyle(.titleAndIcon)
                    .foregroundStyle(issue.severity == .error ? Theme.diffRemove : Color.orange)
                }
            }
            .padding(.top, 2)
        }
    }

    private func borderColor(_ issues: [ReplacementValidationIssue], base: Color) -> Color {
        issues.contains { $0.severity == .error } ? Theme.diffRemove : base
    }

    // MARK: Group

    private func groupRow(_ index: Int) -> some View {
        HStack {
            Text("Group").font(Theme.bodyMed).foregroundStyle(Theme.text2)
            Spacer()
            Picker("Group", selection: groupBinding(index)) {
                Text("Ungrouped").tag(Self.noneTag)
                Divider()
                ForEach(model.groups) { g in
                    HStack(spacing: 7) {
                        Circle().fill(g.color).frame(width: 8, height: 8)
                        Text(g.name)
                    }
                    .tag(g.name)
                }
                // Allow keeping a group that has only this (new) member.
                let current = model.replacements[index].groupName ?? ""
                if !current.isEmpty, !model.groups.contains(where: { $0.name == current }) {
                    Text(current).tag(current)
                }
            }
            .labelsHidden()
            .pickerStyle(.menu)
            .fixedSize()
            .tint(Theme.text)
        }
        .padding(.vertical, 11)
        .overlay(Rectangle().fill(Theme.separator).frame(height: 1), alignment: .top)
    }

    // MARK: Notes

    private func notesRow(_ index: Int) -> some View {
        HStack(alignment: .top, spacing: 20) {
            Text("Notes").font(Theme.bodyMed).foregroundStyle(Theme.text2)
            Spacer()
            TextField("Add a note…", text: optionalBinding(index, \.notes), axis: .vertical)
                .textFieldStyle(.plain)
                .font(.system(size: 13))
                .foregroundStyle(Theme.text)
                .multilineTextAlignment(.trailing)
                .lineLimit(1...6)
                .frame(maxWidth: 300, alignment: .trailing)
        }
        .padding(.vertical, 11)
        .overlay(Rectangle().fill(Theme.separator).frame(height: 1), alignment: .top)
    }

    // MARK: Bits

    private func caption(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11, weight: .semibold))
            .tracking(0.6)
            .foregroundStyle(Theme.text2)
    }

    private var emptyState: some View {
        VStack(spacing: Theme.Space.m) {
            Image(systemName: "character.cursor.ibeam")
                .font(.system(size: 30))
                .foregroundStyle(Theme.text3)
            Text("No replacement selected")
                .font(Theme.display).foregroundStyle(Theme.text2)
            Text("Select a replacement to edit it, then Apply to macOS.")
                .font(Theme.body).foregroundStyle(Theme.text3)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.window)
    }

    // MARK: Bindings (resolve the row by id each time so edits survive reordering)

    private func stringBinding(_ index: Int, _ keyPath: WritableKeyPath<Replacement, String>) -> Binding<String> {
        Binding(
            get: { MainActor.assumeIsolated { model.replacements[index][keyPath: keyPath] } },
            set: { value in MainActor.assumeIsolated {
                model.replacements[index][keyPath: keyPath] = value
                model.replacements[index].updatedAt = Date()
            } }
        )
    }

    private func boolBinding(_ index: Int, _ keyPath: WritableKeyPath<Replacement, Bool>) -> Binding<Bool> {
        Binding(
            get: { MainActor.assumeIsolated { model.replacements[index][keyPath: keyPath] } },
            set: { value in MainActor.assumeIsolated {
                model.replacements[index][keyPath: keyPath] = value
                model.replacements[index].updatedAt = Date()
            } }
        )
    }

    private func optionalBinding(_ index: Int, _ keyPath: WritableKeyPath<Replacement, String?>) -> Binding<String> {
        Binding(
            get: { MainActor.assumeIsolated { model.replacements[index][keyPath: keyPath] ?? "" } },
            set: { value in MainActor.assumeIsolated {
                model.replacements[index][keyPath: keyPath] = value.isEmpty ? nil : value
                model.replacements[index].updatedAt = Date()
            } }
        )
    }

    /// String-keyed binding for the Group picker; the sentinel maps to `nil`.
    private func groupBinding(_ index: Int) -> Binding<String> {
        Binding(
            get: { MainActor.assumeIsolated {
                let g = model.replacements[index].groupName ?? ""
                return g.isEmpty ? Self.noneTag : g
            } },
            set: { value in MainActor.assumeIsolated {
                model.replacements[index].groupName = value == Self.noneTag ? nil : value
                model.replacements[index].updatedAt = Date()
            } }
        )
    }
}
