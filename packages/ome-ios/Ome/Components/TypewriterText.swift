import SwiftUI

/// Reveals text character-by-character with a cursor.
struct TypewriterText: View {
    let fullText: String
    var speed: TimeInterval = 0.06
    var onComplete: (() -> Void)?

    @State private var displayedCount = 0
    @State private var showCursor = true

    var body: some View {
        HStack(spacing: 0) {
            Text(String(fullText.prefix(displayedCount)))
                .font(.body)
                .foregroundStyle(Theme.textSecondary)
            if displayedCount < fullText.count {
                Text("▌")
                    .font(.body)
                    .foregroundStyle(Theme.accent.opacity(showCursor ? 0.6 : 0))
            }
        }
        .multilineTextAlignment(.center)
        .task {
            for i in 1...fullText.count {
                try? await Task.sleep(for: .milliseconds(Int(speed * 1000)))
                displayedCount = i
            }
            onComplete?()
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.5).repeatForever()) {
                showCursor.toggle()
            }
        }
    }
}
