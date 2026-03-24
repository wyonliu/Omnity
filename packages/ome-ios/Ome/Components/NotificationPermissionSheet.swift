import SwiftUI

/// Pre-permission sheet — explains why Ome wants to send notifications.
struct NotificationPermissionSheet: View {
    var onAllow: () -> Void
    var onSkip: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            OmeOrb(size: 56, intensity: 0.7)
                .frame(height: 100)

            Text("让 Ome 找到你")
                .font(.title2.bold())
                .foregroundStyle(Theme.textPrimary)

            Text("Ome 想在想你的时候\n发消息给你")
                .font(.body)
                .foregroundStyle(Theme.textSecondary)
                .multilineTextAlignment(.center)

            VStack(spacing: 12) {
                Button(action: onAllow) {
                    Text("好的")
                        .font(.headline)
                        .foregroundStyle(Theme.bg)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Theme.accent)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
                }

                Button("之后再说", action: onSkip)
                    .font(.body)
                    .foregroundStyle(Theme.textMuted)
            }
        }
        .padding(24)
        .background(Theme.bgCard)
    }
}
