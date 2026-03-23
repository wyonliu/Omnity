import SwiftUI

/// Global session state — drives navigation between first-chat, tabs, etc.
@MainActor
class SessionManager: ObservableObject {
    @Published var isLoggedIn: Bool = false
    @Published var userName: String = ""
    @Published var bondLevel: Int = 0

    private let api = APIClient.shared

    init() {
        Task {
            let loggedIn = await api.isLoggedIn
            isLoggedIn = loggedIn
            userName = UserDefaults.standard.string(forKey: "ome_name") ?? ""
            bondLevel = UserDefaults.standard.integer(forKey: "ome_bond_level")
        }
    }

    func register(name: String, traits: [String] = ["curious"], style: String = "warm and casual") async throws {
        let userId = name.lowercased().replacingOccurrences(of: " ", with: "_")
        let req = RegisterRequest(
            user_id: userId,
            password: userId + "_ome",
            name: name,
            traits: traits,
            style: style
        )
        let resp = try await api.register(req)
        isLoggedIn = true
        userName = resp.name
    }

    func logout() async {
        await api.logout()
        isLoggedIn = false
        userName = ""
        bondLevel = 0
        UserDefaults.standard.removeObject(forKey: "ome_bond_level")
    }

    func updateBondLevel(_ level: Int) {
        bondLevel = level
        UserDefaults.standard.set(level, forKey: "ome_bond_level")
    }
}
