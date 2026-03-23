import SwiftUI

/// Chat message bubble — user on right (gold), Ome on left (card bg).
struct MessageBubble: View {
    let message: Message

    private var isUser: Bool { message.role == .user }

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if isUser { Spacer(minLength: 60) }

            if !isUser, let emoji = message.moodEmoji {
                Text(emoji)
                    .font(.title3)
            }

            Text(message.text + (message.isStreaming ? "▌" : ""))
                .font(.body)
                .foregroundStyle(isUser ? Theme.bg : Theme.textPrimary)
                .lineSpacing(4)
                .padding(12)
                .background(isUser ? Theme.accent : Theme.bgCard)
                .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.cornerRadius)
                        .stroke(isUser ? Color.clear : Theme.border, lineWidth: 1)
                )

            if !isUser { Spacer(minLength: 60) }
        }
    }
}
