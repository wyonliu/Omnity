import SwiftUI

/// Life dashboard — bond progress, achievements, skills, streak.
struct LifeView: View {
    @EnvironmentObject var session: SessionManager
    @State private var profile: ProfileResponse?
    @State private var dashboard: DashboardResponse?
    @State private var selectedTab = 0

    private let api = APIClient.shared
    private let milestones = [3, 7, 14, 30, 90, 365]

    private let stages = [
        ("🌱", "初见"), ("🌿", "嫩芽"), ("🌳", "小树"), ("🌲", "茂盛"),
        ("🍊", "结果"), ("🌸", "繁花"), ("🏔️", "参天"),
    ]

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Header
                Text("📊 成长")
                    .font(.title2.bold())
                    .foregroundStyle(Theme.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 20)
                    .padding(.top, 8)

                // Bond hero
                let level = min(profile?.bond.level ?? 0, 6)
                VStack(spacing: 8) {
                    Text(stages[level].0)
                        .font(.system(size: 56))
                    Text("Lv.\(level) · \(stages[level].1)")
                        .font(.headline.bold())
                        .foregroundStyle(Theme.bondGreen)

                    // Progress bar
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 3)
                                .fill(Theme.bgInput)
                            RoundedRectangle(cornerRadius: 3)
                                .fill(Theme.bondGreen)
                                .frame(width: geo.size.width * 0.3) // placeholder
                        }
                    }
                    .frame(height: 6)
                    .padding(.horizontal, 24)

                    Text("第 \(profile?.bond.total_interactions ?? 0) 次对话")
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                }
                .padding()
                .background(Theme.bgCard)
                .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
                .padding(.horizontal, 20)

                // Streak
                VStack(alignment: .leading, spacing: 12) {
                    Text("连续互动")
                        .font(.headline)
                        .foregroundStyle(Theme.accent)

                    HStack {
                        HStack(alignment: .lastTextBaseline, spacing: 2) {
                            Text("\(profile?.streak.current ?? 0)")
                                .font(.largeTitle.bold())
                                .foregroundStyle(Theme.streakOrange)
                            Text("天")
                                .foregroundStyle(Theme.streakOrange)
                        }
                        Spacer()
                        Text("最长 \(profile?.streak.max ?? 0) 天")
                            .font(.caption)
                            .foregroundStyle(Theme.textMuted)
                    }

                    // Milestone dots
                    HStack {
                        ForEach(milestones, id: \.self) { m in
                            let done = (profile?.streak.current ?? 0) >= m
                            Text("\(m)")
                                .font(.caption2.bold())
                                .foregroundStyle(done ? Theme.bg : Theme.textMuted)
                                .frame(width: 40, height: 40)
                                .background(done ? Theme.streakOrange : Theme.bgInput)
                                .clipShape(Circle())
                        }
                    }
                }
                .padding()
                .background(Theme.bgCard)
                .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
                .padding(.horizontal, 20)

                // Achievements
                if let achievements = dashboard?.achievements.unlocked, !achievements.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("成就 \(dashboard?.achievements.count ?? "0/0")")
                            .font(.headline)
                            .foregroundStyle(Theme.accent)

                        ForEach(achievements) { a in
                            HStack(spacing: 12) {
                                Text(a.icon ?? "🎖️")
                                    .font(.title2)
                                VStack(alignment: .leading) {
                                    Text(a.name)
                                        .font(.body.bold())
                                        .foregroundStyle(Theme.textPrimary)
                                    Text(a.description)
                                        .font(.caption)
                                        .foregroundStyle(Theme.textSecondary)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Theme.bgCard)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                    .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
                    .padding(.horizontal, 20)
                }

                // Highlights
                if let highlights = dashboard?.highlights, !highlights.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("本周亮点")
                            .font(.headline)
                            .foregroundStyle(Theme.accent)
                        ForEach(highlights, id: \.self) { h in
                            Text("· \(h)")
                                .font(.subheadline)
                                .foregroundStyle(Theme.textSecondary)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Theme.bgCard)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                    .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
                    .padding(.horizontal, 20)
                }
            }
            .padding(.bottom, 32)
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
        } catch {
            print("Life load error:", error)
        }
    }
}
