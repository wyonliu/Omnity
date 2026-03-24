import Foundation

// MARK: - Auth

struct RegisterRequest: Codable {
    let user_id: String
    let password: String
    let name: String
    var traits: [String]?
    var style: String?
    var session_id: String?
}

struct AuthResponse: Codable {
    let token: String
    let user_id: String
    let name: String
}

// MARK: - Chat

struct ChatRequest: Codable {
    let message: String
}

struct ChatResponse: Codable {
    let reply: String
    let mood: String
    let mood_emoji: String
    let bond_level: Int
    let streak_days: Int
    // Gamification events
    let level_up: LevelUpEvent?
    let achievements: [AchievementEvent]?
    let daily_challenge: DailyChallenge?
}

struct LevelUpEvent: Codable {
    let level: Int
    let name: String
    let unlocks: [String]?
}

struct AchievementEvent: Codable, Identifiable {
    var id: String { name }
    let name: String
    let icon: String?
    let description: String
}

struct DailyChallenge: Codable {
    let id: String
    let text: String
    let progress: Int
    let target: Int
    let completed: Bool
}

struct AnonChatResponse: Codable {
    let reply: String
    let mood: String
    let mood_emoji: String
    let message_count: Int
    let session_id: String
}

struct SessionResponse: Codable {
    let session_id: String
}

// MARK: - SSE Token

struct StreamToken: Codable {
    var token: String?
    var done: Bool?
    var full_reply: String?
    var mood: String?
    var mood_emoji: String?
    var bond_level: Int?
    var streak_days: Int?
    // Gamification events (only in final "done" token)
    var level_up: LevelUpEvent?
    var achievements: [AchievementEvent]?
    var daily_challenge: DailyChallenge?
}

// MARK: - Life

struct ProfileResponse: Codable {
    let name: String
    let traits: [String]
    let bond: BondInfo
    let streak: StreakInfo
    let emotion: EmotionInfo
    let total_memories: Int
    let achievements_count: String
}

struct BondInfo: Codable {
    let level: Int
    let name: String
    let total_interactions: Int?
    let streak_days: Int?
    let next_level: String?
    let interactions_needed: Int?
}

struct StreakInfo: Codable {
    let current: Int
    let max: Int?
}

struct EmotionInfo: Codable {
    let mood: String
    let mood_emoji: String
    let energy: Double?
    let warmth: Double?
}

struct DashboardResponse: Codable {
    let bond: BondInfo
    let achievements: AchievementsInfo
    let highlights: [String]?
    let autonomy: AutonomyInfo?
}

struct AchievementsInfo: Codable {
    let unlocked: [Achievement]?
    let count: String
}

struct Achievement: Codable, Identifiable {
    var id: String { name }
    let name: String
    let icon: String?
    let description: String
}

struct AutonomyInfo: Codable {
    let state: String?
    let level: Int?
    let level_name: String?
    let actions_today: Int?
    let daily_budget: Int?
}

// MARK: - Agents

struct AgentDirectoryResponse: Codable {
    let agents: [AgentInfo]
    let total: Int
}

struct AgentInfo: Codable, Identifiable {
    var id: String { user_id }
    let user_id: String
    let name: String
    let bond_level: Int
    let mood: String
    let mood_emoji: String
}

struct AgentMessageResponse: Codable {
    let my_message: String
    let their_reply: String
    let their_name: String
    let their_mood_emoji: String
}

// MARK: - Soul Card

struct SoulCardResponse: Codable {
    let ready: Bool
    let user_name: String?
    let personality_tags: [String]?
    let style_line: String?
    let quote: String?
    let soul_insight: String?
    let similarity: Int?
    let phase: String?
    let conversation_count: Int?
    let days_together: Int?
    let emotion_signature: [String]?
    let conversations_needed: Int?
}

// MARK: - Memory

struct RecallResponse: Codable {
    let results: [MemoryItem]
    let count: Int
}

struct MemoryItem: Codable, Identifiable {
    var id: String { text.prefix(50) + "\(score ?? 0)" }
    let text: String
    let score: Double?
}
