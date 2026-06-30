import Foundation

private struct Focus5APIErrorBody: Decodable {
    let detail: String?
    let error: String?
    let message: String?
    let reason: String?
}

enum Focus5ClientError: LocalizedError {
    case allCandidatesFailed(path: String, attempts: [String])
    case transport(url: URL, underlying: URLError)
    case invalidResponse(path: String)
    case http(url: URL, status: Int, message: String?)
    case decoding(url: URL, underlying: Error)

    var errorDescription: String? {
        switch self {
        case .allCandidatesFailed(let path, let attempts):
            if attempts.isEmpty {
                return "Couldn't load \(path) from the local Focus 5 servers."
            }
            return "Couldn't load \(path). Tried " + attempts.joined(separator: " | ")
        case .transport(let url, let err):
            switch err.code {
            case .cannotConnectToHost, .cannotFindHost, .networkConnectionLost, .notConnectedToInternet:
                return "Can't reach rebalance serve at \(url.host(percentEncoded: false) ?? "localhost"):\(url.port ?? 80) for \(url.path)."
            case .timedOut:
                return "Timed out waiting for \(url.path) from rebalance serve."
            default:
                return "Network error for \(url.path): \(err.localizedDescription)"
            }
        case .invalidResponse(let path):
            return "Invalid response from rebalance serve for \(path)."
        case .http(let url, let status, let message):
            if status == 404 && url.path == "/focus-5/goals" {
                return "The local server returned 404 for \(url.path). Restart rebalance serve or reinstall the updated server routes."
            }
            if let message, !message.isEmpty {
                return "Server error \(status) for \(url.path): \(message)"
            }
            return "Server error \(status) for \(url.path)."
        case .decoding(let url, let err):
            return "Couldn't decode \(url.path): \(err.localizedDescription)"
        }
    }
}

// Live client for the SAME endpoint that backs the web /focus-5 page:
//   GET /focus-5.json → summarize_focus5(db, mode)   (src/rebalance/web.py)
// Read-only. `?view=dirty` re-ranks in memory exactly like the web "Dirty Five"
// tab. NO ranking / git / DB logic lives here — the server owns it; the client
// only fetches and decodes. (Reading SQLite directly would be a divergent path
// and lose the live re-probe; see the project Architecture Decision.)
struct Focus5Client {
    var baseURL: URL
    var session: URLSession

    static let pulseServerBaseURL = URL(string: "http://127.0.0.1:8767")!

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

    private var candidateBaseURLs: [URL] {
        let env = ProcessInfo.processInfo.environment
        if env["FOCUS5_BASE_URL"] != nil {
            return [baseURL]
        }
        return Self.dedupedURLs([baseURL, Self.pulseServerBaseURL])
    }

    private static func dedupedURLs(_ urls: [URL]) -> [URL] {
        var seen: Set<String> = []
        var out: [URL] = []
        for url in urls {
            let key = "\(url.scheme ?? "http")://\(url.host(percentEncoded: false) ?? ""):\(url.port ?? 80)"
            if seen.insert(key).inserted {
                out.append(url)
            }
        }
        return out
    }

    private func request(_ req: URLRequest, for base: URL) -> URLRequest {
        guard let current = req.url,
              var comps = URLComponents(url: current, resolvingAgainstBaseURL: false)
        else { return req }
        comps.scheme = base.scheme
        comps.host = base.host(percentEncoded: false)
        comps.port = base.port
        var copy = req
        copy.url = comps.url
        return copy
    }

    private static func describeAttempt(_ error: Focus5ClientError) -> String {
        switch error {
        case .transport(let url, let underlying):
            return "\(url.host(percentEncoded: false) ?? "localhost"):\(url.port ?? 80) \(underlying.localizedDescription)"
        case .http(let url, let status, let message):
            if let message, !message.isEmpty {
                return "\(url.host(percentEncoded: false) ?? "localhost"):\(url.port ?? 80) HTTP \(status) \(message)"
            }
            return "\(url.host(percentEncoded: false) ?? "localhost"):\(url.port ?? 80) HTTP \(status)"
        case .decoding(let url, let underlying):
            return "\(url.host(percentEncoded: false) ?? "localhost"):\(url.port ?? 80) decode \(underlying.localizedDescription)"
        case .invalidResponse(let path):
            return "invalid response for \(path)"
        case .allCandidatesFailed(_, let attempts):
            return attempts.joined(separator: " | ")
        }
    }

