#!/usr/bin/env python3
"""Make native camera / scanner permissions deterministic after `cap sync`.

The A+ app opens both its packaged customer UI and the remote management UI inside
Capacitor. Native Camera and Barcode Scanner are used on iOS/Android, while
getUserMedia remains as a browser fallback.
"""
from pathlib import Path
import plistlib
import re

ROOT = Path(__file__).resolve().parents[1]
ANDROID_MANIFEST = ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
ANDROID_VARS = ROOT / "android" / "variables.gradle"
IOS_INFO = ROOT / "ios" / "App" / "App" / "Info.plist"


def patch_android():
    if not ANDROID_MANIFEST.exists():
        print("AndroidManifest.xml not present yet; skipping camera permission patch.")
        return
    text = ANDROID_MANIFEST.read_text(encoding="utf-8")
    changed = False
    if 'android.permission.CAMERA' not in text:
        insert = '    <uses-permission android:name="android.permission.CAMERA" />\n'
        marker = '<uses-permission android:name="android.permission.INTERNET" />'
        if marker in text:
            text = text.replace(marker, marker + "\n" + insert.rstrip(), 1)
        else:
            text = text.replace('<application', insert + '\n    <application', 1)
        changed = True
    if 'android.hardware.camera' not in text:
        feature = '    <uses-feature android:name="android.hardware.camera" android:required="false" />\n'
        text = text.replace('<application', feature + '\n    <application', 1)
        changed = True
    if changed:
        ANDROID_MANIFEST.write_text(text, encoding="utf-8")
        print("Configured Android camera permission for QR scanner/native photo capture.")

    if ANDROID_VARS.exists():
        value = ANDROID_VARS.read_text(encoding="utf-8")
        next_value, count = re.subn(r"minSdkVersion\s*=\s*\d+", "minSdkVersion = 26", value, count=1)
        if count and next_value != value:
            ANDROID_VARS.write_text(next_value, encoding="utf-8")
            print("Raised Android minSdkVersion to 26 for native barcode scanner.")


def patch_ios():
    if not IOS_INFO.exists():
        print("iOS Info.plist not present yet; skipping camera permission patch.")
        return
    with IOS_INFO.open("rb") as handle:
        info = plistlib.load(handle)
    values = {
        "NSCameraUsageDescription": "A+ Esthetic benötigt die Kamera, um QR-Codes zu scannen und Fotos sicher zur Patientenakte hinzuzufügen.",
        "NSPhotoLibraryUsageDescription": "A+ Esthetic benötigt Zugriff auf ausgewählte Fotos, wenn Sie ein Bild zur Patientenakte hinzufügen.",
        "NSPhotoLibraryAddUsageDescription": "A+ Esthetic kann auf Wunsch ein aufgenommenes Foto in Ihrer Mediathek sichern.",
    }
    changed = False
    for key, value in values.items():
        if info.get(key) != value:
            info[key] = value
            changed = True
    if changed:
        with IOS_INFO.open("wb") as handle:
            plistlib.dump(info, handle, sort_keys=False)
        print("Configured iOS camera/photo usage descriptions for native scanner and photo capture.")


if __name__ == "__main__":
    patch_android()
    patch_ios()
