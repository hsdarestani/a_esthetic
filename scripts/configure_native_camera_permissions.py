#!/usr/bin/env python3
"""Apply the native permissions needed by getUserMedia in the embedded admin WebView.

Capacitor 8's BridgeWebChromeClient already maps WebView VIDEO_CAPTURE requests to
Android's CAMERA runtime permission. The generated host app still has to declare
that permission in AndroidManifest.xml. WKWebView likewise needs an iOS camera
usage description before iOS can grant camera access.
"""
from pathlib import Path
import plistlib


ANDROID_MANIFEST = Path("android/app/src/main/AndroidManifest.xml")
IOS_PLIST = Path("ios/App/App/Info.plist")
ANDROID_PERMISSION = '<uses-permission android:name="android.permission.CAMERA" />'
ANDROID_FEATURE = '<uses-feature android:name="android.hardware.camera.any" android:required="false" />'
IOS_CAMERA_TEXT = "A+ Esthetic benötigt die Kamera, um A+ Wallet QR-Codes zu scannen."


def configure_android() -> None:
    if not ANDROID_MANIFEST.exists():
        return
    text = ANDROID_MANIFEST.read_text(encoding="utf-8")
    additions = []
    if ANDROID_PERMISSION not in text:
        additions.append(ANDROID_PERMISSION)
    if ANDROID_FEATURE not in text:
        additions.append(ANDROID_FEATURE)
    if additions:
        marker = "<application"
        if marker not in text:
            raise SystemExit("AndroidManifest.xml has no <application> element")
        text = text.replace(marker, "\n    ".join(additions) + "\n\n    " + marker, 1)
        ANDROID_MANIFEST.write_text(text, encoding="utf-8")
    print("Android camera permission configured for embedded QR scanning.")


def configure_ios() -> None:
    if not IOS_PLIST.exists():
        return
    with IOS_PLIST.open("rb") as handle:
        data = plistlib.load(handle)
    if data.get("NSCameraUsageDescription") != IOS_CAMERA_TEXT:
        data["NSCameraUsageDescription"] = IOS_CAMERA_TEXT
        with IOS_PLIST.open("wb") as handle:
            plistlib.dump(data, handle, fmt=plistlib.FMT_XML, sort_keys=False)
    print("iOS camera usage description configured for embedded QR scanning.")


if __name__ == "__main__":
    configure_android()
    configure_ios()
