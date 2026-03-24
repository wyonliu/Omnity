import SwiftUI

/// Progressive tab layout — unlocks tabs as bond level grows.
/// Tab selection persists across app launches.
/// Shows level-up celebration on bond level change.
struct MainTabView: View {
    @EnvironmentObject var session: SessionManager
    @AppStorage("ome_selected_tab") private var selectedTab = 0
    @AppStorage("ome_should_request_notifications") private var shouldRequestNotif = false
    @State private var previousBondLevel: Int?
    @State private var showLevelUp = false
    @State private var showNotifSheet = false

    private let stageNames = ["种子", "嫩芽", "小树", "茂盛", "结果", "繁花", "参天"]
    private let stageDescs = ["一切刚开始", "开始有记忆了", "开始有生活了", "能帮你做事了", "能替你社交了", "完全代表你了", "传说级存在"]

    var body: some View {
        ZStack {
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

            // Level-up celebration overlay
            if showLevelUp {
                let level = min(session.bondLevel, 6)
                LevelUpCelebration(
                    level: level,
                    stageName: stageNames[level],
                    stageDesc: stageDescs[level],
                    onDismiss: { showLevelUp = false }
                )
            }
        }
        .onChange(of: session.bondLevel) { _, newLevel in
            // Detect level-up
            if let prev = previousBondLevel, newLevel > prev {
                showLevelUp = true
            }
            previousBondLevel = newLevel

            // Tab availability check
            let validTabs: Set<Int> = {
                var tabs: Set<Int> = [0, 1, 9]
                if newLevel >= 1 { tabs.insert(2) }
                if newLevel >= 2 { tabs.insert(3) }
                if newLevel >= 3 { tabs.insert(4) }
                return tabs
            }()
            if !validTabs.contains(selectedTab) {
                selectedTab = 0
            }
        }
        .onAppear {
            previousBondLevel = session.bondLevel
            // Update last active date
            UserDefaults.standard.set(Date(), forKey: "ome_last_active_date")
            // Notification permission request (delayed)
            if shouldRequestNotif {
                shouldRequestNotif = false
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    showNotifSheet = true
                }
            }
        }
        .sheet(isPresented: $showNotifSheet) {
            NotificationPermissionSheet(
                onAllow: {
                    showNotifSheet = false
                    Task {
                        let nm = NotificationManager.shared
                        _ = await nm.requestPermission()
                    }
                },
                onSkip: { showNotifSheet = false }
            )
            .presentationDetents([.medium])
            .presentationDragIndicator(.visible)
        }
    }
}
