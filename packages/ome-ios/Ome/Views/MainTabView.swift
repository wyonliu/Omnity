import SwiftUI

/// Progressive tab layout — unlocks tabs as bond level grows.
/// Tab selection persists across app launches.
struct MainTabView: View {
    @EnvironmentObject var session: SessionManager
    @AppStorage("ome_selected_tab") private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            ChatView()
                .tabItem { Label("对话", systemImage: "bubble.left.and.bubble.right") }
                .tag(0)

            SoulscapeView()
                .tabItem { Label("灵境", systemImage: "sparkles") }
                .tag(1)

            if session.bondLevel >= 1 {
                MemoryView()
                    .tabItem { Label("记忆", systemImage: "brain.head.profile") }
                    .tag(2)
            }

            if session.bondLevel >= 2 {
                LifeView()
                    .tabItem { Label("成长", systemImage: "chart.line.uptrend.xyaxis") }
                    .tag(3)
            }

            if session.bondLevel >= 3 {
                AgentsView()
                    .tabItem { Label("广场", systemImage: "person.3") }
                    .tag(4)
            }

            SettingsView()
                .tabItem { Label("设置", systemImage: "gearshape") }
                .tag(9)
        }
        .tint(Theme.accent)
        .onChange(of: session.bondLevel) {
            // If current tab is no longer available, reset to Chat
            let validTabs: Set<Int> = {
                var tabs: Set<Int> = [0, 1, 9]
                if session.bondLevel >= 1 { tabs.insert(2) }
                if session.bondLevel >= 2 { tabs.insert(3) }
                if session.bondLevel >= 3 { tabs.insert(4) }
                return tabs
            }()
            if !validTabs.contains(selectedTab) {
                selectedTab = 0
            }
        }
    }
}
