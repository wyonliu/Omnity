import SwiftUI

/// Root navigation — routes based on auth state.
/// New users → FirstChat (zero registration)
/// Returning users → MainTabs
struct RootView: View {
    @EnvironmentObject var session: SessionManager

    var body: some View {
        Group {
            if session.isLoggedIn {
                MainTabView()
            } else {
                FirstChatView()
            }
        }
        .animation(.easeInOut(duration: 0.3), value: session.isLoggedIn)
    }
}
