import SwiftUI

/// Soft registration bottom sheet — appears after first few chats.
struct SoftRegisterSheet: View {
    @Binding var name: String
    @Binding var error: String
    @Binding var registering: Bool
    var onRegister: () -> Void
    var onSkip: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Text("🌱")
                .font(.system(size: 48))

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

            if !error.isEmpty {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(Theme.error)
            }

            Button(action: onRegister) {
                Text(registering ? "创建中..." : "记住我")
                    .font(.headline)
                    .foregroundStyle(Theme.bg)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Theme.accent)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
            }
            .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || registering)
            .opacity(name.trimmingCharacters(in: .whitespaces).isEmpty || registering ? 0.5 : 1)

            Button("先不了，继续聊", action: onSkip)
                .font(.body)
                .foregroundStyle(Theme.textMuted)
        }
        .padding(24)
        .background(Theme.bgCard)
    }
}
