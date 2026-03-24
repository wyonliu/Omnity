import SwiftUI

/// The breathing soul-light of Ome — a pulsing orb that evolves with bond level.
struct OmeOrb: View {
    var size: CGFloat = 80
    var intensity: CGFloat = 0.5   // 0→dormant  1→fully awake
    var breathing: Bool = true
    var bondLevel: Int = 0          // 0-6, controls visual evolution

    @State private var phase: CGFloat = 0

    private var coreColor: Color {
        switch bondLevel {
        case 0: return Theme.accent
        case 1: return Color(hex: "b8c06e")       // Gold + green tint
        case 2: return Color(hex: "8ec86e")        // More green
        case 3: return Theme.accent                // Back to gold with particles
        case 4: return Color(hex: "b88bfa")        // Purple accent
        case 5: return Color(hex: "d4a6f5")        // Aurora purple-gold
        default: return .white                      // Radiant white
        }
    }

    private var glowColor: Color {
        bondLevel >= 5 ? Color(hex: "a78bfa") : Theme.accent
    }

    private var glowRadius: CGFloat { size * 0.6 * intensity }
    private var breathingSpeed: Double {
        bondLevel >= 2 ? 2.5 : 3.0
    }

    var body: some View {
        ZStack {
            // Outer pulse ring
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            glowColor.opacity(0.15 * intensity),
                            glowColor.opacity(0.05 * intensity),
                            .clear,
                        ],
                        center: .center,
                        startRadius: size * 0.4,
                        endRadius: size * 1.2
                    )
                )
                .frame(width: size * 2.4, height: size * 2.4)
                .scaleEffect(breathing ? 1.0 + phase * 0.12 : 1.0)

            // Aurora outer ring (Lv.5+)
            if bondLevel >= 5 {
                Circle()
                    .fill(
                        AngularGradient(
                            colors: [
                                Theme.accent.opacity(0.2 * intensity),
                                Theme.emotionPurple.opacity(0.15 * intensity),
                                Theme.bondGreen.opacity(0.1 * intensity),
                                Theme.accent.opacity(0.2 * intensity),
                            ],
                            center: .center
                        )
                    )
                    .frame(width: size * 1.8, height: size * 1.8)
                    .rotationEffect(.degrees(phase * 30))
                    .blur(radius: 8)
            }

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
                            .white.opacity(bondLevel >= 6 ? 0.8 * intensity : 0.6 * intensity),
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

            // Orbiting particles (Lv.3+)
            if bondLevel >= 3 {
                ForEach(0..<min(bondLevel - 1, 6), id: \.self) { i in
                    Circle()
                        .fill(coreColor.opacity(0.6 * intensity))
                        .frame(width: 3, height: 3)
                        .blur(radius: 0.5)
                        .offset(x: size * 0.55)
                        .rotationEffect(.degrees(Double(i) * (360 / Double(min(bondLevel - 1, 6))) + phase * 60))
                }
            }
        }
        .onAppear {
            guard breathing else { return }
            withAnimation(
                .easeInOut(duration: breathingSpeed)
                .repeatForever(autoreverses: true)
            ) {
                phase = 1.0
            }
        }
        .accessibilityHidden(true)
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
        .accessibilityHidden(true)
    }
}
