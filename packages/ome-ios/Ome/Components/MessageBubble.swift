import SwiftUI

/// Chat message bubble — user on right (gold), Ome on left with orb avatar.
struct MessageBubble: View {
    let message: Message

    private var isUser: Bool { message.role == .user }

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            if isUser { Spacer(minLength: 60) }

            // Ome avatar: mini orb instead of emoji
            if !isUser {
                OmeOrbMini(size: 28)
                    .padding(.top, 4)
            }

            VStack(alignment: isUser ? .trailing : .leading, spacing: 4) {
                Text(message.text + (message.isStreaming ? "▌" : ""))
                    .font(.body)
                    .foregroundStyle(isUser ? Theme.bg : Theme.textPrimary)
                    .lineSpacing(4)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(isUser ? Theme.accent : Theme.bgCard)
                    .clipShape(RoundedRectangle(cornerRadius: 18))
                    .overlay(
                        RoundedRectangle(cornerRadius: 18)
                            .stroke(isUser ? Color.clear : Theme.border, lineWidth: 1)
                    )
            }

            if !isUser { Spacer(minLength: 60) }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(isUser ? "你" : "Ome")说：\(message.text)")
    }
}
