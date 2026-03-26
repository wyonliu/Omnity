import SwiftUI

/// 灵境 — 你的 AI 分身控制台。
/// v3: 从可爱小工具升级为人生操作系统。日记复盘、进化任务、灵魂画像、成长轨迹。
struct SoulscapeView: View {
    @EnvironmentObject var session: SessionManager
    @State private var profile: ProfileResponse?
    @State private var dashboard: DashboardResponse?
    @State private var soulCard: SoulCardResponse?
    @State private var loading = true
    @State private var showSoulCardSheet = false
    @State private var soulCardImage: UIImage?
    @State private var soulCardImageLoading = false
    @State private var insightPrompt: String = ""
    @AppStorage("ome_selected_tab") private var selectedTab = 0

    private let api = APIClient.shared

    private let stageNames = ["种子", "嫩芽", "小树", "茂盛", "结果", "繁花", "参天"]
    private let stageDescs = ["刚刚苏醒", "开始有记忆", "有了自己的想法", "能帮你做事", "能替你社交", "完全代表你", "传说级存在"]

    private var level: Int { min(profile?.bond.level ?? session.bondLevel, 6) }

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // 身份卡 — 你的 AI 分身状态
                identityCard

                // 核心模块 — 日记、进化、反思、关系
                modulesGrid

                // 灵魂卡片
                soulCardSection

                // 成长数据
                if !loading {
                    growthDashboard
                }

                // 今日洞察
                insightCard

