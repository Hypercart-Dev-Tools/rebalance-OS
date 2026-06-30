import Foundation

// Loads the bundled `sample-focus5.json` fixture (a representative 5-card
// /focus-5.json capture) so the UI builds and runs with zero network. The
// JSONDecoder config here is the SAME one Phase 4's live client will use.

enum SampleData {
    enum SampleError: Error, CustomStringConvertible {
        case missingResource
        var description: String {
            switch self {
            case .missingResource: return "sample-focus5.json not found in Bundle.module"
            }
        }
    }

    static func decoder() -> JSONDecoder {
        let dec = JSONDecoder()
        dec.keyDecodingStrategy = .convertFromSnakeCase
        return dec
    }

    static func load() throws -> Focus5Response {
        guard let url = Bundle.module.url(forResource: "sample-focus5", withExtension: "json") else {
            throw SampleError.missingResource
        }
        return try decoder().decode(Focus5Response.self, from: Data(contentsOf: url))
    }
}
