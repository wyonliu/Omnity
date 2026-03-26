import SwiftUI

/// Progressive tab layout — unlocks tabs as bond level grows.
/// v2: All tabs always rendered to prevent TabView structural changes from destroying state.
/// Locked tabs show an overlay prompt instead of being removed.
struct MainTabView: View {
    @EnvironmentObject var session: SessionManager
    @EnvironmentObject var chatStore: ChatStore
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

                tabContent(for: 2, requiredLevel: 1) { MemoryView() }
                    .tabItem { Label("记忆", systemImage: "brain.head.profile") }
                    .tag(2)

                tabContent(for: 3, requiredLevel: 2) { LifeView() }
                    .tabItem { Label("成长", systemImage: "chart.line.uptrend.xyaxis") }
                    .tag(3)

                SettingsView()
                    .tabItem { Label("我的", systemImage: "person.crop.circle") }
                    .tag(9)
            }
            .tint(Theme.accent)

            // Level-up celebration overlay
            if showLevelUp {
                let level = min(max(session.bondLevel, 0), stageNames.count - 1)
                LevelUpCelebration(
                    level: level,
                    stageName: stageNames[level],
                    stageDesc: stageDescs[level],
                    onDismiss: { showLevelUp = false }
                )
            }
        }
        .onChange(of: session.bondLevel) { _, newLevel in
            if let prev = previousBondLevel, newLevel > prev {
                showLevelUp = true
            }
            previousBondLevel = newLevel
        }
        .onAppear {
            previousBondLevel = session.bondLevel
            UserDefaults.standard.set(Date(), forKey: "ome_last_active_date")
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

    /// Wraps tab content with a locked overlay when bond level is insufficient.
    @ViewBuilder
    private func tabContent<Content: View>(for tag: Int, requiredLevel: Int, @ViewBuilder content: () -> Content) -> some View {
        if session.bondLevel >= requiredLevel {
            content()
        } else {
            lockedView(requiredLevel: requiredLevel)
        }
    }

    private func lockedView(requiredLevel: Int) -> some View {
        VStack(spacing: 20) {
            Spacer()
            Image(systemName: "lock.fill")
                .font(.system(size: 40))
                .foregroundStyle(Theme.textMuted)
            Text("需要亲密度 Lv.\(requiredLevel) 解锁")
                .font(.headline)
                .foregroundStyle(Theme.textSecondary)
            Text("继续和 Ome 聊天来提升关系")
                .font(.subheadline)
                .foregroundStyle(Theme.textMuted)
            Button {
                selectedTab = 0
            } label: {
                Text("去聊天")
                    .font(.subheadline.bold())
                    .foregroundStyle(Theme.bg)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 10)
                    .background(Theme.accent)
                    .clipShape(Capsule())
            }
            Spacer()
        }
        .frame(maxWidth: .infinity)
        .background(Theme.bg)
    }
}
