import XCTest
@testable import Focus5Float

/// Round-trips the on-disk roster cache and the bundled sample fixture — both
/// pointed at a throwaway temp URL, never the real Application Support cache.
final class RosterCacheAndSampleDataTests: XCTestCase {
    func testSampleDataDecodesBundledFixture() throws {
        let resp = try SampleData.load()
        XCTAssertFalse(resp.roster.isEmpty)
    }

    func testRosterCacheRoundTrip() throws {
        let tempURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("f5-cache-test-\(UUID().uuidString).json")
        defer { try? FileManager.default.removeItem(at: tempURL) }

        let sample = try SampleData.load()
        let cache = RosterCache(url: tempURL)
        let fetchedAt = Date()
        cache.save(sample, fetchedAt: fetchedAt)

        let loaded = try XCTUnwrap(cache.load())
        XCTAssertEqual(loaded.response.roster.count, sample.roster.count)
        XCTAssertEqual(loaded.response.roster.first?.repoName, sample.roster.first?.repoName)
        XCTAssertEqual(loaded.response.summary.rosterSize, sample.summary.rosterSize)
        // JSONEncoder's .iso8601 strategy truncates to whole seconds, so the
        // round-tripped date loses sub-second precision by design.
        XCTAssertEqual(loaded.fetchedAt.timeIntervalSince1970, fetchedAt.timeIntervalSince1970, accuracy: 1.0)
    }

    func testRosterCacheLoadReturnsNilWhenFileMissing() {
        let tempURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("f5-cache-missing-\(UUID().uuidString).json")
        let cache = RosterCache(url: tempURL)
        XCTAssertNil(cache.load())
    }
}
