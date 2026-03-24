import SwiftUI

@main
struct OmeApp: App {
    @StateObject private var session = SessionManager()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
                .preferredColorScheme(.dark)
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                // Update last active date for streak tracking
                UserDefaults.standard.set(Date(), forKey: "ome_last_active_date")
                // Reschedule re-engagement notifications
                Task {
                    let nm = NotificationManager.shared
                    await nm.checkStatus()
                    if nm.permissionGranted {
                        nm.scheduleReengagement()
                    }
                }
            }
        }
    }
}