    private func execute(_ req: URLRequest) async throws -> (Data, HTTPURLResponse) {
        var attempts: [String] = []
        var lastError: Focus5ClientError?
        let path = req.url?.path ?? "(unknown)"

        for base in candidateBaseURLs {
            let candidateReq = request(req, for: base)
            do {
                let (data, response) = try await session.data(for: candidateReq)
                guard let http = response as? HTTPURLResponse else {
                    throw Focus5ClientError.invalidResponse(path: candidateReq.url?.path ?? path)
                }
                guard (200..<300).contains(http.statusCode) else {
                    throw Focus5ClientError.http(
                        url: candidateReq.url ?? baseURL,
                        status: http.statusCode,
                        message: Self.errorMessage(from: data)
                    )
                }
                return (data, http)
            } catch let err as Focus5ClientError {
                lastError = err
                attempts.append(Self.describeAttempt(err))
            } catch let err as URLError {
                let wrapped = Focus5ClientError.transport(url: candidateReq.url ?? baseURL, underlying: err)
                lastError = wrapped
                attempts.append(Self.describeAttempt(wrapped))
            } catch {
                throw error
            }
        }

        if attempts.count <= 1, let lastError {
            throw lastError
        }
        throw Focus5ClientError.allCandidatesFailed(path: path, attempts: attempts)
    }

    private func decode<T: Decodable>(_ type: T.Type, from req: URLRequest) async throws -> T {
        let (data, _) = try await execute(req)
        do {
            return try Focus5JSON.decoder().decode(T.self, from: data)
        } catch {
            throw Focus5ClientError.decoding(url: req.url ?? baseURL, underlying: error)
        }
    }

    private static func errorMessage(from data: Data) -> String? {
        if let body = try? Focus5JSON.decoder().decode(Focus5APIErrorBody.self, from: data) {
            for candidate in [body.detail, body.error, body.message, body.reason] {
                let text = (candidate ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                if !text.isEmpty { return text }
            }
        }
        let text = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard let text, !text.isEmpty else { return nil }
        return text.count > 220 ? String(text.prefix(220)) + "…" : text
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
        return try await decode(Focus5Response.self, from: req)
    }

    /// Fetch the operator's `focus5.md` note from the local vault, projected by the
    /// server's read-only `GET /focus-5/note` route. The server always answers with
    /// `{exists, content, path}`; `exists == false` means no vault / no note yet.
    func fetchNote() async throws -> Focus5Note {
        var req = URLRequest(url: baseURL.appendingPathComponent("focus-5/note"))
        req.httpMethod = "GET"                       // read-only, always GET
        req.timeoutInterval = 6
        req.cachePolicy = .reloadIgnoringLocalCacheData

        do {
            return try await decode(Focus5Note.self, from: req)
        } catch let err as Focus5ClientError {
            // Note is optional: a non-2xx (e.g. a server that doesn't expose the
            // route) means "no note", not a failure — never break the card over it.
            switch err {
            case .http:
                return Focus5Note(exists: false, content: "", path: nil)
            default:
                throw err
            }
        }
    }

    /// Fetch the top open tasks from the local vault's `0. Goals.md`, projected by
    /// the server's read-only `GET /focus-5/goals` route. Missing vault/file is a
    /// normal empty state (`exists == false`), not an error.
    func fetchGoals() async throws -> Focus5GoalsResponse {
        var req = URLRequest(url: baseURL.appendingPathComponent("focus-5/goals"))
        req.httpMethod = "GET"
        req.timeoutInterval = 6
        req.cachePolicy = .reloadIgnoringLocalCacheData
        return try await decode(Focus5GoalsResponse.self, from: req)
    }

    /// Complete one `0. Goals.md` checkbox through the server's local-only write
    /// route, then decode the refreshed top-8 response body.
    func completeGoal(title: String, lineIndex: Int) async throws -> Focus5GoalCompleteResponse {
        struct GoalCompletePayload: Encodable {
            let title: String
            let lineIndex: Int

            enum CodingKeys: String, CodingKey {
                case title
                case lineIndex = "line_index"
            }
        }

        var req = URLRequest(url: baseURL.appendingPathComponent("api/focus5/goals/complete"))
        req.httpMethod = "POST"
        req.timeoutInterval = 6
        req.cachePolicy = .reloadIgnoringLocalCacheData
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(GoalCompletePayload(title: title, lineIndex: lineIndex))
        return try await decode(Focus5GoalCompleteResponse.self, from: req)
    }
}

/// Wire shape of `GET /focus-5/note` — the Focus 5 Float bottom note.
struct Focus5Note: Codable {
    let exists: Bool
    let content: String
    let path: String?
}
