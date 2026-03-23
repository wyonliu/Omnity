import SwiftUI

/// Authenticated chat with SSE streaming + mirror mode.
struct ChatView: View {
    @EnvironmentObject var session: SessionManager
    @State private var messages: [Message] = []
    @State private var input = ""
    @State private var sending = false
    @State private var isMirror = false
    @FocusState private var inputFocused: Bool

    private let api = APIClient.shared

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text(isMirror ? "🪞 镜像 · \(session.userName)" : "💬 对话")
                    .font(.title2.bold())
                    .foregroundStyle(Theme.textPrimary)

                Spacer()

                Button(isMirror ? "普通" : "镜像") {
                    isMirror.toggle()
                    setupWelcome()
                }
                .font(.subheadline)
                .foregroundStyle(Theme.accent)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Theme.bgCard)
                .clipShape(Capsule())
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .background(Theme.bg)
            .overlay(alignment: .bottom) {
                Divider().background(Theme.border)
            }

            // Messages
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(messages) { msg in
                            MessageBubble(message: msg)
                                .id(msg.id)
                        }
                    }
                    .padding()
                }
                .onChange(of: messages.count) {
                    withAnimation {
                        proxy.scrollTo(messages.last?.id, anchor: .bottom)
                    }
                }
            }

            // Input bar
            HStack(alignment: .bottom, spacing: 8) {
                TextField(isMirror ? "和自己聊聊..." : "说点什么...", text: $input, axis: .vertical)
                    .lineLimit(1...4)
                    .textFieldStyle(.plain)
                    .padding(12)
                    .background(Theme.bgInput)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                    .foregroundStyle(Theme.textPrimary)
                    .focused($inputFocused)
                    .onSubmit { send() }

                Button(action: send) {
                    Text(sending ? "···" : "→")
                        .font(.title2.bold())
                        .foregroundStyle(Theme.bg)
                        .frame(width: 44, height: 44)
                        .background(Theme.accent)
                        .clipShape(Circle())
                }
                .disabled(input.trimmingCharacters(in: .whitespaces).isEmpty || sending)
                .opacity(input.trimmingCharacters(in: .whitespaces).isEmpty || sending ? 0.4 : 1)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .padding(.bottom, 8)
            .background(Theme.bgCard)
        }
        .background(Theme.bg)
        .onAppear { setupWelcome() }
    }

    private func setupWelcome() {
        messages = [
            Message(
                role: .ome,
                text: isMirror
                    ? "镜像模式：我会用\(session.userName)的语气说话。试试看？"
                    : "嗨！有什么想聊的？",
                moodEmoji: "😊"
            )
        ]
    }

    private func send() {
        let text = input.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !sending else { return }

        messages.append(Message(role: .user, text: text))
        input = ""
        sending = true

        if isMirror {
            sendMirror(text)
        } else {
            sendStream(text)
        }
    }

    private func sendStream(_ text: String) {
        let streamMsg = Message(role: .ome, text: "", moodEmoji: "💭", isStreaming: true)
        let streamId = streamMsg.id
        messages.append(streamMsg)

        Task {
            var accumulated = ""
            do {
                for try await token in api.chatStream(text) {
                    if let t = token.token {
                        accumulated += t
                        if let idx = messages.firstIndex(where: { $0.id == streamId }) {
                            messages[idx].text = accumulated
                        }
                    }
                    if token.done == true {
                        if let idx = messages.firstIndex(where: { $0.id == streamId }) {
                            messages[idx].text = token.full_reply ?? accumulated
                            messages[idx].moodEmoji = token.mood_emoji
                            messages[idx].isStreaming = false
                        }
                        if let level = token.bond_level {
                            session.updateBondLevel(level)
                        }
                    }
                }
            } catch {
                // Fallback to regular chat
                do {
                    let result = try await api.chat(text)
                    if let idx = messages.firstIndex(where: { $0.id == streamId }) {
                        messages[idx].text = result.reply
                        messages[idx].moodEmoji = result.mood_emoji
                        messages[idx].isStreaming = false
                    }
                    session.updateBondLevel(result.bond_level)
                } catch {
                    if let idx = messages.firstIndex(where: { $0.id == streamId }) {
                        messages[idx].text = "连接失败: \(error.localizedDescription)"
                        messages[idx].isStreaming = false
                    }
                }
            }
            sending = false
        }
    }

    private func sendMirror(_ text: String) {
        Task {
            do {
                let result = try await api.mirror(text)
                messages.append(Message(role: .ome, text: result.reply, moodEmoji: result.mood_emoji))
            } catch {
                messages.append(Message(role: .ome, text: "连接失败: \(error.localizedDescription)"))
            }
            sending = false
        }
    }
}