                // 本周亮点
                highlightsSection
            }
            .padding(20)
        }
        .background(Theme.bg)
        .refreshable { await load() }
        .task { await load() }
        .sheet(isPresented: $showSoulCardSheet) {
            soulCardSheet
        }
    }

    // MARK: - Identity Card (养成核心)

    private var identityCard: some View {
        VStack(spacing: 16) {
            // Orb — centerpiece, size grows with level
            OmeOrb(size: CGFloat(80 + level * 10), intensity: 0.35 + CGFloat(level) * 0.1, bondLevel: level)
                .padding(.top, 8)

            // Name + Level
            VStack(spacing: 4) {
                Text(session.omeDisplayName)
                    .font(.title2.bold())
                    .foregroundStyle(Theme.accent)
                Text("\(stageNames[level]) · Lv.\(level)")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
            }

            // Mood
            if let emotion = profile?.emotion {
                HStack(spacing: 6) {
                    Text(emotion.mood_emoji)
                    Text(emotion.mood)
                        .font(.caption)
                        .foregroundStyle(Theme.textSecondary)
                }
            }

            // Stage description
            Text(stageDescs[level])
                .font(.caption)
                .foregroundStyle(Theme.textMuted)
                .padding(.horizontal, 12)
                .padding(.vertical, 4)
                .background(Theme.bgCard)
                .clipShape(Capsule())
        }
        .frame(maxWidth: .infinity)
        .padding(.bottom, 4)
    }

    // MARK: - Core Modules (2x2 grid → 智能意图)

    private struct OmeModule: Identifiable {
        let id = UUID()
        let icon: String
        let name: String
        let desc: String
        let intent: String  // 发给 Ome 的自然语言意图，Ome 会智能引导
    }

    private var modules: [OmeModule] {
        let hour = Calendar.current.component(.hour, from: Date())
        let timeHint = hour < 12 ? "早上" : hour < 18 ? "下午" : "晚上"
        return [
            OmeModule(icon: "📝", name: "今日复盘", desc: "记录·沉淀·成长",
                      intent: "我想做\(timeHint)的复盘，帮我梳理一下"),
            OmeModule(icon: "🎯", name: "进化任务", desc: "突破舒适区",
                      intent: "给我一个今天的进化任务，根据你对我的了解来"),
            OmeModule(icon: "🪞", name: "照见自己", desc: "认识真实的我",
                      intent: "帮我做一次深度自我反思"),
            OmeModule(icon: "🔗", name: "关系洞察", desc: "理解人与人",
                      intent: "帮我分析一下最近的人际关系"),
        ]
    }

    private var modulesGrid: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("你的进化工具")
                .font(.subheadline.bold())
                .foregroundStyle(Theme.textSecondary)

            LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                ForEach(modules) { mod in
                    Button {
                        launchModule(mod.intent)
                    } label: {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(mod.icon)
                                .font(.title2)
                            Text(mod.name)
                                .font(.subheadline.bold())
                                .foregroundStyle(Theme.textPrimary)
                            Text(mod.desc)
                                .font(.caption2)
                                .foregroundStyle(Theme.textMuted)
                                .lineLimit(2)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(14)
                        .background(Theme.bgCard)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                        .overlay(
                            RoundedRectangle(cornerRadius: 14)
                                .stroke(Theme.accent.opacity(0.12), lineWidth: 1)
                        )
                    }
                }
            }
        }
    }

    // MARK: - Soul Card

    private var soulCardSection: some View {
        Group {
            if let card = soulCard, card.ready {
                Button { loadSoulCardImage() } label: {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("灵魂画像")
                                .font(.headline.bold())
                                .foregroundStyle(Theme.accent)
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundStyle(Theme.textMuted)
                        }

                        if let insight = card.soul_insight {
                            Text("「\(insight)」")
                                .font(.body)
                                .foregroundStyle(Theme.textPrimary)
                                .lineSpacing(4)
                        }

                        if let tags = card.personality_tags, !tags.isEmpty {
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 6) {
                                    ForEach(tags, id: \.self) { tag in
                                        Text(tag)
                                            .font(.caption)
                                            .foregroundStyle(Theme.accent)
                                            .padding(.horizontal, 10)
                                            .padding(.vertical, 4)
                                            .background(Theme.accent.opacity(0.1))
                                            .clipShape(Capsule())
                                    }
                                }
                            }
                        }

                        HStack(spacing: 16) {
                            if let sim = card.similarity {
                                Label("\(sim)% 相似", systemImage: "heart.fill")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.bondGreen)
                            }
                            if let count = card.conversation_count {
                                Label("\(count) 次对话", systemImage: "bubble.left.and.bubble.right")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.textMuted)
                            }
                            if let days = card.days_together {
                                Label("\(days) 天", systemImage: "calendar")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.textMuted)
                            }
                        }
                    }
                    .padding(16)
                    .background(
                        LinearGradient(
                            colors: [Theme.accent.opacity(0.05), Theme.bgCard],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.cornerRadius)
                            .stroke(Theme.accent.opacity(0.3), lineWidth: 1)
                    )
                }
            } else {
                let needed = soulCard?.conversations_needed ?? 10
                VStack(spacing: 12) {
                    Image(systemName: "sparkles")
                        .font(.title)
                        .foregroundStyle(Theme.textMuted)
                    Text("灵魂画像")
                        .font(.headline)
                        .foregroundStyle(Theme.textSecondary)
                    Text("再聊 \(needed) 次，Ome 就能生成你的灵魂画像")
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                    Button {
                        selectedTab = 0
                    } label: {
                        Text("去聊天")
                            .font(.caption.bold())
                            .foregroundStyle(Theme.bg)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 6)
                            .background(Theme.accent)
                            .clipShape(Capsule())
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(20)
                .background(Theme.bgCard)
                .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
            }
        }
    }

    // MARK: - Growth Dashboard

    private var growthDashboard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("成长轨迹")
                .font(.subheadline.bold())
                .foregroundStyle(Theme.textSecondary)

            HStack(spacing: 8) {
                StatCard(value: "Lv.\(level)",
                         label: stageNames[level],
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
    }

    // MARK: - Insight Card

    private var insightCard: some View {
        let displayPrompt = insightPrompt.isEmpty ? PromptManager.featuredPrompt() : insightPrompt
        return VStack(alignment: .leading, spacing: 10) {
            Text("\(session.omeDisplayName)想问你")
                .font(.subheadline.bold())
                .foregroundStyle(Theme.textSecondary)
            Text(displayPrompt)
                .font(.body)
                .foregroundStyle(Theme.textPrimary)
                .lineSpacing(4)
            Button {
                launchModule(displayPrompt)
            } label: {
                Text("和 Ome 聊这个")
                    .font(.caption.bold())
                    .foregroundStyle(Theme.bg)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 6)
                    .background(Theme.accent)
                    .clipShape(Capsule())
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Theme.bgCard)
        .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
        .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
    }

    // MARK: - Highlights

    @ViewBuilder
    private var highlightsSection: some View {
        if let highlights = dashboard?.highlights, !highlights.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Text("本周亮点")
                    .font(.subheadline.bold())
                    .foregroundStyle(Theme.textSecondary)
                ForEach(highlights.prefix(5), id: \.self) { h in
                    Text("· \(h)")
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
            .background(Theme.bgCard)
            .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
            .overlay(RoundedRectangle(cornerRadius: Theme.cornerRadius).stroke(Theme.border))
        }
    }

    // MARK: - Soul Card Sheet

    private var soulCardSheet: some View {
        VStack(spacing: 20) {
            if let img = soulCardImage {
                Text("你的灵魂画像").font(.headline).foregroundStyle(Theme.textPrimary)
                Image(uiImage: img)
                    .resizable()
                    .scaledToFit()
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .shadow(radius: 10)
                    .padding(.horizontal)
                Button {
                    shareSoulCard(img)
                } label: {
                    HStack {
                        Image(systemName: "square.and.arrow.up")
                        Text("分享")
                    }
                    .font(.headline)
                    .foregroundStyle(Theme.bg)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Theme.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                }
                .padding(.horizontal, 30)
                Button("关闭") { showSoulCardSheet = false }
                    .foregroundStyle(Theme.textMuted)
            } else {
                ProgressView().tint(Theme.accent)
                Text("生成中...").font(.caption).foregroundStyle(Theme.textMuted)
            }
        }
        .padding(.vertical, 30)
        .background(Theme.bg)
    }

    // MARK: - Helpers

    private func launchModule(_ prompt: String) {
        selectedTab = 0
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            NotificationCenter.default.post(name: .omeStartActivity, object: prompt)
        }
    }

    private func load() async {
        do {
            async let p = api.getProfile()
            async let d = api.getDashboard()
            async let s = api.getSoulCard()
            profile = try await p
            dashboard = try await d
            soulCard = try? await s
            if let level = profile?.bond.level {
                session.updateBondLevel(level)
            }
        } catch {
            // Silent — show cached/default values
        }
        loading = false
        // Load LLM-generated insight prompt (fire-and-forget)
        if let prompts = try? await api.generatePrompts(count: 1), let first = prompts.first {
            insightPrompt = first
        }
    }

    private func loadSoulCardImage() {
        guard !soulCardImageLoading else { return }
        soulCardImageLoading = true
        showSoulCardSheet = true
        Task {
            do {
                let data = try await api.getSoulCardImage()
                if let image = UIImage(data: data) {
                    soulCardImage = image
                }
            } catch {}
            soulCardImageLoading = false
        }
    }

    private func shareSoulCard(_ image: UIImage) {
        let av = UIActivityViewController(
            activityItems: [image, "我的AI分身这样看我 #OmeAI"],
            applicationActivities: nil
        )
        if let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let root = scene.windows.first?.rootViewController {
            root.present(av, animated: true)
        }
    }
}

// MARK: - Notification for activity launch

extension Notification.Name {
    static let omeStartActivity = Notification.Name("omeStartActivity")
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
