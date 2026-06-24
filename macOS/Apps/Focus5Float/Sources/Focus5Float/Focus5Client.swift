import Foundation

// Live client for the SAME endpoint that backs the web /focus-5 page:
//   GET /focus-5.json → summarize_focus5(db, mode)   (src/rebalance/web.py)
// Read-only. `?view=dirty` re-ranks in memory exactly like the web "Dirty Five"
// tab. NO ranking / git / DB logic lives here — the server owns it; the client
// only fetches and decodes. (Reading SQLite directly would be a divergent path
// and lose the live re-probe; see the project Architecture Decision.)
struct Focus5Client {
    var baseURL: URL
    var session: URLSession

    init(baseURL: URL = Focus5Client.defaultBaseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    /// Defaults to the local `rebalance serve`; override with FOCUS5_BASE_URL.
    static var defaultBaseURL: URL {
        if let raw = ProcessInfo.processInfo.environment["FOCUS5_BASE_URL"],
           let url = URL(string: raw) {
            return url
        }
        return URL(string: "http://localhost:8787")!
    }

    func fetch(dirty: Bool) async throws -> Focus5Response {
        var comps = URLComponents(
            url: baseURL.appendingPathComponent("focus-5.json"),
            resolvingAgainstBaseURL: false
        )!
        if dirty { comps.queryItems = [URLQueryItem(name: "view", value: "dirty")] }

        var req = URLRequest(url: comps.url!)
        req.httpMethod = "GET"                       // read-only, always GET
        req.timeoutInterval = 6
        req.cachePolicy = .reloadIgnoringLocalCacheData

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse,
              (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try Focus5JSON.decoder().decode(Focus5Response.self, from: data)
    }
}
