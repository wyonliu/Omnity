import SwiftUI

/// Life dashboard — bond progress, achievements, streak.
struct LifeView: View {
    @EnvironmentObject var session: SessionManager
    @State private var profile: ProfileResponse?
    @State private var dashboard: DashboardResponse?
    @State private var loadError = false

    private let api = APIClient.shared
    private let milestones = [3, 7, 14, 30, 90, 365]

    private let stages = [
        ("🌱", "初见"), ("🌿", "嫩芽"), ("🌳", "小树"), ("🌲", "茂盛"),
        ("🍊", "结果"), ("🌸", "繁花"), ("🏔️", "参天"),
    ]

    private var bondProgress: Double {
        guard let bond = profile?.bond else { return 0 }
        let needed = bond.interactions_needed ?? 50
        guard needed > 0 else { return 1.0 }
        let total = bond.total_interactions ?? 0
        // Progress within current level
        return min(1.0, Double(total % needed) / Double(needed))
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Header with orb
                HStack(spacing: 10) {
                    OmeOrbMini(size: 28)
                    Text("成长")
                        .font(.title2.bold())
                        .foregroundStyle(Theme.textPrimary)
                    Spacer()
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)

                // Bond hero
                let level = min(profile?.bond.level ?? session.bondLevel, 6)
                VStack(spacing: 10) {
                    Text(stages[level].0)
                        .font(.system(size: 56))

                    Text("Lv.\(level) · \(stages[level].1)")
                        .font(.headline.bold())
                        .foregroundStyle(Theme.bondGreen)

                    // Progress bar — actual calculation
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 3)
                                .fill(Theme.bgInput)
                            RoundedRectangle(cornerRadius: 3)
                                .fill(Theme.bondGreen)
                                .frame(width: geo.size.width * bondProgress)
                                .animation(.easeInOut(duration: 0.5), value: bondProgress)
                        }
                    }
                    .frame(height: 6)
                    .padding(.horizontal, 24)

                    if let bond = profile?.bond {
                        Text("第 \(bond.total_interactions ?? 0) 次对话")
                            .font(.caption)
                            .foregroundStyle(Theme.textMuted)
                        if let next = bond.next_level, let needed = bond.interactions_needed {
                            Text("距离「\(next)」还需 \(needed) 次对话")
                                .font(.caption2)
                                .foregroundStyle(Theme.textMuted.opacity(0.7))
                        }
                    }
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
                    HStack(spacing: 0) {
                        ForEach(milestones, id: \.self) { m in
                            let done = (profile?.streak.current ?? 0) >= m
                            Text("\(m)")
                                .font(.caption2.bold())
                                .foregroundStyle(done ? Theme.bg : Theme.textMuted)
                                .frame(maxWidth: .infinity)
                                .frame(height: 36)
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

                // Error state
                if loadError {
                    Text("加载失败，下拉刷新重试")
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                        .padding()
                }
            }
            .padding(.bottom, 32)
        }
        .background(Theme.bg)
        .refreshable { await load() }
        .task { await load() }
    }

    private func load() async {
        loadError = false
        do {
            async let p = api.getProfile()
            async let d = api.getDashboard()
            profile = try await p
            dashboard = try await d
            if let level = profile?.bond.level {
                session.updateBondLevel(level)
            }
        } catch {
            loadError = true
        }
    }
}
