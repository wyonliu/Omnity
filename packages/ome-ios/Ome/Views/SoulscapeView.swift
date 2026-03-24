import SwiftUI

/// Soulscape — the Ome's soul visualized. Orb + growth stage + quick stats.
struct SoulscapeView: View {
    @EnvironmentObject var session: SessionManager
    @State private var profile: ProfileResponse?
    @State private var dashboard: DashboardResponse?

    private let api = APIClient.shared

    private let stages = [
        ("种子", "一切刚开始"),
        ("嫩芽", "开始有记忆了"),
        ("小树", "开始有生活了"),
        ("茂盛", "能帮你做事了"),
        ("结果", "能替你社交了"),
        ("繁花", "完全代表你了"),
        ("参天", "传说级存在"),
    ]

    private var level: Int { min(profile?.bond.level ?? session.bondLevel, 6) }

    // Orb grows with bond level
    private var orbSize: CGFloat { CGFloat(80 + level * 12) }
    private var orbIntensity: CGFloat { 0.35 + CGFloat(level) * 0.1 }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Soulscape — orb as the centerpiece
                VStack(spacing: 12) {
                    OmeOrb(size: orbSize, intensity: orbIntensity)
                        .padding(.top, 20)

                    Text(stages[level].0)
                        .font(.title3.bold())
                        .foregroundStyle(Theme.accent)

                    Text("Lv.\(level) · \(stages[level].1)")
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                }
                .padding(.vertical, 16)

                // Greeting
                HStack(spacing: 12) {
                    OmeOrbMini(size: 32)
                    Text("嗨，\(session.userName)。今天想聊什么？")
                        .font(.body)
                        .foregroundStyle(Theme.textPrimary)
                        .lineSpacing(4)
                    Spacer()
                }
                .padding()
                .background(Theme.bgCard)
                .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.cornerRadius)
                        .stroke(Theme.border, lineWidth: 1)
                )

                // Quick stats
                HStack(spacing: 8) {
                    StatCard(value: "Lv.\(level)",
                             label: profile?.bond.name ?? stages[level].0,
                             color: Theme.bondGreen)
                    StatCard(value: "\(profile?.streak.current ?? 0)",
                             label: "连续天数",
                             color: Theme.streakOrange)
                    StatCard(value: profile?.achievements_count ?? "0",
                             label: "成就",
                             color: Theme.achieveGold)
                    StatCard(value: "\(profile?.total_memories ?? 0)",
                             label: "记忆",
                             color: Theme.emotionPurple)
                }

                // Highlights
                if let highlights = dashboard?.highlights, !highlights.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("本周亮点")
                            .font(.headline)
                            .foregroundStyle(Theme.accent)
                        ForEach(highlights.prefix(5), id: \.self) { h in
                            Text("· \(h)")
                                .font(.subheadline)
                                .foregroundStyle(Theme.textSecondary)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Theme.bgCard)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.cornerRadius)
                            .stroke(Theme.border, lineWidth: 1)
                    )
                }
            }
            .padding(20)
        }
        .background(Theme.bg)
        .refreshable { await load() }
        .task { await load() }
    }

    private func load() async {
        do {
            async let p = api.getProfile()
            async let d = api.getDashboard()
            profile = try await p
            dashboard = try await d
            if let level = profile?.bond.level {
                session.updateBondLevel(level)
            }
        } catch {
            // Silent — stats just show cached/default values
        }
    }
}

struct StatCard: View {
    let value: String
    let label: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.headline.bold())
                .foregroundStyle(color)
            Text(label)
                .font(.caption2)
                .foregroundStyle(Theme.textMuted)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(Theme.bgCard)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Theme.border, lineWidth: 1)
        )
    }
}
