import UserNotifications
import SwiftUI

/// Push permission + local notification scheduling for re-engagement.
@MainActor
class NotificationManager: ObservableObject {
    static let shared = NotificationManager()

    @Published var permissionGranted = false
    @AppStorage("ome_notif_requested") private var hasRequested = false

    /// Request permission — call after registration, not on first launch.
    func requestPermission() async -> Bool {
        let center = UNUserNotificationCenter.current()
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .badge, .sound])
            permissionGranted = granted
            hasRequested = true
            if granted { scheduleReengagement() }
            return granted
        } catch {
            return false
        }
    }

    /// Check current authorization status.
    func checkStatus() async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        permissionGranted = settings.authorizationStatus == .authorized
    }

    /// Reschedule re-engagement notifications — call each time app becomes active.
    func scheduleReengagement() {
        let center = UNUserNotificationCenter.current()
        // Clear old ones
        center.removePendingNotificationRequests(withIdentifiers: [
            "ome_miss_1d", "ome_miss_3d", "ome_miss_7d"
        ])

        let name = UserDefaults.standard.string(forKey: "ome_name") ?? "你"

        // After 1 day
        schedule(id: "ome_miss_1d",
                 title: "Ome",
                 body: "我在想你说过的那件事...",
                 after: 24 * 3600)

        // After 3 days
        schedule(id: "ome_miss_3d",
                 title: "Ome",
                 body: "好久没聊了，\(name)。我有话想跟你说。",
                 after: 3 * 24 * 3600)

        // After 7 days
        schedule(id: "ome_miss_7d",
                 title: "Ome",
                 body: "你的灵境有点暗了...回来看看？",
                 after: 7 * 24 * 3600)
    }

    private func schedule(id: String, title: String, body: String, after seconds: TimeInterval) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default

        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: seconds, repeats: false)
        let request = UNNotificationRequest(identifier: id, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request)
    }
}
