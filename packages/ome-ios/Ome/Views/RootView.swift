import SwiftUI

/// Root navigation — routes based on auth state.
/// Loading → Splash with orb
/// Anonymous → Awakening ceremony
/// Authenticated → MainTabs
struct RootView: View {
    @EnvironmentObject var session: SessionManager
    @EnvironmentObject var chatStore: ChatStore
    @State private var splashOpacity: Double = 0
    @State private var showLogoutToast = false

    var body: some View {
        Group {
            switch session.authState {
            case .loading:
                splashView
            case .anonymous:
                AwakeningView()
            case .authenticated:
                MainTabView()
            }
        }
        .animation(.easeInOut(duration: 0.5), value: session.authState)
        .onChange(of: session.authState) { _, newState in
            if newState == .anonymous {
                chatStore.clearOnLogout()
                if session.logoutReason != nil {
                    showLogoutToast = true
                }
            }
        }
        .overlay(alignment: .top) {
            if showLogoutToast, let reason = session.logoutReason {
                Text(reason)
                    .font(.subheadline)
                    .foregroundStyle(Theme.textPrimary)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())
                    .padding(.top, 60)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .onAppear {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                            withAnimation { showLogoutToast = false }
                            session.logoutReason = nil
                        }
                    }
            }
        }
    }

    private var splashView: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            VStack(spacing: 16) {
                OmeOrb(size: 60, intensity: 0.6)
                Text("Ome")
                    .font(.title2.bold())
                    .foregroundStyle(Theme.accent)
            }
            .opacity(splashOpacity)
            .onAppear {
                withAnimation(.easeIn(duration: 0.8)) {
                    splashOpacity = 1
                }
            }
        }
    }
}
