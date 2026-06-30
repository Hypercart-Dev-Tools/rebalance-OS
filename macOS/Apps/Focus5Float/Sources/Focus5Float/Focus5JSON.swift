import Foundation

// The single JSON decode config, shared by the live client and the fixture
// loader so there is exactly ONE decode path (Phase 4 QA). Matches the wire
// shape documented in CONTRACT.md.
enum Focus5JSON {
    static func decoder() -> JSONDecoder {
        let dec = JSONDecoder()
        dec.keyDecodingStrategy = .convertFromSnakeCase
        return dec
    }
}
