import SwiftUI

/// Chat message bubble — user on right (gold), Ome on left with orb avatar + mood.
struct MessageBubble: View {
    let message: Message

    private var isUser: Bool { message.role == .user }

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            if isUser { Spacer(minLength: 60) }

            // Ome avatar: mini orb
            if !isUser {
                OmeOrbMini(size: 28)
                    .padding(.top, 4)
            }

            VStack(alignment: isUser ? .trailing : .leading, spacing: 4) {
                Text(message.text + (message.isStreaming ? "\u{258C}" : ""))
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

                // Mood emoji for Ome messages
                if !isUser, let emoji = message.moodEmoji, !emoji.isEmpty {
                    Text(emoji)
                        .font(.system(size: 11))
                        .padding(.leading, 8)
                }
            }

            if !isUser { Spacer(minLength: 60) }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(isUser ? "你" : "Ome")说：\(message.text)")
    }
}
