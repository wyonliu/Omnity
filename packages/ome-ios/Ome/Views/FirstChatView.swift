import SwiftUI

/// Zero-registration first chat — the Aha Moment screen.
/// User opens app → starts chatting immediately → after 3 exchanges, soft registration.
struct FirstChatView: View {
    @EnvironmentObject var session: SessionManager
    @State private var messages: [Message] = [
        Message(role: .ome, text: "嗨。随便聊聊？", moodEmoji: "😊")
    ]
    @State private var input = ""
    @State private var sending = false
    @State private var exchangeCount = 0
    @State private var showRegister = false
    @State private var registerName = ""
    @State private var registering = false
    @State private var registerError = ""
    @FocusState private var inputFocused: Bool

    private let softRegisterAfter = 3
    private let api = APIClient.shared

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Ome")
                    .font(.title2.bold())
                    .foregroundStyle(Theme.accent)

                Spacer()

                if exchangeCount >= softRegisterAfter {
                    Button("记住我") { showRegister = true }
                        .font(.subheadline.bold())
                        .foregroundStyle(Theme.accent)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 6)
                        .background(Theme.bgCard)
                        .clipShape(Capsule())
                        .overlay(Capsule().stroke(Theme.accent, lineWidth: 1))
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 8)

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
                TextField("说点什么...", text: $input, axis: .vertical)
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
        .onAppear { inputFocused = true }
        .sheet(isPresented: $showRegister) {
            SoftRegisterSheet(
                name: $registerName,
                error: $registerError,
                registering: $registering,
                onRegister: handleRegister,
                onSkip: skipRegister
            )
            .presentationDetents([.medium])
            .presentationDragIndicator(.visible)
        }
    }

    private func send() {
        let text = input.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !sending else { return }

        messages.append(Message(role: .user, text: text))
        input = ""
        sending = true

        Task {
            do {
                let result = try await api.anonChat(text)
                let newCount = exchangeCount + 1
                exchangeCount = newCount

                messages.append(Message(role: .ome, text: result.reply, moodEmoji: result.mood_emoji))

                if newCount == softRegisterAfter {
                    try await Task.sleep(for: .seconds(1.5))
                    messages.append(Message(
                        role: .ome,
                        text: "我记住了这些对话。但如果你关掉 App，我就会忘记。\n\n给我个名字，让我一直记住你？",
                        moodEmoji: "🥺"
                    ))
                    try await Task.sleep(for: .seconds(1))
                    showRegister = true
                }
            } catch {
                messages.append(Message(role: .ome, text: "连接失败: \(error.localizedDescription)"))
            }
            sending = false
        }
    }

    private func handleRegister() {
        let name = registerName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else {
            registerError = "给我一个名字吧"
            return
        }

        registering = true
        registerError = ""

        Task {
            do {
                try await session.register(name: name)
                showRegister = false
                messages.append(Message(
                    role: .ome,
                    text: "好的，\(name)。以后我会记住你说的每一句。",
                    moodEmoji: "😊"
                ))
                try await Task.sleep(for: .seconds(1.5))
                // session.isLoggedIn triggers navigation to MainTabView
            } catch {
                registerError = error.localizedDescription
            }
            registering = false
        }
    }

    private func skipRegister() {
        showRegister = false
        messages.append(Message(
            role: .ome,
            text: "没关系，我们继续聊。随时可以让我记住你。",
            moodEmoji: "😌"
        ))
    }
}
