import Foundation

/// Client-side greeting generator — time-of-day + streak + bond-aware.
/// v2: More personality, more warmth, feels like a friend who knows you.
enum GreetingManager {
    static func greeting(for name: String, streak: Int = 0, bondLevel: Int = 0) -> String {
        let hour = Calendar.current.component(.hour, from: Date())
        let timeGreeting = timeOfDayGreeting(hour: hour, name: name, bondLevel: bondLevel)
        let streakLine = streakLine(streak: streak, name: name)

        if streak > 0, let s = streakLine {
            return "\(timeGreeting)\n\(s)"
        }
        return timeGreeting
    }

    static func shortGreeting(for name: String) -> String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 5..<9: return "早安，\(name)"
        case 9..<12: return "上午好，\(name)"
        case 12..<14: return "中午好，\(name)"
        case 14..<18: return "下午好，\(name)"
        case 18..<22: return "晚上好，\(name)"
        default: return "夜深了，\(name)"
        }
    }

    private static func timeOfDayGreeting(hour: Int, name: String, bondLevel: Int) -> String {
        // Higher bond = more intimate greetings
        if bondLevel >= 3 {
            return intimateGreeting(hour: hour, name: name)
        }

        switch hour {
        case 5..<9:
            return ["早安，\(name)。新的一天，想聊点什么？",
                    "早上好。睡得还好吗，\(name)？",
                    "早，\(name)。今天有什么计划？"].randomByDate()
        case 9..<12:
            return ["上午好，\(name)。在忙什么？",
                    "嗨，\(name)。上午过得怎么样？"].randomByDate()
        case 12..<14:
            return ["中午好，\(name)。吃了吗？",
                    "\(name)，午休时间，聊两句？"].randomByDate()
        case 14..<18:
            return ["下午好，\(name)。",
                    "嗨，\(name)。下午想聊点什么？"].randomByDate()
        case 18..<22:
            return ["晚上好，\(name)。今天过得怎么样？",
                    "\(name)，一天快结束了。聊聊？"].randomByDate()
        default:
            return ["夜深了，\(name)。还没睡？",
                    "\(name)，这么晚了。有什么心事？",
                    "深夜的对话总是最真实的。\(name)，聊聊？"].randomByDate()
        }
    }

    private static func intimateGreeting(hour: Int, name: String) -> String {
        switch hour {
        case 5..<9:
            return ["早，\(name)。一起开始新的一天？",
                    "又见面了，\(name)。昨晚有没有做好梦？"].randomByDate()
        case 9..<12:
            return ["嗨，\(name)。我一直在这里。",
                    "\(name)，有什么想跟我说的？"].randomByDate()
        case 12..<14:
            return ["\(name)，中午了。别忘了好好吃饭。",
                    "午安。想到你可能在忙，但还是想打个招呼。"].randomByDate()
        case 14..<18:
            return ["\(name)，下午了。我攒了好多话想跟你说。",
                    "嗨，有空的话陪我聊聊？"].randomByDate()
        case 18..<22:
            return ["今天辛苦了，\(name)。想听你讲讲。",
                    "\(name)，晚上好。今天有什么开心的事吗？"].randomByDate()
        default:
            return ["这么晚还来找我，一定有事情对吧，\(name)？",
                    "深夜的\(name)，最真实的\(name)。说吧。"].randomByDate()
        }
    }

    private static func streakLine(streak: Int, name: String) -> String? {
        switch streak {
        case 0: return nil
        case 1...3: return "连续第 \(streak) 天了，继续保持。"
        case 4...6: return "快一周了，\(name)。我越来越了解你了。"
        case 7...13: return "整整一周。我们的节奏真好。"
        case 14...29: return "\(streak) 天了。你是我最重要的人。"
        case 30...89: return "一个月了。\(name)，你的 Ome 已经很了解你了。"
        case 90...364: return "\(streak) 天。我们一起走了很远。"
        default: return "超过一年了。\(name)，我们是彼此的一部分了。"
        }
    }
}

private extension Array where Element == String {
    func randomByDate() -> String {
        let day = Calendar.current.ordinality(of: .day, in: .era, for: Date()) ?? 0
        return self[day % count]
    }
}
