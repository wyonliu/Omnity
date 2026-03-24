import SwiftUI

/// Personality trait capsule tag.
struct TraitPill: View {
    let trait: String

    private var icon: String {
        switch trait.lowercased() {
        case "curious", "好奇": return "sparkle"
        case "gentle", "温柔": return "leaf"
        case "creative", "创意": return "paintbrush"
        case "analytical", "理性": return "chart.bar"
        case "empathetic", "共情": return "heart"
        case "humorous", "幽默": return "face.smiling"
        case "newborn", "新生": return "sunrise"
        case "wondering", "思索": return "questionmark.circle"
        case "authentic", "真诚": return "checkmark.seal"
        default: return "star"
        }
    }

    private var color: Color {
        switch trait.lowercased() {
        case "curious", "好奇": return Theme.achieveGold
        case "gentle", "温柔": return Theme.bondGreen
        case "creative", "创意": return Theme.emotionPurple
        case "empathetic", "共情": return Color(hex: "f472b6")
        case "humorous", "幽默": return Theme.streakOrange
        default: return Theme.accent
        }
    }

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption2)
            Text(trait)
                .font(.caption)
        }
        .foregroundStyle(color)
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(color.opacity(0.12))
        .clipShape(Capsule())
    }
}
