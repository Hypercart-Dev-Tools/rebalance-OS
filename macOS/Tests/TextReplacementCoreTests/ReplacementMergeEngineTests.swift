import Foundation
import Testing
@testable import TextReplacementCore

/// The merge engine computes the diff used on import and underpins Merge/Replace
/// semantics. Changes are keyed by shortcut (matching the Python writer).
struct ReplacementMergeEngineTests {
    let engine = DefaultReplacementMergeEngine()

    @Test func incomingShortcutNotPresentLocallyIsAnAdd() {
        let incoming = Replacement(shortcut: "new", phrase: "brand new")
        let changes = engine.merge(local: [], incoming: [incoming], policy: .previewConflicts)
        guard case .add(let r) = changes.first else { Issue.record("expected .add"); return }
        #expect(r.shortcut == "new")
    }

    @Test func identicalPhraseIsSkipped() {
        let local = Replacement(shortcut: "omw", phrase: "On my way!")
        let incoming = Replacement(shortcut: "omw", phrase: "On my way!")
        let changes = engine.merge(local: [local], incoming: [incoming], policy: .previewConflicts)
        guard case .skip = changes.first else { Issue.record("expected .skip"); return }
    }

    @Test func differingPhraseUnderPreviewIsAConflict() {
        let local = Replacement(shortcut: "omw", phrase: "On my way!")
        let incoming = Replacement(shortcut: "omw", phrase: "Omw shortly")
        let diff = engine.diff(local: [local], incoming: [incoming])
        #expect(diff.hasConflicts)
    }

    @Test func replaceLocalProducesUpdatePreservingIdentity() {
        let local = Replacement(shortcut: "omw", phrase: "old", createdAt: Date(timeIntervalSince1970: 0))
        let incoming = Replacement(shortcut: "omw", phrase: "new")
        let changes = engine.merge(local: [local], incoming: [incoming], policy: .replaceLocal)
        guard case .update(let old, let new) = changes.first else { Issue.record("expected .update"); return }
        #expect(old.id == local.id)
        #expect(new.id == local.id)                         // identity preserved
        #expect(new.createdAt == local.createdAt)           // createdAt preserved
        #expect(new.phrase == "new")
    }

    @Test func keepLocalAndAddOnlySkipExistingConflicts() {
        let local = Replacement(shortcut: "omw", phrase: "old")
        let incoming = Replacement(shortcut: "omw", phrase: "new")
        for policy in [ReplacementMergePolicy.keepLocal, .addOnly] {
            let changes = engine.merge(local: [local], incoming: [incoming], policy: policy)
            guard case .skip = changes.first else { Issue.record("expected .skip for \(policy)"); return }
        }
    }

    @Test func noConflictsWhenEverythingIsNew() {
        let diff = engine.diff(local: [], incoming: [Replacement(shortcut: "a", phrase: "1")])
        #expect(!diff.hasConflicts)
    }
}
