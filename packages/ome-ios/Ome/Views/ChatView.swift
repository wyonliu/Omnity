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
            // Header with orb
            HStack(spacing: 10) {
                OmeOrbMini(size: 32)
                VStack(alignment: .leading, spacing: 2) {
                    Text(isMirror ? "镜像 · \(session.userName)" : "Ome")
                        .font(.headline)
                        .foregroundStyle(Theme.textPrimary)
                    Text(isMirror ? "用你的语气说话" : "你的 AI 化身")
                        .font(.caption2)
                        .foregroundStyle(Theme.textMuted)
                }

                Spacer()

                Button(isMirror ? "对话" : "镜像") {
                    isMirror.toggle()
                    setupWelcome()
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }
                .font(.subheadline)
                .foregroundStyle(Theme.accent)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Theme.bgCard)
                .clipShape(Capsule())
                .overlay(Capsule().stroke(Theme.border, lineWidth: 1))
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
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
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: messages.count) {
                    withAnimation(.easeOut(duration: 0.3)) {
                        proxy.scrollTo(messages.last?.id, anchor: .bottom)
                    }
                }
                .onChange(of: messages.last?.text) {
                    // Scroll during streaming
                    proxy.scrollTo(messages.last?.id, anchor: .bottom)
                }
            }

            // Input bar
            inputBar
        }
        .background(Theme.bg)
        .onAppear { setupWelcome() }
    }

    private var inputBar: some View {
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
                Image(systemName: sending ? "ellipsis" : "arrow.up")
                    .font(.body.bold())
                    .foregroundStyle(Theme.bg)
                    .frame(width: 44, height: 44)
                    .background(canSend ? Theme.accent : Theme.accent.opacity(0.3))
                    .clipShape(Circle())
            }
            .disabled(!canSend)
            .animation(.easeInOut(duration: 0.15), value: canSend)
            .accessibilityLabel("发送")
        }
        .padding(.horizontal, 16)
        .padding(.top, 12)
        .padding(.bottom, 16)
        .background(Theme.bgCard)
    }

    private var canSend: Bool {
        !input.trimmingCharacters(in: .whitespaces).isEmpty && !sending
    }

    private func setupWelcome() {
        messages = [
            Message(
                role: .ome,
                text: isMirror
                    ? "镜像模式：我会用\(session.userName)的语气说话。试试看？"
                    : "嗨，\(session.userName)。想聊点什么？"
            )
        ]
    }

    private func send() {
        let text = input.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !sending else { return }

        messages.append(Message(role: .user, text: text))
        input = ""
        sending = true
        UIImpactFeedbackGenerator(style: .light).impactOccurred()

        if isMirror {
            sendMirror(text)
        } else {
            sendStream(text)
        }
    }

    private func sendStream(_ text: String) {
        let streamMsg = Message(role: .ome, text: "", isStreaming: true)
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
                        messages[idx].isStreaming = false
                    }
                    session.updateBondLevel(result.bond_level)
                } catch {
                    if let idx = messages.firstIndex(where: { $0.id == streamId }) {
                        messages[idx].text = friendlyError(error)
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
                messages.append(Message(role: .ome, text: result.reply))
            } catch {
                messages.append(Message(role: .ome, text: friendlyError(error)))
            }
            sending = false
        }
    }

    private func friendlyError(_ error: Error) -> String {
        if let apiErr = error as? APIError {
            switch apiErr {
            case .network: return "信号不太好，检查一下网络？"
            case .unauthorized: return "需要重新登录一下"
            case .serverError: return "服务器开小差了，稍后再试"
            case .invalidURL: return "出了点问题，稍后再试"
            }
        }
        return "信号不太好，稍后再试"
    }
}
