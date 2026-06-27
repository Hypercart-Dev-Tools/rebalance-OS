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

    /// Defaults to the local `rebalance serve`. The payload carries local-only /
    /// PII fields (`local_path`, `vscode_url`, `remote_url`, `author_email`), so a
    /// non-loopback `FOCUS5_BASE_URL` is honored ONLY under an explicit debug
    /// opt-in (`FOCUS5_LIVETEST` / `FOCUS5_ALLOW_REMOTE`); otherwise it falls back
    /// to localhost. (CONTRACT.md: this endpoint is local-only.)
    static var defaultBaseURL: URL {
        let fallback = URL(string: "http://localhost:8787")!
        let env = ProcessInfo.processInfo.environment
        guard let raw = env["FOCUS5_BASE_URL"], let url = URL(string: raw) else {
            return fallback
        }
        let remoteAllowed = env["FOCUS5_LIVETEST"] != nil || env["FOCUS5_ALLOW_REMOTE"] != nil
        return (isLoopback(url) || remoteAllowed) ? url : fallback
    }

    private static func isLoopback(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return host == "localhost" || host == "127.0.0.1" || host == "::1" || host == "[::1]"
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
