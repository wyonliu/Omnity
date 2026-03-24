import SwiftUI

/// Soft registration bottom sheet — appears after first few chats.
struct SoftRegisterSheet: View {
    @Binding var name: String
    @Binding var error: String
    @Binding var registering: Bool
    var onRegister: () -> Void
    var onSkip: () -> Void

    @FocusState private var nameFocused: Bool

    var body: some View {
        VStack(spacing: 20) {
            OmeOrb(size: 48, intensity: 0.6, breathing: true)
                .frame(height: 80)

            Text("让我记住你")
                .font(.title2.bold())
                .foregroundStyle(Theme.textPrimary)

            Text("给自己起个名字，之前聊的我都会记住")
                .font(.body)
                .foregroundStyle(Theme.textSecondary)
                .multilineTextAlignment(.center)

            TextField("你的名字", text: $name)
                .textFieldStyle(.plain)
                .padding()
                .background(Theme.bgInput)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .foregroundStyle(Theme.textPrimary)
                .multilineTextAlignment(.center)
                .font(.title3)
                .focused($nameFocused)
                .onSubmit(onRegister)

            if !error.isEmpty {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(Theme.error)
                    .transition(.opacity)
            }

            Button(action: onRegister) {
                HStack(spacing: 8) {
                    if registering {
                        ProgressView()
                            .tint(Theme.bg)
                            .scaleEffect(0.8)
                    }
                    Text(registering ? "创建中..." : "记住我")
                        .font(.headline)
                }
                .foregroundStyle(Theme.bg)
                .frame(maxWidth: .infinity)
                .padding()
                .background(canRegister ? Theme.accent : Theme.accent.opacity(0.4))
                .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
            }
            .disabled(!canRegister)
            .animation(.easeInOut(duration: 0.15), value: canRegister)

            Button("先不了，继续聊", action: onSkip)
                .font(.body)
                .foregroundStyle(Theme.textMuted)
        }
        .padding(24)
        .background(Theme.bgCard)
        .onAppear { nameFocused = true }
    }

    private var canRegister: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty && !registering
    }
}
