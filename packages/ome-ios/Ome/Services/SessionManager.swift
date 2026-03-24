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
        // Check Keychain first, fall back to UserDefaults for migration
        let hasToken = KeychainHelper.load("ome_token") != nil
            || UserDefaults.standard.string(forKey: "ome_token") != nil
        userName = UserDefaults.standard.string(forKey: "ome_name") ?? ""
        bondLevel = UserDefaults.standard.integer(forKey: "ome_bond_level")

        if hasToken && !userName.isEmpty {
            // Migrate token from UserDefaults to Keychain if needed
            if let oldToken = UserDefaults.standard.string(forKey: "ome_token"),
               KeychainHelper.load("ome_token") == nil {
                KeychainHelper.save(oldToken, for: "ome_token")
                UserDefaults.standard.removeObject(forKey: "ome_token")
            }
            if let oldPwd = UserDefaults.standard.string(forKey: "ome_password") {
                KeychainHelper.save(oldPwd, for: "ome_password")
                UserDefaults.standard.removeObject(forKey: "ome_password")
            }
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
            // Token expired or invalid — try auto-login
            if let userId = UserDefaults.standard.string(forKey: "ome_user_id"),
               let password = KeychainHelper.load("ome_password") {
                do {
                    let resp = try await api.login(userId: userId, password: password)
                    userName = resp.name
                } catch {
                    // Auto-login also failed — force logout
                    await logout()
                }
            }
        }
    }

    func register(name: String, traits: [String] = ["curious"], style: String = "warm and casual") async throws {
        let userId = name.lowercased()
            .replacingOccurrences(of: " ", with: "_")
            .replacingOccurrences(of: "\u{3000}", with: "_")  // fullwidth space
        let password = userId + "_ome_" + String(UUID().uuidString.prefix(8))

        let req = RegisterRequest(
            user_id: userId,
            password: password,
            name: name,
            traits: traits,
            style: style
        )
        let resp = try await api.register(req)

        // Store credentials securely for auto-login
        UserDefaults.standard.set(userId, forKey: "ome_user_id")
        KeychainHelper.save(password, for: "ome_password")

        userName = resp.name
        withAnimation(.easeInOut(duration: 0.5)) {
            authState = .authenticated
        }
    }

    func logout() async {
        await api.logout()
        UserDefaults.standard.removeObject(forKey: "ome_bond_level")
        KeychainHelper.delete("ome_password")
        KeychainHelper.delete("ome_token")

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
