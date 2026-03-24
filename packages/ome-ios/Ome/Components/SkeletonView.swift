import SwiftUI

/// Shimmer loading placeholder — replaces plain ProgressView spinners.
struct SkeletonRect: View {
    var width: CGFloat? = nil
    var height: CGFloat = 16
    var cornerRadius: CGFloat = 8

    @State private var shimmerOffset: CGFloat = -1

    var body: some View {
        RoundedRectangle(cornerRadius: cornerRadius)
            .fill(Theme.bgCard)
            .frame(width: width, height: height)
            .overlay(
                GeometryReader { geo in
                    RoundedRectangle(cornerRadius: cornerRadius)
                        .fill(
                            LinearGradient(
                                colors: [.clear, Theme.bgInput.opacity(0.5), .clear],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .offset(x: shimmerOffset * geo.size.width)
                }
                .clipped()
            )
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            .onAppear {
                withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: false)) {
                    shimmerOffset = 2
                }
            }
    }
}

/// Pre-built skeleton layouts for common views.
struct SkeletonCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            SkeletonRect(width: 120, height: 14)
            SkeletonRect(height: 12)
            SkeletonRect(width: 180, height: 12)
        }
        .padding()
        .background(Theme.bgCard)
        .clipShape(RoundedRectangle(cornerRadius: Theme.cornerRadius))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.cornerRadius)
                .stroke(Theme.border, lineWidth: 1)
        )
    }
}

struct SkeletonStatRow: View {
    var body: some View {
        HStack(spacing: 8) {
            ForEach(0..<4, id: \.self) { _ in
                VStack(spacing: 6) {
                    SkeletonRect(width: 40, height: 18)
                    SkeletonRect(width: 30, height: 10)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(Theme.bgCard)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Theme.border, lineWidth: 1)
                )
            }
        }
    }
}
