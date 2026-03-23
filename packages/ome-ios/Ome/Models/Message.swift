import Foundation

struct Message: Identifiable, Equatable {
    let id: UUID
    let role: Role
    var text: String
    var moodEmoji: String?
    var isStreaming: Bool

    enum Role: String {
        case user, ome, system
    }

    init(role: Role, text: String, moodEmoji: String? = nil, isStreaming: Bool = false) {
        self.id = UUID()
        self.role = role
        self.text = text
        self.moodEmoji = moodEmoji
        self.isStreaming = isStreaming
    }
}
