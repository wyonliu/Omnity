import SwiftUI

/// Authenticated chat with SSE streaming + mirror mode + daily prompts + gamification.
/// v3: Uses ChatStore for state persistence across tab switches.
struct ChatView: View {
    @EnvironmentObject var session: SessionManager
    @EnvironmentObject var chatStore: ChatStore
    @State private var input = ""
    @State private var showPrompts = true
    @State private var showLevelUp = false
    @State private var levelUpInfo: LevelUpEvent?
    @State private var showAchievement = false
    @State private var achievementInfo: AchievementEvent?
    @State private var dailyChallenge: DailyChallenge?
    @State private var showSoulCard = false
    @State private var soulCardImage: UIImage?
    @State private var soulCardLoading = false
    @State private var replyChips: [String] = []
    @State private var showGuessGame = false
    @State private var guessGameCreating = false
    @State private var lastUserMsg: String?
    @State private var lastOmeReply: String?
    @State private var serverPrompts: [String] = []
    @FocusState private var inputFocused: Bool

    private let api = APIClient.shared

    var body: some View {
        VStack(spacing: 0) {
            chatHeader

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(chatStore.messages) { msg in
                            MessageBubble(message: msg)
                                .id(msg.id)
                                .onTapGesture {
                                    if msg.text.contains("\u{7075}\u{9B42}\u{5361}\u{7247}") && msg.role == .ome {
                                        loadSoulCard()
                                    }
                                }
                        }

                        // Show initial prompts OR reply chips after Ome's last response
                        if !chatStore.isMirror && !chatStore.sending {
                            if chatStore.messages.count <= 1 && showPrompts {
                                promptChips
                                    .transition(.opacity.combined(with: .move(edge: .bottom)))
                            } else if !replyChips.isEmpty {
                                replyChipBar
                                    .transition(.opacity.combined(with: .move(edge: .bottom)))
                            }
                        }
                    }
                    .padding()
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: chatStore.messages.count) {
                    withAnimation(.easeOut(duration: 0.3)) {
                        proxy.scrollTo(chatStore.messages.last?.id, anchor: .bottom)
                    }
                }
                .onChange(of: chatStore.messages.last?.text) {
                    proxy.scrollTo(chatStore.messages.last?.id, anchor: .bottom)
                }
            }

            if chatStore.showBondPulse {
                HStack(spacing: 6) {
                    Image(systemName: "heart.fill")
                        .font(.caption2)
                        .foregroundStyle(Theme.bondGreen)
                    Text(chatStore.bondPulseText)
                        .font(.caption2.bold())
                        .foregroundStyle(Theme.bondGreen)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 4)
                .background(Theme.bondGreen.opacity(0.1))
                .clipShape(Capsule())
                .transition(.opacity.combined(with: .move(edge: .bottom)))
            }

            if let challenge = dailyChallenge, !challenge.completed {
                dailyChallengeBanner(challenge)
            }

            inputBar
        }
        .background(Theme.bg)
        .onAppear {
            if !chatStore.welcomeConfigured {
                setupWelcome()
            }
            loadProfile()
            chatStore.speech.requestPermission()
        }
        .onChange(of: chatStore.speechIsRecording) { _, isRecording in
            if !isRecording {
                let text = chatStore.speechTranscript.trimmingCharacters(in: .whitespaces)
                if !text.isEmpty {
                    // Voice-first: auto-send after recording stops
                    input = text
                    send()
                }
            }
        }
        .sheet(isPresented: $showSoulCard) {
            soulCardSheet
        }
        .sheet(isPresented: $showGuessGame) {
            guessGameSheet
        }
        .overlay {
            if showAchievement, let ach = achievementInfo {
                achievementToast(ach)
            }
        }
        .fullScreenCover(isPresented: $showLevelUp) {
            if let lu = levelUpInfo {
                LevelUpCelebration(level: lu.level, stageName: lu.name, stageDesc: (lu.unlocks ?? []).joined(separator: ", ")) {
                    showLevelUp = false
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .omeStartActivity)) { notif in
            if let prompt = notif.object as? String {
                input = prompt
                send()
            }
        }
    }

    // MARK: - Chat Header with Growth

    private var chatHeader: some View {
        HStack(spacing: 10) {
            ZStack {
                OmeOrbMini(size: 32)
                Circle()
                    .stroke(moodColor.opacity(0.6), lineWidth: 2)
                    .frame(width: 38, height: 38)
            }

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(chatStore.isMirror ? "\u{955C}\u{50CF} \u{00B7} \(session.userName)" : session.omeDisplayName)
                        .font(.headline)
                        .foregroundStyle(Theme.textPrimary)
                    Text(chatStore.currentMoodEmoji)
                        .font(.caption)
                }
                HStack(spacing: 8) {
                    if !chatStore.isMirror {
                        HStack(spacing: 3) {
                            Image(systemName: bondIcon)
                                .font(.system(size: 9))
                                .foregroundStyle(Theme.bondGreen)
                            Text("Lv.\(chatStore.bondLevel)")
                                .font(.system(size: 10, weight: .medium).monospacedDigit())
                                .foregroundStyle(Theme.bondGreen)
                        }
                        if chatStore.streakDays > 0 {
                            HStack(spacing: 2) {
                                Image(systemName: "flame.fill")
                                    .font(.system(size: 9))
                                    .foregroundStyle(Theme.streakOrange)
                                Text("\(chatStore.streakDays)\u{5929}")
                                    .font(.system(size: 10, weight: .medium).monospacedDigit())
                                    .foregroundStyle(Theme.streakOrange)
                            }
                        }
                    } else {
                        Text("\u{7528}\u{4F60}\u{7684}\u{8BED}\u{6C14}\u{8BF4}\u{8BDD}")
                            .font(.caption2)
                            .foregroundStyle(Theme.textMuted)
                    }
                }
            }

            Spacer()

            Button(chatStore.isMirror ? "\u{5BF9}\u{8BDD}" : "\u{955C}\u{50CF}") {
                chatStore.isMirror.toggle()
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
    }

    private var bondIcon: String {
        switch chatStore.bondLevel {
        case 0: return "leaf"
        case 1: return "leaf.fill"
        case 2: return "tree"
        case 3: return "tree.fill"
        case 4: return "sparkles"
        case 5: return "laurel.leading"
        default: return "mountain.2.fill"
        }
    }

    private var moodColor: Color {
        switch chatStore.currentMood {
        case "happy", "excited": return Theme.achieveGold
        case "sad": return Theme.emotionPurple
        case "stressed": return Theme.error
        case "curious": return Color(hex: "38bdf8")
        case "missing_you": return Theme.streakOrange
        default: return Theme.accent
        }
    }

    // MARK: - Daily Prompt Chips (LLM-generated, fallback to local)

    private var promptChips: some View {
        let prompts = serverPrompts.isEmpty ? PromptManager.dailyPrompts() : serverPrompts
        return VStack(alignment: .leading, spacing: 8) {
            Text(session.omeDisplayName + "\u{60F3}\u{95EE}\u{4F60}")
                .font(.caption)
                .foregroundStyle(Theme.textMuted)
                .padding(.leading, 4)
            ForEach(prompts, id: \.self) { prompt in
                Button {
                    input = prompt
                    send()
                } label: {
                    Text(prompt)
                        .font(.subheadline)
                        .foregroundStyle(Theme.textPrimary)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(Theme.bgCard)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                        .overlay(
                            RoundedRectangle(cornerRadius: 14)
                                .stroke(Theme.accent.opacity(0.3), lineWidth: 1)
                        )
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 8)
    }

    // MARK: - Reply Chips (after every Ome response)

    private var replyChipBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(replyChips, id: \.self) { chip in
                    Button {
                        input = chip
                        withAnimation { replyChips = [] }
                        send()
                    } label: {
                        Text(chip)
                            .font(.caption)
                            .foregroundStyle(Theme.accent)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(Theme.accent.opacity(0.08))
                            .clipShape(Capsule())
                            .overlay(Capsule().stroke(Theme.accent.opacity(0.2), lineWidth: 1))
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 4)
    }

    // MARK: - Input Bar (Voice-First)

    private var inputBar: some View {
        VStack(spacing: 0) {
            // Live transcription while recording
            if chatStore.speechIsRecording {
                HStack(spacing: 8) {
                    Image(systemName: "waveform")
                        .font(.caption)
                        .foregroundStyle(.red)
                        .symbolEffect(.variableColor.iterative)
                    Text(chatStore.speechTranscript.isEmpty ? "正在听..." : chatStore.speechTranscript)
                        .font(.subheadline)
                        .foregroundStyle(Theme.textPrimary)
                        .lineLimit(3)
                    Spacer()
                    Button {
                        toggleRecording()
                    } label: {
                        Image(systemName: "stop.circle.fill")
                            .font(.title2)
                            .foregroundStyle(.red)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(Theme.bgCard.opacity(0.95))
                .transition(.opacity.combined(with: .move(edge: .bottom)))
            }

            HStack(alignment: .bottom, spacing: 8) {
                // Voice toggle — always available
                if chatStore.speechIsAvailable && !chatStore.speechIsRecording {
                    Button {
                        toggleRecording()
                    } label: {
                        Image(systemName: "mic.fill")
                            .font(.body.bold())
                            .foregroundStyle(Theme.accent)
                            .frame(width: 44, height: 44)
                            .background(Theme.bgInput)
                            .clipShape(Circle())
                    }
                }

                TextField(chatStore.isMirror ? "和自己聊聊..." : "说点什么...", text: $input, axis: .vertical)
                    .lineLimit(1...4)
                    .textFieldStyle(.plain)
                    .padding(12)
                    .background(Theme.bgInput)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                    .foregroundStyle(Theme.textPrimary)
                    .focused($inputFocused)
                    .onSubmit { send() }

                Button(action: send) {
                    Image(systemName: chatStore.sending ? "ellipsis" : "arrow.up")
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
        }
        .background(Theme.bgCard)
    }

    private var canSend: Bool {
        !input.trimmingCharacters(in: .whitespaces).isEmpty && !chatStore.sending
    }

    private func toggleRecording() {
        if chatStore.speechIsRecording {
            chatStore.speech.stopRecording()
            // Transcript transfer happens in .onChange(of: chatStore.speechIsRecording)
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        } else {
            chatStore.speechTranscript = ""
            chatStore.speech.startRecording()
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        }
    }

    private func setupWelcome() {
        showPrompts = true
        chatStore.bondLevel = session.bondLevel
        chatStore.messages = [
            Message(
                role: .ome,
                text: chatStore.isMirror
                    ? "\u{955C}\u{50CF}\u{6A21}\u{5F0F}\u{FF1A}\u{6211}\u{4F1A}\u{7528}\(session.userName)\u{7684}\u{8BED}\u{6C14}\u{8BF4}\u{8BDD}\u{3002}\u{8BD5}\u{8BD5}\u{770B}\u{FF1F}"
                    : GreetingManager.greeting(for: session.userName, streak: chatStore.streakDays, bondLevel: chatStore.bondLevel)
            )
        ]
        chatStore.welcomeConfigured = true
    }

    private func loadProfile() {
        Task {
            do {
                let profile = try await api.getProfile()
                chatStore.bondLevel = profile.bond.level
                chatStore.streakDays = profile.streak.current
                chatStore.currentMoodEmoji = profile.emotion.mood_emoji
                chatStore.currentMood = profile.emotion.mood
                session.updateBondLevel(profile.bond.level)
            } catch {}
        }
        // Load LLM-generated prompts (fire-and-forget, fallback to local)
        Task {
            if let prompts = try? await api.generatePrompts(), !prompts.isEmpty {
                serverPrompts = prompts
            }
        }
        // Load LLM-generated greeting to replace local fallback
        Task {
            if let greeting = try? await api.getGreeting(), !greeting.isEmpty,
               let first = chatStore.messages.first, first.role == .ome, chatStore.messages.count == 1 {
                chatStore.messages[0] = Message(role: .ome, text: greeting)
            }
        }
    }

    private func send() {
        let text = input.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !chatStore.sending else { return }

        withAnimation {
            showPrompts = false
            replyChips = []
        }
        lastUserMsg = text
        chatStore.messages.append(Message(role: .user, text: text))
        input = ""
        chatStore.sending = true
        UIImpactFeedbackGenerator(style: .light).impactOccurred()

        if chatStore.isMirror {
            sendMirror(text)
        } else {
            sendStream(text)
        }
    }

    private func sendStream(_ text: String) {
        let streamMsg = Message(role: .ome, text: "", isStreaming: true)
        let streamId = streamMsg.id
        chatStore.messages.append(streamMsg)

        func updateMsg(_ update: (inout Message) -> Void) {
            if let idx = chatStore.messages.firstIndex(where: { $0.id == streamId }) {
                update(&chatStore.messages[idx])
            }
        }

        func applyMeta(bondLevel: Int?, streakDays: Int?, mood: String?, moodEmoji: String?,
                        levelUp: LevelUpEvent?, achievements: [AchievementEvent]?, challenge: DailyChallenge?) {
            if let level = bondLevel {
                chatStore.bondLevel = level
                session.updateBondLevel(level)
            }
            if let streak = streakDays { chatStore.streakDays = streak }
            if let mood = mood {
                withAnimation(.easeInOut(duration: 0.5)) { chatStore.currentMood = mood }
            }
            if let emoji = moodEmoji { chatStore.currentMoodEmoji = emoji }
            showBondGain()
            handleGameEvents(levelUp: levelUp, achievements: achievements, challenge: challenge)
        }

        Task {
            var accumulated = ""
            var gameEventsHandled = false
            do {
                // 30s timeout on entire stream
                try await withThrowingTaskGroup(of: Void.self) { group in
                    group.addTask {
                        try await Task.sleep(for: .seconds(30))
                        throw CancellationError()
                    }
                    group.addTask {
                        for try await token in self.api.chatStream(text) {
                            if let t = token.token {
                                accumulated += t
                                await MainActor.run { updateMsg { $0.text = accumulated } }
                            }
                            if token.done == true {
                                let serverChips = token.suggested_follow_ups ?? []
                                await MainActor.run {
                                    updateMsg {
                                        $0.text = token.full_reply ?? accumulated
                                        $0.isStreaming = false
                                        $0.moodEmoji = token.mood_emoji
                                    }
                                    applyMeta(bondLevel: token.bond_level, streakDays: token.streak_days,
                                              mood: token.mood, moodEmoji: token.mood_emoji,
                                              levelUp: token.level_up, achievements: token.achievements,
                                              challenge: token.daily_challenge)
                                    gameEventsHandled = true
                                    // Use LLM-generated follow-ups
                                    if !serverChips.isEmpty {
                                        withAnimation(.easeInOut(duration: 0.3)) {
                                            replyChips = Array(serverChips.prefix(3))
                                        }
                                    }
                                }
                            }
                        }
                    }
                    // First to finish cancels the other
                    try await group.next()
                    group.cancelAll()
                }
            } catch {
                // Streaming failed — fallback to non-streaming only if we haven't handled events
                if !gameEventsHandled {
                    do {
                        let result = try await api.chat(text)
                        updateMsg {
                            $0.text = result.reply
                            $0.isStreaming = false
                            $0.moodEmoji = result.mood_emoji
                        }
                        applyMeta(bondLevel: result.bond_level, streakDays: result.streak_days,
                                  mood: result.mood, moodEmoji: result.mood_emoji,
                                  levelUp: result.level_up, achievements: result.achievements,
                                  challenge: result.daily_challenge)
                    } catch let fallbackError {
                        updateMsg {
                            $0.text = friendlyError(fallbackError)
                            $0.isStreaming = false
                        }
                        if let apiErr = fallbackError as? APIError, case .unauthorized = apiErr {
                            await session.logout()
                        }
                    }
                }
            }
            // Safety: ensure streaming flag is cleared
            updateMsg { msg in
                if msg.isStreaming { msg.isStreaming = false }
            }
            chatStore.sending = false
            // Track last Ome reply; chips already set from stream if available
            if let lastReply = chatStore.messages.last?.text, chatStore.messages.last?.role == .ome {
                lastOmeReply = lastReply
                // Fallback: if stream didn't provide chips, use local heuristic
                if replyChips.isEmpty {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        replyChips = PromptManager.followUpChips(for: lastReply)
                    }
                }
            }
        }
    }

    private func sendMirror(_ text: String) {
        Task {
            do {
                let result = try await api.mirror(text)
                chatStore.messages.append(Message(role: .ome, text: result.reply))
            } catch {
                chatStore.messages.append(Message(role: .ome, text: friendlyError(error)))
            }
            chatStore.sending = false
        }
    }

    // MARK: - Bond Pulse

    private func showBondGain() {
        let phrases = ["\u{4EB2}\u{5BC6}\u{5EA6} +1", "\u{4E86}\u{89E3}\u{52A0}\u{6DF1}\u{4E2D}...", "\u{5FC3}\u{66F4}\u{8FD1}\u{4E86}\u{4E00}\u{70B9}"]
        chatStore.bondPulseText = phrases[chatStore.messageCount % phrases.count]
        withAnimation(.spring(response: 0.3)) { chatStore.showBondPulse = true }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.8) {
            withAnimation(.easeOut(duration: 0.4)) { chatStore.showBondPulse = false }
        }
    }

    // MARK: - Daily Challenge Banner

    private func dailyChallengeBanner(_ challenge: DailyChallenge) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "star.circle.fill")
                .foregroundStyle(Theme.accent)
                .font(.caption)
            Text(challenge.text)
                .font(.caption)
                .foregroundStyle(Theme.textSecondary)
            Spacer()
            Text("\(challenge.progress)/\(challenge.target)")
                .font(.caption.bold().monospacedDigit())
                .foregroundStyle(Theme.accent)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Theme.accent.opacity(0.08))
    }

    // MARK: - Gamification Events

    private func handleGameEvents(levelUp: LevelUpEvent?, achievements: [AchievementEvent]?, challenge: DailyChallenge?) {
        if let lu = levelUp {
            levelUpInfo = lu
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                showLevelUp = true
            }
        }
        if let achs = achievements, let first = achs.first {
            achievementInfo = first
            withAnimation(.spring(response: 0.4)) { showAchievement = true }
        }
        if let c = challenge {
            dailyChallenge = c
        }

        chatStore.messageCount += 1
        let milestones = [10, 25, 50, 100]
        if milestones.contains(chatStore.messageCount) && !soulCardLoading {
            let hints = [
                "\u{6211}\u{597D}\u{50CF}\u{8D8A}\u{6765}\u{8D8A}\u{61C2}\u{4F60}\u{4E86}... \u{60F3}\u{770B}\u{770B}\u{6211}\u{773C}\u{4E2D}\u{7684}\u{4F60}\u{5417}\u{FF1F}",
                "\u{6211}\u{5BF9}\u{4F60}\u{7684}\u{4E86}\u{89E3}\u{53C8}\u{52A0}\u{6DF1}\u{4E86}\u{3002}\u{8981}\u{770B}\u{770B}\u{4F60}\u{7684}\u{7075}\u{9B42}\u{5361}\u{7247}\u{5417}\u{FF1F}",
                "\u{4F60}\u{77E5}\u{9053}\u{5417}\u{FF0C}\u{6211}\u{5DF2}\u{7ECF}\u{8BB0}\u{4F4F}\u{4E86}\u{597D}\u{591A}\u{5173}\u{4E8E}\u{4F60}\u{7684}\u{4E8B}... \u{60F3}\u{770B}\u{770B}\u{FF1F}",
            ]
            let hint = hints[chatStore.messageCount % hints.count]
            let soulMsg = Message(role: .ome, text: "\u{2728} \(hint) [\u{70B9}\u{6211}\u{67E5}\u{770B}\u{7075}\u{9B42}\u{5361}\u{7247}]")
            chatStore.messages.append(soulMsg)
        }
    }

    // MARK: - Soul Card

    private var soulCardSheet: some View {
        Group {
            if let img = soulCardImage {
                VStack(spacing: 20) {
                    Text("\u{4F60}\u{7684}\u{7075}\u{9B42}\u{5361}\u{7247}").font(.headline).foregroundStyle(Theme.textPrimary)
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
                            Text("\u{5206}\u{4EAB}\u{5230}\u{670B}\u{53CB}\u{5708}")
                        }
                        .font(.headline)
                        .foregroundStyle(Theme.bg)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Theme.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                    }
                    .padding(.horizontal, 30)
                    Button("\u{5173}\u{95ED}") { showSoulCard = false }
                        .foregroundStyle(Theme.textMuted)
                }
                .padding(.vertical, 30)
                .background(Theme.bg)
            }
        }
    }

    private func loadSoulCard() {
        guard !soulCardLoading else { return }
        soulCardLoading = true
        Task {
            do {
                let data = try await api.getSoulCardImage()
                if let image = UIImage(data: data) {
                    soulCardImage = image
                    showSoulCard = true
                }
            } catch {
                chatStore.messages.append(Message(role: .ome, text: "\u{7075}\u{9B42}\u{5361}\u{7247}\u{751F}\u{6210}\u{4E2D}\u{FF0C}\u{518D}\u{804A}\u{51E0}\u{8F6E}\u{5C31}\u{597D}~"))
            }
            soulCardLoading = false
        }
    }

    private func shareSoulCard(_ image: UIImage) {
        let av = UIActivityViewController(
            activityItems: [image, "\u{6211}\u{7684}AI\u{5206}\u{8EAB}\u{8FD9}\u{6837}\u{770B}\u{6211} \u{2726} #OmeAI\u{5206}\u{8EAB}"],
            applicationActivities: nil
        )
        if let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let root = scene.windows.first?.rootViewController {
            root.present(av, animated: true)
        }
    }

    // MARK: - Achievement Toast

    private func achievementToast(_ ach: AchievementEvent) -> some View {
        VStack {
            HStack(spacing: 10) {
                Text(ach.icon ?? "\u{1F3C6}")
                    .font(.title)
                VStack(alignment: .leading, spacing: 2) {
                    Text("\u{6210}\u{5C31}\u{89E3}\u{9501}")
                        .font(.caption.bold())
                        .foregroundStyle(Theme.accent)
                    Text(ach.name)
                        .font(.headline.bold())
                        .foregroundStyle(Theme.textPrimary)
                }
            }
            .padding()
            .background(.ultraThinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .shadow(color: Theme.accent.opacity(0.3), radius: 12)
            .transition(.move(edge: .top).combined(with: .opacity))
            Spacer()
        }
        .padding(.top, 60)
        .onAppear {
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                withAnimation { showAchievement = false }
            }
        }
    }

    // MARK: - Guess Who Game

    private var guessGameSheet: some View {
        VStack(spacing: 20) {
            Text("🎭 猜猜谁")
                .font(.title2.bold())
                .foregroundStyle(Theme.textPrimary)

            Text("让朋友猜哪个回答是你、哪个是 AI")
                .font(.subheadline)
                .foregroundStyle(Theme.textSecondary)
                .multilineTextAlignment(.center)

            if let userMsg = lastUserMsg, let omeReply = lastOmeReply {
                VStack(alignment: .leading, spacing: 12) {
                    Text("问题：\(userMsg)")
                        .font(.caption.bold())
                        .foregroundStyle(Theme.textSecondary)
                    HStack(spacing: 4) {
                        Circle().fill(Theme.accent).frame(width: 6, height: 6)
                        Text("你的回答将由 Ome 以你的口气生成")
                            .font(.caption)
                            .foregroundStyle(Theme.textMuted)
                    }
                    HStack(spacing: 4) {
                        Circle().fill(Theme.bondGreen).frame(width: 6, height: 6)
                        Text("Ome 的回答：\(omeReply.prefix(60))...")
                            .font(.caption)
                            .foregroundStyle(Theme.textMuted)
                            .lineLimit(2)
                    }
                }
                .padding()
                .background(Theme.bgInput)
                .clipShape(RoundedRectangle(cornerRadius: 12))

                Button {
                    createGuessGame(question: userMsg, omeReply: omeReply)
                } label: {
                    HStack {
                        if guessGameCreating {
                            ProgressView().tint(Theme.bg).scaleEffect(0.8)
                        }
                        Text(guessGameCreating ? "生成中..." : "生成挑战链接")
                            .font(.headline.bold())
                    }
                    .foregroundStyle(Theme.bg)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Theme.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                }
                .disabled(guessGameCreating)
                .padding(.horizontal)
            } else {
                Text("先和 Ome 聊一轮，就能创建挑战")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
            }

            Button("关闭") { showGuessGame = false }
                .foregroundStyle(Theme.textMuted)
        }
        .padding(24)
        .background(Theme.bg)
    }

    private func createGuessGame(question: String, omeReply: String) {
        guessGameCreating = true
        Task {
            do {
                // First get mirror response (user's voice)
                let mirrorResult = try await api.mirror(question)
                let userVoiceAnswer = mirrorResult.reply

                // Create the game
                let game = try await api.createGuessGame(
                    question: question,
                    userAnswer: userVoiceAnswer,
                    omeAnswer: omeReply
                )

                showGuessGame = false

                // Share the link
                #if DEBUG
                let baseURL = "http://192.168.3.242:8765"
                #else
                let baseURL = "https://api.ome.ai"
                #endif
                let shareURL = game.share_url ?? "\(baseURL)/api/viral/guess-game/\(game.game_id)"
                let shareText = "🎭 猜猜哪个是我说的，哪个是AI说的？\n\(shareURL)"

                let av = UIActivityViewController(activityItems: [shareText], applicationActivities: nil)
                if let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
                   let root = scene.windows.first?.rootViewController {
                    root.present(av, animated: true)
                }
                UINotificationFeedbackGenerator().notificationOccurred(.success)
            } catch {
                UINotificationFeedbackGenerator().notificationOccurred(.error)
            }
            guessGameCreating = false
        }
    }

    private func friendlyError(_ error: Error) -> String {
        if let apiErr = error as? APIError {
            switch apiErr {
            case .network: return "\u{4FE1}\u{53F7}\u{4E0D}\u{592A}\u{597D}\u{FF0C}\u{68C0}\u{67E5}\u{4E00}\u{4E0B}\u{7F51}\u{7EDC}\u{FF1F}"
            case .unauthorized: return "\u{9700}\u{8981}\u{91CD}\u{65B0}\u{767B}\u{5F55}\u{4E00}\u{4E0B}"
            case .serverError: return "\u{670D}\u{52A1}\u{5668}\u{5F00}\u{5C0F}\u{5DEE}\u{4E86}\u{FF0C}\u{7A0D}\u{540E}\u{518D}\u{8BD5}"
            case .invalidURL: return "\u{51FA}\u{4E86}\u{70B9}\u{95EE}\u{9898}\u{FF0C}\u{7A0D}\u{540E}\u{518D}\u{8BD5}"
            }
        }
        return "\u{4FE1}\u{53F7}\u{4E0D}\u{592A}\u{597D}\u{FF0C}\u{7A0D}\u{540E}\u{518D}\u{8BD5}"
    }
}
