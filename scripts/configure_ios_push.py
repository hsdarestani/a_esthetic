#!/usr/bin/env python3
"""Wire Capacitor iOS APNs callbacks after the generated iOS project is synced.

Only the native push registration hooks are changed. This runs on every signed
App Store build because Capacitor regenerates AppDelegate.swift.
"""
from pathlib import Path

app_delegate = Path("ios/App/App/AppDelegate.swift")
if not app_delegate.is_file():
    raise SystemExit("Missing generated iOS AppDelegate.swift")

source = app_delegate.read_text(encoding="utf-8")
success = "func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data)"
failure = "func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error)"
hooks = """
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        NotificationCenter.default.post(name: .capacitorDidRegisterForRemoteNotifications, object: deviceToken)
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        NotificationCenter.default.post(name: .capacitorDidFailToRegisterForRemoteNotifications, object: error)
    }
"""
if success in source or failure in source:
    if success not in source or failure not in source:
        raise SystemExit("Only one APNs delegate method exists; cannot safely add the other")
else:
    if "class AppDelegate" not in source or "import Capacitor" not in source:
        raise SystemExit("Unexpected Capacitor AppDelegate.swift; refusing to modify it")
    end = source.rfind("\n}")
    if end < source.find("class AppDelegate"):
        raise SystemExit("Cannot locate end of AppDelegate class")
    source = source[:end] + "\n" + hooks.rstrip() + source[end:]
    app_delegate.write_text(source, encoding="utf-8")

result = app_delegate.read_text(encoding="utf-8")
if result.count(success) != 1 or result.count(failure) != 1:
    raise SystemExit("iOS APNs delegate hook validation failed")
if ".capacitorDidRegisterForRemoteNotifications" not in result or ".capacitorDidFailToRegisterForRemoteNotifications" not in result:
    raise SystemExit("iOS APNs event bridge is missing")
print("PASS: iOS AppDelegate forwards both APNs registration callbacks to Capacitor")
