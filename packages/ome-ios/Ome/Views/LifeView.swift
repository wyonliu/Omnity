import SwiftUI

/// Life dashboard — bond progress, achievements, streak with flame + 7-day calendar.
struct LifeView: View {
    @EnvironmentObject var session: SessionManager
    @State private var profile: ProfileResponse?
    @State private var dashboard: DashboardResponse?
    @State private var loading = true
    @State private var loadError = false

    private let api = APIClient.shared

    private let stages = [
        ("leaf", "初见"), ("leaf.fill", "嫩芽"), ("tree", "小树"), ("tree.fill", "茂盛"),
        ("sparkles", "结果"), ("laurel.leading", "繁花"), ("mountain.2.fill", "参天"),
    ]

    private var bondProgress: Double {
        guard let bond = profile?.bond else { return 0 }
        let needed = bond.interactions_needed ?? 50
        guard needed > 0 else { return 1.0 }
        let total = bond.total_interactions ?? 0
        return min(1.0, Double(total % needed) / Double(needed))
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Header
                HStack(spacing: 10) {
                    OmeOrbMini(size: 28)
                    Text("成长")
                        .font(.title2.bold())
                        .foregroundStyle(Theme.textPrimary)
                    Spacer()
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)

                if loading {
                    // Skeleton loading
                    VStack(spacing: 16) {
                        SkeletonCard()
                        SkeletonCard()
                    }
                    .padding(.horizontal, 20)
                } else {
                    // Bond hero
                    bondSection

                    // Streak
                    streakSection

                    // Achievements
                    achievementsSection

                    // Highlights
                    highlightsSection

                    // Error state
                    if loadError {
                        Button {
                            loading = true
                            loadError = false
                            Task { await load() }
                        } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "arrow.clockwise")
                                Text("加载失败，点击重试")
                            }
                            .font(.caption)
                            .foregroundStyle(Theme.textMuted)
                            .padding()
                        }
                    }
                }
            }
            .padding(.bottom, 32)
        }
        .background(Theme.bg)
        .refreshable { await load() }
        .task { await load() }
    }

    // MARK: - Bond Section

    private var bondSection: some View {
        let level = min(profile?.bond.level ?? session.bondLevel, 6)
        return VStack(spacing: 10) {
            Image(systemName: stages[level].0)
                .font(.system(size: 48))
                .foregroundStyle(Theme.bondGreen)

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
    }

    // MARK: - Streak Section

    private var streakSection: some View {
        let streak = profile?.streak.current ?? 0
        return VStack(alignment: .leading, spacing: 12) {
            Text("连续互动")
                .font(.headline)
                .foregroundStyle(Theme.accent)

            HStack {
                HStack(alignment: .lastTextBaseline, spacing: 4) {
                    // Streak flame — grows with streak
                    Image(systemName: streak > 0 ? "flame.fill" : "flame")
                        .font(.title2)
                        .foregroundStyle(streak > 0 ? Theme.streakOrange : Theme.textMuted)
                        .symbolEffect(.pulse, options: .repeating, isActive: streak >= 7)

                    Text("\(streak)")
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

            // 7-day calendar strip
            HStack(spacing: 4) {
                ForEach(0..<7, id: \.self) { daysAgo in
                    let dayOffset = 6 - daysAgo
                    let isActive = dayOffset < streak
                    let isToday = daysAgo == 6
                    VStack(spacing: 4) {
                        Text(dayLabel(daysAgo: dayOffset))
                            .font(.system(size: 9))
                            .foregroundStyle(Theme.textMuted)
                        Circle()
                            .fill(isActive ? Theme.streakOrange : Theme.bgInput)
                            .frame(width: 28, height: 28)
                            .overlay(
                                Circle()
                                    .stroke(isToday ? Theme.accent : Color.clear, lineWidth: 2)
                            )
                            .overlay {
                                if isActive {
                                    Image(systemName: "checkmark")
                                        .font(.caption2.bold())
                                        .foregroundStyle(Theme.bg)
                                }
                            }
                    }
                    .frame(maxWidth: .infinity)
                }
            }

            // Streak at risk
            if streak > 0 {
                let today = Calendar.current.startOfDay(for: Date())
                let lastActive = UserDefaults.standard.object(forKey: "ome_last_active_date") as? Date ?? today
                if !Calendar.current.isDate(lastActive, inSameDayAs: today) {
                    HStack(spacing: 4) {
                        Image(systemName: "flame.fill")
                            .font(.caption)
                        Text("今天还没聊天，别让连续记录断了")
                            .font(.caption)
                    }
                    .foregroundStyle(Theme.streakOrange)
                    .padding(.top, 4)
                }
            }
        }
        .padding()
        .background(Theme.bgCard)
        .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
        .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
        .padding(.horizontal, 20)
    }

    // MARK: - Achievements

    @ViewBuilder
    private var achievementsSection: some View {
        if let achievements = dashboard?.achievements.unlocked, !achievements.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("成就 \(dashboard?.achievements.count ?? "0/0")")
                    .font(.headline)
                    .foregroundStyle(Theme.accent)

                ForEach(achievements) { a in
                    HStack(spacing: 12) {
                        Text(a.icon ?? "")
                            .font(.title2)
                            .frame(width: 32)
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
    }

    // MARK: - Highlights

    @ViewBuilder
    private var highlightsSection: some View {
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

    // MARK: - Helpers

    private func dayLabel(daysAgo: Int) -> String {
        if daysAgo == 0 { return "今" }
        let date = Calendar.current.date(byAdding: .day, value: -daysAgo, to: Date())!
        let formatter = DateFormatter()
        formatter.dateFormat = "E"
        formatter.locale = Locale(identifier: "zh_CN")
        return String(formatter.string(from: date).prefix(1))
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
        loading = false
    }
}
