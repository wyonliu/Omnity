import SwiftUI

/// Global session state — drives navigation between awakening, tabs, etc.
/// Handles auth persistence, credential storage, and bond tracking.
@MainActor
class SessionManager: ObservableObject {
    enum AuthState: Equatable {
        case loading
        case anonymous
        case authenticated
    }

    @Published var authState: AuthState = .loading
    @Published var userName: String = ""
    @Published var bondLevel: Int = 0

    var isLoggedIn: Bool { authState == .authenticated }

    private let api = APIClient.shared

    init() {
        // Synchronously read cached state to avoid flicker
        let hasToken = UserDefaults.standard.string(forKey: "ome_token") != nil
        userName = UserDefaults.standard.string(forKey: "ome_name") ?? ""
        bondLevel = UserDefaults.standard.integer(forKey: "ome_bond_level")

        if hasToken && !userName.isEmpty {
            // Optimistic: show authenticated immediately, validate in background
            authState = .authenticated
            Task { await validateSession() }
        } else {
            authState = .anonymous
        }
    }

    /// Validate the stored token by calling /profile
    private func validateSession() async {
        do {
            let profile = try await api.getProfile()
            userName = profile.name
            bondLevel = profile.bond.level
            UserDefaults.standard.set(profile.bond.level, forKey: "ome_bond_level")
        } catch {
            // Token expired or invalid — stay authenticated but don't force logout
            // User can still use the app; next API call will reveal the issue
        }
    }

    func register(name: String, traits: [String] = ["curious"], style: String = "warm and casual") async throws {
        let userId = name.lowercased()
            .replacingOccurrences(of: " ", with: "_")
            .replacingOccurrences(of: " ", with: "_")  // fullwidth space
        let password = userId + "_ome_" + String(UUID().uuidString.prefix(8))

        let req = RegisterRequest(
            user_id: userId,
            password: password,
            name: name,
            traits: traits,
            style: style
        )
        let resp = try await api.register(req)

        // Store credentials for auto-login
        UserDefaults.standard.set(userId, forKey: "ome_user_id")
        UserDefaults.standard.set(password, forKey: "ome_password")

        userName = resp.name
        withAnimation(.easeInOut(duration: 0.5)) {
            authState = .authenticated
        }
    }

    func logout() async {
        await api.logout()
        UserDefaults.standard.removeObject(forKey: "ome_bond_level")
        UserDefaults.standard.removeObject(forKey: "ome_password")

        withAnimation(.easeInOut(duration: 0.3)) {
            authState = .anonymous
            userName = ""
            bondLevel = 0
        }
    }

    func updateBondLevel(_ level: Int) {
        guard level != bondLevel else { return }
        withAnimation(.easeInOut(duration: 0.3)) {
            bondLevel = level
        }
        UserDefaults.standard.set(level, forKey: "ome_bond_level")
    }
}
