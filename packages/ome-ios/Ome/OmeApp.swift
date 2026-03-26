import SwiftUI
import os

private let logger = Logger(subsystem: "com.omnity.ome", category: "App")

private func setupCrashLog() {
    let handler: @convention(c) (NSException) -> Void = { exception in
        let msg = """
        CRASH: \(exception.name.rawValue)
        Reason: \(exception.reason ?? "nil")
        Stack: \(exception.callStackSymbols.joined(separator: "\n"))
        """
        let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("crash.log")
        try? msg.write(to: url, atomically: true, encoding: .utf8)
    }
    NSSetUncaughtExceptionHandler(handler)
}

@main
struct OmeApp: App {
    @StateObject private var session = SessionManager()
    @StateObject private var chatStore = ChatStore()
    @Environment(\.scenePhase) private var scenePhase

    init() {
        setupCrashLog()
        logger.info("OmeApp init OK")
        // Check for previous crash log
        let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("crash.log")
        if let log = try? String(contentsOf: url, encoding: .utf8) {
            logger.error("Previous crash: \(log)")
            UserDefaults.standard.set(log, forKey: "ome_last_crash")
            try? FileManager.default.removeItem(at: url)
        }
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
                .environmentObject(chatStore)
                .preferredColorScheme(.dark)
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                UserDefaults.standard.set(Date(), forKey: "ome_last_active_date")
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
