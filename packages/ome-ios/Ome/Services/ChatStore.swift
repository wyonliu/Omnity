import SwiftUI

/// Persistent chat state — survives tab switches and view transitions.
/// Held at app level via @StateObject in OmeApp, passed as @EnvironmentObject.
@MainActor
class ChatStore: ObservableObject {
    @Published var messages: [Message] = []
    @Published var sending = false
    @Published var isMirror = false
    @Published var currentMoodEmoji = "\u{1F319}"
    @Published var currentMood = "neutral"
    @Published var bondLevel = 0
    @Published var streakDays = 0
    @Published var messageCount: Int {
        didSet { UserDefaults.standard.set(messageCount, forKey: "ome_message_count") }
    }
    @Published var showBondPulse = false
    @Published var bondPulseText = ""

    // Speech state — published here, updated via callbacks from SpeechRecognizer
    @Published var speechTranscript = ""
    @Published var speechIsRecording = false
    @Published var speechIsAvailable = false
    private var _speech: SpeechRecognizer?
    private var speechWired = false

    /// Whether the initial welcome has been configured this session
    var welcomeConfigured = false

    /// Lazy speech access — wires callbacks on first use to avoid Swift 5/6 init issues
    var speech: SpeechRecognizer {
        if let s = _speech { return s }
        let s = SpeechRecognizer()
        _speech = s
        wireSpeech(s)
        return s
    }

    init() {
        // Restore persisted message count for soul card milestones
        messageCount = UserDefaults.standard.integer(forKey: "ome_message_count")
    }

    private func wireSpeech(_ s: SpeechRecognizer) {
        guard !speechWired else { return }
        speechWired = true
        s.onStateChange = { [weak self] transcript, isRecording in
            Task { @MainActor [weak self] in
                self?.speechTranscript = transcript
                self?.speechIsRecording = isRecording
            }
        }
        s.onAvailabilityChange = { [weak self] available in
            Task { @MainActor [weak self] in
                self?.speechIsAvailable = available
            }
        }
    }

    /// Transfer messages from awakening chat into the main chat store.
    func transferFromAwakening(_ msgs: [Message]) {
        messages = msgs
        welcomeConfigured = true
    }

    /// Reset all state on logout.
    func clearOnLogout() {
        messages = []
        sending = false
        isMirror = false
        currentMoodEmoji = "\u{1F319}"
        currentMood = "neutral"
        bondLevel = 0
        streakDays = 0
        messageCount = 0
        showBondPulse = false
        bondPulseText = ""
        speechTranscript = ""
        speechIsRecording = false
        welcomeConfigured = false
        _speech?.stopRecording()
    }
}
