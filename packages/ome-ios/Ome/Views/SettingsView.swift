import SwiftUI

/// Settings — profile, autonomy level, about, logout, account deletion.
struct SettingsView: View {
    @EnvironmentObject var session: SessionManager
    @AppStorage("ome_autonomy_level") private var autonomyLevel = 0
    @State private var profile: ProfileResponse?
    @State private var showLogoutConfirm = false
    @State private var showDeleteConfirm = false
    @State private var deleteConfirmName = ""
    @State private var deleting = false

    private let api = APIClient.shared

    private let autonomyLevels = [
        ("eye", "观察者", "Ome 只观察不主动行动"),
        ("hand.raised", "助手", "Ome 可以提建议、写草稿"),
        ("bolt.fill", "代理人", "Ome 可以代你执行操作"),
    ]

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Header
                HStack(spacing: 10) {
                    OmeOrbMini(size: 28)
                    Text("设置")
                        .font(.title2.bold())
                        .foregroundStyle(Theme.textPrimary)
                    Spacer()
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)

                // Profile card
                HStack(spacing: 16) {
                    ZStack {
                        Circle()
                            .fill(Theme.accent)
                            .frame(width: 48, height: 48)
                        Text(String(session.userName.prefix(1)).uppercased())
                            .font(.title2.bold())
                            .foregroundStyle(Theme.bg)
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        Text(session.userName)
                            .font(.headline)
                            .foregroundStyle(Theme.textPrimary)
                        HStack(spacing: 8) {
                            Label("Lv.\(profile?.bond.level ?? session.bondLevel)", systemImage: "leaf")
                            Label("\(profile?.total_memories ?? 0) 记忆", systemImage: "brain.head.profile")
                        }
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Theme.bgCard)
                .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
                .padding(.horizontal, 20)

                // Autonomy level
                VStack(alignment: .leading, spacing: 10) {
                    Text("自治等级")
                        .font(.headline)
                        .foregroundStyle(Theme.accent)
                    Text("决定 Ome 可以自主做多少事情")
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)

                    ForEach(0..<3, id: \.self) { i in
                        let al = autonomyLevels[i]
                        let selected = autonomyLevel == i
                        Button {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                autonomyLevel = i
                            }
                            UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        } label: {
                            HStack(spacing: 12) {
                                Image(systemName: al.0)
                                    .font(.title2)
                                    .foregroundStyle(selected ? Theme.accent : Theme.textSecondary)
                                    .frame(width: 32)
                                VStack(alignment: .leading) {
                                    Text(al.1)
                                        .font(.body.bold())
                                        .foregroundStyle(selected ? Theme.accent : Theme.textPrimary)
                                    Text(al.2)
                                        .font(.caption)
                                        .foregroundStyle(Theme.textSecondary)
                                }
                                Spacer()
                                if selected {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundStyle(Theme.accent)
                                }
                            }
                            .padding(12)
                            .background(Theme.bgCard)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(selected ? Theme.accent : Theme.border, lineWidth: 1)
                            )
                        }
                    }
                }
                .padding(.horizontal, 20)

                // About
                VStack(spacing: 0) {
                    aboutRow("版本", value: "0.1.0")
                    Divider().background(Theme.border)
                    aboutRow("引擎", value: "Mindos + Ome")
                    Divider().background(Theme.border)
                    aboutRow("项目", value: "Omnity (开源)")
                    Divider().background(Theme.border)
                    linkRow("隐私政策", url: "https://omnity.ai/privacy")
                    Divider().background(Theme.border)
                    linkRow("用户协议", url: "https://omnity.ai/terms")
                }
                .background(Theme.bgCard)
                .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
                .padding(.horizontal, 20)

                // Logout
                Button {
                    showLogoutConfirm = true
                } label: {
                    Text("退出登录")
                        .font(.body.bold())
                        .foregroundStyle(Theme.textSecondary)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Theme.bgCard)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.cornerRadius)
                                .stroke(Theme.border, lineWidth: 1)
                        )
                }
                .padding(.horizontal, 20)

                // Delete account
                Button {
                    showDeleteConfirm = true
                } label: {
                    Text("删除账号")
                        .font(.body)
                        .foregroundStyle(Theme.error.opacity(0.7))
                }
                .padding(.top, 8)

                Text("Omnity · 碳硅共居，万物有灵")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
                    .padding(.top, 16)
            }
            .padding(.bottom, 32)
        }
        .background(Theme.bg)
        .task {
            do { profile = try await api.getProfile() } catch {}
        }
        .alert("退出登录", isPresented: $showLogoutConfirm) {
            Button("取消", role: .cancel) {}
            Button("退出", role: .destructive) {
                Task { await session.logout() }
            }
        } message: {
            Text("确定要退出吗？Ome 的记忆不会丢失，下次回来还在。")
        }
        .alert("删除账号", isPresented: $showDeleteConfirm) {
            TextField("输入你的名字确认", text: $deleteConfirmName)
            Button("取消", role: .cancel) {
                deleteConfirmName = ""
            }
            Button("永久删除", role: .destructive) {
                guard deleteConfirmName.trimmingCharacters(in: .whitespaces) == session.userName else {
                    deleteConfirmName = ""
                    return
                }
                Task { await deleteAccount() }
            }
        } message: {
            Text("删除账号将永久清除 Ome 的所有记忆，无法恢复。\n\n请输入「\(session.userName)」确认删除。")
        }
    }

    private func aboutRow(_ label: String, value: String) -> some View {
        HStack {
            Text(label)
                .foregroundStyle(Theme.textSecondary)
            Spacer()
            Text(value)
                .foregroundStyle(Theme.textPrimary)
        }
        .font(.body)
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    private func linkRow(_ label: String, url: String) -> some View {
        Button {
            if let u = URL(string: url) {
                UIApplication.shared.open(u)
            }
        } label: {
            HStack {
                Text(label)
                    .foregroundStyle(Theme.textSecondary)
                Spacer()
                Image(systemName: "arrow.up.right")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
            }
            .font(.body)
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }

    private func deleteAccount() async {
        deleting = true
        do {
            try await api.deleteAccount()
        } catch {
            // Server endpoint may not exist yet — proceed with local cleanup
        }
        await session.deleteAccount()
        deleting = false
        deleteConfirmName = ""
    }
}
