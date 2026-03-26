import SwiftUI

/// "我的" — profile card + quick actions + settings, replaces old SettingsView.
struct SettingsView: View {
    @EnvironmentObject var session: SessionManager
    @AppStorage("ome_autonomy_level") private var autonomyLevel = 0
    @State private var profile: ProfileResponse?
    @State private var showLogoutConfirm = false
    @State private var showDeleteConfirm = false
    @State private var deleteConfirmName = ""
    @State private var deleting = false
    @State private var editingOmeName = false
    @State private var newOmeName = ""

    private let api = APIClient.shared

    private let autonomyLevels = [
        ("eye", "观察者", "只观察不主动行动"),
        ("hand.raised", "助手", "可以提建议、写草稿"),
        ("bolt.fill", "代理人", "可以代你执行操作"),
    ]

    private var level: Int { profile?.bond.level ?? session.bondLevel }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Profile Card — compact
                profileCard
                    .padding(.horizontal, 20)
                    .padding(.top, 8)

                // Ome Name
                omeNameCard
                    .padding(.horizontal, 20)

                // Quick Stats
                quickStats
                    .padding(.horizontal, 20)

                // Autonomy Level — compact picker
                autonomyPicker
                    .padding(.horizontal, 20)

                // About
                aboutSection
                    .padding(.horizontal, 20)

                // Actions
                actionsSection
                    .padding(.horizontal, 20)

