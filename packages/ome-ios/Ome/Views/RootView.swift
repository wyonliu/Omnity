import SwiftUI

/// Root navigation — routes based on auth state.
/// Loading → Splash with orb
/// Anonymous → Awakening ceremony
/// Authenticated → MainTabs
struct RootView: View {
    @EnvironmentObject var session: SessionManager

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
        }
    }
}
