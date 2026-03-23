import SwiftUI

/// Progressive tab layout — unlocks tabs as bond level grows.
struct MainTabView: View {
    @EnvironmentObject var session: SessionManager
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            // Always: Chat (primary)
            ChatView()
                .tabItem {
                    Label("对话", systemImage: "bubble.left.and.bubble.right")
                }
                .tag(0)

            // Always: Soulscape
            SoulscapeView()
                .tabItem {
                    Label("灵境", systemImage: "leaf")
                }
                .tag(1)

            // Bond >= 1: Memory
            if session.bondLevel >= 1 {
                MemoryView()
                    .tabItem {
                        Label("记忆", systemImage: "cube")
                    }
                    .tag(2)
            }

            // Bond >= 2: Growth
            if session.bondLevel >= 2 {
                LifeView()
                    .tabItem {
                        Label("成长", systemImage: "trophy")
                    }
                    .tag(3)
            }

            // Bond >= 3: OmeTown Agents
            if session.bondLevel >= 3 {
                AgentsView()
                    .tabItem {
                        Label("广场", systemImage: "person.3")
                    }
                    .tag(4)
            }

            // Always: Settings
            SettingsView()
                .tabItem {
                    Label("设置", systemImage: "gearshape")
                }
                .tag(9)
        }
        .tint(Theme.accent)
    }
}
