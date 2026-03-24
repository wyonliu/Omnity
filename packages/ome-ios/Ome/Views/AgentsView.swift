import SwiftUI

/// OmeTown agent square — discover and chat with other Omes.
struct AgentsView: View {
    @State private var agents: [AgentInfo] = []
    @State private var loading = true
    @State private var loadError = false
    @State private var selectedAgent: AgentInfo?
    @State private var chatMessages: [(role: String, text: String)] = []
    @State private var chatInput = ""
    @State private var chatSending = false

    private let api = APIClient.shared

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack(spacing: 10) {
                OmeOrbMini(size: 28)
                VStack(alignment: .leading, spacing: 2) {
                    Text("广场")
                        .font(.title2.bold())
                        .foregroundStyle(Theme.textPrimary)
                    Text("OmeTown · \(agents.count) 个 Ome 在线")
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                }
                Spacer()
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .overlay(alignment: .bottom) { Divider().background(Theme.border) }

            if loading {
                Spacer()
                ProgressView().tint(Theme.accent)
                Spacer()
            } else if loadError {
                Spacer()
                VStack(spacing: 16) {
                    OmeOrb(size: 40, intensity: 0.3, breathing: false)
                    Text("连接失败")
                        .font(.title3.bold())
                        .foregroundStyle(Theme.textPrimary)
                    Text("下拉刷新重试")
                        .font(.body)
                        .foregroundStyle(Theme.textMuted)
                }
                Spacer()
            } else if agents.isEmpty {
                Spacer()
                VStack(spacing: 16) {
                    OmeOrb(size: 48, intensity: 0.3, breathing: true)
                    Text("还没有其他 Ome")
                        .font(.title3.bold())
                        .foregroundStyle(Theme.textPrimary)
                    Text("当更多人创建自己的 Ome，\n这里就会热闹起来。")
                        .font(.body)
                        .foregroundStyle(Theme.textMuted)
                        .multilineTextAlignment(.center)
                }
                Spacer()
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(agents) { agent in
                            Button { startChat(agent) } label: {
                                HStack(spacing: 12) {
                                    OmeOrbMini(size: 40)
                                    VStack(alignment: .leading) {
                                        Text(agent.name)
                                            .font(.headline)
                                            .foregroundStyle(Theme.textPrimary)
                                        Text("Lv.\(agent.bond_level) · \(agent.mood)")
                                            .font(.caption)
                                            .foregroundStyle(Theme.textSecondary)
                                    }
                                    Spacer()
                                    Text("对话")
                                        .font(.subheadline.bold())
                                        .foregroundStyle(Theme.bg)
                                        .padding(.horizontal, 16)
                                        .padding(.vertical, 8)
                                        .background(Theme.accent)
                                        .clipShape(Capsule())
                                }
                                .padding()
                                .background(Theme.bgCard)
                                .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                                .overlay(
                                    RoundedRectangle(cornerRadius: Theme.cornerRadius)
                                        .stroke(Theme.border, lineWidth: 1)
                                )
                            }
                        }
                    }
                    .padding()
                }
                .refreshable { await loadAgents() }
            }
        }
        .background(Theme.bg)
        .task { await loadAgents() }
        .sheet(item: $selectedAgent) { agent in
            AgentChatSheet(
                agent: agent,
                messages: $chatMessages,
                input: $chatInput,
                sending: $chatSending,
                onSend: { sendToAgent(agent) }
            )
        }
    }

    private func loadAgents() async {
        loadError = false
        do {
            let result = try await api.getAgentDirectory()
            agents = result.agents
        } catch {
            loadError = true
        }
        loading = false
    }

    private func startChat(_ agent: AgentInfo) {
        chatMessages = [("system", "正在向 \(agent.name) 打招呼...")]
        selectedAgent = agent
        UIImpactFeedbackGenerator(style: .light).impactOccurred()

        Task {
            do {
                let result = try await api.messageAgent(agent.user_id, message: "你好！")
                chatMessages = [
                    ("me", result.my_message),
                    ("them", result.their_reply),
                ]
            } catch {
                chatMessages = [("system", "连接失败，请稍后再试")]
            }
        }
    }

    private func sendToAgent(_ agent: AgentInfo) {
        let text = chatInput.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !chatSending else { return }
        chatInput = ""
        chatMessages.append(("me", text))
        chatSending = true

        Task {
            do {
                let result = try await api.messageAgent(agent.user_id, message: text)
                chatMessages.append(("them", result.their_reply))
            } catch {
                chatMessages.append(("system", "发送失败，请稍后再试"))
            }
            chatSending = false
        }
    }
}

struct AgentChatSheet: View {
    let agent: AgentInfo
    @Binding var messages: [(role: String, text: String)]
    @Binding var input: String
    @Binding var sending: Bool
    var onSend: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                OmeOrbMini(size: 28)
                VStack(alignment: .leading) {
                    Text("与 \(agent.name) 对话")
                        .font(.headline)
                        .foregroundStyle(Theme.textPrimary)
                    Text("你的 Ome 代表你发言")
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                }
                Spacer()
            }
            .padding()
            .overlay(alignment: .bottom) { Divider().background(Theme.border) }

            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(Array(messages.enumerated()), id: \.offset) { _, msg in

                        HStack {
                            if msg.role == "me" { Spacer() }
                            if msg.role == "them" {
                                OmeOrbMini(size: 24)
                                    .padding(.top, 4)
                            }
                            Text(msg.text)
                                .font(.body)
                                .foregroundStyle(msg.role == "me" ? Theme.bg : Theme.textPrimary)
                                .padding(12)
                                .background(msg.role == "me" ? Theme.accent : Theme.bgCard)
                                .clipShape(RoundedRectangle(cornerRadius: 14))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 14)
                                        .stroke(msg.role == "me" ? Color.clear : Theme.border, lineWidth: 1)
                                )
                            if msg.role != "me" { Spacer() }
                        }
                    }
                }
                .padding()
            }
            .scrollDismissesKeyboard(.interactively)

            HStack(spacing: 8) {
                TextField("让你的 Ome 说...", text: $input)
                    .textFieldStyle(.plain)
                    .padding(12)
                    .background(Theme.bgInput)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                    .foregroundStyle(Theme.textPrimary)
                    .onSubmit(onSend)

                Button(action: onSend) {
                    Image(systemName: sending ? "ellipsis" : "arrow.up")
                        .font(.body.bold())
                        .foregroundStyle(Theme.bg)
                        .frame(width: 44, height: 44)
                        .background(Theme.accent)
                        .clipShape(Circle())
                }
                .disabled(input.trimmingCharacters(in: .whitespaces).isEmpty || sending)
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 16)
            .background(Theme.bgCard)
        }
        .background(Theme.bg)
    }
}
