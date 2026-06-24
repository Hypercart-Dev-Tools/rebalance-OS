import Foundation
import Testing
@testable import TextReplacementCore

/// Tests the validation rules that drive the editor's inline hints and the Apply
/// preflight. `DefaultReplacementLinter` is the single source of truth for both.
struct ReplacementLinterTests {
    let linter = DefaultReplacementLinter()

    @Test func validReplacementHasNoIssues() {
        let r = Replacement(shortcut: "omw", phrase: "On my way!")
        #expect(linter.validate(r).isEmpty)
    }

    @Test func blankShortcutIsAnError() {
        let r = Replacement(shortcut: "", phrase: "On my way!")
        let codes = linter.validate(r).map(\.code)
        #expect(codes.contains("shortcut.empty"))
        #expect(linter.validate(r).first { $0.code == "shortcut.empty" }?.severity == .error)
    }

    @Test func whitespaceOnlyShortcutIsAnError() {
        let r = Replacement(shortcut: "   ", phrase: "x")
        #expect(linter.validate(r).contains { $0.code == "shortcut.empty" && $0.severity == .error })
    }

    @Test func blankPhraseIsAnError() {
        let r = Replacement(shortcut: "omw", phrase: "")
        let issue = linter.validate(r).first { $0.code == "phrase.empty" }
        #expect(issue?.severity == .error)
    }

    @Test func leadingOrTrailingWhitespaceShortcutWarns() {
        let r = Replacement(shortcut: "omw ", phrase: "On my way!")
        #expect(linter.validate(r).contains { $0.code == "shortcut.whitespace" && $0.severity == .warning })
    }

    @Test func internalWhitespaceShortcutWarns() {
        let r = Replacement(shortcut: "o w", phrase: "On my way!")
        #expect(linter.validate(r).contains { $0.code == "shortcut.contains-whitespace" && $0.severity == .warning })
    }

    @Test func issuesCarryTheReplacementID() {
        let r = Replacement(shortcut: "", phrase: "")
        #expect(linter.validate(r).allSatisfy { $0.replacementID == r.id })
    }

    @Test func duplicateShortcutsAreFlaggedAcrossTheLibrary() {
        let a = Replacement(shortcut: "dup", phrase: "first")
        let b = Replacement(shortcut: "dup", phrase: "second")
        let c = Replacement(shortcut: "unique", phrase: "third")

        let dupeIssues = linter.validate([a, b, c]).filter { $0.code == "shortcut.duplicate" }
        // Both members of the duplicate pair are flagged; the unique one is not.
        #expect(Set(dupeIssues.compactMap(\.replacementID)) == Set([a.id, b.id]))
        #expect(dupeIssues.allSatisfy { $0.severity == .error })
    }

    @Test func arrayValidationAlsoIncludesPerRowIssues() {
        let issues = linter.validate([Replacement(shortcut: "", phrase: "x")])
        #expect(issues.contains { $0.code == "shortcut.empty" })
    }
}
