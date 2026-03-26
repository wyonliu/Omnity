import Foundation
import Speech
import AVFoundation

/// Real-time speech-to-text using Apple's on-device Speech framework.
/// NOT an ObservableObject — state is reported via callbacks to avoid
/// Swift 6 concurrency crashes on physical devices.
final class SpeechRecognizer: @unchecked Sendable {
    /// Called on main thread when transcript or recording state changes.
    var onStateChange: ((String, Bool) -> Void)?
    /// Called on main thread when availability changes.
    var onAvailabilityChange: ((Bool) -> Void)?

    private var audioEngine: AVAudioEngine?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var speechRecognizer: SFSpeechRecognizer?
    private var currentTranscript = ""

    init() {}

    func requestPermission() {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "zh-Hans"))
            let available = self.speechRecognizer?.isAvailable ?? false
            self.onAvailabilityChange?(available)

            SFSpeechRecognizer.requestAuthorization { status in
                DispatchQueue.main.async {
                    self.onAvailabilityChange?(status == .authorized)
                }
            }
            AVAudioApplication.requestRecordPermission { _ in }
        }
    }

    func startRecording() {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            guard let recognizer = self.speechRecognizer, recognizer.isAvailable else {
                self.onAvailabilityChange?(false)
                return
            }

            self.stopRecordingInternal()

            let engine = AVAudioEngine()
            self.audioEngine = engine

            let audioSession = AVAudioSession.sharedInstance()
            do {
                try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
                try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
            } catch {
                self.onAvailabilityChange?(false)
                return
            }

            let request = SFSpeechAudioBufferRecognitionRequest()
            request.shouldReportPartialResults = true
            request.addsPunctuation = true
            self.recognitionRequest = request

            let inputNode = engine.inputNode
            let recordingFormat = inputNode.outputFormat(forBus: 0)

            guard recordingFormat.sampleRate > 0, recordingFormat.channelCount > 0 else {
                self.onAvailabilityChange?(false)
                return
            }

            inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
                request.append(buffer)
            }

            self.recognitionTask = recognizer.recognitionTask(with: request) { [weak self] taskResult, error in
                let text = taskResult?.bestTranscription.formattedString ?? ""
                let isFinal = error != nil || (taskResult?.isFinal ?? false)
                DispatchQueue.main.async {
                    guard let self else { return }
                    self.currentTranscript = text
                    if isFinal {
                        self.stopRecordingInternal()
                        self.onStateChange?(text, false)
                    } else {
                        self.onStateChange?(text, true)
                    }
                }
            }

            do {
                engine.prepare()
                try engine.start()
                self.currentTranscript = ""
                self.onStateChange?("", true)
            } catch {
                self.stopRecordingInternal()
                self.onStateChange?("", false)
            }
        }
    }

    func stopRecording() {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            let transcript = self.currentTranscript
            self.stopRecordingInternal()
            self.onStateChange?(transcript, false)
        }
    }

    private func stopRecordingInternal() {
        recognitionRequest?.endAudio()
        recognitionRequest = nil
        recognitionTask?.cancel()
        recognitionTask = nil
        if let engine = audioEngine, engine.isRunning {
            engine.stop()
            engine.inputNode.removeTap(onBus: 0)
        }
        audioEngine = nil
        // Restore audio session for other uses
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
}
