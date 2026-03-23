import SwiftUI

/// Settings — autonomy level, about, logout.
struct SettingsView: View {
    @EnvironmentObject var session: SessionManager
    @State private var autonomyLevel = 0
    @State private var profile: ProfileResponse?
    @State private var showLogoutConfirm = false

    private let api = APIClient.shared

    private let autonomyLevels = [
        ("👁️", "观察者", "Ome 只观察不主动行动"),
        ("🤝", "助手", "Ome 可以提建议、写草稿"),
        ("🚀", "代理人", "Ome 可以代你执行操作"),
    ]

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Header
                Text("⚙️ 设置")
                    .font(.title2.bold())
                    .foregroundStyle(Theme.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 20)
                    .padding(.top, 8)

                // Profile card
                HStack(spacing: 16) {
                    Text(String(session.userName.prefix(1)).uppercased())
                        .font(.title2.bold())
                        .foregroundStyle(Theme.bg)
                        .frame(width: 48, height: 48)
                        .background(Theme.accent)
                        .clipShape(Circle())

                    VStack(alignment: .leading) {
                        Text(session.userName)
                            .font(.headline)
                            .foregroundStyle(Theme.textPrimary)
                        Text("Lv.\(profile?.bond.level ?? 0) · \(profile?.bond.total_interactions ?? 0) 次对话 · \(profile?.total_memories ?? 0) 条记忆")
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
                VStack(alignment: .leading, spacing: 8) {
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
                            autonomyLevel = i
                        } label: {
                            HStack(spacing: 12) {
                                Text(al.0).font(.title2)
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
                                    Text("✓")
                                        .font(.headline)
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
                    aboutRow("版本", value: "Ome v0.4.0")
                    Divider().background(Theme.border)
                    aboutRow("引擎", value: "Mindos v0.4.0")
                    Divider().background(Theme.border)
                    aboutRow("项目", value: "Omnity (开源)")
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
                        .foregroundStyle(Theme.error)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Theme.bgCard)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.cornerRadius)
                                .stroke(Theme.error, lineWidth: 1)
                        )
                }
                .padding(.horizontal, 20)

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
            Text("确定要退出吗？Ome 的记忆不会丢失。")
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
}
