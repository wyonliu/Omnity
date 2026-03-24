import SwiftUI

/// Ambient floating particles — gold dots drifting upward behind the orb.
struct ParticleField: View {
    var count: Int = 6
    var color: Color = Theme.accent
    var opacity: Double = 0.4

    @State private var particles: [Particle] = []
    @State private var animating = false

    struct Particle: Identifiable {
        let id = UUID()
        var x: CGFloat
        var y: CGFloat
        var size: CGFloat
        var speed: CGFloat
        var delay: CGFloat
    }

    var body: some View {
        GeometryReader { geo in
            ZStack {
                ForEach(particles) { p in
                    Circle()
                        .fill(color.opacity(opacity))
                        .frame(width: p.size, height: p.size)
                        .blur(radius: 1)
                        .position(
                            x: p.x * geo.size.width,
                            y: animating
                                ? -p.size
                                : p.y * geo.size.height
                        )
                        .animation(
                            .easeInOut(duration: Double(p.speed))
                            .repeatForever(autoreverses: false)
                            .delay(Double(p.delay)),
                            value: animating
                        )
                }
            }
            .onAppear {
                particles = (0..<count).map { _ in
                    Particle(
                        x: CGFloat.random(in: 0.1...0.9),
                        y: CGFloat.random(in: 0.3...1.0),
                        size: CGFloat.random(in: 2...5),
                        speed: CGFloat.random(in: 4...8),
                        delay: CGFloat.random(in: 0...3)
                    )
                }
                animating = true
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}
