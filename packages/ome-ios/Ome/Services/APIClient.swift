import Foundation

/// Ome API client — handles all communication with ome-server.
/// Supports anonymous sessions, authenticated requests, and SSE streaming.
actor APIClient {
    static let shared = APIClient()

    #if DEBUG
    private let baseURL = "http://localhost:8765/api"
    #else
    private let baseURL = "https://api.ome.ai/api"
    #endif

    private var token: String? {
        get { UserDefaults.standard.string(forKey: "ome_token") }
        set { UserDefaults.standard.set(newValue, forKey: "ome_token") }
    }

    private var sessionId: String? {
        get { UserDefaults.standard.string(forKey: "ome_session_id") }
        set { UserDefaults.standard.set(newValue, forKey: "ome_session_id") }
    }

    var isLoggedIn: Bool { token != nil }

    // MARK: - Anonymous Session

    func createSession() async throws -> String {
        let resp: SessionResponse = try await post("/anon/session")
        sessionId = resp.session_id
        return resp.session_id
    }

    func ensureSession() async throws -> String {
        if let sid = sessionId { return sid }
        return try await createSession()
    }

    func anonChat(_ message: String) async throws -> AnonChatResponse {
        let sid = try await ensureSession()
        var request = try makeRequest("/anon/chat", method: "POST")
        request.addValue(sid, forHTTPHeaderField: "X-Session-ID")
        request.httpBody = try JSONEncoder().encode(ChatRequest(message: message))
        return try await execute(request)
    }

    // MARK: - Auth

    func register(_ req: RegisterRequest) async throws -> AuthResponse {
        var body = req
        body.session_id = sessionId  // Migrate anonymous history
        let resp: AuthResponse = try await post("/auth/register", body: body)
        token = resp.token
        sessionId = nil
        UserDefaults.standard.set(resp.name, forKey: "ome_name")
        UserDefaults.standard.set(resp.user_id, forKey: "ome_user_id")
        return resp
    }

    func login(userId: String, password: String) async throws -> AuthResponse {
        struct LoginReq: Codable { let user_id: String; let password: String }
        let resp: AuthResponse = try await post("/auth/login", body: LoginReq(user_id: userId, password: password))
        token = resp.token
        UserDefaults.standard.set(resp.name, forKey: "ome_name")
        return resp
    }

    func logout() {
        token = nil
        sessionId = nil
        UserDefaults.standard.removeObject(forKey: "ome_token")
        UserDefaults.standard.removeObject(forKey: "ome_session_id")
        UserDefaults.standard.removeObject(forKey: "ome_name")
        UserDefaults.standard.removeObject(forKey: "ome_user_id")
    }

    // MARK: - Chat

    func chat(_ message: String) async throws -> ChatResponse {
        try await post("/chat", body: ChatRequest(message: message))
    }

    func mirror(_ message: String) async throws -> ChatResponse {
        try await post("/mirror", body: ChatRequest(message: message))
    }

    /// SSE streaming chat — yields tokens as they arrive
    nonisolated func chatStream(_ message: String) -> AsyncThrowingStream<StreamToken, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    let token = UserDefaults.standard.string(forKey: "ome_token")
                    #if DEBUG
                    let urlStr = "http://localhost:8765/api/chat/stream"
                    #else
                    let urlStr = "https://api.ome.ai/api/chat/stream"
                    #endif
                    guard let url = URL(string: urlStr) else { throw APIError.invalidURL }
                    var request = URLRequest(url: url)
                    request.httpMethod = "POST"
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    if let t = token { request.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }
                    request.httpBody = try JSONEncoder().encode(ChatRequest(message: message))

                    let (bytes, response) = try await URLSession.shared.bytes(for: request)
                    guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                        throw APIError.serverError("Stream failed")
                    }

                    for try await line in bytes.lines {
                        guard line.hasPrefix("data: ") else { continue }
                        let json = String(line.dropFirst(6))
                        guard let data = json.data(using: .utf8) else { continue }
                        if let token = try? JSONDecoder().decode(StreamToken.self, from: data) {
                            continuation.yield(token)
                            if token.done == true {
                                continuation.finish()
                                return
                            }
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    // MARK: - Life

    func getProfile() async throws -> ProfileResponse {
        try await get("/profile")
    }

    func getDashboard() async throws -> DashboardResponse {
        try await get("/dashboard")
    }

    // MARK: - Memory

    func remember(_ text: String) async throws {
        struct Req: Codable { let text: String }
        let _: [String: String] = try await post("/remember", body: Req(text: text))
    }

    func recall(_ query: String, topK: Int = 20) async throws -> RecallResponse {
        struct Req: Codable { let query: String; let top_k: Int }
        return try await post("/recall", body: Req(query: query, top_k: topK))
    }

    // MARK: - Agents

    func getAgentDirectory() async throws -> AgentDirectoryResponse {
        try await get("/agents/directory")
    }

    func messageAgent(_ targetId: String, message: String) async throws -> AgentMessageResponse {
        struct Req: Codable { let message: String }
        return try await post("/agents/\(targetId)/message", body: Req(message: message))
    }

    // MARK: - HTTP Helpers

    private func makeRequest(_ path: String, method: String = "GET") throws -> URLRequest {
        guard let url = URL(string: baseURL + path) else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let t = token {
            request.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization")
        }
        return request
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let request = try makeRequest(path)
        return try await execute(request)
    }

    private func post<T: Decodable>(_ path: String) async throws -> T {
        let request = try makeRequest(path, method: "POST")
        return try await execute(request)
    }

    private func post<B: Encodable, T: Decodable>(_ path: String, body: B) async throws -> T {
        var request = try makeRequest(path, method: "POST")
        request.httpBody = try JSONEncoder().encode(body)
        return try await execute(request)
    }

    private func execute<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw APIError.serverError("No HTTP response")
        }
        guard (200...299).contains(http.statusCode) else {
            let detail = (try? JSONDecoder().decode([String: String].self, from: data))?["detail"]
            throw APIError.serverError(detail ?? "HTTP \(http.statusCode)")
        }
        return try JSONDecoder().decode(T.self, from: data)
    }
}

enum APIError: LocalizedError {
    case invalidURL
    case serverError(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL"
        case .serverError(let msg): return msg
        }
    }
}
