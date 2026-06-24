import Foundation
import Testing
@testable import TextReplacementCore

/// The canonical `keyboard-replacements.v1` JSON is the wire contract between the Swift
/// app and the Python scripts (native_to_json.py / json_to_apple_sqlite.py). These tests
/// pin the field mapping and round-trip behavior.
struct CanonicalReplacementCodecTests {
    let codec = CanonicalReplacementCodec()

    @Test func encodeDecodePreservesUserFields() throws {
        let original = [
            Replacement(shortcut: "omw", phrase: "On my way!", enabled: true, groupName: "Personal", notes: "casual"),
            Replacement(shortcut: "/sig", phrase: "Sam Rivera", enabled: false, groupName: "Work", notes: nil),
        ]
        let decoded = try codec.decode(codec.encode(original))

        #expect(decoded.count == original.count)
        for (a, b) in zip(original, decoded) {
            #expect(a.id == b.id)               // ids round-trip as uuid strings
            #expect(a.shortcut == b.shortcut)
            #expect(a.phrase == b.phrase)
            #expect(a.enabled == b.enabled)
            #expect(a.groupName == b.groupName)
            #expect(a.notes == b.notes)
        }
    }

    @Test func encodedPayloadCarriesSchemaAndPythonFieldNames() throws {
        let data = try codec.encode([Replacement(shortcut: "omw", phrase: "On my way!", groupName: "Personal")])
        let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])

        #expect(json["schema"] as? String == "keyboard-replacements.v1")
        let items = try #require(json["items"] as? [[String: Any]])
        let item = try #require(items.first)
        // Python uses `group` (not `groupName`) and a string `id`.
        #expect(item["group"] as? String == "Personal")
        #expect(item["shortcut"] as? String == "omw")
        #expect(item["id"] is String)
    }

    @Test func decodeDefaultsEnabledToTrueWhenAbsent() throws {
        let json = """
        { "schema": "keyboard-replacements.v1", "items": [ { "shortcut": "omw", "phrase": "On my way!" } ] }
        """.data(using: .utf8)!
        let decoded = try codec.decode(json)
        #expect(decoded.count == 1)
        #expect(decoded[0].enabled == true)
        #expect(decoded[0].groupName == nil)
        #expect(decoded[0].notes == nil)
    }

    @Test func decodeMapsGroupOntoGroupName() throws {
        let json = """
        { "items": [ { "shortcut": "/main", "phrase": "Maintenance", "enabled": false, "group": "Work" } ] }
        """.data(using: .utf8)!
        let decoded = try codec.decode(json)
        #expect(decoded[0].groupName == "Work")
        #expect(decoded[0].enabled == false)
    }

    @Test func decodeMintsUUIDWhenIDMissingOrInvalid() throws {
        let json = """
        { "items": [ { "shortcut": "a", "phrase": "b" }, { "id": "not-a-uuid", "shortcut": "c", "phrase": "d" } ] }
        """.data(using: .utf8)!
        let decoded = try codec.decode(json)
        #expect(decoded.count == 2)              // both decode; ids are freshly minted
        #expect(decoded[0].id != decoded[1].id)
    }
}
