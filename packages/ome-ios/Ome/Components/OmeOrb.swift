import SwiftUI

/// The breathing soul-light of Ome — a pulsing orb that grows with bond.
struct OmeOrb: View {
    var size: CGFloat = 80
    var intensity: CGFloat = 0.5   // 0→dormant  1→fully awake
    var breathing: Bool = true

    @State private var phase: CGFloat = 0

    private var coreColor: Color { Theme.accent }
    private var glowRadius: CGFloat { size * 0.6 * intensity }

    var body: some View {
        ZStack {
            // Outer pulse ring
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            coreColor.opacity(0.15 * intensity),
                            coreColor.opacity(0.05 * intensity),
                            .clear,
                        ],
                        center: .center,
                        startRadius: size * 0.4,
                        endRadius: size * 1.2
                    )
                )
                .frame(width: size * 2.4, height: size * 2.4)
                .scaleEffect(breathing ? 1.0 + phase * 0.12 : 1.0)

            // Mid glow
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            coreColor.opacity(0.35 * intensity),
                            coreColor.opacity(0.1 * intensity),
                            .clear,
                        ],
                        center: .center,
                        startRadius: size * 0.1,
                        endRadius: size * 0.7
                    )
                )
                .frame(width: size * 1.4, height: size * 1.4)
                .scaleEffect(breathing ? 1.0 + phase * 0.08 : 1.0)

            // Core
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            .white.opacity(0.6 * intensity),
                            coreColor,
                            coreColor.opacity(0.7),
                            Color(hex: "1a0e00").opacity(0.8),
                        ],
                        center: .center,
                        startRadius: 0,
                        endRadius: size * 0.5
                    )
                )
                .frame(width: size, height: size)
                .scaleEffect(breathing ? 1.0 + phase * 0.05 : 1.0)
                .shadow(color: coreColor.opacity(0.5 * intensity), radius: glowRadius)

            // Inner spark
            Circle()
                .fill(.white.opacity(0.5 * intensity))
                .frame(width: size * 0.18, height: size * 0.18)
                .blur(radius: 3)
                .scaleEffect(breathing ? 1.0 + phase * 0.15 : 1.0)
        }
        .onAppear {
            guard breathing else { return }
            withAnimation(
                .easeInOut(duration: 3.0)
                .repeatForever(autoreverses: true)
            ) {
                phase = 1.0
            }
        }
    }
}

/// Mini orb for chat bubbles & headers
struct OmeOrbMini: View {
    var size: CGFloat = 28

    var body: some View {
        ZStack {
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            .white.opacity(0.4),
                            Theme.accent,
                            Theme.accent.opacity(0.6),
                        ],
                        center: .center,
                        startRadius: 0,
                        endRadius: size * 0.5
                    )
                )
                .frame(width: size, height: size)

            Circle()
                .fill(.white.opacity(0.35))
                .frame(width: size * 0.3, height: size * 0.3)
                .blur(radius: 1.5)
                .offset(x: -size * 0.08, y: -size * 0.08)
        }
        .shadow(color: Theme.accent.opacity(0.3), radius: 4)
    }
}
