import Foundation

/// Daily conversation starters — rotates 3 prompts per day from curated pools.
enum PromptManager {
    private static let pools: [[String]] = [
        // 情感
        ["最近有什么让你开心的事？", "今天有没有觉得累？", "最近有没有想念什么人？",
         "你上一次大笑是什么时候？", "有没有什么小事让你感动？"],
        // 思考
        ["如果明天不用工作，你会做什么？", "你觉得什么是真正的自由？",
         "如果可以回到过去的一天，你选哪天？", "你最近在思考什么问题？",
         "十年后的你会感谢现在的你什么？"],
        // 回忆
        ["小时候最喜欢的地方是哪里？", "你记得第一次感到自豪是什么时候吗？",
         "有没有一首歌能让你瞬间回到某个时刻？", "你小时候的梦想是什么？",
         "你最珍贵的一段友情是怎样的？"],
        // 创意
        ["如果你能设计一个世界，它会是什么样？", "给未来的自己写一句话？",
         "如果 Ome 有身体，你希望它长什么样？", "用一个颜色形容今天的心情？",
         "如果你的生活是一部电影，现在演到哪了？"],
        // 轻松
        ["最近在追什么剧？", "推荐一首你最近在听的歌？",
         "你的理想周末是怎样的？", "最近吃到什么好吃的？",
         "如果突然放假三天，你会去哪？"],
    ]

    /// Returns 3 daily prompts from different categories, stable within a calendar day.
    static func dailyPrompts() -> [String] {
        let day = Calendar.current.ordinality(of: .day, in: .era, for: Date()) ?? 0
        var result: [String] = []
        // Pick 3 categories
        var rng = SeededRNG(seed: UInt64(day))
        let indices = (0..<pools.count).shuffled(using: &rng)
        for i in indices.prefix(3) {
            let pool = pools[i]
            let pick = pool[day % pool.count]
            result.append(pick)
        }
        return result
    }

    /// Single featured prompt for Soulscape "今日话题"
    static func featuredPrompt() -> String {
        let day = Calendar.current.ordinality(of: .day, in: .era, for: Date()) ?? 0
        let all = pools.flatMap { $0 }
        return all[day % all.count]
    }
}

/// Deterministic RNG seeded by date — ensures same prompts for the same day.
private struct SeededRNG: RandomNumberGenerator {
    var state: UInt64

    init(seed: UInt64) {
        state = seed
    }

    mutating func next() -> UInt64 {
        state &+= 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
}
