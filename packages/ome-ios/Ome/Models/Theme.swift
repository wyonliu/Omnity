import SwiftUI

/// 神临山海 design system — 安静而活 (quiet but alive)
enum Theme {
    // Backgrounds
    static let bg = Color(hex: "0a1628")
    static let bgCard = Color(hex: "111d33")
    static let bgInput = Color(hex: "1a2a44")

    // Text
    static let textPrimary = Color(hex: "f0f4f8")
    static let textSecondary = Color(hex: "8a9bb5")
    static let textMuted = Color(hex: "4a5d78")

    // Accents
    static let accent = Color(hex: "c8a96e")       // Warm gold
    static let accentLight = Color(hex: "e8d5a8")
    static let accentDark = Color(hex: "8a6e3a")

    // Life system
    static let bondGreen = Color(hex: "4ade80")
    static let streakOrange = Color(hex: "fb923c")
    static let achieveGold = Color(hex: "fbbf24")
    static let emotionPurple = Color(hex: "a78bfa")

    // Functional
    static let error = Color(hex: "ef4444")
    static let success = Color(hex: "22c55e")
    static let border = Color(hex: "1e3050")

    // Sizing
    static let cornerRadius: CGFloat = 16
    static let cornerRadiusSm: CGFloat = 8
    static let cornerRadiusXl: CGFloat = 24
}

extension Color {
    init(hex: String) {
        let scanner = Scanner(string: hex)
        var rgb: UInt64 = 0
        scanner.scanHexInt64(&rgb)
        self.init(
            red: Double((rgb >> 16) & 0xFF) / 255,
            green: Double((rgb >> 8) & 0xFF) / 255,
            blue: Double(rgb & 0xFF) / 255
        )
    }
}
