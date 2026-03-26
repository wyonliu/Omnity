import Foundation

/// Ome Prompt Engine — 对话引导 + 跟进建议。
/// prompts 只是引子，真正的智能由 Ome 后端根据用户记忆、情绪、成长阶段动态生成。
enum PromptManager {

    // MARK: - Daily Prompts (仅作聊天入口引导，不写死对话内容)

    private static let pools: [[String]] = [
        // 日常
        ["今天过得怎么样？", "最近在忙什么？", "今天有什么收获？",
         "最近有没有什么新发现？", "今天心情如何？"],
        // 反思
        ["最近有什么让你纠结的事？", "你觉得最近哪方面在进步？",
         "有没有什么事一直想做但没开始？", "最近什么事最消耗你的精力？",
         "你现在最想改变的一件事是什么？"],
        // 关系
        ["最近和谁聊天最开心？", "有没有想念什么人？",
         "最近有没有遇到让你佩服的人？", "你和家人最近怎么样？",
         "最近有没有一个意外的帮助或温暖？"],
        // 成长
        ["你最近学到了什么新东西？", "如果给今天的自己打个分？",
         "你觉得上周的自己和这周有什么不同？", "你现在最想提升的能力是什么？",
         "你觉得自己最大的优势是什么？"],
        // 想象
        ["如果明天不用工作，你最想干嘛？", "给十年后的自己说一句话？",
         "你最近在想什么有意思的问题？", "如果你的人生是一部电影，现在到哪了？",
         "如果可以和任何人吃一顿饭，你选谁？"],
    ]

    /// Returns 3 daily prompts, stable within a calendar day.
    static func dailyPrompts() -> [String] {
        let day = Calendar.current.ordinality(of: .day, in: .era, for: Date()) ?? 0
        var result: [String] = []
        for (i, pool) in pools.enumerated() {
            if result.count >= 3 { break }
            let pick = pool[(day + i * 7) % pool.count]
            if !result.contains(pick) {
                result.append(pick)
            }
        }
        return result
    }

    /// Featured prompt for SoulscapeView.
    static func featuredPrompt() -> String {
        let day = Calendar.current.ordinality(of: .day, in: .era, for: Date()) ?? 0
        let all = pools.flatMap { $0 }
        return all[day % all.count]
    }

    /// Context-aware follow-up reply chips after Ome responds.
    static func followUpChips(for reply: String) -> [String] {
        let lower = reply.lowercased()
        var chips: [String] = []

        if reply.hasSuffix("？") || reply.hasSuffix("?") {
            chips.append(contentsOf: questionReplies(for: lower))
        }

        if hasKeywords(lower, ["开心", "高兴", "快乐", "好消息", "成长", "进步"]) {
            chips.append("展开说说")
        }
        if hasKeywords(lower, ["累", "压力", "辛苦", "难", "焦虑", "纠结"]) {
            chips.append("确实")
            chips.append("帮我分析一下")
        }
        if hasKeywords(lower, ["记得", "记住", "上次", "之前"]) {
            chips.append("你记得！")
        }
        if hasKeywords(lower, ["建议", "可以", "试试", "方法"]) {
            chips.append("具体怎么做？")
        }
        if hasKeywords(lower, ["目标", "计划", "未来", "想要"]) {
            chips.append("帮我拆解一下")
        }

        if chips.count < 2 {
            let fallbacks = ["继续", "说得对", "深挖一下", "换个角度"]
            let day = Calendar.current.ordinality(of: .day, in: .era, for: Date()) ?? 0
            for (i, f) in fallbacks.enumerated() {
                if chips.count >= 3 { break }
                if !chips.contains(f) {
                    if (day + i) % 2 == 0 || chips.count < 2 {
                        chips.append(f)
                    }
                }
            }
        }

        return Array(chips.prefix(3))
    }

    // MARK: - Helpers

    private static func questionReplies(for text: String) -> [String] {
        if hasKeywords(text, ["怎么样", "怎样", "如何", "进展"]) {
            return ["还在调整", "比预期好"]
        }
        if hasKeywords(text, ["吗", "是不是"]) {
            return ["是的", "不太是"]
        }
        if hasKeywords(text, ["什么", "啥", "哪"]) {
            return ["让我想想..."]
        }
        return ["嗯...", "让我想想"]
    }

    private static func hasKeywords(_ text: String, _ keywords: [String]) -> Bool {
        keywords.contains { text.contains($0) }
    }
}
