import SwiftUI

/// Soulscape — the Ome's soul visualized. Orb + growth stage + quick stats + daily prompt.
struct SoulscapeView: View {
    @EnvironmentObject var session: SessionManager
    @State private var profile: ProfileResponse?
    @State private var dashboard: DashboardResponse?
    @State private var loading = true
    @AppStorage("ome_selected_tab") private var selectedTab = 0

    private let api = APIClient.shared

    private let stageNames = ["种子", "嫩芽", "小树", "茂盛", "结果", "繁花", "参天"]
    private let stageDescs = ["一切刚开始", "开始有记忆了", "开始有生活了", "能帮你做事了", "能替你社交了", "完全代表你了", "传说级存在"]

    private var level: Int { min(profile?.bond.level ?? session.bondLevel, 6) }
    private var orbSize: CGFloat { CGFloat(80 + level * 12) }
    private var orbIntensity: CGFloat { 0.35 + CGFloat(level) * 0.1 }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Soulscape — orb as the centerpiece
                ZStack {
                    // Ambient particles at higher levels
                    if level >= 2 {
                        ParticleField(count: 4 + level * 2, color: Theme.accent, opacity: 0.2 + Double(level) * 0.05)
                            .frame(height: 220)
                    }

                    VStack(spacing: 12) {
                        OmeOrb(size: orbSize, intensity: orbIntensity, bondLevel: level)
                            .padding(.top, 20)

                        Text(stageNames[level])
                            .font(.title3.bold())
                            .foregroundStyle(Theme.accent)

                        Text("Lv.\(level) · \(stageDescs[level])")
                            .font(.caption)
                            .foregroundStyle(Theme.textMuted)
                    }
                }
                .padding(.vertical, 16)

                // Mood ring (from profile emotion)
                if let emotion = profile?.emotion {
                    HStack(spacing: 8) {
                        Circle()
                            .fill(moodColor(emotion.mood))
                            .frame(width: 8, height: 8)
                        Text("心情：\(emotion.mood)")
                            .font(.caption)
                            .foregroundStyle(Theme.textSecondary)
                    }
                }

                // Personality traits
                if let traits = profile?.traits, !traits.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("性格特征")
                            .font(.caption.bold())
                            .foregroundStyle(Theme.textMuted)
                        FlowLayout(spacing: 6) {
                            ForEach(traits, id: \.self) { trait in
                                TraitPill(trait: trait)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 4)
                }

                // Greeting — time + streak aware
                HStack(spacing: 12) {
                    OmeOrbMini(size: 32)
                    Text(GreetingManager.greeting(
                        for: session.userName,
                        streak: profile?.streak.current ?? 0,
                        bondLevel: level
                    ))
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
                if loading {
                    SkeletonStatRow()
                } else {
                    HStack(spacing: 8) {
                        StatCard(value: "Lv.\(level)",
                                 label: profile?.bond.name ?? stageNames[level],
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
                }

                // Daily prompt — "今日话题"
                VStack(alignment: .leading, spacing: 10) {
                    Text("今日话题")
                        .font(.headline)
                        .foregroundStyle(Theme.accent)
                    Text(PromptManager.featuredPrompt())
                        .font(.body)
                        .foregroundStyle(Theme.textPrimary)
                        .lineSpacing(4)
                    Button {
                        selectedTab = 0  // Switch to Chat tab
                    } label: {
                        Text("去聊聊")
                            .font(.subheadline.bold())
                            .foregroundStyle(Theme.bg)
                            .padding(.horizontal, 20)
                            .padding(.vertical, 8)
                            .background(Theme.accent)
                            .clipShape(Capsule())
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
        loading = false
    }

    private func moodColor(_ mood: String) -> Color {
        switch mood.lowercased() {
        case "happy", "joyful", "开心": return Theme.achieveGold
        case "calm", "平静": return Theme.bondGreen
        case "excited", "兴奋": return Theme.streakOrange
        case "reflective", "思考": return Theme.emotionPurple
        case "sad", "难过": return Color(hex: "60a5fa")
        default: return Theme.accent
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

/// Simple flow layout for trait pills.
struct FlowLayout: Layout {
    var spacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = arrange(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = arrange(proposal: proposal, subviews: subviews)
        for (index, position) in result.positions.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y),
                                   proposal: .unspecified)
        }
    }

    private func arrange(proposal: ProposedViewSize, subviews: Subviews) -> (positions: [CGPoint], size: CGSize) {
        let maxWidth = proposal.width ?? .infinity
        var positions: [CGPoint] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        var totalHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > maxWidth && x > 0 {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            positions.append(CGPoint(x: x, y: y))
            rowHeight = max(rowHeight, size.height)
            x += size.width + spacing
            totalHeight = y + rowHeight
        }

        return (positions, CGSize(width: maxWidth, height: totalHeight))
    }
}