                Text("Omnity · 碳硅共居，万物有灵")
                    .font(.caption2)
                    .foregroundStyle(Theme.textMuted)
                    .padding(.top, 8)
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
            Text("Ome 的记忆不会丢失，下次回来还在。")
        }
        .alert("删除账号", isPresented: $showDeleteConfirm) {
            TextField("输入你的名字确认", text: $deleteConfirmName)
            Button("取消", role: .cancel) { deleteConfirmName = "" }
            Button("永久删除", role: .destructive) {
                guard deleteConfirmName.trimmingCharacters(in: .whitespaces) == session.userName else {
                    deleteConfirmName = ""
                    return
                }
                Task { await deleteAccount() }
            }
        } message: {
            Text("将永久清除 Ome 的所有记忆，无法恢复。\n输入「\(session.userName)」确认。")
        }
    }

    // MARK: - Profile Card

    private var profileCard: some View {
        HStack(spacing: 14) {
            ZStack {
                Circle()
                    .fill(Theme.accent)
                    .frame(width: 52, height: 52)
                Text(String(session.userName.prefix(1)).uppercased())
                    .font(.title2.bold())
                    .foregroundStyle(Theme.bg)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(session.userName)
                    .font(.title3.bold())
                    .foregroundStyle(Theme.textPrimary)
                HStack(spacing: 12) {
                    Label("Lv.\(level)", systemImage: "leaf.fill")
                        .foregroundStyle(Theme.bondGreen)
                    Label("\(profile?.total_memories ?? 0) 记忆", systemImage: "brain.head.profile")
                        .foregroundStyle(Theme.textMuted)
                }
                .font(.caption)
            }

            Spacer()
        }
        .padding(16)
        .background(Theme.bgCard)
        .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
        .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
    }

    // MARK: - Ome Name

    private var omeNameCard: some View {
        HStack {
            OmeOrbMini(size: 28)
            VStack(alignment: .leading, spacing: 2) {
                Text("分身名")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
                Text(session.omeDisplayName)
                    .font(.subheadline.bold())
                    .foregroundStyle(Theme.textPrimary)
            }
            Spacer()
            Button("改名") {
                newOmeName = session.omeName
                editingOmeName = true
            }
            .font(.caption)
            .foregroundStyle(Theme.accent)
        }
        .padding(14)
        .background(Theme.bgCard)
        .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
        .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
        .alert("给分身起个名字", isPresented: $editingOmeName) {
            TextField("分身的名字", text: $newOmeName)
            Button("取消", role: .cancel) {}
            Button("确定") {
                let name = newOmeName.trimmingCharacters(in: .whitespaces)
                if !name.isEmpty {
                    session.updateOmeName(name)
                }
            }
        } message: {
            Text("这是你的 AI 分身，它正在学习成为你。")
        }
    }

    // MARK: - Quick Stats

    private var quickStats: some View {
        HStack(spacing: 12) {
            statPill(icon: "flame.fill", value: "\(profile?.streak.current ?? 0)天", label: "连续", color: Theme.streakOrange)
            statPill(icon: "bubble.left.and.bubble.right", value: "\(profile?.bond.total_interactions ?? 0)", label: "对话", color: Theme.accent)
            statPill(icon: "face.smiling", value: profile?.emotion.mood_emoji ?? "🌙", label: "心情", color: Theme.emotionPurple)
        }
    }

    private func statPill(icon: String, value: String, label: String, color: Color) -> some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.body)
                .foregroundStyle(color)
            Text(value)
                .font(.headline.monospacedDigit())
                .foregroundStyle(Theme.textPrimary)
            Text(label)
                .font(.caption2)
                .foregroundStyle(Theme.textMuted)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(Theme.bgCard)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border))
    }

    // MARK: - Autonomy

    private var autonomyPicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("自治等级")
                .font(.subheadline.bold())
                .foregroundStyle(Theme.textSecondary)

            HStack(spacing: 8) {
                ForEach(0..<3, id: \.self) { i in
                    let al = autonomyLevels[i]
                    let selected = autonomyLevel == i
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) { autonomyLevel = i }
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    } label: {
                        VStack(spacing: 4) {
                            Image(systemName: al.0)
                                .font(.title3)
                            Text(al.1)
                                .font(.caption2.bold())
                        }
                        .foregroundStyle(selected ? Theme.accent : Theme.textMuted)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(selected ? Theme.accent.opacity(0.1) : Theme.bgCard)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .stroke(selected ? Theme.accent : Theme.border, lineWidth: 1)
                        )
                    }
                }
            }
        }
    }

    // MARK: - About

    private var aboutSection: some View {
        VStack(spacing: 0) {
            infoRow("版本", value: "0.1.0")
            Divider().background(Theme.border)
            infoRow("引擎", value: "Mindos + Ome")
            Divider().background(Theme.border)
            linkRow("隐私政策", url: "https://omnity.ai/privacy")
            Divider().background(Theme.border)
            linkRow("用户协议", url: "https://omnity.ai/terms")
        }
        .background(Theme.bgCard)
        .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
        .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
    }

    // MARK: - Actions

    private var actionsSection: some View {
        VStack(spacing: 10) {
            Button {
                showLogoutConfirm = true
            } label: {
                HStack {
                    Image(systemName: "rectangle.portrait.and.arrow.right")
                    Text("退出登录")
                }
                .font(.subheadline)
                .foregroundStyle(Theme.textSecondary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(Theme.bgCard)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border))
            }

            Button { showDeleteConfirm = true } label: {
                Text("删除账号")
                    .font(.caption)
                    .foregroundStyle(Theme.error.opacity(0.5))
            }
        }
    }

    // MARK: - Helpers

    private func infoRow(_ label: String, value: String) -> some View {
        HStack {
            Text(label).foregroundStyle(Theme.textSecondary)
            Spacer()
            Text(value).foregroundStyle(Theme.textPrimary)
        }
        .font(.subheadline)
        .padding(.horizontal, 16)
        .padding(.vertical, 11)
    }

    private func linkRow(_ label: String, url: String) -> some View {
        Button {
            if let u = URL(string: url) { UIApplication.shared.open(u) }
        } label: {
            HStack {
                Text(label).foregroundStyle(Theme.textSecondary)
                Spacer()
                Image(systemName: "arrow.up.right")
                    .font(.caption2)
                    .foregroundStyle(Theme.textMuted)
            }
            .font(.subheadline)
            .padding(.horizontal, 16)
            .padding(.vertical, 11)
        }
    }

    private func deleteAccount() async {
        deleting = true
        do { try await api.deleteAccount() } catch {}
        await session.deleteAccount()
        deleting = false
        deleteConfirmName = ""
    }
}
