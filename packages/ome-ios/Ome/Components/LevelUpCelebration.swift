import SwiftUI

/// Full-screen overlay when bond level increases.
struct LevelUpCelebration: View {
    let level: Int
    let stageName: String
    let stageDesc: String
    var onDismiss: () -> Void

    @State private var show = false
    @State private var orbScale: CGFloat = 0.3
    @State private var textOpacity: Double = 0

    private let unlockDescriptions = [
        1: "记忆宫殿已开启",
        2: "成长系统已开启",
        3: "广场已开启",
    ]

    var body: some View {
        ZStack {
            // Dimmed background
            Color.black.opacity(show ? 0.7 : 0)
                .ignoresSafeArea()
                .onTapGesture { dismiss() }

            VStack(spacing: 20) {
                // Burst particles
                ParticleField(count: 12, color: Theme.accent, opacity: 0.6)
                    .frame(width: 200, height: 200)
                    .overlay {
                        OmeOrb(size: 80, intensity: 1.0)
                            .scaleEffect(orbScale)
                    }

                VStack(spacing: 8) {
                    Text("Lv.\(level)")
                        .font(.system(size: 36, weight: .bold, design: .rounded))
                        .foregroundStyle(Theme.accent)

                    Text(stageName)
                        .font(.title2.bold())
                        .foregroundStyle(Theme.textPrimary)

                    Text(stageDesc)
                        .font(.body)
                        .foregroundStyle(Theme.textSecondary)

                    if let unlock = unlockDescriptions[level] {
                        Text(unlock)
                            .font(.caption)
                            .foregroundStyle(Theme.bondGreen)
                            .padding(.top, 4)
                    }
                }
                .opacity(textOpacity)
            }
        }
        .onAppear {
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            withAnimation(.spring(response: 0.6, dampingFraction: 0.6)) {
                show = true
                orbScale = 1.0
            }
            withAnimation(.easeIn(duration: 0.5).delay(0.4)) {
                textOpacity = 1
            }
            // Auto-dismiss after 3.5 seconds
            DispatchQueue.main.asyncAfter(deadline: .now() + 3.5) {
                dismiss()
            }
        }
    }

    private func dismiss() {
        withAnimation(.easeOut(duration: 0.3)) {
            show = false
            orbScale = 0.3
            textOpacity = 0
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            onDismiss()
        }
    }
}
